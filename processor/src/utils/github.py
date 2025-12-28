"""GitHub API utilities for Critiquely."""

import logging
import re
from typing import List, Set

import httpx
from unidiff import PatchSet

from src.config import settings

logger = logging.getLogger(__name__)


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL into components.

    Args:
        pr_url: GitHub PR URL (HTML or API format).

    Returns:
        Tuple of (owner, repo, pr_number).

    Raises:
        ValueError: If URL format is invalid.
    """
    # Handle HTML URL: https://github.com/owner/repo/pull/123
    html_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url
    )
    if html_match:
        return html_match.group(1), html_match.group(2), int(html_match.group(3))

    # Handle API URL: https://api.github.com/repos/owner/repo/pulls/123
    api_match = re.match(
        r"https?://api\.github\.com/repos/([^/]+)/([^/]+)/pulls/(\d+)", pr_url
    )
    if api_match:
        return api_match.group(1), api_match.group(2), int(api_match.group(3))

    raise ValueError(f"Invalid PR URL format: {pr_url}")


def get_api_url(owner: str, repo: str, pr_number: int) -> str:
    """Get the GitHub API URL for a PR.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.

    Returns:
        API URL for the PR.
    """
    return f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"


def extract_changed_lines(patch_text: str, filename: str) -> Set[int]:
    """Extract changed line numbers from a patch.

    Args:
        patch_text: The patch/diff text.
        filename: The filename for context.

    Returns:
        Set of changed line numbers.
    """
    if not patch_text:
        return set()

    try:
        synthetic_diff = f"--- a/{filename}\n+++ b/{filename}\n{patch_text}"
        patch = PatchSet.from_string(synthetic_diff)

        changed = set()
        for patched_file in patch:
            for hunk in patched_file:
                for line in hunk:
                    if line.is_added or line.is_removed:
                        line_no = line.target_line_no or line.source_line_no
                        if line_no:
                            changed.add(line_no)
        return changed
    except Exception as e:
        logger.warning(f"Failed to parse patch for {filename}: {e}")
        return set()


async def get_pr_modified_files(pr_url: str) -> List[dict]:
    """Fetch modified files for a PR from GitHub API.

    Args:
        pr_url: GitHub PR URL (HTML or API format).

    Returns:
        List of modified file dicts with filename, type, and lines_changed.

    Raises:
        RuntimeError: If GitHub token is not set.
        httpx.HTTPError: If API request fails.
    """
    token = settings.github_token
    if not token:
        raise RuntimeError("GitHub token is not set")

    # Parse URL and construct API endpoint
    owner, repo, pr_number = parse_pr_url(pr_url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    logger.info(f"Fetching modified files from {api_url}")

    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url, headers=headers)
        resp.raise_for_status()

    files = resp.json()
    logger.info(f"Found {len(files)} modified files")

    return [
        {
            "filename": file.get("filename"),
            "type": file.get("status"),
            "lines_changed": sorted(
                extract_changed_lines(file.get("patch", ""), file.get("filename", ""))
            ),
        }
        for file in files
    ]


async def get_pr_info(pr_url: str) -> dict:
    """Fetch PR information from GitHub API.

    Args:
        pr_url: GitHub PR URL (HTML or API format).

    Returns:
        Dict with PR info including head branch, base branch, etc.
    """
    token = settings.github_token
    if not token:
        raise RuntimeError("GitHub token is not set")

    owner, repo, pr_number = parse_pr_url(pr_url)
    api_url = get_api_url(owner, repo, pr_number)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    return {
        "number": data.get("number"),
        "title": data.get("title"),
        "head_branch": data.get("head", {}).get("ref"),
        "base_branch": data.get("base", {}).get("ref"),
        "html_url": data.get("html_url"),
        "state": data.get("state"),
    }
