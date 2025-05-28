"""FastAPI GitHub webhook that returns the lines changed in each file of a PR."""
import os
from typing import Dict, List, Set

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from unidiff import PatchSet

# ────────────────────────────────────  Config  ──────────────────────────────────

GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
if GITHUB_TOKEN is None:
    raise RuntimeError("GITHUB_TOKEN environment variable is required")

HEADERS: Dict[str, str] = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

# ────────────────────────────────────  App  ─────────────────────────────────────

app = FastAPI()
handler = Mangum(app)  # for AWS Lambda / API Gateway

# ─────────────────────────────────  Helpers  ────────────────────────────────────

def extract_changed_lines(file_info: Dict[str, str]) -> Set[int]:
    """
    Return a set of line numbers (added or removed) for one file diff
    taken from the GitHub `/pulls/:num/files` endpoint.
    """
    patch_text = file_info.get("patch")
    if not patch_text:
        return set()

    synthetic_diff = (
        f"--- a/{file_info['filename']}\n"
        f"+++ b/{file_info['filename']}\n"
        f"{patch_text}"
    )
    patch = PatchSet.from_string(synthetic_diff)

    changed: Set[int] = set()
    for patched_file in patch:
        for hunk in patched_file:
            for line in hunk:
                if line.is_added or line.is_removed:
                    changed.add(line.target_line_no or line.source_line_no)
    return changed


async def get_pr_modified_files(pr_url: str) -> list[dict[str, object]]:
    """Get the modified files for a given PR url"""
    if not pr_url:
        raise HTTPException(status_code=400, detail="Missing Pull-Request URL")

    files_url = f"{pr_url}/files"

    async with httpx.AsyncClient() as client:
        resp = await client.get(files_url, headers=HEADERS)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"GitHub returned {resp.status_code} for {files_url}",
        )

    files_data = resp.json()
    return [
        {
            "filename": file.get("filename"),
            "type": file.get("status"),
            "lines_changed": sorted(extract_changed_lines(file)),
        }
        for file in files_data
    ]

# ────────────────────────────────  Webhook route  ───────────────────────────────

@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_github_event: str = Header(...),
):
    """Accept a GitHub pull-request webhook and list the changed lines per file."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if x_github_event != "pull_request.opened":
        return JSONResponse(
            status_code=400,
            content={
                "message": (
                    "Only pull_request events are handled. "
                    f"Received '{x_github_event}' instead."
                )
            },
        )

    pr_url = payload.get("pull_request").get("url")
    modified_files = await get_pr_modified_files(pr_url)
    return {"modified_files": modified_files}
