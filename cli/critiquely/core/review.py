import logging
from typing import Any, Dict

from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver

from critiquely.core.mcp_client import get_mcp_client, CodeReviewError
from critiquely.core.agent import build_agent
from critiquely.tools.git import local_git_push
from critiquely.tools.human_in_the_loop import add_human_in_the_loop

logger = logging.getLogger(__name__)

async def run_code_review(
    local_dir: str,
    remote_repo: str,
    branch: str,
    interactive: bool = False,
) -> Dict[str, Any]:
    """
    Main orchestration function for running a code review using MCP and LangGraph.

    Args:
        local_dir: Path to the cloned Git repo
        remote_repo: Original remote URL
        branch: Branch name
        interactive: Whether to enable human-in-the-loop monitoring

    Returns:
        Dict containing agent messages or final state

    Raises:
        CodeReviewError: On any critical failure
    """
    try:
        async with get_mcp_client() as client:
            logger.info("Fetching tools from MCP servers")
            mcp_tools = await client.get_tools()
            local_tools = [local_git_push]
            tools = mcp_tools + local_tools

            if interactive:
                wrapped_tools = []
                for tool in tools:
                    try:
                        wrapped_tool = add_human_in_the_loop(tool)
                        wrapped_tools.append(wrapped_tool)
                    except Exception as e:
                        logger.warning(f"Could not wrap tool {getattr(tool, 'name', str(tool))}: {e}")
                        wrapped_tools.append(tool)
                tools = wrapped_tools

            logger.info("Creating LangGraph agent")
            checkpointer = InMemorySaver()
            agent = build_agent(tools=tools, checkpointer=checkpointer)

            input_data = {
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Conduct a code review of the repository cloned to: {local_dir}.\n"
                        f"The remote URL of the repository is: {remote_repo}.\n"
                        f"The branch we have pulled is: {branch}.\n"
                    )
                }]
            }

            config = {
                "configurable": {
                    "thread_id": "1",
                    "recursion_limit": 40
                }
            }

            logger.info("Starting code review loop")
            while True:
                chunks = []
                async for chunk in agent.astream(input_data, config):
                    chunks.append(chunk)
                    print(chunk, "\n")

                last_chunk = chunks[-1] if chunks else {}

                if "__interrupt__" in last_chunk:
                    interrupt_data = last_chunk["__interrupt__"]
                    print("\nAgent is waiting for your input...")
                    print("1. Type 'accept' to approve the action")
                    print("2. Type 'edit' to modify the action arguments")
                    print("3. Type 'respond' to send a custom response")
                    user_choice = input("\nYour choice (accept/edit/respond): ").strip().lower()

                    if user_choice == "accept":
                        resume_cmd = [{"type": "accept"}]
                    elif user_choice == "edit":
                        print("\nCurrent arguments:")
                        print(interrupt_data[0].value[0]["action_request"]["args"])
                        print("\nEnter new arguments as a JSON object:")
                        new_args = input("> ").strip()
                        resume_cmd = [{"type": "edit", "args": {"args": new_args}}]
                    elif user_choice == "respond":
                        print("\nEnter your response:")
                        user_response = input("> ").strip()
                        resume_cmd = [{"type": "response", "args": user_response}]
                    else:
                        print("Invalid choice. Defaulting to 'accept'.")
                        resume_cmd = [{"type": "accept"}]

                    input_data = Command(resume=resume_cmd)
                else:
                    break

            final_state = await checkpointer.aget(config)
            return {"messages": final_state.get("messages", [])}

    except Exception as e:
        logger.error(f"Error during code review: {e}")
        raise CodeReviewError(f"Failed to complete code review: {e}") from e