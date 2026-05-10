#!/usr/bin/env python3

import asyncio
import json
import math
import os
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import rclpy
from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from rclpy.node import Node
from std_msgs.msg import String
import uvicorn
import etsi_its_cpm_ts_msgs.msg as cpm_msg
from etsi_its_cam_msgs.msg import CAM

_SERVER_SHUTDOWN_TIMEOUT_SECONDS = 3.0
_STALE_DATA_SECONDS = 5.0
_CLEANUP_PERIOD_SECONDS = 1.0
_HEADING_SCALE_THRESHOLD_DEGREES = 360.0
_METERS_PER_DEGREE_LAT = 111111.0
_MIN_COS_LATITUDE_SCALE = 1e-6


def _scaled_coord_to_decimal(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    numeric = float(value)
    if abs(numeric) > 180.0:
        return numeric / 1e7
    return numeric


def _to_float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _safe_nested_attr(root: Any, path: Iterable[str]) -> Any:
    node = root
    for attr in path:
        if node is None or not hasattr(node, attr):
            return None
        node = getattr(node, attr)
    return node


def _extract_first(root: Any, paths: Iterable[Tuple[str, ...]]) -> Any:
    for path in paths:
        value = _safe_nested_attr(root, path)
        if value is not None:
            return value
    return None


def _heading_to_degrees(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if abs(value) > _HEADING_SCALE_THRESHOLD_DEGREES:
        return value / 10.0
    return value


class LdmStore:
    def __init__(self) -> None:
        self._stations: Dict[str, Dict[str, Any]] = {}
        self._perceived_objects: Dict[str, Dict[str, Any]] = {}
        self._pois: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    @staticmethod
    def _copy_for_wire(record: Dict[str, Any], now: float) -> Dict[str, Any]:
        item = dict(record)
        last_update = _to_float_or_none(item.pop('last_update', None))
        # Defensive clamp for rare timing edge-cases when snapshots race with updates.
        item['age_seconds'] = max(0.0, now - last_update) if last_update is not None else 0.0
        return item

    def update_station_from_cam(self, msg: CAM) -> bool:
        station_id = _to_str_or_none(_extract_first(msg, (
            ('header', 'station_id', 'value'),
            ('header', 'station_id'),
        )))
        if station_id is None:
            return False

        lat_raw = _to_float_or_none(_extract_first(msg, (
            ('payload', 'cam', 'cam_parameters', 'basic_container', 'reference_position', 'latitude', 'value'),
            ('payload', 'basic_container', 'reference_position', 'latitude', 'value'),
        )))
        lon_raw = _to_float_or_none(_extract_first(msg, (
            ('payload', 'cam', 'cam_parameters', 'basic_container', 'reference_position', 'longitude', 'value'),
            ('payload', 'basic_container', 'reference_position', 'longitude', 'value'),
        )))
        heading_raw = _to_float_or_none(_extract_first(msg, (
            ('payload', 'cam', 'cam_parameters', 'high_frequency_container', 'basic_vehicle_container_high_frequency', 'heading', 'heading_value', 'value'),
            ('payload', 'high_frequency_container', 'basic_vehicle_container_high_frequency', 'heading', 'heading_value', 'value'),
        )))
        speed_raw = _to_float_or_none(_extract_first(msg, (
            ('payload', 'cam', 'cam_parameters', 'high_frequency_container', 'basic_vehicle_container_high_frequency', 'speed', 'speed_value', 'value'),
            ('payload', 'high_frequency_container', 'basic_vehicle_container_high_frequency', 'speed', 'speed_value', 'value'),
        )))
        station_type = _to_float_or_none(_extract_first(msg, (
            ('payload', 'cam', 'cam_parameters', 'basic_container', 'station_type', 'value'),
            ('payload', 'basic_container', 'station_type', 'value'),
        )))
        rssi = _to_float_or_none(_extract_first(msg, (
            ('header', 'rssi'),
            ('header', 'rx_power'),
        )))

        station_record = {
            'id': station_id,
            'station_id': station_id,
            'station_type': int(station_type) if station_type is not None else None,
            'latitude': _scaled_coord_to_decimal(lat_raw),
            'longitude': _scaled_coord_to_decimal(lon_raw),
            'heading': _heading_to_degrees(heading_raw),
            'speed': speed_raw,
            'rssi': rssi,
            'last_update': self._now(),
        }

        with self._lock:
            self._stations[station_id] = station_record
        return True

    def update_from_cpm(self, msg: cpm_msg.CollectivePerceptionMessage) -> bool:
        station_id = _to_str_or_none(_extract_first(msg, (
            ('header', 'station_id', 'value'),
            ('header', 'station_id'),
        )))
        if station_id is None:
            return False

        ref_lat = _scaled_coord_to_decimal(_to_float_or_none(_extract_first(msg, (
            ('payload', 'management_container', 'reference_position', 'latitude', 'value'),
        ))))
        ref_lon = _scaled_coord_to_decimal(_to_float_or_none(_extract_first(msg, (
            ('payload', 'management_container', 'reference_position', 'longitude', 'value'),
        ))))
        containers = _extract_first(msg, (('payload', 'cpm_containers', 'value', 'array'),))
        if containers is None:
            return False

        changed = False
        now = self._now()
        with self._lock:
            for container in containers:
                perceived_container = getattr(container, 'container_data_perceived_object_container', None)
                if perceived_container is None or not hasattr(perceived_container, 'perceived_objects'):
                    continue
                for obj in perceived_container.perceived_objects.array:
                    object_id = _to_str_or_none(_extract_first(obj, (
                        ('object_id', 'value'),
                        ('object_id',),
                    )))
                    if object_id is None:
                        continue

                    x_cm = _to_float_or_none(_extract_first(obj, (
                        ('position', 'x_coordinate', 'value', 'value'),
                        ('position', 'x_coordinate', 'value'),
                    )))
                    y_cm = _to_float_or_none(_extract_first(obj, (
                        ('position', 'y_coordinate', 'value', 'value'),
                        ('position', 'y_coordinate', 'value'),
                    )))
                    x_m = (x_cm / 100.0) if x_cm is not None else None
                    y_m = (y_cm / 100.0) if y_cm is not None else None

                    lat = ref_lat
                    lon = ref_lon
                    if ref_lat is not None and ref_lon is not None and x_m is not None and y_m is not None:
                        # Approximate local ENU->lat/lon conversion; accurate for short-range
                        # CPM object offsets and less reliable near the poles.
                        lat = ref_lat + (y_m / _METERS_PER_DEGREE_LAT)
                        lon_scale = _METERS_PER_DEGREE_LAT * max(
                            _MIN_COS_LATITUDE_SCALE,
                            math.cos(math.radians(ref_lat)),
                        )
                        lon = ref_lon + (x_m / lon_scale)

                    key = f'{station_id}:{object_id}'
                    self._perceived_objects[key] = {
                        'id': key,
                        'source_station_id': station_id,
                        'object_id': object_id,
                        'latitude': lat,
                        'longitude': lon,
                        'x_m': x_m,
                        'y_m': y_m,
                        'last_update': now,
                    }
                    changed = True
        return changed

    def update_poi_from_json(self, payload: Dict[str, Any]) -> bool:
        poi_id = payload.get('poi_id') or payload.get('id') or payload.get('poiId')
        if poi_id is None:
            return False

        lat = _scaled_coord_to_decimal(_to_float_or_none(payload.get('latitude')))
        lon = _scaled_coord_to_decimal(_to_float_or_none(payload.get('longitude')))
        if lat is None or lon is None:
            return False

        occupancy = _to_float_or_none(payload.get('occupancy_percent'))
        if occupancy is None:
            occupancy = _to_float_or_none(payload.get('current_occupancy'))
        if occupancy is None:
            occupancy = 0.0
        occupancy = max(0.0, min(100.0, occupancy))

        key = str(poi_id)
        with self._lock:
            self._pois[key] = {
                'id': key,
                'name': payload.get('facility_name') or 'Parking',
                'latitude': lat,
                'longitude': lon,
                'occupancy_percent': occupancy,
                'last_update': self._now(),
            }
        return True

    def prune_stale(self, stale_seconds: float) -> bool:
        now = self._now()
        changed = False
        with self._lock:
            for store in (self._stations, self._perceived_objects, self._pois):
                stale_keys = [
                    key for key, item in store.items()
                    if (now - item.get('last_update', 0.0)) > stale_seconds
                ]
                for key in stale_keys:
                    del store[key]
                    changed = True
        return changed

    def snapshot(self) -> Dict[str, Any]:
        now = self._now()
        with self._lock:
            stations = [self._copy_for_wire(item, now) for item in self._stations.values()]
            perceived_objects = [self._copy_for_wire(item, now) for item in self._perceived_objects.values()]
            pois = [self._copy_for_wire(item, now) for item in self._pois.values()]
        return {
            'timestamp': time.time(),
            'stations': stations,
            'perceived_objects': perceived_objects,
            'pois': pois,
        }

    def geojson(self) -> Dict[str, Any]:
        snapshot = self.snapshot()
        features: List[Dict[str, Any]] = []

        for station in snapshot['stations']:
            if station.get('latitude') is None or station.get('longitude') is None:
                continue
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [station['longitude'], station['latitude']],
                },
                'properties': {
                    'type': 'station',
                    'id': station.get('station_id'),
                    'station_type': station.get('station_type'),
                    'heading': station.get('heading'),
                    'speed': station.get('speed'),
                    'rssi': station.get('rssi'),
                },
            })

        for obj in snapshot['perceived_objects']:
            if obj.get('latitude') is None or obj.get('longitude') is None:
                continue
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [obj['longitude'], obj['latitude']],
                },
                'properties': {
                    'type': 'perceived_object',
                    'id': obj.get('id'),
                    'source_station_id': obj.get('source_station_id'),
                    'object_id': obj.get('object_id'),
                },
            })

        for poi in snapshot['pois']:
            if poi.get('latitude') is None or poi.get('longitude') is None:
                continue
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [poi['longitude'], poi['latitude']],
                },
                'properties': {
                    'type': 'parking',
                    'id': poi.get('id'),
                    'name': poi.get('name', 'Parking'),
                    'occupancy': poi.get('occupancy_percent', 0.0),
                },
            })

        return {'type': 'FeatureCollection', 'features': features}


class WebSocketHub:
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._clients: Set[WebSocket] = set()
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            clients = list(self._clients)
        disconnected: List[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        if disconnected:
            with self._lock:
                for ws in disconnected:
                    self._clients.discard(ws)

    def broadcast_threadsafe(self, payload: Dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)


class LdmServer(Node):
    def __init__(self) -> None:
        super().__init__('ldm_server')
        self._store = LdmStore()
        self._ws_hub = WebSocketHub()

        self.declare_parameter('web_host', '0.0.0.0')
        self.declare_parameter('web_port', 8000)
        self.declare_parameter('web_log_level', 'warning')
        self.declare_parameter('cam_topic', '/its/cam')
        self.declare_parameter('cpm_topic', '/its/cpm')
        self.declare_parameter('poim_outgoing_topic', '/parking/poim_outgoing')
        self.declare_parameter('poim_incoming_topic', '/parking/poim_incoming')
        self.declare_parameter('poim_decoded_topic', '/parking/poim_decoded')

        self.create_subscription(CAM, self.get_parameter('cam_topic').value, self._on_cam, 10)
        self.create_subscription(cpm_msg.CollectivePerceptionMessage, self.get_parameter('cpm_topic').value, self._on_cpm, 10)
        self.create_subscription(String, self.get_parameter('poim_outgoing_topic').value, self._on_poim_object, 10)
        self.create_subscription(String, self.get_parameter('poim_incoming_topic').value, self._on_poim_object, 10)
        self.create_subscription(String, self.get_parameter('poim_decoded_topic').value, self._on_poim_object, 10)
        self.create_timer(_CLEANUP_PERIOD_SECONDS, self._on_cleanup_timer)

        self._app = FastAPI(title='LDM Server', version='1.0')
        self._configure_routes()
        self._server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self._start_web_server()
        self.get_logger().info(
            f"LDM Server ready at http://{self.get_parameter('web_host').value}:{int(self.get_parameter('web_port').value)}/"
        )

    def _configure_routes(self) -> None:
        @self._app.on_event('startup')
        async def _on_app_startup() -> None:
            self._ws_hub.set_loop(asyncio.get_running_loop())

        www_dir = self._resolve_www_directory()
        if www_dir and os.path.isdir(www_dir):
            self._app.mount('/www', StaticFiles(directory=www_dir), name='www')

            @self._app.get('/')
            def root():
                return RedirectResponse(url='/www/map.html')

            @self._app.get('/map.html')
            def map_html():
                return FileResponse(os.path.join(www_dir, 'map.html'))

        @self._app.get('/ldm/geojson')
        def ldm_geojson():
            return self._store.geojson()

        @self._app.get('/ldm/state')
        def ldm_state():
            return self._store.snapshot()

        @self._app.websocket('/ws/ldm')
        async def ws_ldm(websocket: WebSocket):
            await self._ws_hub.connect(websocket)
            await websocket.send_json(self._store.snapshot())
            try:
                while True:
                    # Broadcast-only endpoint: read and ignore client payloads to detect disconnect.
                    _ = await websocket.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                await self._ws_hub.disconnect(websocket)

    def _resolve_www_directory(self) -> Optional[str]:
        try:
            share_dir = get_package_share_directory('v2x_apps')
            candidate = os.path.join(share_dir, 'www')
            if os.path.isdir(candidate):
                return candidate
        except PackageNotFoundError:
            pass

        source_candidate = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'www'))
        if os.path.isdir(source_candidate):
            return source_candidate
        return None

    def _start_web_server(self) -> None:
        host = self.get_parameter('web_host').value
        port = int(self.get_parameter('web_port').value)
        log_level = self.get_parameter('web_log_level').value
        config = uvicorn.Config(self._app, host=host, port=port, log_level=log_level)
        self._server = uvicorn.Server(config)
        self._server_thread = threading.Thread(target=self._server.run, daemon=True)
        self._server_thread.start()

    def _broadcast_snapshot(self) -> None:
        self._ws_hub.broadcast_threadsafe(self._store.snapshot())

    def _on_cam(self, msg: CAM) -> None:
        if self._store.update_station_from_cam(msg):
            self._broadcast_snapshot()

    def _on_cpm(self, msg: cpm_msg.CollectivePerceptionMessage) -> None:
        if self._store.update_from_cpm(msg):
            self._broadcast_snapshot()

    def _on_poim_object(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning('Skipping POIM object with invalid JSON payload')
            return

        if self._store.update_poi_from_json(payload):
            self._broadcast_snapshot()

    def _on_cleanup_timer(self) -> None:
        if self._store.prune_stale(_STALE_DATA_SECONDS):
            self._broadcast_snapshot()

    def destroy_node(self) -> bool:
        if self._server is not None:
            self._server.should_exit = True
        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=_SERVER_SHUTDOWN_TIMEOUT_SECONDS)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = LdmServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
