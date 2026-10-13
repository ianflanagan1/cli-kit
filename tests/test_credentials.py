import os
import platform
from collections.abc import Callable
from pathlib import Path

import pytest

from cli_kit.credentials import Credential, Token, keychain_account, secret_tool_username
from cli_kit.outcome import Precondition

KEYCHAIN_LISTING = """\
keychain: "/Users/me/Library/Keychains/login.keychain-db"
class: "genp"
attributes:
    0x00000007 <blob>="packagist-api-token"
    "acct"<blob>="someone"
    "svce"<blob>="packagist-api-token"
"""

SECRET_TOOL_LISTING = """\
[/org/freedesktop/secrets/collection/login/1]
label = Packagist main API token
attribute.service = packagist-api-token
attribute.username = someone
"""

PACKAGIST = Token(
    service="packagist-api-token",
    name="Packagist main API token",
    username="packagist-username",
    create="Copy the main API token from your profile at https://packagist.org/profile/.",
)

GITHUB_DELETE = Token(
    service="github-delete-repo-token",
    name="GitHub delete_repo token",
    username="github-username",
    create="Create a classic token with only the delete_repo scope.",
    confirm_each_read=True,
)


def test_reads_the_account_from_a_keychain_listing():
    assert keychain_account(KEYCHAIN_LISTING) == "someone"


def test_reads_the_username_from_a_secret_tool_listing():
    assert secret_tool_username(SECRET_TOOL_LISTING) == "someone"


def test_finds_no_user_in_an_empty_listing():
    assert keychain_account("") == ""
    assert secret_tool_username("") == ""


# What secret-tool 0.21 on Ubuntu 24.04 prints for `search --all service packagist-api-token`:
# the secret and its metadata on stdout, and its attributes on stderr.
SECRET_TOOL_SEARCH_STDOUT = """\
[/1]
label = Packagist main API token
secret = the-token
created = 2026-10-12 19:50:50
modified = 2026-10-12 19:50:50
schema = org.freedesktop.Secret.Generic
"""
SECRET_TOOL_SEARCH_STDERR = """\
attribute.service = packagist-api-token
attribute.username = someone
"""


@pytest.fixture
def fake_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str, str], None]:
    """Puts a program on the PATH whose sh body is given, ahead of any real one."""
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    def install(name: str, body: str) -> None:
        script = tmp_path / name
        script.write_text(f"#!/bin/sh\n{body}\n")
        script.chmod(0o755)

    return install


@pytest.fixture
def linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")


@pytest.fixture
def macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")


@pytest.fixture
def secret_tool(fake_program, tmp_path: Path, linux) -> None:
    """A secret-tool that prints what the real one does, on the same streams."""
    (tmp_path / "stdout").write_text(SECRET_TOOL_SEARCH_STDOUT)
    (tmp_path / "stderr").write_text(SECRET_TOOL_SEARCH_STDERR)
    fake_program(
        "secret-tool",
        'case "$1" in\n'
        f'  search) cat "{tmp_path}/stdout"; cat "{tmp_path}/stderr" >&2 ;;\n'
        "  lookup) printf the-token ;;\n"
        "esac",
    )


@pytest.fixture
def keychain(fake_program, tmp_path: Path, macos) -> None:
    """A security that finds the token, printing its attributes, or with -w the token."""
    (tmp_path / "listing").write_text(KEYCHAIN_LISTING)
    fake_program(
        "security",
        f'case "$*" in\n  *-w*) echo the-token ;;\n  *) cat "{tmp_path}/listing" ;;\nesac',
    )


@pytest.fixture
def empty_secret_tool(fake_program, linux) -> None:
    """A secret-tool with nothing stored: it prints nothing and exits 1."""
    fake_program("secret-tool", "exit 1")


@pytest.fixture
def empty_keychain(fake_program, macos) -> None:
    """A security with nothing stored: like the real one, it exits 44."""
    fake_program("security", "echo 'The specified item could not be found.' >&2; exit 44")


def missing(token: Token) -> list[str]:
    """The status line and details of the Precondition reading token raises."""
    with pytest.raises(Precondition) as raised:
        token.read()
    return [raised.value.message, *raised.value.details]


def test_on_linux_a_token_is_read_from_secret_tool(secret_tool):
    assert PACKAGIST.read() == Credential("someone", "the-token")


def test_on_macos_a_token_is_read_from_the_keychain(keychain):
    assert PACKAGIST.read() == Credential("someone", "the-token")


def test_on_linux_a_missing_token_says_how_to_create_and_store_it(empty_secret_tool):
    assert missing(PACKAGIST) == [
        "No Packagist main API token is stored.",
        "Copy the main API token from your profile at https://packagist.org/profile/.",
        "Then store it, pasting it at the prompt:",
        "  secret-tool store --label='Packagist main API token' service packagist-api-token"
        " username <packagist-username>",
    ]


def test_on_macos_a_missing_token_says_how_to_create_and_store_it(empty_keychain):
    assert missing(PACKAGIST) == [
        "No Packagist main API token is stored.",
        "Copy the main API token from your profile at https://packagist.org/profile/.",
        "Then store it, pasting it at the prompt:",
        "  security add-generic-password -a <packagist-username> -s packagist-api-token -w",
    ]


def test_on_macos_a_token_confirmed_on_each_read_is_stored_trusting_no_app(empty_keychain):
    assert missing(GITHUB_DELETE)[3:] == [
        "  security add-generic-password -a <github-username> -s github-delete-repo-token -T '' -w",
        "macOS will ask for your login password each time it's read: choose Allow, never"
        " Always Allow.",
    ]


def test_on_linux_a_token_confirmed_on_each_read_is_stored_as_any_other(empty_secret_tool):
    assert missing(GITHUB_DELETE)[3:] == [
        "  secret-tool store --label='GitHub delete_repo token' service github-delete-repo-token"
        " username <github-username>",
    ]


def test_on_linux_without_secret_tool_it_says_to_install_it(linux, monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert missing(PACKAGIST) == ["secret-tool is missing.", "Install libsecret-tools."]
