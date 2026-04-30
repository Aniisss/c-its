"""
POIM Provider – Point of Interest Message (Parking Availability)
ETSI TS 103 916 V2.1.1

This ROS 2 node implements the POIM facility layer for the cube-its platform.
Because cube-its does not yet offer a native POIM facility (unlike its CPM
or VAM facilities), this node performs the complete encode-and-send cycle:

  1. Reads the station's own position from  /its/position_vector
  2. Reads real-time parking availability from  /parking/spaces_available
  3. Assembles a POIM message that conforms to ETSI TS 103 916 V2.1.1
  4. Encodes the message with ASN.1 UPER via the ``asn1tools`` library,
     loading the schema from the  asn1/poim_ts103916.asn  file that is
     bundled with this package
  5. Transmits the encoded payload via the cube-its BTP service
     (/vanetza/btp_request) on the BTP-B destination port defined by the
     standard

All protocol-level constants (BTP port, message ID, protocol version) are
exposed as ROS 2 parameters so that no value is hardcoded and adjustments
can be made without touching the source.

ROS 2 Topics / Services
------------------------
Subscriptions:
  /its/position_vector          vanetza_msgs/PositionVector
  /parking/spaces_available     std_msgs/Int32
  /parking/spaces_total         std_msgs/Int32   (optional, sets total capacity)
  /parking/spaces_occupied      std_msgs/Int32   (optional, sets occupied count)

Services (client):
  /vanetza/btp_request          vanetza_msgs/BtpData

Parameters (all configurable at launch):
  btp_port            (int,   default 2019)  – BTP-B destination port for POIM
  message_id          (int,   default 26)    – ItsPduHeader.messageID
  protocol_version    (int,   default 2)     – ItsPduHeader.protocolVersion
  poi_id              (int,   default 1)     – PoiId of this parking facility
  parking_total       (int,   default 0)     – static total capacity (0 = omit)
  validity_duration   (int,   default 600)   – seconds, 0 = omit field
  publish_rate_hz     (float, default 1.0)   – POIM generation frequency
  transport_type      (str,   default 'SHB') – 'SHB' or 'GBC'
  asn1_schema_path    (str,   default '')    – override path to .asn schema
"""

import math
import os
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
from vanetza_msgs.msg import PositionVector, TrafficClass
from vanetza_msgs.srv import BtpData

try:
    import asn1tools
    _ASN1TOOLS_AVAILABLE = True
except ImportError:
    _ASN1TOOLS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Standard-defined defaults (configurable via ROS parameters)
# Source: ETSI TS 103 916 V2.1.1 Table 1 (Communication Profile)
#         ETSI TS 102 894-2     (Common Data Dictionary)
# ---------------------------------------------------------------------------
_POIM_BTP_PORT_DEFAULT       = 2019   # BTP-B destination port for POIM
_POIM_MESSAGE_ID_DEFAULT     = 26     # ItsPduHeader.messageID for POIM
_POIM_PROTOCOL_VERSION_DEF   = 2      # ItsPduHeader.protocolVersion

# Path to the bundled ASN.1 schema (resolved relative to this file)
_DEFAULT_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'asn1', 'poim_ts103916.asn'
)

# Coordinate unavailable / out-of-range sentinels (ETSI TS 102 894-2)
_LAT_UNAVAILABLE  = 900000001
_LON_UNAVAILABLE  = 1800000001
_ALT_UNAVAILABLE  = 800001
_SEMI_UNAVAILABLE = 4094   # Unavailable per ETSI TS 102 894-2; 4095 = OutOfRange


class PoimProvider(Node):
    """
    ROS 2 node that builds and transmits ETSI TS 103 916 POIM messages
    via the cube-its BTP service.
    """

    def __init__(self):
        super().__init__('poim_provider')
        self.get_logger().info(f'Node "{self.get_name()}" started')

        if not _ASN1TOOLS_AVAILABLE:
            self.get_logger().error(
                'asn1tools is not installed. '
                'Install it with:  pip install asn1tools'
            )
            raise RuntimeError('asn1tools is required for POIM encoding')

        # ------------------------------------------------------------------ #
        # ROS 2 parameters – all protocol values are exposed here so nothing  #
        # is hardcoded                                                         #
        # ------------------------------------------------------------------ #
        self.declare_parameter('btp_port',         _POIM_BTP_PORT_DEFAULT)
        self.declare_parameter('message_id',        _POIM_MESSAGE_ID_DEFAULT)
        self.declare_parameter('protocol_version',  _POIM_PROTOCOL_VERSION_DEF)
        self.declare_parameter('poi_id',            1)
        self.declare_parameter('parking_total',     0)      # 0 → field omitted
        self.declare_parameter('validity_duration', 600)    # seconds
        self.declare_parameter('publish_rate_hz',   1.0)
        self.declare_parameter('transport_type',    'SHB')
        self.declare_parameter('asn1_schema_path',  '')

        # ------------------------------------------------------------------ #
        # Load ASN.1 schema                                                   #
        # ------------------------------------------------------------------ #
        schema_path = self.get_parameter('asn1_schema_path').value or _DEFAULT_SCHEMA_PATH
        try:
            self._db = asn1tools.compile_files(schema_path, codec='uper')
            self.get_logger().info(f'POIM ASN.1 schema loaded from: {schema_path}')
        except Exception as exc:
            self.get_logger().error(f'Failed to load POIM ASN.1 schema: {exc}')
            raise

        # ------------------------------------------------------------------ #
        # Internal state                                                       #
        # ------------------------------------------------------------------ #
        self._position_vector: Optional[PositionVector] = None
        self._spaces_available: Optional[int]           = None
        self._spaces_total:     Optional[int]           = None
        self._spaces_occupied:  Optional[int]           = None

        # ------------------------------------------------------------------ #
        # Subscriptions                                                        #
        # ------------------------------------------------------------------ #
        self.create_subscription(
            PositionVector, '/its/position_vector',
            self._on_position_vector, 1)

        self.create_subscription(
            Int32, '/parking/spaces_available',
            self._on_spaces_available, 10)

        self.create_subscription(
            Int32, '/parking/spaces_total',
            self._on_spaces_total, 10)

        self.create_subscription(
            Int32, '/parking/spaces_occupied',
            self._on_spaces_occupied, 10)

        # ------------------------------------------------------------------ #
        # BTP service client                                                   #
        # ------------------------------------------------------------------ #
        self._btp_client = self.create_client(BtpData, '/vanetza/btp_request')
        if not self._btp_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().warning(
                'BTP request service not yet available – will retry on each publish cycle'
            )

        # ------------------------------------------------------------------ #
        # Periodic publish timer                                               #
        # ------------------------------------------------------------------ #
        rate = float(self.get_parameter('publish_rate_hz').value)
        self.create_timer(1.0 / rate, self._on_timer)

    # ---------------------------------------------------------------------- #
    # Subscription callbacks                                                   #
    # ---------------------------------------------------------------------- #

    def _on_position_vector(self, msg: PositionVector) -> None:
        self._position_vector = msg

    def _on_spaces_available(self, msg: Int32) -> None:
        self._spaces_available = msg.data

    def _on_spaces_total(self, msg: Int32) -> None:
        self._spaces_total = msg.data

    def _on_spaces_occupied(self, msg: Int32) -> None:
        self._spaces_occupied = msg.data

    # ---------------------------------------------------------------------- #
    # Message construction                                                     #
    # ---------------------------------------------------------------------- #

    def _encode_reference_position(self) -> dict:
        """
        Convert the latest PositionVector into the ReferencePosition dict
        expected by the ASN.1 schema.

        Scaling per ETSI TS 102 894-2:
          Latitude  : ×10^7  (1/10 micro-degree steps)
          Longitude : ×10^7
          SemiAxis  : ×10^2  (centimetre steps)
          Altitude  : ×10^2  (centimetre steps)
        """
        pv = self._position_vector

        # Latitude
        if math.isfinite(pv.latitude):
            lat = int(round(pv.latitude * 1e7))
            lat = max(-900000000, min(900000000, lat))
        else:
            lat = _LAT_UNAVAILABLE

        # Longitude
        if math.isfinite(pv.longitude):
            lon = int(round(pv.longitude * 1e7))
            lon = max(-1800000000, min(1800000000, lon))
        else:
            lon = _LON_UNAVAILABLE

        # Confidence ellipse semi-axes
        if math.isfinite(pv.semi_major_confidence):
            semi_major = int(round(pv.semi_major_confidence * 1e2))
            semi_major = max(0, min(4093, semi_major))
        else:
            semi_major = _SEMI_UNAVAILABLE

        if math.isfinite(pv.semi_minor_confidence):
            semi_minor = int(round(pv.semi_minor_confidence * 1e2))
            semi_minor = max(0, min(4093, semi_minor))
        else:
            semi_minor = _SEMI_UNAVAILABLE

        # Altitude
        if math.isfinite(pv.altitude):
            alt_val = int(round(pv.altitude * 1e2))
            alt_val = max(-100000, min(800000, alt_val))
        else:
            alt_val = _ALT_UNAVAILABLE

        return {
            'latitude':  lat,
            'longitude': lon,
            'positionConfidenceEllipse': {
                'semiMajorConfidence':  semi_major,
                'semiMinorConfidence':  semi_minor,
                'semiMajorOrientation': 3601,     # unavailable
            },
            'altitude': {
                'altitudeValue':      alt_val,
                'altitudeConfidence': 'unavailable',  # AltitudeConfidence enum
            },
        }

    def _build_parking_facility_container(self) -> dict:
        """
        Assemble the ParkingFacilityContainer dict from current state and
        ROS parameters. OPTIONAL fields are included only when a meaningful
        value is available.
        """
        poi_id            = self.get_parameter('poi_id').value
        parking_total_cfg = self.get_parameter('parking_total').value
        validity_duration = self.get_parameter('validity_duration').value

        spaces_available = self._spaces_available if self._spaces_available is not None else 0
        spaces_available = max(0, min(65535, spaces_available))

        container: dict = {
            'poiId':                   poi_id,
            'referencePosition':       self._encode_reference_position(),
            'parkingSpacesAvailable':  spaces_available,
        }

        # parkingSpacesTotal: prefer live topic value, fall back to parameter
        total = self._spaces_total if self._spaces_total is not None else parking_total_cfg
        if total and total > 0:
            container['parkingSpacesTotal'] = max(0, min(65535, total))

        # parkingSpacesOccupied: only if a subscriber has provided the value
        if self._spaces_occupied is not None:
            container['parkingSpacesOccupied'] = max(0, min(65535, self._spaces_occupied))

        # validityDuration: include if positive
        if validity_duration and validity_duration > 0:
            container['validityDuration'] = max(0, min(86400, validity_duration))

        return container

    def _build_and_encode_poim(self) -> bytes:
        """
        Build the full POIM structure and encode it with ASN.1 UPER.

        Returns the raw encoded bytes ready to be passed as BTP payload.
        """
        protocol_version = self.get_parameter('protocol_version').value
        message_id       = self.get_parameter('message_id').value

        # generationDeltaTime: milliseconds since 2004-01-01 modulo 65 536
        epoch_2004_ms  = 1072915200000   # 2004-01-01T00:00:00Z in ms since Unix epoch
        now_ms         = int(time.time() * 1000)
        gen_delta_time = (now_ms - epoch_2004_ms) % 65536

        poim_data = {
            'header': {
                'protocolVersion': protocol_version,
                'messageID':       message_id,
                'stationID':       0,   # cube-its fills the real station ID on transmission
            },
            'poim': {
                'generationDeltaTime': gen_delta_time,
                'poiContainers': [
                    ('parkingFacility', self._build_parking_facility_container()),
                ],
            },
        }

        encoded: bytes = self._db.encode('POIM', poim_data)
        return encoded

    # ---------------------------------------------------------------------- #
    # BTP transmission                                                         #
    # ---------------------------------------------------------------------- #

    def _send_via_btp(self, payload: bytes) -> None:
        """
        Forward the encoded POIM payload to cube-its via the BTP service.

        The BTP-B destination port and transport type are read from ROS
        parameters so they can be overridden without modifying the source.
        """
        if not self._btp_client.service_is_ready():
            self.get_logger().warning(
                'BTP request service not ready – skipping this publish cycle',
                throttle_duration_sec=10.0,
            )
            return

        btp_port       = self.get_parameter('btp_port').value
        transport_str  = self.get_parameter('transport_type').value.upper()

        request = BtpData.Request()
        request.btp_type = BtpData.Request.BTP_TYPE_NON_INTERACTIVE  # BTP-B

        if transport_str == 'GBC':
            request.transport_type = BtpData.Request.TRANSPORT_TYPE_GBC
        else:
            request.transport_type = BtpData.Request.TRANSPORT_TYPE_SHB

        request.destination_port      = btp_port
        request.traffic_class.id      = TrafficClass.TC_OTHER
        request.data                  = bytes(payload)

        future = self._btp_client.call_async(request)
        future.add_done_callback(self._on_btp_response)

    def _on_btp_response(self, future) -> None:
        response = future.result()
        if response.confirm == BtpData.Response.CONFIRM_ACCEPTED:
            self.get_logger().debug('POIM BTP request accepted')
        else:
            self.get_logger().warning(
                f'POIM BTP request rejected (confirm={response.confirm})'
            )

    # ---------------------------------------------------------------------- #
    # Timer callback                                                           #
    # ---------------------------------------------------------------------- #

    def _on_timer(self) -> None:
        if self._position_vector is None:
            self.get_logger().warning(
                'Waiting for /its/position_vector …',
                throttle_duration_sec=10.0,
            )
            return

        if self._spaces_available is None:
            self.get_logger().info(
                'No /parking/spaces_available received yet – using 0',
                throttle_duration_sec=30.0,
            )

        try:
            payload = self._build_and_encode_poim()
            self._send_via_btp(payload)
            self.get_logger().info(
                f'POIM sent: poi_id={self.get_parameter("poi_id").value}, '
                f'available={self._spaces_available or 0}, '
                f'payload={len(payload)} bytes, '
                f'btp_port={self.get_parameter("btp_port").value}'
            )
        except Exception as exc:
            self.get_logger().error(f'Failed to build/send POIM: {exc}')


# --------------------------------------------------------------------------- #
# Entry point                                                                   #
# --------------------------------------------------------------------------- #

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
