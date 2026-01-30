"""Tests for Python environment tools."""

from __future__ import annotations

from pathlib import Path


def test_configure_python_environment(tool_handlers, sandbox: Path):
    result = tool_handlers["configure_python_environment"]({})
    assert "output" in result


def test_get_python_executable_details(tool_handlers, sandbox: Path):
    result = tool_handlers["get_python_executable_details"]({})
    assert "output" in result
    # Should contain Python version info
    assert "python" in result["output"].lower() or "version" in result["output"].lower()


def test_install_python_packages_validation(tool_handlers, sandbox: Path):
    import pytest

    # Empty packages should fail
    with pytest.raises(Exception):
        tool_handlers["install_python_packages"]({"packageList": []})


def test_install_python_packages_dry_run(tool_handlers, sandbox: Path):
    # Test with a package that won't actually install in test env
    result = tool_handlers["install_python_packages"]({"packageList": ["nonexistent-package-xyz123"]})
    # Should either succeed or fail gracefully
    assert "output" in result
