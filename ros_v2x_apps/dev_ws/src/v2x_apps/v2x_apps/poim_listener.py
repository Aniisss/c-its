#!/usr/bin/env python3

"""
POIM Listener - decodes POIM packets and republishes a compact summary.
"""

import json
import os
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from vanetza_msgs.msg import BtpDataIndication
from ament_index_python.packages import get_package_share_directory

try:
    import asn1tools
    _ASN1TOOLS_AVAILABLE = True
except ImportError:
    _ASN1TOOLS_AVAILABLE = False

_POIM_BTP_PORT_DEFAULT = 2025
_QUEUE_DEPTH = 10

_ASN1_DIR = os.path.join(
    get_package_share_directory('v2x_apps'),
    'asn1'
)

_DEFAULT_SCHEMA_FILES = [
    os.path.join(_ASN1_DIR, 'POIM-PDU-Description.asn'),
    os.path.join(_ASN1_DIR, 'POIM-CommonContainers.asn'),
    os.path.join(_ASN1_DIR, 'POIM-ParkingAvailability.asn'),
    os.path.join(_ASN1_DIR, 'ETSI-ITS-CDD.asn'),
    os.path.join(_ASN1_DIR, 'EfcDataDictionary.asn'),
]


class PoimListener(Node):
    def __init__(self):
        super().__init__('poim_listener')
        self.get_logger().info('Initializing POIM Listener Node')

        if not _ASN1TOOLS_AVAILABLE:
            self.get_logger().error('asn1tools not found. Run: pip3 install asn1tools --break-system-packages')
            raise RuntimeError('Missing dependency: asn1tools')

        self.declare_parameter('btp_port', _POIM_BTP_PORT_DEFAULT)
        self.declare_parameter('output_topic', '/parking/poim_decoded')
        self.declare_parameter('incoming_object_topic', '/parking/poim_incoming')

        try:
            self._db = asn1tools.compile_files(_DEFAULT_SCHEMA_FILES, codec='uper')
            self.get_logger().info(f'Successfully compiled {len(_DEFAULT_SCHEMA_FILES)} ASN.1 schema files.')
        except Exception as exc:
            self.get_logger().error(f'ASN.1 Compilation Error: {exc}')
            raise

        self._decoded_publisher = self.create_publisher(
            String,
            self.get_parameter('output_topic').value,
            _QUEUE_DEPTH,
        )
        self._incoming_object_publisher = self.create_publisher(
            String,
            self.get_parameter('incoming_object_topic').value,
            _QUEUE_DEPTH,
        )

        self.create_subscription(
            BtpDataIndication,
            '/vanetza/btp_indication',
            self._on_btp,
            _QUEUE_DEPTH,
        )

    def _on_btp(self, msg: BtpDataIndication) -> None:
        if msg.destination_port != self.get_parameter('btp_port').value:
            return

        try:
            poim = self._db.decode('POIM', msg.data)
            payload_entries = poim.get('payload', [])
            if not payload_entries:
                self.get_logger().warn('Received POIM with empty payload')
                return

            block_entry = payload_entries[0]
            parking_block = self._db.decode('ParkingAvailabilityBlock', block_entry['poiBlock'])

            management = parking_block['managementContainer']
            place_info = parking_block['placeInfo']
            aggregated_status = parking_block['aggregatedStatus']
            position = place_info['position']
            occupancy = aggregated_status.get('currentOccupancy')

            summary = {
                'destination_port': msg.destination_port,
                'poi_type': block_entry['poiType'],
                'poi_id': management['blockIdentificationNumber'],
                'timestamp': management['timestamp'],
                'latitude': position['latitude'] / 1e7,
                'longitude': position['longitude'] / 1e7,
                'altitude': position.get('altitude', 800001),
                'facility_status': aggregated_status['currentFacilityStatus'],
                'current_occupancy': occupancy,
                'facility_name': place_info['name'],
            }

            out_msg = String()
            out_msg.data = json.dumps(summary, separators=(',', ':'))
            self._decoded_publisher.publish(out_msg)

            incoming_object = {
                'direction': 'incoming',
                'poi_id': management['blockIdentificationNumber'],
                'latitude': position['latitude'],
                'longitude': position['longitude'],
                'occupancy_percent': occupancy,
                'facility_name': place_info['name'],
            }
            incoming_msg = String()
            incoming_msg.data = json.dumps(incoming_object, separators=(',', ':'))
            self._incoming_object_publisher.publish(incoming_msg)

            self.get_logger().info(
                f"Decoded POIM on port {msg.destination_port} and published to {self.get_parameter('output_topic').value}"
            )

        except Exception as exc:
            self.get_logger().error(f'POIM decode failure: {exc}')


def main(args=None):
    rclpy.init(args=args)
    node = PoimListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
