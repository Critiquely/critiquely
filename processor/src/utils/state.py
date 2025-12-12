import logging
from src.state.state import DevAgentState

logger = logging.getLogger(__name__)


def get_state_value(state: DevAgentState, key: str) -> str:
    """Safely retrieve and validate a value from the DevAgentState.

    Args:
        state: DevAgentState dictionary containing workflow state.
        key: The key name to retrieve from state.

    Returns:
        The validated state value. String values are stripped of whitespace.

    Raises:
        KeyError: If the key doesn't exist in the state.
        ValueError: If the value is None or an empty string after stripping.

    Note:
        String values are automatically stripped of leading/trailing whitespace
        and validated to ensure they're not empty.
    """
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