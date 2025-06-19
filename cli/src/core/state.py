from typing import Annotated, Optional
from typing_extensions import TypedDict
import operator
from langchain_core.messages import AnyMessage

class DevAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    repo_url: Optional[str]
    repo_path: Optional[str]
    modified_files: Optional[str]
    