"""API tokens, read from the system credential store.

A tool declares each token it needs once, as a module constant, and reads it where it's used:

    MAIN_TOKEN = Token(
        service="packagist-api-token",
        name="Packagist main API token",
        username="packagist-username",
        create="Copy the main API token from your profile at https://packagist.org/profile/.",
    )
    main = MAIN_TOKEN.read()  # main.username, main.token

Each token is stored under the username of the account it belongs to, in the macOS keychain
or, on Linux, the Secret Service keyring. When it isn't stored, reading it raises a
Precondition that says how to create it and the command that stores it on this system. A token
is only ever held in memory: it is never put on a command line or written to a file.
"""

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass

from cli_kit.outcome import Precondition


@dataclass(frozen=True)
class Credential:
    username: str
    token: str


@dataclass(frozen=True)
class Token:
    """A token a tool needs.

    service: the name it's stored under, such as "packagist-api-token".
    name: what it is, such as "Packagist main API token", for messages and the keyring's label.
    username: the account it's stored under, as a placeholder, such as "packagist-username".
    create: a sentence saying where and how to create one, with the scopes it needs.
    confirm_each_read: on macOS, store it trusting no app, so the keychain asks for your login
        password each time it's read. For a token that can do lasting harm.
    """

    service: str
    name: str
    username: str
    create: str
    confirm_each_read: bool = False

    def read(self) -> Credential:
        """The stored credential. Raises Precondition, saying how to store it, when it isn't."""
        match platform.system():
            case "Darwin":
                listing = _quiet("security", "find-generic-password", "-s", self.service)
                username = keychain_account(listing)
                token = _quiet("security", "find-generic-password", "-s", self.service, "-w")
            case "Linux":
                if not shutil.which("secret-tool"):
                    raise Precondition("secret-tool is missing.", "Install libsecret-tools.")
                # secret-tool prints the attributes, username among them, on stderr.
                search = ("secret-tool", "search", "--all", "service", self.service)
                username = secret_tool_username(_quiet(*search, stderr=True))
                token = _quiet("secret-tool", "lookup", "service", self.service)
            case system:
                raise Precondition(f"Credentials aren't supported on {system}.")
        token = token.strip()
        if not username or not token:
            raise Precondition(
                f"No {self.name} is stored.",
                self.create,
                "Then store it, pasting it at the prompt:",
                *self._how_to_store(platform.system()),
            )
        return Credential(username, token)

    def _how_to_store(self, system: str) -> list[str]:
        """The commands that store the token on system, then anything to know about them.

        On macOS the token is read at a hidden prompt and passed to `security -i` on stdin, so
        it's on no command line. The prompt of `security add-generic-password -w` would be
        simpler, but it keeps only the first 128 characters, and Atlassian's tokens have 192.
        """
        if system == "Linux":
            return [
                f"  secret-tool store --label='{self.name}' service {self.service}"
                f" username <{self.username}>"
            ]
        trust_no_app = ' -T ""' if self.confirm_each_read else ""
        lines = [
            "  printf 'Token: '; read -rs token; echo",
            f"  printf 'add-generic-password -a <{self.username}> -s {self.service}{trust_no_app}"
            ' -w %s\\n\' "$token" | security -i; unset token',
        ]
        if self.confirm_each_read:
            lines.append(
                "macOS will ask for your login password each time it's read: choose Allow, never"
                " Always Allow."
            )
        return lines


def keychain_account(listing: str) -> str:
    """The account name in `security find-generic-password` output, or ""."""
    match = re.search(r'^\s*"acct"<blob>="(.*)"$', listing, re.MULTILINE)
    return match.group(1) if match else ""


def secret_tool_username(listing: str) -> str:
    """The first username attribute in what `secret-tool search` prints, or ""."""
    match = re.search(r"^attribute\.username = (.*)$", listing, re.MULTILINE)
    return match.group(1) if match else ""


def _quiet(*args: str, stderr: bool = False) -> str:
    """A command's stdout, followed by its stderr when asked for, or "" when it fails."""
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout + result.stderr if stderr else result.stdout
