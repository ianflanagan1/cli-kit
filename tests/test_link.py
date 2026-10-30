"""Linking a tool's commands onto the PATH, as `devbox run -- task setup` does after `uv sync`."""

import os
from pathlib import Path

import pytest

from cli_kit import link


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The directory commands are linked into, on the PATH."""
    path = tmp_path / "bin"
    monkeypatch.setenv("XDG_BIN_HOME", str(path))
    monkeypatch.setenv("PATH", f"{path}{os.pathsep}/usr/bin")
    return path


def project(tmp_path: Path, *commands: str, built: bool = True) -> Path:
    """A tool's project naming commands in [project.scripts], built into .venv/bin."""
    root = tmp_path / "tool"
    (root / ".venv" / "bin").mkdir(parents=True)
    scripts = "".join(f'{command} = "tool:main"\n' for command in commands)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "tool"\n\n[project.scripts]\n{scripts}'
    )
    if built:
        for command in commands:
            script = root / ".venv" / "bin" / command
            script.write_text("#!/bin/sh\n")
            script.chmod(0o755)
    return root


def test_links_each_command_into_the_bin_directory(tmp_path, bin_dir, capsys):
    root = project(tmp_path, "one", "two")
    assert link.main([str(root)]) == 0
    for command in ("one", "two"):
        assert os.readlink(bin_dir / command) == str(root / ".venv" / "bin" / command)
    assert capsys.readouterr().out.splitlines()[-1] == "✅ Linked."


def test_takes_the_project_from_the_current_directory(tmp_path, bin_dir, monkeypatch, capsys):
    root = project(tmp_path, "one")
    monkeypatch.chdir(root)
    assert link.main([]) == 0
    assert os.readlink(bin_dir / "one") == str(root / ".venv" / "bin" / "one")


def test_the_bin_directory_is_local_bin_in_home_without_xdg_bin_home(
    tmp_path, bin_dir, monkeypatch, capsys
):
    monkeypatch.delenv("XDG_BIN_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = project(tmp_path, "one")
    assert link.main([str(root)]) == 0
    assert (tmp_path / "home" / ".local" / "bin" / "one").is_symlink()


def test_running_it_again_has_nothing_to_do(tmp_path, bin_dir, capsys):
    root = project(tmp_path, "one")
    link.main([str(root)])
    capsys.readouterr()
    assert link.main([str(root)]) == 0
    assert capsys.readouterr().out == "➖ Already linked.\n"


def test_a_link_left_dangling_by_a_moved_checkout_is_replaced(tmp_path, bin_dir, capsys):
    root = project(tmp_path, "one")
    bin_dir.mkdir()
    (bin_dir / "one").symlink_to(tmp_path / "gone" / ".venv" / "bin" / "one")
    assert link.main([str(root)]) == 0
    assert os.readlink(bin_dir / "one") == str(root / ".venv" / "bin" / "one")


def test_a_command_of_the_same_name_from_elsewhere_is_left_alone_and_nothing_is_linked(
    tmp_path, bin_dir, capsys
):
    root = project(tmp_path, "one", "two")
    bin_dir.mkdir()
    other = tmp_path / "other"
    other.write_text("#!/bin/sh\n")
    (bin_dir / "two").symlink_to(other)
    assert link.main([str(root)]) == 1
    assert os.readlink(bin_dir / "two") == str(other)
    assert not (bin_dir / "one").exists()
    err = capsys.readouterr().err
    assert err.startswith(f"⚠️ {bin_dir} already has two, from elsewhere.\n")
    assert f"  {bin_dir / 'two'} → {other}" in err


def test_a_command_not_built_yet_says_to_run_setup_and_nothing_is_linked(tmp_path, bin_dir, capsys):
    root = project(tmp_path, "one", built=False)
    assert link.main([str(root)]) == 1
    assert not (bin_dir / "one").exists()
    assert capsys.readouterr().err == (
        "⚠️ Not built: one.\n"
        f"Run `devbox run -- task setup` in {root}, which builds them with `uv sync` first.\n"
    )


def test_a_directory_without_pyproject_toml_isnt_a_tool(tmp_path, bin_dir, capsys):
    assert link.main([str(tmp_path)]) == 1
    assert capsys.readouterr().err == f"⚠️ No pyproject.toml in {tmp_path.resolve()}.\n"


def test_a_project_without_commands_has_nothing_to_link(tmp_path, bin_dir, capsys):
    root = project(tmp_path)
    assert link.main([str(root)]) == 0
    assert capsys.readouterr().out == "➖ No commands to link.\n"


def test_says_how_to_put_the_bin_directory_on_the_path_when_it_isnt(
    tmp_path, bin_dir, monkeypatch, capsys
):
    monkeypatch.setenv("PATH", "/usr/bin")
    root = project(tmp_path, "one")
    assert link.main([str(root)]) == 0
    assert capsys.readouterr().out.splitlines()[-3:] == [
        "✅ Linked.",
        f"{bin_dir} isn't on your PATH.",
        "Add it in your shell's profile, so these commands run.",
    ]


def test_already_linked_but_off_the_path_is_a_precondition(tmp_path, bin_dir, monkeypatch, capsys):
    root = project(tmp_path, "one")
    link.main([str(root)])
    capsys.readouterr()
    monkeypatch.setenv("PATH", "/usr/bin")
    assert link.main([str(root)]) == 1
    assert capsys.readouterr().err == (
        f"⚠️ {bin_dir} isn't on your PATH.\nAdd it in your shell's profile, so these commands run.\n"
    )


def test_says_when_another_command_earlier_on_the_path_runs_instead(
    tmp_path, bin_dir, monkeypatch, capsys
):
    earlier = tmp_path / "earlier"
    earlier.mkdir()
    (earlier / "one").write_text("#!/bin/sh\n")
    (earlier / "one").chmod(0o755)
    monkeypatch.setenv("PATH", f"{earlier}{os.pathsep}{bin_dir}")
    root = project(tmp_path, "one")
    assert link.main([str(root)]) == 0
    assert capsys.readouterr().out.splitlines()[-2:] == [
        f"`one` runs {earlier / 'one'}, which is earlier on your PATH.",
        f"Remove it, or move {bin_dir} ahead of it in your shell's profile.",
    ]
