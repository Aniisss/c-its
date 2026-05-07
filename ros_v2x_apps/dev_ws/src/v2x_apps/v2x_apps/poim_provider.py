#!/usr/bin/env python3

"""
POIM Provider – Point of Interest Message (Parking Availability)
ETSI TS 103 916 V2.1.1 (C-ITS Hybridization Project)

Description:
This node implements the Facility Layer for POIM. It bridges the gap between 
local ROS 2 perception/sensor data and the standardized V2X communication stack.

Implementation Details:
  1. Loads a multi-file ASN.1 schema (PDU, Common, and Parking Availability).
  2. Subscribes to local vehicle/infrastructure topics.
  3. Performs Semantic Scaling (ETSI CDD TS 102 894-2).
  4. Encodes to binary UPER (Un-aligned Packed Encoding Rules).
  5. Transmits via the Cube BTP Service (Port 2019).
"""

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

# ---------------------------------------------------------------------------
# ETSI Standard Defaults (TS 103 916 & TS 102 894-2)
# ---------------------------------------------------------------------------
_POIM_BTP_PORT_DEFAULT       = 2025   # BTP-B destination port for POIM
_POIM_MESSAGE_ID_DEFAULT     = 26     # ItsPduHeader.messageID for POIM
_POIM_PROTOCOL_VERSION_DEF   = 2      # ItsPduHeader.protocolVersion

# ---------------------------------------------------------------------------
# Multi-File Schema Definition
# ---------------------------------------------------------------------------
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
        self.get_logger().info(f'Initializing POIM Facility Node for C-ITS Hybridization')

        if not _ASN1TOOLS_AVAILABLE:
            self.get_logger().error('asn1tools not found. Run: pip3 install asn1tools --break-system-packages')
            raise RuntimeError('Missing dependency: asn1tools')

        # --- ROS 2 Parameters ---
        self.declare_parameter('btp_port',         _POIM_BTP_PORT_DEFAULT)
        self.declare_parameter('message_id',        _POIM_MESSAGE_ID_DEFAULT)
        self.declare_parameter('protocol_version',  _POIM_PROTOCOL_VERSION_DEF)
        self.declare_parameter('poi_id',            1)
        self.declare_parameter('parking_total',     100)    # Capacity
        self.declare_parameter('publish_rate_hz',   1.0)    # 1 message per second
        self.declare_parameter('transport_type',    'SHB')  # Single Hop Broadcast
        self.declare_parameter('outgoing_object_topic', '/parking/poim_outgoing')

        # --- Load ASN.1 Ruleset (Multiple Files) ---
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

        # --- Subscriptions (Input) ---
        self.create_subscription(PositionVector, '/its/position_vector', self._on_pos, 1)
        self.create_subscription(Int32, '/parking/spaces_available', self._on_avail, 10)
        self.create_subscription(Int32, '/parking/spaces_occupied', self._on_occ, 10)

        # --- BTP Service (Output) ---
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
    def _on_pos(self, msg): self._position_vector = msg
    def _on_avail(self, msg): self._spaces_available = msg.data
    def _on_occ(self, msg): self._spaces_occupied = msg.data

    def _calculate_occupancy_percent(self) -> int:
        parking_total = int(self.get_parameter('parking_total').value)
        if parking_total <= 0:
            return 0
        occupancy_percent = int(round((self._spaces_occupied / parking_total) * 100.0))
        return max(0, min(100, occupancy_percent))

    def _on_timer(self):
        """Main Facility Layer Logic: Build -> Encode -> Send"""
        if self._position_vector is None:
            self.get_logger().warn("Waiting for GPS/Position fix...", throttle_duration_sec=5)
            return

        try:
            now_ms = int(time.time() * 1000)
            timestamp = (now_ms - 1072915200000) % 4294967296  # ITS Epoch 2004 (32-bit)

            pv = self._position_vector
            occupancy_percent = self._calculate_occupancy_percent()

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
                        'latitude': int(round(pv.latitude * 1e7)),
                        'longitude': int(round(pv.longitude * 1e7)),
                        'altitude': 800001,
                    },
                    'name': 'Parking',
                },
                'aggregatedStatus': {
                    'currentFacilityStatus': 1,
                    'currentOccupancy': occupancy_percent,
                },
            }

            outgoing_summary = {
                'direction': 'outgoing',
                'poi_id': self.get_parameter('poi_id').value,
                'latitude': int(round(pv.latitude * 1e7)),
                'longitude': int(round(pv.longitude * 1e7)),
                'occupancy_percent': occupancy_percent,
                'facility_name': parking_block['placeInfo']['name'],
            }
            summary_msg = String()
            summary_msg.data = json.dumps(outgoing_summary, separators=(',', ':'), sort_keys=True)
            self._poim_object_publisher.publish(summary_msg)

            parking_block_bytes = self._db.encode('ParkingAvailabilityBlock', parking_block)

            poim_data = {
                'header': {
                    'protocolVersion': 2,
                    'messageId': 26,
                    'stationId': 0,
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
            self.get_logger().error(f"Encoding Failure: {e}")

    def _send_btp(self, payload: bytes):
        if not self._btp_client.service_is_ready():
            return

        req = BtpData.Request()
        req.btp_type = BtpData.Request.BTP_TYPE_NON_INTERACTIVE # BTP-B
        req.destination_port = self.get_parameter('btp_port').value
        req.data = payload
        
        transport = self.get_parameter('transport_type').value.upper()
        req.transport_type = BtpData.Request.TRANSPORT_TYPE_GBC if transport == 'GBC' else BtpData.Request.TRANSPORT_TYPE_SHB
        
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
