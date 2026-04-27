import rclpy

from typing import Optional
from rclpy.node import Node
from vanetza_msgs.msg import PositionVector, TrafficClass, GeoNetArea
from vanetza_msgs.srv import BtpData

from v2x_apps.poim_pa_codec import POIM_BTP_PORT, encode as _codec_encode


class PoimPaProvider(Node):
    """
    ROS 2 node that periodically broadcasts POIM-PA (Point of Interest Message –
    Parking Availability) messages over the BTP/GeoNetworking layer via cube-its.

    The payload is UPER-encoded according to ETSI TS 103 916 v2.1.1 using the
    ``asn1tools`` library with the bundled ``asn1/POIM-PA-Standalone.asn`` schema
    (see :mod:`v2x_apps.poim_pa_codec` for wire-format details).

    Since cube-its does not yet expose a dedicated POIM facility service this node
    uses the raw Vanetza BTP service (``/vanetza/btp_request``) and targets the
    ETSI-assigned BTP-B port **2009** for POIM messages.

    Subscriptions:
        /its/position_vector  (vanetza_msgs/PositionVector)
            Used to set the vehicle's current position as the GeoNetworking
            destination area centre.

    Services called:
        /vanetza/btp_request  (vanetza_msgs/BtpData)
            Transmits the encoded POIM-PA payload over ITS-G5.

    Parameters (ROS 2 node parameters, set via ``--ros-args -p``):
        block_id         (int,   default 1)           POI block identifier (0-65535).
        facility_name    (str,   default "Parking")   Name of the parking facility (≤31 chars).
        facility_lat     (float, default 48.135)      Facility latitude  (degrees WGS-84).
        facility_lon     (float, default 11.582)      Facility longitude (degrees WGS-84).
        opening_status   (str,   default "open")      "open", "closed", or "unknown".
        total_spaces     (int,   default 100)         Total number of parking spaces.
        free_spaces      (int,   default 42)          Currently free parking spaces.
        publish_period   (float, default 1.0)         Broadcast interval (seconds).
        geo_radius_m     (float, default 1000.0)      GeoNetworking circle radius (m).
    """

    def __init__(self):
        super().__init__("poim_pa_provider")
        self.get_logger().info(f'Node "{self.get_name()}" started')

        self.declare_parameter("block_id", 1)
        self.declare_parameter("facility_name", "Parking")
        self.declare_parameter("facility_lat", 48.135)
        self.declare_parameter("facility_lon", 11.582)
        self.declare_parameter("opening_status", "open")
        self.declare_parameter("total_spaces", 100)
        self.declare_parameter("free_spaces", 42)
        self.declare_parameter("publish_period", 1.0)
        self.declare_parameter("geo_radius_m", 1000.0)

        self.position_vector: Optional[PositionVector] = None
        self.create_subscription(
            PositionVector, "/its/position_vector", self._position_update, 1
        )

        self.btp_client = self.create_client(BtpData, "/vanetza/btp_request")
        while not self.btp_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for /vanetza/btp_request service …")

        period = self.get_parameter("publish_period").get_parameter_value().double_value
        self.create_timer(timer_period_sec=period, callback=self._publish)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _position_update(self, msg: PositionVector) -> None:
        self.position_vector = msg

    def _publish(self) -> None:
        if self.position_vector is None:
            self.get_logger().warn("No position vector yet – skipping POIM-PA broadcast")
            return
        try:
            payload = self._encode_poim_pa()
            future = self._send_btp(payload)
            future.add_done_callback(self._on_btp_response)
        except Exception as exc:
            self.get_logger().error(f"POIM-PA encoding/transmission failed: {exc}")

    def _on_btp_response(self, future: rclpy.task.Future) -> None:
        response = future.result()
        if response.confirm == BtpData.Response.CONFIRM_ACCEPTED:
            self.get_logger().info("POIM-PA broadcast accepted by BTP service")
        else:
            self.get_logger().warning(
                f"POIM-PA broadcast rejected (confirm={response.confirm})"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _p_int(self, name: str) -> int:
        return self.get_parameter(name).get_parameter_value().integer_value

    def _p_float(self, name: str) -> float:
        return self.get_parameter(name).get_parameter_value().double_value

    def _p_str(self, name: str) -> str:
        return self.get_parameter(name).get_parameter_value().string_value

    def _encode_poim_pa(self) -> bytes:
        total = self._p_int("total_spaces")
        free = self._p_int("free_spaces")
        rate = round((total - free) / total * 100) if total > 0 else 0
        return _codec_encode(
            facility_lat=self._p_float("facility_lat"),
            facility_lon=self._p_float("facility_lon"),
            facility_name=self._p_str("facility_name"),
            block_id=self._p_int("block_id"),
            opening_status=self._p_str("opening_status"),
            total_spaces=total,
            free_spaces=free,
            occupancy_rate=rate,
        )

    def _send_btp(self, payload: bytes) -> rclpy.task.Future:
        pv = self.position_vector
        geo_radius = self._p_float("geo_radius_m")

        request = BtpData.Request()
        request.btp_type = BtpData.Request.BTP_TYPE_NON_INTERACTIVE
        request.transport_type = BtpData.Request.TRANSPORT_TYPE_GBC
        request.destination_port = POIM_BTP_PORT
        request.traffic_class.id = TrafficClass.TC_OTHER
        request.data = payload

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
