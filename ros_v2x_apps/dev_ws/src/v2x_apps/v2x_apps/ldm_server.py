#!/usr/bin/env python3

import json
import math
import os
import threading
from typing import Any, Dict, Optional

import rclpy
from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from rclpy.node import Node
from std_msgs.msg import String
from vanetza_msgs.msg import PositionVector
import uvicorn


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


class LdmServer(Node):
    def __init__(self) -> None:
        super().__init__('ldm_server')
        self._lock = threading.Lock()
        self._vehicle: Dict[str, Any] = {}
        self._parking_pois: Dict[str, Dict[str, Any]] = {}

        self.declare_parameter('web_host', '0.0.0.0')
        self.declare_parameter('web_port', 8000)
        self.declare_parameter('vehicle_id', 'DS7')
        self.declare_parameter('poim_outgoing_topic', '/parking/poim_outgoing')
        self.declare_parameter('poim_incoming_topic', '/parking/poim_incoming')
        self.declare_parameter('poim_decoded_topic', '/parking/poim_decoded')

        self.create_subscription(PositionVector, '/its/position_vector', self._on_position_vector, 10)
        self.create_subscription(String, self.get_parameter('poim_outgoing_topic').value, self._on_poim_object, 10)
        self.create_subscription(String, self.get_parameter('poim_incoming_topic').value, self._on_poim_object, 10)
        self.create_subscription(String, self.get_parameter('poim_decoded_topic').value, self._on_poim_object, 10)

        self._app = FastAPI(title='LDM Server', version='1.0')
        self._configure_routes()
        self._server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self._start_web_server()
        self.get_logger().info(
            f"LDM Server ready at http://{self.get_parameter('web_host').value}:{int(self.get_parameter('web_port').value)}/"
        )

    def _configure_routes(self) -> None:
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
            return self._build_geojson()

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
        config = uvicorn.Config(self._app, host=host, port=port, log_level='warning')
        self._server = uvicorn.Server(config)
        self._server_thread = threading.Thread(target=self._server.run, daemon=True)
        self._server_thread.start()

    def _on_position_vector(self, msg: PositionVector) -> None:
        heading = _to_float_or_none(getattr(msg, 'heading', None))
        speed = _to_float_or_none(getattr(msg, 'speed', None))
        with self._lock:
            self._vehicle = {
                'id': self.get_parameter('vehicle_id').value,
                'latitude': _scaled_coord_to_decimal(getattr(msg, 'latitude', None)),
                'longitude': _scaled_coord_to_decimal(getattr(msg, 'longitude', None)),
                'heading': heading,
                'speed': speed,
            }

    def _on_poim_object(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning('Skipping POIM object with invalid JSON payload')
            return

        poi_id = payload.get('poi_id') or payload.get('id') or payload.get('poiId')
        if poi_id is None:
            return

        lat = _scaled_coord_to_decimal(_to_float_or_none(payload.get('latitude')))
        lon = _scaled_coord_to_decimal(_to_float_or_none(payload.get('longitude')))
        if lat is None or lon is None:
            return

        occupancy = _to_float_or_none(payload.get('occupancy_percent'))
        if occupancy is None:
            occupancy = _to_float_or_none(payload.get('current_occupancy'))
        if occupancy is None:
            occupancy = 0.0
        occupancy = max(0.0, min(100.0, occupancy))

        key = str(poi_id)
        with self._lock:
            self._parking_pois[key] = {
                'id': key,
                'name': payload.get('facility_name') or 'Parking',
                'latitude': lat,
                'longitude': lon,
                'occupancy_percent': occupancy,
            }

    def _build_geojson(self) -> Dict[str, Any]:
        with self._lock:
            vehicle = dict(self._vehicle)
            pois = [dict(p) for p in self._parking_pois.values()]

        features = []
        if vehicle.get('latitude') is not None and vehicle.get('longitude') is not None:
            properties = {
                'type': 'vehicle',
                'id': vehicle.get('id', self.get_parameter('vehicle_id').value),
                'heading': vehicle.get('heading'),
                'speed': vehicle.get('speed'),
            }
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [vehicle['longitude'], vehicle['latitude']],
                },
                'properties': properties,
            })

        for poi in pois:
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

    def destroy_node(self) -> bool:
        if self._server is not None:
            self._server.should_exit = True
        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=3.0)
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
