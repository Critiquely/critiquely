import os
import logging
from urllib.parse import urlparse, urlunparse, quote


def create_github_https_url(https_url: str, token_env="GITHUB_TOKEN") -> str:
    token = os.getenv(token_env, "").strip()
    if not token:
        msg = "❌ Error: GITHUB_TOKEN is unset or empty."
        logger.error(msg)
        raise ValueError(msg)
    if not https_url.startswith("https://"):
        msg = "❌ Error: SSH URL has been provided. The app will not handle these.."
        logger.error(msg)
        raise ValueError(msg)

    parts = urlparse(https_url)
    auth = quote(token, safe="")
    url = urlunparse(parts._replace(netloc=f"{auth}@{parts.netloc}"))

    return url
