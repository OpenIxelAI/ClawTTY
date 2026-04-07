# Python Sidecar

This folder hosts the Python runtime entry points and backend package.

- `sidecar.py` — stdio JSON-RPC bridge consumed by the React/Tauri app.
- `backend/` — shared backend package used by both GUI (`clawtty.py`) and sidecar.

The `src/` directory is frontend-only (React/TypeScript). Python runtime code lives under `python/backend/`.
