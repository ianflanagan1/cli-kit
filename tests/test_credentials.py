from cli_kit.credentials import keychain_account, secret_tool_username

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


def test_reads_the_account_from_a_keychain_listing():
    assert keychain_account(KEYCHAIN_LISTING) == "someone"


def test_reads_the_username_from_a_secret_tool_listing():
    assert secret_tool_username(SECRET_TOOL_LISTING) == "someone"


def test_finds_no_user_in_an_empty_listing():
    assert keychain_account("") == ""
    assert secret_tool_username("") == ""
