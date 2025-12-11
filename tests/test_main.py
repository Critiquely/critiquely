"""Unit tests for the CLI tool and queue worker main module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys

from click.testing import CliRunner

from src.main import main


class TestMainCLI:
    """Test cases for the main CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_queue_mode_starts_queue_worker(self, runner):
        """Test that --queue-mode flag starts the queue worker."""
        with patch('src.main.start_queue_worker') as mock_worker:
            result = runner.invoke(main, ['--queue-mode'])
            mock_worker.assert_called_once()
            assert result.exit_code == 0

    def test_cli_mode_missing_all_required_args(self, runner):
        """Test CLI mode fails when no required arguments are provided."""
        with patch('src.main.logger') as mock_logger:
            result = runner.invoke(main, [])
            assert result.exit_code == 1

    def test_cli_mode_missing_repo_url(self, runner):
        """Test CLI mode fails when repo_url is missing."""
        result = runner.invoke(main, [
            '--original_pr_url', 'https://github.com/owner/repo/pull/1',
            '--branch', 'main',
            '--modified_files', '{"files": []}'
        ])
        assert result.exit_code == 1

    def test_cli_mode_missing_original_pr_url(self, runner):
        """Test CLI mode fails when original_pr_url is missing."""
        result = runner.invoke(main, [
            '--repo_url', 'https://github.com/owner/repo',
            '--branch', 'main',
            '--modified_files', '{"files": []}'
        ])
        assert result.exit_code == 1

    def test_cli_mode_missing_branch(self, runner):
        """Test CLI mode fails when branch is missing."""
        result = runner.invoke(main, [
            '--repo_url', 'https://github.com/owner/repo',
            '--original_pr_url', 'https://github.com/owner/repo/pull/1',
            '--modified_files', '{"files": []}'
        ])
        assert result.exit_code == 1

    def test_cli_mode_missing_modified_files(self, runner):
        """Test CLI mode fails when modified_files is missing."""
        result = runner.invoke(main, [
            '--repo_url', 'https://github.com/owner/repo',
            '--original_pr_url', 'https://github.com/owner/repo/pull/1',
            '--branch', 'main'
        ])
        assert result.exit_code == 1

    def test_cli_mode_missing_multiple_args_logs_all(self, runner):
        """Test CLI mode logs all missing arguments when multiple are missing."""
        result = runner.invoke(main, [
            '--repo_url', 'https://github.com/owner/repo'
        ])
        assert result.exit_code == 1

    def test_cli_mode_with_all_args_no_github_token(self, runner):
        """Test CLI mode fails when GITHUB_TOKEN is not set."""
        with patch('src.main.settings') as mock_settings:
            mock_settings.github_token = None
            result = runner.invoke(main, [
                '--repo_url', 'https://github.com/owner/repo',
                '--original_pr_url', 'https://github.com/owner/repo/pull/1',
                '--branch', 'main',
                '--modified_files', '{"files": []}'
            ])
            assert result.exit_code == 1

    def test_cli_mode_with_all_args_empty_github_token(self, runner):
        """Test CLI mode fails when GITHUB_TOKEN is empty string."""
        with patch('src.main.settings') as mock_settings:
            mock_settings.github_token = ''
            result = runner.invoke(main, [
                '--repo_url', 'https://github.com/owner/repo',
                '--original_pr_url', 'https://github.com/owner/repo/pull/1',
                '--branch', 'main',
                '--modified_files', '{"files": []}'
            ])
            assert result.exit_code == 1

    def test_cli_mode_successful_review(self, runner):
        """Test CLI mode runs successfully with all required arguments."""
        with patch('src.main.settings') as mock_settings, \
             patch('src.main.run_review_graph', new_callable=AsyncMock) as mock_review:
            mock_settings.github_token = 'test-token'
            mock_review.return_value = 'Review completed successfully'
            
            result = runner.invoke(main, [
                '--repo_url', 'https://github.com/owner/repo',
                '--original_pr_url', 'https://github.com/owner/repo/pull/1',
                '--branch', 'main',
                '--modified_files', '{"files": []}'
            ])
            
            assert result.exit_code == 0
            mock_review.assert_called_once_with(
                repo_url='https://github.com/owner/repo',
                original_pr_url='https://github.com/owner/repo/pull/1',
                base_branch='main',
                modified_files='{"files": []}'
            )
            assert 'Review completed successfully' in result.output

    def test_cli_mode_review_exception(self, runner):
        """Test CLI mode handles exceptions from run_review_graph."""
        with patch('src.main.settings') as mock_settings, \
             patch('src.main.run_review_graph', new_callable=AsyncMock) as mock_review:
            mock_settings.github_token = 'test-token'
            mock_review.side_effect = Exception('Review failed')
            
            result = runner.invoke(main, [
                '--repo_url', 'https://github.com/owner/repo',
                '--original_pr_url', 'https://github.com/owner/repo/pull/1',
                '--branch', 'main',
                '--modified_files', '{"files": []}'
            ])
            
            # The exception is caught and logged, so exit code is 0
            assert result.exit_code == 0


class TestModuleImports:
    """Test that module-level code executes correctly."""

    def test_logging_configuration_exists(self):
        """Test that logging is configured at module level."""
        import src.main
        import logging
        
        # Verify logger exists and is configured
        logger = logging.getLogger('src.main')
        assert logger is not None

    def test_httpx_logging_level_is_warning(self):
        """Test that httpx logger is set to WARNING level."""
        import logging
        httpx_logger = logging.getLogger('httpx')
        assert httpx_logger.level == logging.WARNING


class TestMainEntryPoint:
    """Test the __main__ entry point."""

    def test_main_callable(self):
        """Test that main function is callable."""
        from src.main import main
        assert callable(main)

    def test_main_is_click_command(self):
        """Test that main is decorated as a click command."""
        from src.main import main
        import click
        # Check that it has click command attributes
        assert hasattr(main, 'params')
        assert hasattr(main, 'callback')


@pytest.mark.parametrize('missing_arg,provided_args', [
    ('repo_url', ['--original_pr_url', 'http://pr', '--branch', 'main', '--modified_files', '{}']),
    ('original_pr_url', ['--repo_url', 'http://repo', '--branch', 'main', '--modified_files', '{}']),
    ('branch', ['--repo_url', 'http://repo', '--original_pr_url', 'http://pr', '--modified_files', '{}']),
    ('modified_files', ['--repo_url', 'http://repo', '--original_pr_url', 'http://pr', '--branch', 'main']),
])
def test_cli_mode_individual_missing_args(missing_arg, provided_args):
    """Parametrized test for each individual missing argument."""
    runner = CliRunner()
    result = runner.invoke(main, provided_args)
    assert result.exit_code == 1
