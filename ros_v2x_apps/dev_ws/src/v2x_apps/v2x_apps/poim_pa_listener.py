import rclpy

from rclpy.node import Node
from vanetza_msgs.msg import BtpDataIndication

from v2x_apps.poim_pa_codec import POIM_BTP_PORT, decode as _codec_decode


class PoimPaListener(Node):
    """
    ROS 2 node that listens for incoming POIM-PA (Point of Interest Message –
    Parking Availability) messages on BTP port **2009** and logs their contents.

    cube-its forwards every received BTP packet to the ``/vanetza/btp_indication``
    topic as a :class:`vanetza_msgs.msg.BtpDataIndication`.  This node filters for
    the ETSI-assigned POIM port and decodes payloads using the ``asn1tools`` UPER
    codec via :func:`v2x_apps.poim_pa_codec.decode`.

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
        if msg.destination_port != POIM_BTP_PORT:
            return

        raw = bytes(msg.data)
        try:
            info = _codec_decode(raw)
        except Exception as exc:
            self.get_logger().warning(
                f"Received {len(raw)}-byte POIM-PA packet that could not be decoded: {exc}"
            )
            return

        free = info["free_spaces"]
        total = info["total_spaces"]
        fac_lat = info["facility_latitude_deg"]
        fac_lon = info["facility_longitude_deg"]
        name = info["facility_name"]
        status = info["opening_status"]
        rate = info["occupancy_rate"]
        station = info["station_id"]
        block_id = info["block_id"]

        free_str = str(free) if free is not None else "unknown"
        total_str = str(total) if total is not None else "unknown"
        pos_str = (
            f"({fac_lat:.6f}, {fac_lon:.6f})"
            if fac_lat is not None and fac_lon is not None
            else "unavailable"
        )
        rate_str = f"{rate}%" if rate is not None else "unknown"

        self.get_logger().info(
            f"POIM-PA from station {station} | "
            f"Block-ID={block_id} | "
            f'"{name}" | '
            f"Status={status} | "
            f"Free={free_str}/{total_str} spaces | "
            f"Occupancy={rate_str} | "
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

