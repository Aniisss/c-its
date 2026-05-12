#!/usr/bin/env python3

"""
POIM Provider – Point of Interest Message (Parking Availability)
ETSI TS 103 916 V2.1.1 (C-ITS Hybridization Project)
...
"""

import math
import os
import time
import json
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, String
from vanetza_msgs.msg import PositionVector
from vanetza_msgs.srv import BtpData
from ament_index_python.packages import get_package_share_directory

try:
    import asn1tools
    _ASN1TOOLS_AVAILABLE = True
except ImportError:
    _ASN1TOOLS_AVAILABLE = False

_POIM_BTP_PORT_DEFAULT       = 2025
_POIM_MESSAGE_ID_DEFAULT     = 26
_POIM_PROTOCOL_VERSION_DEF   = 2

# ── Static facility descriptor (ASN.1 / ETSI TS 103 916 inspired) ─────────────
_FACILITY = {
    'facility_name': 'Central Station Underground Parking',
    'parking_type':  'Underground',
    'total_spots':   320,
    'amenities':     ['Electric Charging', 'Handicap Access', 'CCTV', '24h Security'],
    'floors':        3,
    'max_height_cm': 210,
}

# Fallback coordinates used when no GPS position vector has been received yet.
# Defaults to Brussels Central Station area.
_FALLBACK_LAT_DEG =  50.8366
_FALLBACK_LON_DEG =   4.3360

_ASN1_DIR = os.path.join(
    get_package_share_directory('v2x_apps'),
    'asn1'
)

_DEFAULT_SCHEMA_FILES = [
    os.path.join(_ASN1_DIR, 'POIM-PDU-Description.asn'),
    os.path.join(_ASN1_DIR, 'POIM-CommonContainers.asn'),
    os.path.join(_ASN1_DIR, 'POIM-ParkingAvailability.asn'),
    os.path.join(_ASN1_DIR, 'ETSI-ITS-CDD.asn'),
    os.path.join(_ASN1_DIR, 'EfcDataDictionary.asn')
]


class PoimProvider(Node):

    def __init__(self):
        super().__init__('poim_provider')
        self.get_logger().info('Initializing POIM Facility Node for C-ITS Hybridization')

        if not _ASN1TOOLS_AVAILABLE:
            self.get_logger().error('asn1tools not found. Run: pip3 install asn1tools --break-system-packages')
            raise RuntimeError('Missing dependency: asn1tools')

        # --- ROS 2 Parameters ---
        self.declare_parameter('btp_port',              _POIM_BTP_PORT_DEFAULT)
        self.declare_parameter('message_id',             _POIM_MESSAGE_ID_DEFAULT)
        self.declare_parameter('protocol_version',       _POIM_PROTOCOL_VERSION_DEF)
        self.declare_parameter('poi_id',                 1)
        self.declare_parameter('parking_total',          _FACILITY['total_spots'])
        self.declare_parameter('publish_rate_hz',        1.0)
        self.declare_parameter('transport_type',         'SHB')
        self.declare_parameter('outgoing_object_topic',  '/parking/poim_outgoing')  # ← added param

        # --- Load ASN.1 Ruleset ---
        try:
            self._db = asn1tools.compile_files(_DEFAULT_SCHEMA_FILES, codec='uper')
            self.get_logger().info(f'Successfully compiled {len(_DEFAULT_SCHEMA_FILES)} ASN.1 schema files.')
        except Exception as exc:
            self.get_logger().error(f'ASN.1 Compilation Error: {exc}')
            raise

        # --- Internal Data State ---
        self._position_vector: Optional[PositionVector] = None
        self._spaces_available: int = 0
        self._spaces_occupied:  int = 0
        self._subscription_data_received: bool = False

        # --- Subscriptions ---
        self.create_subscription(PositionVector, '/its/position_vector', self._on_pos, 1)
        self.create_subscription(Int32, '/parking/spaces_available', self._on_avail, 10)
        self.create_subscription(Int32, '/parking/spaces_occupied',  self._on_occ,   10)

        # --- BTP Service + JSON Publisher ---
        self._btp_client = self.create_client(BtpData, '/vanetza/btp_request')
        self._poim_object_publisher = self.create_publisher(
            String,
            self.get_parameter('outgoing_object_topic').value,
            10,
        )

        # --- Timer Loop ---
        rate = self.get_parameter('publish_rate_hz').value
        self.timer = self.create_timer(1.0 / rate, self._on_timer)

    # --- Callbacks ---
    def _on_pos(self, msg):
        self._position_vector = msg

    def _on_avail(self, msg):
        self._spaces_available = msg.data
        self._subscription_data_received = True

    def _on_occ(self, msg):
        self._spaces_occupied = msg.data
        self._subscription_data_received = True

    def _simulate_occupied_spots(self, total: int) -> int:
        """Simulate a realistic time-varying occupancy with a 5-minute sinusoidal cycle."""
        phase = (time.time() % 300.0) / 300.0
        occupancy_pct = 55.0 + 25.0 * math.sin(2.0 * math.pi * phase)
        return max(0, min(total, int(round(occupancy_pct * total / 100.0))))

    def _calculate_occupancy_percent(self) -> int:
        parking_total = int(self.get_parameter('parking_total').value)
        if parking_total <= 0:
            return 0
        occupied = self._spaces_occupied or 0
        occupancy_percent = int(round((float(occupied) / parking_total) * 100.0))
        return max(0, min(100, occupancy_percent))

    def _on_timer(self):
        # Use GPS position if available; fall back to static coordinates so the
        # facility is always visible even before a GPS fix is acquired.
        if self._position_vector is not None:
            lat_deg = self._position_vector.latitude
            lon_deg = self._position_vector.longitude
        else:
            self.get_logger().warn(
                'No GPS fix – broadcasting POIM with static fallback position.',
                throttle_duration_sec=10,
            )
            lat_deg = _FALLBACK_LAT_DEG
            lon_deg = _FALLBACK_LON_DEG

        try:
            parking_total = int(self.get_parameter('parking_total').value)

            # Determine current occupancy from subscriptions or simulation.
            if self._subscription_data_received:
                occupied = max(0, min(parking_total, self._spaces_occupied or 0))
            else:
                occupied = self._simulate_occupied_spots(parking_total)

            available     = max(0, parking_total - occupied)
            occupancy_pct = int(round((occupied / max(1, parking_total)) * 100.0))

            # Derive human-readable facility status.
            if occupancy_pct >= 100:
                facility_status = 'Full'
            elif occupancy_pct >= 90:
                facility_status = 'Almost Full'
            else:
                facility_status = 'Open'

            now_ms    = int(time.time() * 1000)
            timestamp = (now_ms - 1072915200000) % 4294967296
            lat_e7    = int(round(lat_deg * 1e7))
            lon_e7    = int(round(lon_deg * 1e7))

            # ── ASN.1 parking block (structure unchanged) ─────────────────────
            parking_block = {
                'managementContainer': {
                    'serviceProviderId': {
                        'countryCode': (b'\x00\x00', 10),
                        'providerIdentifier': 0,
                    },
                    'blockIdentificationNumber': self.get_parameter('poi_id').value,
                    'timestamp': timestamp,
                },
                'placeInfo': {
                    'position': {
                        'latitude':  lat_e7,
                        'longitude': lon_e7,
                        'altitude':  800001,
                    },
                    'name': _FACILITY['facility_name'],
                },
                'aggregatedStatus': {
                    'currentFacilityStatus': 1,
                },
            }

            # ── Rich JSON summary published to the ROS outgoing topic ─────────
            outgoing_summary = {
                'direction':         'outgoing',
                'poi_id':            self.get_parameter('poi_id').value,
                'facility_name':     _FACILITY['facility_name'],
                'latitude':          lat_e7,
                'longitude':         lon_e7,
                'total_spots':       parking_total,
                'available_spots':   available,
                'occupancy_percent': occupancy_pct,
                'parking_type':      _FACILITY['parking_type'],
                'status':            facility_status,
                'amenities':         _FACILITY['amenities'],
            }
            summary_msg = String()
            summary_msg.data = json.dumps(outgoing_summary, separators=(',', ':'))
            self._poim_object_publisher.publish(summary_msg)

            # ── ASN.1 encode & BTP broadcast ──────────────────────────────────
            parking_block_bytes = self._db.encode('ParkingAvailabilityBlock', parking_block)
            poim_data = {
                'header': {
                    'protocolVersion': 2,
                    'messageId':       26,
                    'stationId':       0,
                },
                'payload': [
                    {
                        'poiType': 1,
                        'poiBlock': parking_block_bytes,
                    }
                ],
            }
            payload = self._db.encode('POIM', poim_data)
            self._send_btp(payload)

        except Exception as e:
            self.get_logger().error(f'Encoding Failure: {e}')

    def _send_btp(self, payload: bytes):
        if not self._btp_client.service_is_ready():
            return

        req = BtpData.Request()
        req.btp_type         = BtpData.Request.BTP_TYPE_NON_INTERACTIVE
        req.destination_port = self.get_parameter('btp_port').value
        req.data             = payload

        transport = self.get_parameter('transport_type').value.upper()
        req.transport_type = (
            BtpData.Request.TRANSPORT_TYPE_GBC if transport == 'GBC'
            else BtpData.Request.TRANSPORT_TYPE_SHB
        )

        self._btp_client.call_async(req)
        self.get_logger().info(f"Broadcasted POIM: {len(payload)} bytes to BTP Port {req.destination_port}")


def main(args=None):
    rclpy.init(args=args)
    node = PoimProvider()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()