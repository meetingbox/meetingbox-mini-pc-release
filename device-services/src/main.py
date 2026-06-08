"""
MeetingBox device-services — local HTTP bridge for Flutter UI.

Usage:
  cd mini-pc/device-services
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python -m uvicorn bridge:app --app-dir src --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    host = os.getenv("DEVICE_BRIDGE_HOST", "127.0.0.1")
    port = int(os.getenv("DEVICE_BRIDGE_PORT", "8765"))
    uvicorn.run(
        "bridge:app",
        app_dir=os.path.join(os.path.dirname(__file__)),
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )
