import click
import os
from github import Github
from github import Auth
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model="anthropic:claude-3-7-sonnet-latest",  
    tools=[],
    prompt="""You are Python code reviewer. You will be given a Python file and you will review it. 
    Return your suggestions for how to improve the code."""  
)

@click.command()
def cli():
    """Prints a greeting."""
    python_files = get_python_files_from_repo()
    
    # for file in python_files:
    file = python_files[1] # I'm only running this on main.py just now for :money:
    print(f"File: {file.path}")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Review this Python code:\n```python\n{file.decoded_content.decode('utf-8')}\n```"}]}
    )
    print(result)
    print("\n" + "="*50 + "\n")

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