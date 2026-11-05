"""Tests for core logging module."""

import json
import logging
import sys
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from airoom.cli import GlobalOptions
from airoom.core.logging import configure_logging, get_logger, JSONFormatter


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_basic_record(self):
        """Test basic log record formatting as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test"
        record.funcName = "test_func"
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert parsed["module"] == "test"
        assert parsed["function"] == "test_func"
        assert "timestamp" in parsed

    def test_format_with_exception(self):
        """Test formatting with exception info."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
        record.module = "test"
        record.funcName = "test_func"
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed["level"] == "ERROR"
        assert "exception" in parsed
        assert "ValueError: test error" in parsed["exception"]

    def test_format_with_extra_fields(self):
        """Test formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test"
        record.funcName = "test_func"
        record.extra_field = "extra_value"
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed["extra_field"] == "extra_value"


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def setup_method(self):
        """Reset logging state before each test."""
        # Reset root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.NOTSET)
        # Reset all loggers
        for name in list(logging.Logger.manager.loggerDict.keys()):
            logger = logging.getLogger(name)
            logger.handlers.clear()
            logger.setLevel(logging.NOTSET)
            logger.propagate = True

    def test_configure_logging_verbose_0_json(self):
        """Test configure_logging with verbose=0 and json=True -> WARNING level, JSON output."""
        global_opts = GlobalOptions(verbose=0, json_output=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            configure_logging(global_opts)
            logger = logging.getLogger("test")
            logger.warning("Warning message")
            logger.info("Info message")  # Should not appear at WARNING level
            output = mock_stdout.getvalue()
            lines = output.strip().split("\n")
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["level"] == "WARNING"
            assert parsed["message"] == "Warning message"

    def test_configure_logging_verbose_1_json(self):
        """Test configure_logging with verbose=1 and json=True -> INFO level, JSON output."""
        global_opts = GlobalOptions(verbose=1, json_output=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            configure_logging(global_opts)
            logger = logging.getLogger("test")
            logger.info("Info message")
            logger.debug("Debug message")  # Should not appear at INFO level
            output = mock_stdout.getvalue()
            lines = output.strip().split("\n")
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["level"] == "INFO"
            assert parsed["message"] == "Info message"

    def test_configure_logging_verbose_2_json(self):
        """Test configure_logging with verbose=2 and json=True -> DEBUG level, JSON output."""
        global_opts = GlobalOptions(verbose=2, json_output=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            configure_logging(global_opts)
            logger = logging.getLogger("test")
            logger.debug("Debug message")
            output = mock_stdout.getvalue()
            lines = output.strip().split("\n")
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["level"] == "DEBUG"
            assert parsed["message"] == "Debug message"

    def test_configure_logging_verbose_3_json(self):
        """Test configure_logging with verbose>=2 (e.g., 3) and json=True -> DEBUG level."""
        global_opts = GlobalOptions(verbose=3, json_output=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            configure_logging(global_opts)
            logger = logging.getLogger("test")
            logger.debug("Debug message")
            output = mock_stdout.getvalue()
            lines = output.strip().split("\n")
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["level"] == "DEBUG"

    def test_configure_logging_verbose_0_no_json(self):
        """Test configure_logging with verbose=0 and json=False -> WARNING level, Rich handler."""
        global_opts = GlobalOptions(verbose=0, json_output=False)
        with patch("airoom.core.logging.RichHandler") as mock_rich_handler_class:
            mock_handler = MagicMock()
            mock_rich_handler_class.return_value = mock_handler
            configure_logging(global_opts)
            # Check that RichHandler was instantiated
            mock_rich_handler_class.assert_called_once()
            # Check level is WARNING
            root_logger = logging.getLogger()
            assert root_logger.level == logging.WARNING

    def test_configure_logging_verbose_1_no_json(self):
        """Test configure_logging with verbose=1 and json=False -> INFO level, Rich handler."""
        global_opts = GlobalOptions(verbose=1, json_output=False)
        with patch("airoom.core.logging.RichHandler") as mock_rich_handler_class:
            mock_handler = MagicMock()
            mock_rich_handler_class.return_value = mock_handler
            configure_logging(global_opts)
            root_logger = logging.getLogger()
            assert root_logger.level == logging.INFO

    def test_configure_logging_verbose_2_no_json(self):
        """Test configure_logging with verbose=2 and json=False -> DEBUG level, Rich handler."""
        global_opts = GlobalOptions(verbose=2, json_output=False)
        with patch("airoom.core.logging.RichHandler") as mock_rich_handler_class:
            mock_handler = MagicMock()
            mock_rich_handler_class.return_value = mock_handler
            configure_logging(global_opts)
            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG

    def test_configure_logging_clears_existing_handlers(self):
        """Test that configure_logging clears existing handlers."""
        global_opts = GlobalOptions(verbose=1, json_output=True)
        # Add a dummy handler first
        root_logger = logging.getLogger()
        initial_handler_count = len(root_logger.handlers)
        
        class DummyHandler(logging.Handler):
            def emit(self, record):
                pass
        
        dummy_handler = DummyHandler()
        root_logger.addHandler(dummy_handler)
        assert len(root_logger.handlers) == initial_handler_count + 1
        configure_logging(global_opts)
        # Should have only the new handler (plus pytest's handlers)
        # But our dummy handler should be gone
        assert not any(isinstance(h, DummyHandler) for h in root_logger.handlers)
        # And our new StreamHandler should be present
        assert any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)

    def test_configure_logging_idempotent(self):
        """Test that calling configure_logging multiple times works."""
        global_opts = GlobalOptions(verbose=1, json_output=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            configure_logging(global_opts)
            configure_logging(global_opts)  # Second call should not duplicate
            logger = logging.getLogger("test")
            logger.info("Test message")
            output = mock_stdout.getvalue()
            lines = output.strip().split("\n")
            assert len(lines) == 1

    def test_configure_logging_json_outputs_to_stdout(self):
        """Test that JSON logging outputs to stdout."""
        global_opts = GlobalOptions(verbose=1, json_output=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                configure_logging(global_opts)
                logger = logging.getLogger("test")
                logger.info("Test message")
                stdout_output = mock_stdout.getvalue()
                stderr_output = mock_stderr.getvalue()
                assert "Test message" in stdout_output
                assert stderr_output == ""


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_get_logger_same_name_returns_same_instance(self):
        """Test that get_logger returns same instance for same name."""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        assert logger1 is logger2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])