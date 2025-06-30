import logging

from src.core.state import DevAgentState

def get_state_value(state: DevAgentState, key: str) -> str:
    """Raise a ValueError if state[key] is missing/empty after strip()."""
    if key not in state:
        msg = f"❌ '{key}' missing from state."
        logger.error(msg)
        raise KeyError(msg)

    val = state[key]

    if val is None:
        msg = f"❌ '{key}' is None."
        logger.error(msg)
        raise ValueError(msg)

    if isinstance(val, str):
        val = val.strip()
        if val == "":
            msg = f"❌ '{key}' is blank."
            logger.error(msg)
            raise ValueError(msg)

    return val