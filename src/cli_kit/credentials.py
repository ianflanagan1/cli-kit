"""API tokens, read from the system credential store.

Each token is stored under the username of the account it belongs to, in the macOS keychain
or, on Linux, the Secret Service keyring (see the README). A token is only ever held in memory:
it is never put on a command line or written to a file.
"""

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass

from cli_kit.errors import Precondition


@dataclass(frozen=True)
class Credential:
    username: str
    token: str


def credential(service: str) -> Credential:
    """The stored credential for a service, such as "packagist-api-token"."""
    match platform.system():
        case "Darwin":
            username = keychain_account(_quiet("security", "find-generic-password", "-s", service))
            token = _quiet("security", "find-generic-password", "-s", service, "-w").strip()
        case "Linux":
            if not shutil.which("secret-tool"):
                raise Precondition("secret-tool is missing.", "Install libsecret-tools.")
            search = _quiet("secret-tool", "search", "--all", "service", service)
            username = secret_tool_username(search)
            token = _quiet("secret-tool", "lookup", "service", service).strip()
        case system:
            raise Precondition(f"Credentials aren't supported on {system}.")
    if not username or not token:
        raise Precondition(f"No {service} credential.", "See the setup steps in the tool's README.")
    return Credential(username, token)


def keychain_account(listing: str) -> str:
    """The account name in `security find-generic-password` output, or ""."""
    match = re.search(r'^\s*"acct"<blob>="(.*)"$', listing, re.MULTILINE)
    return match.group(1) if match else ""


def secret_tool_username(listing: str) -> str:
    """The first username attribute in `secret-tool search` output, or ""."""
    match = re.search(r"^attribute\.username = (.*)$", listing, re.MULTILINE)
    return match.group(1) if match else ""


def _quiet(*args: str) -> str:
    """A command's stdout, or "" when it fails."""
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""
