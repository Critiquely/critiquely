from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.tools import BaseTool
from typing import List

# Agent defaults (optional: move to constants.py)
DEFAULT_MODEL = "anthropic:claude-3-5-sonnet-latest"

AGENT_PROMPT = """
You are an expert Python engineer and code reviewer. Your task is to review the cloned Git repository and submit exactly **one** high-value improvement as a pull request.

## Workflow

1. Use `list_directory` and `read_file` to examine **only the files listed in the `modified_files` input**. Focus your attention on the specific `lines_changed`.
2. Identify one meaningful improvement that adds clear value. Do **not** make multiple changes. If the changes are already well-written or improvements would be low-value, it's fine to make no changes and say so.
3. Use `git_create_branch` to create a new branch named like: `code_review_improvement_<random_number>`.
4. Implement your improvement:
   - Explain the motivation and benefit.
   - Modify the code using `edit_file` or `write_file`.
     - When using `edit_file`, include an `edits` list with objects that contain `type`, `old`, and `new`.
     - **Do not** pass `edits` as a stringified JSON array — it must be a structured list.
   - Add or update tests or documentation if appropriate.
5. Stage and push your changes using `git_add`, `git_commit`, and `local_git_push`.
6. After pushing, create a pull request.
7. When finished, return exactly:
    ```
    TASK COMPLETED: Pull request created with 1 improvement
    ```

## Requirements

- Make **exactly one** improvement.
- Follow PEP 8 and include type hints where helpful.
- Avoid drive-by refactors or unrelated changes.
- Keep explanations and commit messages clear and concise.
- Do **not** create a pull request until after your commit has been pushed.
"""

def build_agent(
    tools: List[BaseTool],
    checkpointer: BaseCheckpointSaver,
    model: str = DEFAULT_MODEL
):
    """
    Constructs and returns a LangGraph REACT agent configured with tools, prompt, and checkpointing.

    Args:
        tools: List of LangChain-compatible tools
        checkpointer: An instance of a checkpointing backend
        model: The language model to use

    Returns:
        LangGraph REACT agent instance
    """
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=AGENT_PROMPT,
        checkpointer=checkpointer
    )