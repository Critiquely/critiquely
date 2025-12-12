from urllib.parse import urlparse, urlunparse, quote
from src.config import settings
import logging

logger = logging.getLogger(__name__)


def create_github_https_url(https_url: str, token_env="GITHUB_TOKEN") -> str:
    """Create an authenticated GitHub HTTPS URL by injecting the access token.

    Args:
        https_url: GitHub repository HTTPS URL (must start with https://).
        token_env: Name of the environment variable containing the token.
                  Defaults to "GITHUB_TOKEN". (Currently unused, token is
                  always read from settings.github_token)

    Returns:
        Authenticated HTTPS URL with token embedded in the netloc portion.

    Raises:
        ValueError: If github_token is not set in settings, or if the URL
                   doesn't start with "https://".

    Example:
        Input:  "https://github.com/user/repo.git"
        Output: "https://TOKEN@github.com/user/repo.git"
    """
    if not settings.github_token:
        msg = "❌ Error: GITHUB_TOKEN is unset or empty."
        raise ValueError(msg)
    if not https_url.startswith("https://"):
        msg = "❌ Error: SSH URL has been provided. The app will not handle these.."
        logger.error(msg)
        raise ValueError(msg)

    parts = urlparse(https_url)
    auth = quote(settings.github_token, safe="")
    url = urlunparse(parts._replace(netloc=f"{auth}@{parts.netloc}"))

    return url