# Critiquely

_Critiquely_ is an AI-powered CLI tool designed to review code changes in GitHub repositories. It analyzes specific file modifications and optionally opens pull requests with meaningful improvements

## Requirements

- Python 3.13+
- GitHub Personal Access Token
- Anthropic API Key
- Docker
- uv

## Quickstart

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/critiquely.git
   cd critiquely
   ```

2. Set up environment:
   ```bash
   export ANTHROPIC_API_KEY=XXXXXXX
   export GITHUB_TOKEN=XXXXXXX
   export GITHUB_MCP_SERVER_URL=http://localhost:8080
   uv sync
   source .venv/bin/activate
   ```

3. Run the CLI:
   ```bash
   critiquely --repo_url https://github.com/Critiquely/critiquely.git --original_pr_url https://github.com/Critiquely/critiquely/pull/31 --branch langgraph --modified_files '[{"filename":"cli/src/main.py", "type":"modified","lines_changed":[10,11,32,33,34,35]},{"filename":"cli/src/core/nodes.py", "type":"modified","lines_changed":[10]}]'
   ```

## MCP Integration

Critiquely integrates with multiple MCP servers:

- **GitHub MCP Server** for interacting with GitHub e.g. comment on pull request
- **Filesystem MCP** for local file manipulation
- **Git MCP Server** for performing git operaitons e.g. git clone

## License

This project is licensed under the terms of the [MIT License](LICENSE).
