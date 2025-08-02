import tempfile
import pathlib


def get_temp_dir() -> str:
    """Gets the OS-specific temporary directory path.

    Returns:
        str: Resolved path to the OS-specific temporary directory
    """
    try:
        clone_path = pathlib.Path(tempfile.gettempdir())
        return str(clone_path.resolve())
    except (OSError, RuntimeError):
        return tempfile.gettempdir()
