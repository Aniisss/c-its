import rclpy

from rclpy.node import Node
from vanetza_msgs.msg import BtpDataIndication

from v2x_apps.poim_pa_provider import PoimPaEncoder, POIM_BTP_PORT


class PoimPaListener(Node):
    """
    ROS 2 node that listens for incoming POIM-PA (Point of Interest Message –
    Parking Availability) messages on BTP port **2009** and logs their contents.

    cube-its forwards every received BTP packet to the ``/vanetza/btp_indication``
    topic as a :class:`vanetza_msgs.msg.BtpDataIndication`.  This node filters for
    the ETSI-assigned POIM port and decodes payloads produced by
    :class:`v2x_apps.poim_pa_provider.PoimPaProvider` (or any compatible sender).

    Subscriptions:
        /vanetza/btp_indication  (vanetza_msgs/BtpDataIndication)
            Raw BTP packets received by cube-its over ITS-G5.
    """

    def __init__(self):
        super().__init__("poim_pa_listener")
        self.get_logger().info(f'Node "{self.get_name()}" started')

        self.create_subscription(
            BtpDataIndication,
            "/vanetza/btp_indication",
            self._on_btp_indication,
            10,
        )
        self.get_logger().info(
            f"Listening for POIM-PA messages on BTP port {POIM_BTP_PORT} …"
        )

    def _on_btp_indication(self, msg: BtpDataIndication) -> None:
        """Handle an incoming BTP packet; ignore anything not on the POIM port."""
        if msg.destination_port != POIM_BTP_PORT:
            return

        raw = bytes(msg.data)
        try:
            info = PoimPaEncoder.decode(raw)
        except Exception as exc:
            self.get_logger().warning(
                f"Received {len(raw)}-byte POIM-PA packet that could not be decoded: {exc}"
            )
            return

        avail = info["available_spaces"]
        total = info["total_capacity"]
        fac_lat = info["facility_latitude_deg"]
        fac_lon = info["facility_longitude_deg"]
        occ = info["occupancy_type"]
        poi_id = info["poi_id"]
        station = info["station_id"]

        avail_str = str(avail) if avail is not None else "unknown"
        total_str = str(total) if total is not None else "unknown"
        pos_str = (
            f"({fac_lat:.6f}, {fac_lon:.6f})"
            if fac_lat is not None and fac_lon is not None
            else "unavailable"
        )

        self.get_logger().info(
            f"POIM-PA received from station {station} | "
            f"POI-ID={poi_id} | "
            f"Available={avail_str}/{total_str} spaces | "
            f"Occupancy={occ} | "
            f"Position={pos_str}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = PoimPaListener()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
