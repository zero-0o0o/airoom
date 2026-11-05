"""Tests for the `airoom completion` Typer command."""

from typer.testing import CliRunner

from airoom.cli import app


class TestCompletionCommand:
    """Tests for the completion command."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_completion_command_exists(self):
        """Test that the completion command is registered."""
        result = self.runner.invoke(app, ["completion", "--help"])
        assert result.exit_code == 0
        assert "Generate shell completion script" in result.stdout
        assert "bash" in result.stdout
        assert "zsh" in result.stdout
        assert "fish" in result.stdout

    def test_completion_bash_output(self):
        """Test completion command generates non-empty bash script."""
        result = self.runner.invoke(app, ["completion", "bash"])
        assert result.exit_code == 0
        assert len(result.stdout) > 0
        assert "_airoom_completion" in result.stdout or "_airoom_completion_setup" in result.stdout
        assert "complete -o nosort -F _airoom_completion airoom" in result.stdout

    def test_completion_zsh_output(self):
        """Test completion command generates non-empty zsh script."""
        result = self.runner.invoke(app, ["completion", "zsh"])
        assert result.exit_code == 0
        assert len(result.stdout) > 0
        assert "#compdef airoom" in result.stdout
        assert "_airoom_completion" in result.stdout
        assert "compdef _airoom_completion airoom" in result.stdout

    def test_completion_fish_output(self):
        """Test completion command generates non-empty fish script."""
        result = self.runner.invoke(app, ["completion", "fish"])
        assert result.exit_code == 0
        assert len(result.stdout) > 0
        assert "function _airoom_completion" in result.stdout
        assert "complete --no-files --command airoom" in result.stdout

    def test_completion_invalid_shell(self):
        """Test completion command rejects invalid shell."""
        result = self.runner.invoke(app, ["completion", "invalid"])
        assert result.exit_code != 0
        assert (
            "bash" in result.stdout.lower()
            or "zsh" in result.stdout.lower()
            or "fish" in result.stdout.lower()
        )
