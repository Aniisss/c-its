"""
POIM Listener – Point of Interest Message (Parking Availability)
ETSI TS 103 916 V2.1.1

This ROS 2 node listens for incoming POIM messages delivered by cube-its on
the BTP indication topic, decodes their ASN.1 UPER payload and republishes
the parking availability data on ROS 2 topics so other nodes can consume it.

ROS 2 Topics
-------------
Subscriptions:
  /vanetza/btp_indication              vanetza_msgs/BtpDataIndication

Publications (per received POIM):
  /parking/received/spaces_available   std_msgs/Int32
  /parking/received/spaces_total       std_msgs/Int32
  /parking/received/spaces_occupied    std_msgs/Int32

Parameters:
  btp_port          (int, default 2019)  – BTP-B port to filter on
  asn1_schema_path  (str, default '')    – override path to .asn schema file
"""

import os
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
from vanetza_msgs.msg import BtpDataIndication

try:
    import asn1tools
    _ASN1TOOLS_AVAILABLE = True
except ImportError:
    _ASN1TOOLS_AVAILABLE = False

# BTP-B destination port for POIM (ETSI TS 103 916 V2.1.1 Table 1)
_POIM_BTP_PORT_DEFAULT = 2019

_DEFAULT_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'asn1', 'poim_ts103916.asn'
)


class PoimListener(Node):
    """
    ROS 2 node that receives POIM messages from cube-its via BTP indications,
    decodes their ASN.1 UPER payload, and publishes the parking data on ROS 2.
    """

    def __init__(self):
        super().__init__('poim_listener')
        self.get_logger().info(f'Node "{self.get_name()}" started')

        if not _ASN1TOOLS_AVAILABLE:
            self.get_logger().error(
                'asn1tools is not installed – install it with:  pip install asn1tools'
            )
            raise RuntimeError('asn1tools is required for POIM decoding')

        # ------------------------------------------------------------------ #
        # Parameters                                                           #
        # ------------------------------------------------------------------ #
        self.declare_parameter('btp_port',        _POIM_BTP_PORT_DEFAULT)
        self.declare_parameter('asn1_schema_path', '')

        # ------------------------------------------------------------------ #
        # ASN.1 schema                                                         #
        # ------------------------------------------------------------------ #
        schema_path = self.get_parameter('asn1_schema_path').value or _DEFAULT_SCHEMA_PATH
        try:
            self._db = asn1tools.compile_files(schema_path, codec='uper')
            self.get_logger().info(f'POIM ASN.1 schema loaded from: {schema_path}')
        except Exception as exc:
            self.get_logger().error(f'Failed to load POIM ASN.1 schema: {exc}')
            raise

        # ------------------------------------------------------------------ #
        # Publications                                                         #
        # ------------------------------------------------------------------ #
        self._pub_available = self.create_publisher(
            Int32, '/parking/received/spaces_available', 10)
        self._pub_total = self.create_publisher(
            Int32, '/parking/received/spaces_total', 10)
        self._pub_occupied = self.create_publisher(
            Int32, '/parking/received/spaces_occupied', 10)

        # ------------------------------------------------------------------ #
        # BTP indication subscription                                          #
        # ------------------------------------------------------------------ #
        self.create_subscription(
            BtpDataIndication, '/vanetza/btp_indication',
            self._on_btp_indication, 10)

    def _on_btp_indication(self, msg: BtpDataIndication) -> None:
        """
        Filter incoming BTP indications by the POIM BTP-B port and decode
        the ASN.1 UPER payload.
        """
        btp_port = self.get_parameter('btp_port').value

        if msg.destination_port != btp_port:
            return  # not a POIM packet

        self.get_logger().info(
            f'Received BTP indication on port {msg.destination_port}, '
            f'{len(msg.data)} bytes – attempting POIM decode'
        )

        try:
            poim = self._db.decode('POIM', bytes(msg.data))
        except Exception as exc:
            self.get_logger().warning(f'POIM decoding failed: {exc}')
            return

        self._process_poim(poim)

    def _process_poim(self, poim: dict) -> None:
        """
        Extract parking availability data from the decoded POIM dict and
        publish it on the appropriate ROS 2 topics.
        """
        header = poim.get('header', {})
        station_id = header.get('stationID', 'unknown')

        body = poim.get('poim', {})
        containers = body.get('poiContainers', [])

        for container in containers:
            choice_type, container_data = container   # tuple from asn1tools CHOICE

            if choice_type == 'parkingFacility':
                poi_id    = container_data.get('poiId', -1)
                available = container_data.get('parkingSpacesAvailable', 0)
                total     = container_data.get('parkingSpacesTotal')
                occupied  = container_data.get('parkingSpacesOccupied')

                self.get_logger().info(
                    f'POIM from station {station_id}: '
                    f'poi_id={poi_id}, '
                    f'available={available}'
                    + (f', total={total}' if total is not None else '')
                    + (f', occupied={occupied}' if occupied is not None else '')
                )

                self._pub_available.publish(Int32(data=int(available)))

                if total is not None:
                    self._pub_total.publish(Int32(data=int(total)))

                if occupied is not None:
                    self._pub_occupied.publish(Int32(data=int(occupied)))
            else:
                self.get_logger().info(
                    f'POIM from station {station_id}: '
                    f'unhandled container type "{choice_type}"'
                )


# --------------------------------------------------------------------------- #
# Entry point                                                                   #
# --------------------------------------------------------------------------- #

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
