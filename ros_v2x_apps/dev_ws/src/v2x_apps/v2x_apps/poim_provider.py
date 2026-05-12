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

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, String
from vanetza_msgs.srv import BtpData
from ament_index_python.packages import get_package_share_directory

try:
    import asn1tools
    _ASN1TOOLS_AVAILABLE = True
except ImportError:
    _ASN1TOOLS_AVAILABLE = False

# =============================================================================
# SECTION 1 – STATIC FACILITY DATA
# -----------------------------------------------------------------------------
# Everything here is hardcoded for testing.  When real data is available,
# replace each constant with a read from the appropriate source (database,
# config file, ROS parameter, REST API, …) and nothing else needs to change.
# =============================================================================

FACILITY_NAME        = 'Central Station Underground Parking'
FACILITY_LAT_DEG     =  50.8366          # WGS-84 latitude  (decimal degrees)
FACILITY_LON_DEG     =   4.3360          # WGS-84 longitude (decimal degrees)
FACILITY_PARKING_TYPE = 'Underground'    # e.g. 'Underground', 'Surface', 'Multi-storey'
FACILITY_TOTAL_SPOTS =  320              # Total number of parking spaces
FACILITY_AMENITIES   = [                 # List of available amenities
    'Electric Charging',
    'Handicap Access',
    'CCTV',
    '24h Security',
]

# =============================================================================
# SECTION 2 – SIMULATION PARAMETERS
# -----------------------------------------------------------------------------
# Controls the synthetic occupancy curve used when no real-time subscription
# data arrives on /parking/spaces_available or /parking/spaces_occupied.
# Occupancy follows a sinusoid:  base_pct ± amplitude_pct  over one cycle.
# Replace _simulate_occupied_spots() with a real sensor read when ready.
# =============================================================================

SIM_CYCLE_SECONDS      = 300.0   # Duration of one full occupancy cycle (seconds)
SIM_BASE_OCCUPANCY_PCT =  55.0   # Mid-point of the simulated occupancy (%)
SIM_AMPLITUDE_PCT      =  25.0   # Peak deviation from the mid-point (%)

# =============================================================================
# (end of data / configuration sections)
# =============================================================================


# ---------------------------------------------------------------------------
# Internal protocol constants – do not change unless the ETSI spec changes.
# ---------------------------------------------------------------------------
_POIM_BTP_PORT_DEFAULT     = 2025
_POIM_MESSAGE_ID_DEFAULT   = 26
_POIM_PROTOCOL_VERSION_DEF = 2

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
        self.declare_parameter('btp_port',             _POIM_BTP_PORT_DEFAULT)
        self.declare_parameter('message_id',           _POIM_MESSAGE_ID_DEFAULT)
        self.declare_parameter('protocol_version',     _POIM_PROTOCOL_VERSION_DEF)
        self.declare_parameter('poi_id',               1)
        self.declare_parameter('publish_rate_hz',      1.0)
        self.declare_parameter('transport_type',       'SHB')
        self.declare_parameter('outgoing_object_topic', '/parking/poim_outgoing')

        # --- Load ASN.1 Ruleset ---
        try:
            self._db = asn1tools.compile_files(_DEFAULT_SCHEMA_FILES, codec='uper')
            self.get_logger().info(f'Successfully compiled {len(_DEFAULT_SCHEMA_FILES)} ASN.1 schema files.')
        except Exception as exc:
            self.get_logger().error(f'ASN.1 Compilation Error: {exc}')
            raise

        # --- Internal Data State ---
        self._spaces_available: int = 0
        self._spaces_occupied:  int = 0
        self._subscription_data_received: bool = False

        # --- Subscriptions ---
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

    # --- Subscription Callbacks ---
    def _on_avail(self, msg):
        self._spaces_available = msg.data
        self._subscription_data_received = True

    def _on_occ(self, msg):
        self._spaces_occupied = msg.data
        self._subscription_data_received = True

    # --- Simulation Helper (Section 2) ---
    def _simulate_occupied_spots(self, total: int) -> int:
        """Return a synthetic occupied-spot count using the Section 2 parameters."""
        phase = (time.time() % SIM_CYCLE_SECONDS) / SIM_CYCLE_SECONDS
        occupancy_pct = SIM_BASE_OCCUPANCY_PCT + SIM_AMPLITUDE_PCT * math.sin(2.0 * math.pi * phase)
        return max(0, min(total, int(round(occupancy_pct * total / 100.0))))

    # --- Main Publish Loop ---
    def _on_timer(self):
        # ── 1. Resolve position ───────────────────────────────────────────────
        # POIM uses static facility coordinates (Section 1), not vehicle GPS.
        lat_deg = FACILITY_LAT_DEG
        lon_deg = FACILITY_LON_DEG

        try:
            # ── 2. Resolve occupancy ──────────────────────────────────────────
            # Real data from ROS subscriptions takes priority.
            # If nothing has arrived yet, use the sinusoidal simulator defined
            # in Section 2.
            total_spots = FACILITY_TOTAL_SPOTS   # ← Section 1

            if self._subscription_data_received:
                occupied = max(0, min(total_spots, self._spaces_occupied or 0))
            else:
                occupied = self._simulate_occupied_spots(total_spots)   # ← Section 2

            available     = max(0, total_spots - occupied)
            occupancy_pct = int(round((occupied / max(1, total_spots)) * 100.0))

            # ── 3. Derive status label ────────────────────────────────────────
            if occupancy_pct >= 100:
                facility_status = 'Full'
            elif occupancy_pct >= 90:
                facility_status = 'Almost Full'
            else:
                facility_status = 'Open'

            # ── 4. Encode timestamps and coordinates ──────────────────────────
            now_ms    = int(time.time() * 1000)
            timestamp = (now_ms - 1072915200000) % 4294967296
            lat_e7    = int(round(lat_deg * 1e7))
            lon_e7    = int(round(lon_deg * 1e7))

            # ── 5. Build ASN.1 parking block ──────────────────────────────────
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
                    'name': FACILITY_NAME,         # ← Section 1
                },
                'aggregatedStatus': {
                    'currentFacilityStatus': 1,
                },
            }

            # ── 6. Build and publish rich JSON summary ────────────────────────
            outgoing_summary = {
                'direction': 'outgoing',
                'poiId': self.get_parameter('poi_id').value,
                'name': FACILITY_NAME,  # ← Section 1
                'latitude': lat_e7,
                'longitude': lon_e7,
                'totalNumberOfParkingSpaces': total_spots,  # ← Section 1
                'availableParkingSpaces': available,
                'occupiedParkingSpaces': occupied,
                'occupancyRate': occupancy_pct,
                'parkingFacilityType': FACILITY_PARKING_TYPE,  # ← Section 1
                'currentFacilityStatus': facility_status,
                'amenities': FACILITY_AMENITIES,  # ← Section 1
            }
            summary_msg = String()
            summary_msg.data = json.dumps(outgoing_summary, separators=(',', ':'))
            self._poim_object_publisher.publish(summary_msg)

            # ── 7. ASN.1 encode and BTP broadcast ────────────────────────────
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
