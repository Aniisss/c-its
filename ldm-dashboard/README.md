# LDM Dashboard (Host)

Standalone React dashboard for POIM/CAM/CPM visualization on the host machine.

## Run on host

```bash
cd /home/runner/work/c-its/c-its/ldm-dashboard
npm install
npm run dev
```

Dashboard URL:

```text
http://localhost:5173
```

## Configure WebSocket backend URL

Set `VITE_WS_URL` before starting dev server:

```bash
cd /home/runner/work/c-its/c-its/ldm-dashboard
VITE_WS_URL=ws://<backend-ip>:8765 npm run dev
```

If not set, the dashboard defaults to:

```text
ws://localhost:8765
```

## One-command run script

```bash
cd /home/runner/work/c-its/c-its/ldm-dashboard
./run-dashboard.sh
```

The script installs dependencies (if needed) and starts Vite on `0.0.0.0:5173`.
