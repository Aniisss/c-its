# V2X Apps LDM Dashboard Backend

This package now includes a real-time LDM backend in `v2x_apps/ldm_server.py` for C-ITS dashboard use cases.

## LDM data sources

The LDM server subscribes to:

- `/its/cam` (CAM) → updates `stations`
- `/its/cpm` (CPM) → updates `perceived_objects`
- `/parking/poim_outgoing` (JSON String) → updates `pois`
- `/parking/poim_incoming` (JSON String) → updates `pois`
- `/parking/poim_decoded` (JSON String) → updates `pois`

## LDM state model

The server maintains an internal in-memory store:

- `stations`: keyed by CAM station id
- `perceived_objects`: keyed by `{source_station_id}:{object_id}`
- `pois`: keyed by POI id

Each record stores `last_update` internally. Stale entries older than 5 seconds are removed automatically.

## HTTP + WebSocket API

- `GET /ldm/state` → full live LDM snapshot (`stations`, `perceived_objects`, `pois`)
- `GET /ldm/geojson` → GeoJSON projection of the same LDM data
- `WS /ws/ldm` → pushes updated LDM snapshots whenever CAM/CPM/POIM updates are processed or stale entries are pruned

## ETSI station type support

`stations[].station_type` is exposed from CAM basic container data and can be used in frontend icon mapping logic, e.g.:

- Type `5`: passenger car
- Type `15`: RSU

Use this value in the dashboard map layer to choose station icons.
