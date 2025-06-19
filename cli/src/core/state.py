from typing import Annotated, Optional
from typing_extensions import TypedDict
import operator
from langchain_core.messages import AnyMessage

class DevAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    repo_url: str
    repo_branch: str
    repo_path: Optional[str]
    modified_files: list[dict]
    current_file: Optional[str]
    current_file_content: Optional[str]
    current_file_lines_changed: Optional[str]
    last_file_reviewed: str
    recommendations: list[dict]
