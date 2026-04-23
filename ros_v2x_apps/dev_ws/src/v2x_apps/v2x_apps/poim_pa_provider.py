import math
import struct
import rclpy

from typing import Optional
from rclpy.node import Node
from vanetza_msgs.msg import PositionVector, TrafficClass, GeoNetArea
from vanetza_msgs.srv import BtpData

# BTP-B destination port assigned to POIM by ETSI TS 102 636-5-1
POIM_BTP_PORT = 2009

# ETSI TS 102 894-2: message ID 6 is reserved for POIM
POIM_MESSAGE_ID = 6
POIM_PROTOCOL_VERSION = 1

# POI type for parking facilities (ETSI TS 101 556-1)
POI_TYPE_PARKING_FACILITY = 1

# Latitude/longitude scaling factor: 1e-7 degrees per unit (ETSI ITS standard)
LAT_LON_SCALE = 1e7

# Altitude scaling factor: 0.01 m per unit
ALTITUDE_SCALE = 1e2


class PoimPaEncoder:
    """
    Encodes a POIM-PA (Point of Interest Message – Parking Availability) payload
    using a compact binary representation compatible with ETSI TS 101 556-1.

    The encoding follows the ASN.1 structure defined in ETSI TS 101 556-1 V1.1.1.
    Fields are packed in network byte order (big-endian) using fixed-size integers
    consistent with the UPER-equivalent ranges used across the ETSI ITS message set.

    ITS PDU Header (ETSI TS 102 894-2):
        protocolVersion : UINT8
        messageID       : UINT8   (6 = POIM)
        stationID       : UINT32

    Reference Position (ETSI EN 302 637-2):
        latitude        : INT32   (1e-7 degrees,  900000001 = unavailable)
        longitude       : INT32   (1e-7 degrees, 1800000001 = unavailable)
        semiMajorConf   : UINT16  (0.01 m,  4094 = out-of-range, 4095 = unavailable)
        semiMinorConf   : UINT16  (0.01 m,  4094 = out-of-range, 4095 = unavailable)
        altitudeValue   : INT32   (0.01 m,  800001 = unavailable)
        altitudeConf    : UINT8   (14 = unavailable)

    POI fields (ETSI TS 101 556-1):
        poiType         : UINT8
        poiId           : UINT16
        totalCapacity   : UINT16  (0–65534, 65535 = unknown)
        availableSpaces : UINT16  (0–65534, 65535 = unknown)
        occupancyType   : UINT8   (0=shortStay, 1=longStay, 2=disabled, 3=evCharging,
                                   0xFF = unavailable)
        facilityLat     : INT32   (1e-7 degrees, position of the parking facility)
        facilityLon     : INT32   (1e-7 degrees, position of the parking facility)
    """

    # struct format: big-endian
    # Header:          B  B  I            ->  6 bytes
    # RefPosition:     i  i  H  H  i  B  -> 17 bytes
    # POI fields:      B  H  H  H  B  i  i  -> 16 bytes
    # Total: 39 bytes
    _PACK_FMT = ">BBIiiHHiBBHHHBii"

    @staticmethod
    def _clamp(value: int, min_val: int, max_val: int, unavailable: int) -> int:
        if value < min_val or value > max_val:
            return unavailable
        return value

    @classmethod
    def encode(
        cls,
        station_id: int,
        ref_lat: float,
        ref_lon: float,
        ref_alt: float,
        semi_major_conf: float,
        semi_minor_conf: float,
        poi_id: int,
        poi_type: int,
        total_capacity: int,
        available_spaces: int,
        occupancy_type: int,
        facility_lat: float,
        facility_lon: float,
    ) -> bytes:
        """Encode a POIM-PA message into a byte buffer.

        Args:
            station_id:       ITS station identifier (uint32).
            ref_lat:          Vehicle reference latitude in degrees (WGS-84).
            ref_lon:          Vehicle reference longitude in degrees (WGS-84).
            ref_alt:          Vehicle reference altitude in metres.
            semi_major_conf:  Semi-major axis length of position ellipse in metres.
            semi_minor_conf:  Semi-minor axis length of position ellipse in metres.
            poi_id:           Unique parking facility identifier (0–65535).
            poi_type:         POI type code (1 = parkingFacility).
            total_capacity:   Total number of parking spaces (0–65534; 65535 = unknown).
            available_spaces: Currently available parking spaces (0–65534; 65535 = unknown).
            occupancy_type:   Occupancy type code (0=shortStay, 1=longStay, 2=disabled,
                              3=evCharging; 0xFF = unavailable).
            facility_lat:     Parking facility latitude in degrees (WGS-84).
            facility_lon:     Parking facility longitude in degrees (WGS-84).

        Returns:
            Encoded POIM-PA payload as bytes.
        """
        # --- ITS PDU Header ---
        protocol_version = POIM_PROTOCOL_VERSION
        message_id = POIM_MESSAGE_ID
        sid = station_id & 0xFFFFFFFF

        # --- Reference Position ---
        def _lat(deg: float) -> int:
            if math.isfinite(deg):
                return cls._clamp(round(deg * LAT_LON_SCALE), -900000000, 900000000, 900000001)
            return 900000001

        def _lon(deg: float) -> int:
            if math.isfinite(deg):
                return cls._clamp(round(deg * LAT_LON_SCALE), -1800000000, 1800000000, 1800000001)
            return 1800000001

        def _alt(m: float) -> int:
            if math.isfinite(m):
                return cls._clamp(round(m * ALTITUDE_SCALE), -100000, 800000, 800001)
            return 800001

        def _semi(m: float) -> int:
            if math.isfinite(m):
                return cls._clamp(round(m * ALTITUDE_SCALE), 0, 4093, 4094)
            return 4095

        ref_lat_i = _lat(ref_lat)
        ref_lon_i = _lon(ref_lon)
        ref_alt_i = _alt(ref_alt)
        semi_maj = _semi(semi_major_conf)
        semi_min = _semi(semi_minor_conf)
        alt_conf = 14  # unavailable

        # --- POI Attributes ---
        total_cap = cls._clamp(total_capacity, 0, 65534, 65535)
        avail = cls._clamp(available_spaces, 0, 65534, 65535)
        occ_type = occupancy_type & 0xFF
        fac_lat_i = _lat(facility_lat)
        fac_lon_i = _lon(facility_lon)
        poi_id_u = poi_id & 0xFFFF
        poi_type_u = poi_type & 0xFF

        return struct.pack(
            cls._PACK_FMT,
            protocol_version,  # B
            message_id,        # B
            sid,               # I
            ref_lat_i,         # i
            ref_lon_i,         # i
            semi_maj,          # H
            semi_min,          # H
            ref_alt_i,         # i
            alt_conf,          # B
            poi_type_u,        # B
            poi_id_u,          # H
            total_cap,         # H
            avail,             # H
            occ_type,          # B
            fac_lat_i,         # i
            fac_lon_i,         # i
        )

    @classmethod
    def decode(cls, data: bytes) -> dict:
        """Decode a POIM-PA byte buffer produced by :meth:`encode`.

        Returns a dictionary with human-readable field values or raises
        ``struct.error`` if the buffer is too short.
        """
        fields = struct.unpack(cls._PACK_FMT, data)
        (
            protocol_version,
            message_id,
            station_id,
            ref_lat_raw,
            ref_lon_raw,
            semi_major_raw,
            semi_minor_raw,
            ref_alt_raw,
            alt_conf_raw,
            poi_type,
            poi_id,
            total_capacity,
            available_spaces,
            occupancy_type,
            facility_lat_raw,
            facility_lon_raw,
        ) = fields

        occupancy_names = {0: "shortStay", 1: "longStay", 2: "disabled", 3: "evCharging"}

        return {
            "protocol_version": protocol_version,
            "message_id": message_id,
            "station_id": station_id,
            "ref_latitude_deg": ref_lat_raw / LAT_LON_SCALE if ref_lat_raw != 900000001 else None,
            "ref_longitude_deg": ref_lon_raw / LAT_LON_SCALE if ref_lon_raw != 1800000001 else None,
            "ref_altitude_m": ref_alt_raw / ALTITUDE_SCALE if ref_alt_raw != 800001 else None,
            "semi_major_conf_m": semi_major_raw / ALTITUDE_SCALE if semi_major_raw != 4095 else None,
            "semi_minor_conf_m": semi_minor_raw / ALTITUDE_SCALE if semi_minor_raw != 4095 else None,
            "poi_type": poi_type,
            "poi_id": poi_id,
            "total_capacity": total_capacity if total_capacity != 65535 else None,
            "available_spaces": available_spaces if available_spaces != 65535 else None,
            "occupancy_type": occupancy_names.get(occupancy_type, "unavailable"),
            "facility_latitude_deg": facility_lat_raw / LAT_LON_SCALE if facility_lat_raw != 900000001 else None,
            "facility_longitude_deg": facility_lon_raw / LAT_LON_SCALE if facility_lon_raw != 1800000001 else None,
        }


class PoimPaProvider(Node):
    """
    ROS 2 node that periodically broadcasts POIM-PA (Point of Interest Message –
    Parking Availability) messages over the BTP/GeoNetworking layer via cube-its.

    Since cube-its does not yet expose a dedicated POIM facility service, this node
    uses the raw Vanetza BTP service (``/vanetza/btp_request``) and targets the
    ETSI-assigned BTP-B port **2009** for POIM messages.

    Subscriptions:
        /its/position_vector  (vanetza_msgs/PositionVector)
            Used to set the vehicle's current position as the GeoNetworking
            destination area centre.

    Services called:
        /vanetza/btp_request  (vanetza_msgs/BtpData)
            Transmits the encoded POIM-PA payload over ITS-G5.

    Parameters (ROS 2 node parameters, set via --ros-args -p):
        poi_id           (int,   default 1)      Unique parking facility ID.
        total_capacity   (int,   default 100)    Total parking spaces.
        available_spaces (int,   default 42)     Currently free spaces.
        occupancy_type   (int,   default 0)      0=shortStay, 1=longStay,
                                                  2=disabled, 3=evCharging.
        facility_lat     (float, default 48.135) Facility latitude  (degrees).
        facility_lon     (float, default 11.582) Facility longitude (degrees).
        publish_period   (float, default 1.0)    Broadcast interval (seconds).
        geo_radius_m     (float, default 1000.0) GeoNetworking circle radius (m).
    """

    def __init__(self):
        super().__init__("poim_pa_provider")
        self.get_logger().info(f'Node "{self.get_name()}" started')

        # Declare ROS 2 parameters so operators can override them at runtime.
        self.declare_parameter("poi_id", 1)
        self.declare_parameter("total_capacity", 100)
        self.declare_parameter("available_spaces", 42)
        self.declare_parameter("occupancy_type", 0)
        self.declare_parameter("facility_lat", 48.135)
        self.declare_parameter("facility_lon", 11.582)
        self.declare_parameter("publish_period", 1.0)
        self.declare_parameter("geo_radius_m", 1000.0)

        # Subscribe to the vehicle position so we can set a meaningful destination area.
        self.position_vector: Optional[PositionVector] = None
        self.create_subscription(
            PositionVector, "/its/position_vector", self._position_update, 1
        )

        # BTP service client – cube-its exposes this for raw BTP transmission.
        self.btp_client = self.create_client(BtpData, "/vanetza/btp_request")
        while not self.btp_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for /vanetza/btp_request service …")

        period = self.get_parameter("publish_period").get_parameter_value().double_value
        self.create_timer(timer_period_sec=period, callback=self._publish)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _position_update(self, msg: PositionVector) -> None:
        """Cache the latest position vector."""
        self.position_vector = msg

    def _publish(self) -> None:
        """Encode and transmit a POIM-PA message via BTP."""
        if self.position_vector is None:
            self.get_logger().warn("No position vector yet – skipping POIM-PA broadcast")
            return
        try:
            payload = self._encode_poim_pa()
            future = self._send_btp(payload)
            future.add_done_callback(self._on_btp_response)
        except Exception as exc:
            self.get_logger().error(f"POIM-PA transmission failed: {exc}")

    def _on_btp_response(self, future: rclpy.task.Future) -> None:
        """Log BTP service response."""
        response = future.result()
        if response.confirm == BtpData.Response.CONFIRM_ACCEPTED:
            self.get_logger().info("POIM-PA broadcast accepted by BTP service")
        else:
            self.get_logger().warn(
                f"POIM-PA broadcast rejected (confirm={response.confirm})"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _encode_poim_pa(self) -> bytes:
        """Build and encode the POIM-PA payload using current parameter values."""
        pv = self.position_vector
        return PoimPaEncoder.encode(
            station_id=0,  # cube-its fills in the own station ID at the BTP layer
            ref_lat=pv.latitude,
            ref_lon=pv.longitude,
            ref_alt=pv.altitude,
            semi_major_conf=pv.semi_major_confidence,
            semi_minor_conf=pv.semi_minor_confidence,
            poi_id=self.get_parameter("poi_id").get_parameter_value().integer_value,
            poi_type=POI_TYPE_PARKING_FACILITY,
            total_capacity=self.get_parameter("total_capacity").get_parameter_value().integer_value,
            available_spaces=self.get_parameter("available_spaces").get_parameter_value().integer_value,
            occupancy_type=self.get_parameter("occupancy_type").get_parameter_value().integer_value,
            facility_lat=self.get_parameter("facility_lat").get_parameter_value().double_value,
            facility_lon=self.get_parameter("facility_lon").get_parameter_value().double_value,
        )

    def _send_btp(self, payload: bytes) -> rclpy.task.Future:
        """Submit a BTP transmission request for the given payload."""
        pv = self.position_vector
        geo_radius = (
            self.get_parameter("geo_radius_m").get_parameter_value().double_value
        )

        request = BtpData.Request()
        # BTP-B (non-interactive) with single-hop broadcast (SHB) as transport.
        # Switch to GBC if you need geographical broadcast to a specific area.
        request.btp_type = BtpData.Request.BTP_TYPE_NON_INTERACTIVE
        request.transport_type = BtpData.Request.TRANSPORT_TYPE_GBC
        request.destination_port = POIM_BTP_PORT
        request.traffic_class.id = TrafficClass.TC_OTHER
        request.data = payload

        # Destination area: circle centred on the current vehicle position.
        request.destination_area.type = GeoNetArea.TYPE_CIRCLE
        request.destination_area.latitude = pv.latitude
        request.destination_area.longitude = pv.longitude
        request.destination_area.distance_a = geo_radius

        return self.btp_client.call_async(request)


def main(args=None):
    rclpy.init(args=args)
    node = PoimPaProvider()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
