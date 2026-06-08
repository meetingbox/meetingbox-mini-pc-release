# MeetingBox Device Services

Local HTTP bridge between the **Flutter device UI** and Linux hardware helpers (WiFi, brightness, Bluetooth, audio).

The Kivy `device-ui` app calls these modules in-process. The Flutter app calls this service over `http://127.0.0.1:8765`.

## Run (development)

```bash
cd mini-pc/device-services
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

Or with uvicorn directly:

```bash
uvicorn bridge:app --app-dir src --host 127.0.0.1 --port 8765 --reload
```

## API (v0.1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/v1/wifi/scan` | Scan WiFi (nmcli) |
| POST | `/v1/wifi/connect` | Connect to network |
| GET | `/v1/brightness` | Read backlight % |
| POST | `/v1/brightness` | Set backlight % |
| GET | `/v1/bluetooth/status` | Adapter status |
| GET | `/v1/audio/devices` | List input/output devices |

WiFi/brightness implementations are imported from `../device-ui/src/` — no duplication.

## Production

Run as a systemd user/service alongside `meetingbox-device-ui-flutter` (future packaging step).

```ini
[Service]
ExecStart=/usr/bin/python3 /usr/lib/meetingbox/device-services/main.py
Environment=DEVICE_BRIDGE_HOST=127.0.0.1
Environment=DEVICE_BRIDGE_PORT=8765
```
