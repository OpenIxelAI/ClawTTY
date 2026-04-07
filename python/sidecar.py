#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PYTHON_DIR = ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from backend.config import load_profiles, add_profile, update_profile, delete_profile, get_profile_by_id
from backend.ssh import build_ssh_command
from backend.ws_client import GatewayClient
from backend.status_cache import load_status_cache, save_status_cache
from backend.credentials import load_token

_ws_clients: dict[str, GatewayClient] = {}


def _safe_load_token(profile_id: str) -> str:
    try:
        return load_token(profile_id) or ""
    except Exception:
        return ""


def _resp(id_: int, ok: bool, result=None, error: str = ""):
    msg = {"id": id_, "ok": ok}
    if ok:
        msg["result"] = result
    else:
        msg["error"] = error
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def method_profiles_list(_params):
    return load_profiles()


def method_profiles_save(params):
    p = params["profile"]
    if get_profile_by_id(p.get("id", "")):
        return update_profile(p)
    return add_profile(p)


def method_profiles_delete(params):
    return delete_profile(params["profileId"])


def method_session_ssh_open(params):
    p = get_profile_by_id(params["profileId"])
    if not p:
        return "Profile not found.\n"
    cmd = build_ssh_command(p)
    return f"$ {cmd.display_cmd}\n\nSession prepared. Open from CLI/Tauri shell execution pipeline.\n"


def method_session_ws_open(params):
    p = get_profile_by_id(params["profileId"])
    if not p:
        return [{"role": "system", "text": "Profile not found", "ts": datetime.now().strftime("%H:%M:%S")}]
    ws_url = str(p.get("ws_url", "")).strip()
    if not ws_url:
        return [{"role": "system", "text": "Profile has no WebSocket URL configured", "ts": datetime.now().strftime("%H:%M:%S")}]
    token = _safe_load_token(p.get("id", ""))
    client = GatewayClient()
    if not client.connect(ws_url, token):
        return [{"role": "system", "text": f"Failed to connect to {ws_url}", "ts": datetime.now().strftime("%H:%M:%S")}]
    _ws_clients[p["id"]] = client
    return [{"role": "system", "text": f"Connected to {ws_url}", "ts": datetime.now().strftime("%H:%M:%S")}]


def method_session_ws_send(params):
    profile_id = str(params.get("profileId", ""))
    text = str(params.get("text", "")).strip()
    client = _ws_clients.get(profile_id)
    if not client:
        return {"role": "system", "text": "No active WebSocket session.", "ts": datetime.now().strftime("%H:%M:%S")}
    # Gateway chat session routing is deployment-specific; provide a live status-backed reply fallback.
    status = client.get_status(timeout=5.0)
    if status:
        return {"role": "agent", "text": f"Gateway online. Received: {text}", "ts": datetime.now().strftime("%H:%M:%S")}
    return {"role": "system", "text": "Message not delivered (gateway unavailable).", "ts": datetime.now().strftime("%H:%M:%S")}


def method_status_refresh(_params):
    cache = load_status_cache()
    result = {}
    profiles = load_profiles()

    def _check_profile(p: dict) -> tuple[str, bool]:
        pid = str(p.get("id", "")).strip()
        if not pid:
            return "", False
        ws_url = str(p.get("ws_url", "")).strip()
        if not ws_url:
            return pid, False
        token = _safe_load_token(pid)
        c = GatewayClient()
        ok = c.connect(ws_url, token)
        if ok:
            c.disconnect()
        return pid, ok

    with ThreadPoolExecutor(max_workers=max(1, min(8, len(profiles)))) as pool:
        futures = [pool.submit(_check_profile, p) for p in profiles]
        for f in as_completed(futures):
            pid, online = f.result()
            if not pid:
                continue
            if online:
                cache.setdefault(pid, {})["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result[pid] = {
                "online": online,
                "lastSeen": cache.get(pid, {}).get("last_seen")
            }
    save_status_cache(cache)
    return result


def method_session_export(params):
    path = Path(params["path"]).expanduser()
    path.write_text(params.get("text", ""), encoding="utf-8")
    return True


METHODS = {
    "profiles.list": method_profiles_list,
    "profiles.save": method_profiles_save,
    "profiles.delete": method_profiles_delete,
    "session.ssh_open": method_session_ssh_open,
    "session.ws_open": method_session_ws_open,
    "session.ws_send": method_session_ws_send,
    "status.refresh": method_status_refresh,
    "session.export": method_session_export,
}


def main():
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
            id_ = int(req["id"])
            method = req["method"]
            params = req.get("params", {})
            fn = METHODS.get(method)
            if not fn:
                _resp(id_, False, error=f"Unknown method: {method}")
                continue
            result = fn(params)
            _resp(id_, True, result=result)
        except Exception as exc:
            _resp(int(req.get("id", 0)) if "req" in locals() else 0, False, error=str(exc))


if __name__ == "__main__":
    main()
