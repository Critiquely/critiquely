"""Human-in-the-loop functionality for agent monitoring."""

from typing import Callable, Any, Optional, Union
from langchain_core.tools import BaseTool, tool as create_tool
from langgraph.types import interrupt
from langgraph.prebuilt.interrupt import HumanInterruptConfig, HumanInterrupt
from langchain_core.runnables import RunnableConfig


def add_human_in_the_loop(
    tool: Union[Callable, BaseTool],
    *,
    interrupt_config: Optional[HumanInterruptConfig] = None,
) -> BaseTool:
    """Wrap a tool to support human-in-the-loop review.
    
    Args:
        tool: The tool or function to wrap
        interrupt_config: Configuration for the human interrupt
        
    Returns:
        A wrapped tool that supports human-in-the-loop review
    """
    if not isinstance(tool, BaseTool):
        tool = create_tool(tool)

    if interrupt_config is None:
        interrupt_config = {
            "allow_accept": True,
            "allow_edit": True,
            "allow_respond": True,
        }

    class AsyncToolWrapper(BaseTool):
        name: str = tool.name
        description: str = tool.description
        args_schema: type = tool.args_schema
        
        def _run(self, *args, **kwargs):
            raise NotImplementedError("Sync invocation not supported. Use ainvoke() instead.")
            
        async def _arun(self, *args, **kwargs) -> Any:
            config = {}
            if args and isinstance(args[0], dict) and 'configurable' in args[0]:
                config = args[0]
                args = args[1:]
            
            tool_input = {**dict(zip(tool.args.keys(), args)), **kwargs}
            
            request: HumanInterrupt = {
                "action_request": {
                    "action": tool.name,
                    "args": tool_input,
                },
                "config": interrupt_config,
                "description": f"Please review the {tool.name} tool call",
            }
            
            response = interrupt([request])[0]
            
            if response["type"] == "accept":
                if hasattr(tool, 'ainvoke'):
                    return await tool.ainvoke(tool_input, config)
                return await tool._arun(**tool_input)
                
            elif response["type"] == "edit":
                tool_input = response["args"]["args"]
                if hasattr(tool, 'ainvoke'):
                    return await tool.ainvoke(tool_input, config)
                return await tool._arun(**tool_input)
                
            elif response["type"] == "response":
                return response["args"]
                
            else:
                raise ValueError(f"Unsupported interrupt response type: {response['type']}")
    
    return AsyncToolWrapper()