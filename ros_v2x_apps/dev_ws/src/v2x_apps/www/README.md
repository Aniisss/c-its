# C-ITS React Dashboard (www)

This folder contains the frontend dashboard for the `v2x_apps/ldm_server.py` backend.

## Stack

- React + Vite
- Leaflet + react-leaflet
- Tailwind CSS
- lucide-react icons
- WebSocket feed from `ws://localhost:8000/ws/ldm`

## Project structure

- `src/context/LDMContext.jsx`: WebSocket context and `useLDM` hook
- `src/components/LDMMap.jsx`: map layers (CAM/CPM/POIM) and dashboard UI
- `src/App.jsx`: app shell
- `src/main.jsx`: app bootstrap

## Features implemented

- **CAM layer**: connected station markers with station-type icon mapping and heading-based orientation
- **CPM layer**: perceived object circles with dashed links to source station
- **POIM layer**: parking markers with occupancy color coding
- **Layer toggles**: CAM / CPM / POIM enable/disable controls
- **Live sidebar**: active stations sorted by RSSI, then age
- **Connection status**: Live / Connecting / Disconnected indicator
- **Auto-center**: centers on first available CAM station (fallback Brussels coordinates)
- **Dark mode dashboard** styling

## Development

From this folder:

```bash
npm install
npm run dev
```

Open the app via Vite (default `http://localhost:5173/www/`).

## Production build

Build static assets:

```bash
npm run build
```

This creates `www/dist`. The backend is configured to serve `www/dist` automatically when present.

## Backend integration

Start the server node:

```bash
ros2 run v2x_apps ldm_server
```

Dashboard endpoints:

- `http://localhost:8000/` (redirects to `/www/map.html`)
- `http://localhost:8000/map.html`
- `ws://localhost:8000/ws/ldm`

## Packaging note

`setup.py` now packages the full `www` tree recursively, including `dist/assets`, so built frontend files are available after ROS package installation.
