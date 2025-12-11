async def run_cli(repo_url, original_pr_url, branch, modified_files):
    try:
        result = await run_review_graph(
            repo_url=repo_url,
            original_pr_url=original_pr_url,
            base_branch=branch,
            modified_files=modified_files,
        )
        click.echo(result)

    except Exception as exc:
        logger.error(f"❌ Review failed: {exc}", exc_info=True)
        sys.exit(1)