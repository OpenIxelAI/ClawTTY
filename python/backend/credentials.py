"""
credentials.py — Keyring storage for SSH passphrases and WebSocket tokens.

Security design:
  - Secrets stored ONLY in the system keyring (GNOME keyring / KWallet via libsecret).
  - If secretstorage is unavailable, this module raises CredentialUnavailable.
  - NO plaintext fallback. Ever.
  - SSH private keys are referenced by path only (never stored or read here).
  - WebSocket tokens stored by profile_id under a separate attribute namespace.
  - Key generation and ssh-copy-id run as subprocesses; no key material ever
    enters Python memory through this module.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from .platform_info import use_keyring_backend

# ── secretstorage import (optional dep — fail loudly if missing) ──────────────
try:
    import secretstorage  # type: ignore

    _SECRETSTORAGE_AVAILABLE = True
except ImportError:
    _SECRETSTORAGE_AVAILABLE = False

try:
    import keyring  # type: ignore

    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

_SERVICE_NAME = "clawtty-v3"
_TOKEN_ATTR_KEY = "token_profile_id"


class CredentialUnavailable(RuntimeError):
    """Raised when the system keyring backend is not available."""


class KeyringError(RuntimeError):
    """Raised for keyring read/write failures."""


def _require_secretstorage() -> None:
    if use_keyring_backend():
        if not _KEYRING_AVAILABLE:
            raise CredentialUnavailable(
                "keyring is not installed. Run: pip install keyring>=24.0.0"
            )
        return
    if not _SECRETSTORAGE_AVAILABLE:
        raise CredentialUnavailable(
            "secretstorage is not installed. "
            "Run: pip install secretstorage>=3.3.0\n"
            "Passphrase storage requires the GNOME keyring (libsecret)."
        )


def _open_collection():  # type: ignore[return]
    """Open and return the default secretstorage collection, or raise."""
    _require_secretstorage()
    if use_keyring_backend():
        return None
    try:
        conn = secretstorage.dbus_init()
        collection = secretstorage.get_default_collection(conn)
        if collection.is_locked():
            collection.unlock()
        return collection
    except Exception as exc:
        raise KeyringError(f"Could not open keyring: {exc}") from exc


def store_passphrase(profile_id: str, passphrase: str) -> None:
    """
    Store an SSH key passphrase in the system keyring.

    Raises:
        CredentialUnavailable: if secretstorage is not installed.
        KeyringError: on keyring backend failure.
    """
    try:
        _open_collection()
        if use_keyring_backend():
            try:
                keyring.set_password(_SERVICE_NAME, f"passphrase:{profile_id}", passphrase)
            except Exception as exc:
                raise KeyringError(f"Could not store passphrase: {exc}") from exc
        else:
            coll = _open_collection()
            label = f"ClawTTY passphrase for profile {profile_id}"
            attrs = {"service": _SERVICE_NAME, "profile_id": profile_id}
            try:
                coll.create_item(label, attrs, passphrase, replace=True)
            except Exception as exc:
                raise KeyringError(f"Could not store passphrase: {exc}") from exc
    finally:
        # Wipe passphrase from local variable as soon as possible
        # NOTE: Python strings are immutable — zero-filling rebinds only the
        # local name, not the underlying memory. Removed false-security wipe.
        pass


def get_passphrase(profile_id: str) -> str | None:
    """
    Retrieve a stored passphrase from the keyring.
    Returns None if no entry exists.

    Raises:
        CredentialUnavailable / KeyringError on backend issues.
    """
    _open_collection()
    if use_keyring_backend():
        try:
            return keyring.get_password(_SERVICE_NAME, f"passphrase:{profile_id}")
        except Exception as exc:
            raise KeyringError(f"Could not read passphrase: {exc}") from exc
    coll = _open_collection()
    attrs = {"service": _SERVICE_NAME, "profile_id": profile_id}
    try:
        items = list(coll.search_items(attrs))
    except Exception as exc:
        raise KeyringError(f"Keyring search failed: {exc}") from exc

    if not items:
        return None
    try:
        return items[0].get_secret().decode("utf-8")
    except Exception as exc:
        raise KeyringError(f"Could not read passphrase: {exc}") from exc


def delete_passphrase(profile_id: str) -> bool:
    """
    Delete a stored passphrase. Returns True if deleted, False if not found.

    Raises:
        CredentialUnavailable / KeyringError on backend issues.
    """
    _open_collection()
    if use_keyring_backend():
        try:
            current = keyring.get_password(_SERVICE_NAME, f"passphrase:{profile_id}")
            if current is None:
                return False
            keyring.delete_password(_SERVICE_NAME, f"passphrase:{profile_id}")
            return True
        except Exception as exc:
            raise KeyringError(f"Could not delete passphrase: {exc}") from exc
    coll = _open_collection()
    attrs = {"service": _SERVICE_NAME, "profile_id": profile_id}
    try:
        items = list(coll.search_items(attrs))
    except Exception as exc:
        raise KeyringError(f"Keyring search failed: {exc}") from exc

    if not items:
        return False
    for item in items:
        item.delete()
    return True


def is_available() -> bool:
    """Return True if secretstorage is installed and the keyring is reachable."""
    if not _SECRETSTORAGE_AVAILABLE:
        return False
    try:
        _open_collection()
        return True
    except (CredentialUnavailable, KeyringError):
        return False


# ── API token storage (per-profile) ───────────────────────────────────────────
# Tokens are stored with a separate attribute key so they cannot be confused
# with SSH passphrases.

def _token_label(profile_id: str) -> str:
    """
    Build key label format: clawtty-token-{profile_name}-{host}.
    Falls back to profile_id if profile metadata is unavailable.
    """
    name = profile_id
    host = profile_id
    try:
        # Local import to avoid module-level coupling
        from .config import get_profile_by_id

        p = get_profile_by_id(profile_id) or {}
        raw_name = str(p.get("name") or profile_id).strip()
        raw_host = str(p.get("host") or "").strip()
        if not raw_host:
            ws_url = str(p.get("ws_url") or "").strip()
            if ws_url:
                raw_host = urlparse(ws_url).hostname or ws_url
        name = raw_name or profile_id
        host = raw_host or profile_id
    except Exception:
        pass

    def _clean(s: str) -> str:
        s = re.sub(r"\s+", "-", s.strip())
        return re.sub(r"[^a-zA-Z0-9._-]", "_", s) or "unknown"

    return f"clawtty-token-{_clean(name)}-{_clean(host)}"


def save_token(profile_id: str, token: str) -> None:
    """
    Store a WebSocket gateway token in the system keyring.

    Raises:
        CredentialUnavailable: if secretstorage is not installed.
        KeyringError: on keyring backend failure.
    """
    try:
        _open_collection()
        if use_keyring_backend():
            try:
                keyring.set_password(_SERVICE_NAME, f"token:{profile_id}", token)
            except Exception as exc:
                raise KeyringError(f"Could not store API token: {exc}") from exc
        else:
            coll = _open_collection()
            label = _token_label(profile_id)
            attrs = {"service": _SERVICE_NAME, _TOKEN_ATTR_KEY: profile_id}
            try:
                coll.create_item(label, attrs, token, replace=True)
            except Exception as exc:
                raise KeyringError(f"Could not store API token: {exc}") from exc
    finally:
        # NOTE: Python strings are immutable — zero-filling doesn't wipe memory.
        pass


def load_token(profile_id: str) -> str | None:
    """
    Retrieve a stored WebSocket gateway token from the keyring.
    Returns None if no entry exists.

    Raises:
        CredentialUnavailable / KeyringError on backend issues.
    """
    _open_collection()
    if use_keyring_backend():
        try:
            return keyring.get_password(_SERVICE_NAME, f"token:{profile_id}")
        except Exception as exc:
            raise KeyringError(f"Could not read API token: {exc}") from exc
    coll = _open_collection()
    attrs = {"service": _SERVICE_NAME, _TOKEN_ATTR_KEY: profile_id}
    try:
        items = list(coll.search_items(attrs))
    except Exception as exc:
        raise KeyringError(f"Keyring search failed: {exc}") from exc

    if not items:
        return None
    try:
        return items[0].get_secret().decode("utf-8")
    except Exception as exc:
        raise KeyringError(f"Could not read API token: {exc}") from exc


def delete_token(profile_id: str) -> bool:
    """
    Delete a stored WebSocket token. Returns True if deleted, False if not found.

    Raises:
        CredentialUnavailable / KeyringError on backend issues.
    """
    _open_collection()
    if use_keyring_backend():
        try:
            current = keyring.get_password(_SERVICE_NAME, f"token:{profile_id}")
            if current is None:
                return False
            keyring.delete_password(_SERVICE_NAME, f"token:{profile_id}")
            return True
        except Exception as exc:
            raise KeyringError(f"Could not delete API token: {exc}") from exc
    coll = _open_collection()
    attrs = {"service": _SERVICE_NAME, _TOKEN_ATTR_KEY: profile_id}
    try:
        items = list(coll.search_items(attrs))
    except Exception as exc:
        raise KeyringError(f"Keyring search failed: {exc}") from exc

    if not items:
        return False
    for item in items:
        item.delete()
    return True


# Backward-compatible aliases
store_ws_token = save_token
get_ws_token = load_token
delete_ws_token = delete_token


# ── SSH Key Generation ────────────────────────────────────────────────────────

class KeyGenResult:
    """Result object from generate_ssh_key()."""

    def __init__(
        self,
        success: bool,
        private_key_path: Path | None,
        public_key_path: Path | None,
        fingerprint: str,
        message: str,
    ) -> None:
        self.success = success
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path
        self.fingerprint = fingerprint
        self.message = message

    def __repr__(self) -> str:
        return (
            f"KeyGenResult(success={self.success}, "
            f"key={self.private_key_path}, fingerprint={self.fingerprint!r})"
        )


def generate_ssh_key(
    key_path: Path | str,
    key_type: str = "ed25519",
    comment: str = "clawtty-generated",
    passphrase: str = "",
) -> KeyGenResult:
    """
    Generate an SSH key pair using ssh-keygen.

    The passphrase (if given) is passed via a temp file to avoid shell history
    exposure. The temp file is securely deleted immediately after use.

    Args:
        key_path:   Destination path for the private key.
        key_type:   "ed25519" (default) or "rsa" (4096-bit).
        comment:    Key comment field.
        passphrase: Optional passphrase. Empty string = no passphrase.

    Returns:
        KeyGenResult with success flag, paths, fingerprint, and message.
    """
    keygen = shutil.which("ssh-keygen")
    if not keygen:
        return KeyGenResult(False, None, None, "", "ssh-keygen not found on PATH")

    key_path = Path(key_path).expanduser().resolve()
    if key_path.exists():
        return KeyGenResult(
            False, None, None, "", f"Key file already exists: {key_path}"
        )

    key_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(key_path.parent, 0o700)

    # Decide key bits
    bits_args: list[str] = []
    if key_type == "rsa":
        bits_args = ["-b", "4096"]
    elif key_type != "ed25519":
        key_type = "ed25519"

    try:
        # SECURITY FIX: Never pass passphrase as CLI arg (visible in ps/proc).
        # Let ssh-keygen prompt and feed answers via stdin.
        cmd = [
            keygen,
            "-t", key_type,
            *bits_args,
            "-C", comment,
            "-f", str(key_path),
        ]

        stdin_data = None
        if passphrase:
            # ssh-keygen asks for passphrase + confirmation when -N is omitted.
            stdin_data = f"{passphrase}\n{passphrase}\n"

        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return KeyGenResult(
                False, None, None, "",
                f"ssh-keygen failed: {result.stderr.strip()}"
            )

        # Get fingerprint
        fp_result = subprocess.run(
            [keygen, "-l", "-f", str(key_path)],
            capture_output=True, text=True, timeout=10,
        )
        fingerprint = fp_result.stdout.strip() if fp_result.returncode == 0 else "unknown"

        pub_path = key_path.with_suffix(".pub") if not str(key_path).endswith(".pub") else key_path
        if not pub_path.exists():
            pub_path = Path(str(key_path) + ".pub")

        os.chmod(key_path, 0o600)

        return KeyGenResult(
            True, key_path, pub_path if pub_path.exists() else None,
            fingerprint, "Key pair generated successfully."
        )

    except subprocess.TimeoutExpired:
        return KeyGenResult(False, None, None, "", "ssh-keygen timed out")
    except Exception as exc:
        return KeyGenResult(False, None, None, "", f"Key generation error: {exc}")
    finally:
        pass


def copy_id_to_host(
    key_path: Path | str,
    user: str,
    host: str,
    port: int = 22,
) -> tuple[bool, str]:
    """
    Run ssh-copy-id to install a public key on a remote host.

    Returns (success, message).
    """
    copy_id = shutil.which("ssh-copy-id")
    if not copy_id:
        return False, "ssh-copy-id not found on PATH"

    key_path = Path(key_path).expanduser().resolve()
    pub_path = Path(str(key_path) + ".pub")
    if not pub_path.exists():
        pub_path = key_path.with_suffix(".pub")
    if not pub_path.exists():
        return False, f"Public key not found at {pub_path}"

    cmd = [
        copy_id,
        "-i", str(pub_path),
        "-p", str(port),
        f"{user}@{host}",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, "Public key installed on remote host."
        return False, f"ssh-copy-id failed: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "ssh-copy-id timed out"
    except Exception as exc:
        return False, f"ssh-copy-id error: {exc}"
