"""Logging configuration for the application."""

import logging

def configure_logging():
    """Configure application-wide logging settings."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)7s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)