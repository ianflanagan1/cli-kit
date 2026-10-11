import os
import sys
from pathlib import Path

import pytest

from cli_kit import devbox


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(sys, "prefix", str(tmp_path / ".venv"))
    monkeypatch.setenv("PATH", "/usr/bin")
    return tmp_path


def tools(project: Path) -> Path:
    path = project / ".devbox" / "nix" / "profile" / "default" / "bin"
    path.mkdir(parents=True)
    return path


def test_puts_the_tools_devbox_packages_first_on_the_path(project: Path):
    bin = tools(project)
    devbox.use_tools()
    assert os.environ["PATH"] == f"{bin}{os.pathsep}/usr/bin"


def test_adds_them_only_once(project: Path):
    bin = tools(project)
    devbox.use_tools()
    devbox.use_tools()
    assert os.environ["PATH"] == f"{bin}{os.pathsep}/usr/bin"


def test_leaves_the_path_alone_outside_a_project(project: Path):
    devbox.use_tools()
    assert os.environ["PATH"] == "/usr/bin"
