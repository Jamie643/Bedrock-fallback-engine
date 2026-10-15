"""Tests for the CLI — argument parsing and dispatch."""

from __future__ import annotations

import pytest

from bedrock_fallback_engine.cli import main


def test_no_command_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_package_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["package", "--help"])
    assert excinfo.value.code == 0
