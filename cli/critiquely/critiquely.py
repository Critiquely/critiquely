import click
import os
import asyncio
from github import Github
from github import Auth
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "github-mcp-server": {
            "url": os.environ.get("GITHUB_MCP_SERVER_URL"),
            "transport": "streamable_http",
        }
    }
)

async def get_agent():
    """Create and return an agent with tools."""
    tools = await client.get_tools()  # Now properly awaiting the coroutine
    return create_react_agent(
        model="anthropic:claude-3-7-sonnet-latest",  
        tools=tools,
        prompt="""You are Python code reviewer. You will be given a Python file and you will review it. 
        Return your suggestions for how to improve the code."""
    )

@click.command()
@click.pass_context
def cli(ctx):
    """Run the code review CLI."""
    async def run():
        agent = await get_agent()  # Now awaiting get_agent since it's async
        # python_files = get_python_files_from_repo()
        # for file in python_files:
        # file = python_files[1]  # I'm only running this on main.py just now for :money:
        # print(f"File: {file.path}")
        
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Get the content of the Critiquely/critiquely GitHub repository and suggest 5 Python improvements."}]}
        )
        print(result)
        print("\n" + "="*50 + "\n")
    
    asyncio.run(run())

def get_python_files_from_repo(repo_name="CritiqueBot/critique-engine", token=None):
    try:
        token = token or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ValueError("GitHub token not provided")
            
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(repo_name)
        
        files = []
        contents = repo.get_contents("")
        
        while contents:
            content = contents.pop(0)
            if content.type == "dir":
                contents.extend(repo.get_contents(content.path))
            elif content.path.endswith('.py'):  
                files.append(content)
        
        return files
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return []