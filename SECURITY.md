# ClawTTY v3 — Security Model & Threat Model

ClawTTY is a security-critical application. It holds SSH profiles, manages connections
to remote machines running AI agents, and can be a high-value target if built carelessly.
This document describes every security decision, attack surface, and mitigation.

---

## Core Security Principles

1. **Fail closed** — when in doubt, block. Never guess, never silently proceed.
2. **Zero plaintext secrets** — credentials live in the OS keychain, never in files.
3. **Bounded remote commands** — preset agents only allow fixed CLI strings; **Custom** is explicit opt-in with additional guards (not full arbitrary-shell lockdown).
4. **Honest audit trail** — every action logged locally, append-only.
5. **No telemetry** — ClawTTY makes zero unsolicited network calls.

---

## Attack Surfaces & Mitigations

### 1. Remote Command Injection

**Threat:** An attacker manipulates a profile to execute arbitrary shell commands on a remote machine.

**Mitigation:**
- Each SSH profile has an **`agent`** field: `openclaw`, `hermes`, or `custom`.
- For **`openclaw`** and **`hermes`**, `remote_command` must be exactly one of four preset strings per agent (defined in `config.py`), e.g. `openclaw tui`, `hermes status`, etc.
- For **`custom`**, the user supplies the remote command string. ClawTTY enforces length limits and rejects common shell metacharacters and substitution patterns (`config.validate_custom_remote_command`). This reduces casual injection via profile files but is **not** equivalent to a hardcoded four-command allowlist — the user explicitly chooses higher risk.
- Invalid combinations are rejected or sanitized on load in `_sanitize()`; `ssh.py` validates again before building the SSH argv list.
- SSH is invoked with `subprocess` as an argv list — **no `shell=True`**, no string interpolation of profile fields into a shell on the local machine.
- Validation is applied in **two places**: `config.py` (on load/save) and `ssh.py` (on build).

### 2. SSH Man-in-the-Middle (MITM)

**Threat:** An attacker intercepts the SSH connection by impersonating the target host.

**Mitigation:**
- ClawTTY maintains its own `~/.local/share/clawtty/known_hosts` file, separate from `~/.ssh/known_hosts`.
- On first connection, the host's SSH fingerprint is fetched via paramiko and shown to the user.
- The user must **explicitly confirm** the fingerprint before any connection proceeds.
- On subsequent connections, the fingerprint is compared to the stored value.
- If there is **any mismatch**, the connection is **blocked** and a loud warning is shown.
- There is no "trust anyway" or "bypass" option on a mismatch — you must manually edit known_hosts.
- All key confirm/reject/mismatch events are logged to the audit log.

### 3. Credential Theft

**Threat:** An attacker reads stored credentials from disk.

**Mitigation:**
- SSH key passphrases are stored **exclusively** in the OS keychain via `libsecret` (GNOME keyring / KWallet).
- `profiles.json` contains **zero secrets** — only host, user, port, key path (not key data), agent, remote command, and notes.
- `profiles.json` is written with `0o600` permissions (owner read/write only).
- The config directory `~/.config/clawtty/` is created with `0o700` permissions.
- If `secretstorage` is unavailable, ClawTTY **refuses to store the passphrase** — no plaintext fallback.
- SSH private keys are referenced by file path only; ClawTTY never reads or copies key material.

### 4. Identity File Permission Weakness

**Threat:** An SSH key with loose permissions is used, making it readable by other users.

**Mitigation:**
- Before using an identity file, `ssh.py` checks its permissions.
- If the file is group-readable, group-writable, other-readable, or other-writable, the connection is **blocked** with an error message explaining how to fix it (`chmod 600`).

### 5. Profile File Tampering

**Threat:** A malicious actor modifies `profiles.json` to inject dangerous values.

**Mitigation:**
- Every profile loaded from disk is sanitized through `_sanitize()` in `config.py`.
- `_sanitize()` enforces type coercion, port range clamping, `agent` normalization, and remote-command rules (presets vs custom guards).
- Any forbidden key (`password`, `passphrase`, `secret`, `key_data`, `private_key`) is stripped.
- Malformed JSON or wrong schema silently returns an empty profile list.
- Atomic file writes (write to `.tmp`, then rename) prevent partial/corrupt writes.

### 6. SSH Key Generation Passphrase Exposure

**Threat:** A passphrase passed to `ssh-keygen` ends up in shell history, logs, or `/proc`.

**Mitigation:**
- `credentials.py` uses a temp file (with `0o600` permissions) to hold the passphrase temporarily.
- The passphrase is passed via `subprocess` argv, not via shell string.
- The temp file is **securely overwritten with null bytes** and deleted immediately after use.
- Note: passing via argv still exposes it briefly in `/proc/<pid>/cmdline` on Linux.
  For maximum security, prefer generating keys without a passphrase and relying on key file permissions + full-disk encryption.

### 7. Audit Log Tampering

**Threat:** An attacker clears or modifies the audit log to cover tracks.

**Mitigation:**
- The audit log is **append-only** from ClawTTY's perspective (no delete or truncate API).
- The log file is created with `0o600` permissions.
- For environments requiring tamper-proof logs, pipe `~/.local/share/clawtty/audit.log` to a remote syslog or immutable log system (outside scope of ClawTTY).

### 8. Broadcast Mode Abuse

**Threat:** Broadcast sends preset commands to unintended sessions.

**Mitigation:**
- Preset broadcast commands apply only to sessions whose profile **agent** matches that preset (e.g. `openclaw status` is not applied to Hermes-only sessions).
- “Broadcast All (status)” resolves the appropriate status command per session (`openclaw status` vs `hermes status`); custom-only sessions are skipped with a clear status message.
- Broadcast is **opt-in** per action (user must trigger it), not automatic.

### 9. Terminal Emulator Injection

**Threat:** A terminal emulator command is manipulated to execute arbitrary code.

**Mitigation:**
- Terminal emulator path is resolved via `shutil.which()` — only executables on PATH are used.
- The SSH command is passed as an argv list to the terminal, not as a shell string.
- No user-supplied values are interpolated into the terminal launch command.

---

## What ClawTTY Does NOT Protect Against

- **A compromised local machine** — if an attacker has root or your user account on the local machine, they can read keychain secrets, modify ClawTTY's files, or intercept the terminal session.
- **A compromised system keyring** — if your GNOME keyring or KWallet is unlocked and compromised, stored passphrases may be readable.
- **Physical access attacks** — ClawTTY does not provide protection against an attacker with physical access to your machine.
- **Weak SSH keys** — ClawTTY encourages ed25519 keys and warns about bad permissions, but cannot prevent you from using a weak passphrase.
- **Remote machine compromise** — once SSH'd into a remote agent host, security of that node is outside ClawTTY's scope.
- **Custom agent mode** — you can run a user-defined remote command; ClawTTY does not sandbox the remote shell. Use presets when you want the strictest lockdown.

---

## Reporting Vulnerabilities

If you find a security issue in ClawTTY:

1. **Do not open a public GitHub issue.**
2. Contact the maintainer directly (OpenIxelAI) with details.
3. Include: description, reproduction steps, potential impact, and any suggested fix.
4. We aim to respond within 48 hours and ship a fix within 7 days for critical issues.

We take security reports seriously. Thank you for helping keep ClawTTY safe.

---

## Security Design Decisions

| Decision | Reason |
|----------|--------|
| Preset commands per agent + optional custom | Supports multiple agent CLIs; custom is explicit opt-in with guards. |
| Separate known_hosts file | Don't interfere with system SSH; isolate ClawTTY's trust decisions. |
| libsecret only, no plaintext fallback | A fallback would undermine the security guarantee entirely. |
| Fail closed on all errors | Silently proceeding on errors is how security bugs become exploits. |
| Atomic config writes | Prevents corrupt state from a crash mid-write. |
| No `shell=True` anywhere | Shell injection is a trivially exploitable vulnerability class. |
| Audit log append-only | Makes it harder to cover tracks; supports forensic review. |
| 0o600 on all sensitive files | Ensures only the owning user can read credentials/profiles. |

---

*Last updated: 2026-04-06*  
*ClawTTY v3 — OpenIxelAI*
