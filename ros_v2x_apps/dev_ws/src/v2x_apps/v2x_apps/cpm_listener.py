import rclpy

from rclpy.node import Node
import etsi_its_cpm_ts_msgs.msg as cpm_msg


class CpmListener(Node):
    def __init__(self):
        super().__init__('cpm_listener')
        self.get_logger().info(f'Node "{self.get_name()}" started')
        self.subscription = self.create_subscription(
            cpm_msg.CollectivePerceptionMessage,
            '/its/cpm_received',
            self.listener_callback,
            10,
        )

    @staticmethod
    def _deg_from_1e7(value: int) -> float:
        return value / 1e7

    @staticmethod
    def _meters_from_cm(value: int) -> float:
        return value / 100.0

    @staticmethod
    def _meters_from_dm(value: int) -> float:
        return value / 10.0

    def listener_callback(self, msg: cpm_msg.CollectivePerceptionMessage) -> None:
        try:
            station_id = msg.header.station_id.value
            ref_pos = msg.payload.management_container.reference_position
            ref_lat = self._deg_from_1e7(ref_pos.latitude.value)
            ref_lon = self._deg_from_1e7(ref_pos.longitude.value)

            containers = msg.payload.cpm_containers.value.array
            object_count = 0
            object_logs = []

            for container in containers:
                if not hasattr(container, 'container_data_perceived_object_container'):
                    continue

                perceived_container = container.container_data_perceived_object_container
                perceived_objects = perceived_container.perceived_objects.array

                for obj in perceived_objects:
                    object_count += 1
                    obj_x = self._meters_from_cm(obj.position.x_coordinate.value.value)
                    obj_y = self._meters_from_cm(obj.position.y_coordinate.value.value)

                    z_text = 'n/a'
                    if obj.position.z_coordinate_is_present:
                        z_text = f'{self._meters_from_cm(obj.position.z_coordinate.value.value):.2f}m'

                    dim_x_text = 'n/a'
                    if obj.object_dimension_x_is_present:
                        dim_x_text = f'{self._meters_from_dm(obj.object_dimension_x.value.value):.2f}m'

                    dim_y_text = 'n/a'
                    if obj.object_dimension_y_is_present:
                        dim_y_text = f'{self._meters_from_dm(obj.object_dimension_y.value.value):.2f}m'

                    dim_z_text = 'n/a'
                    if obj.object_dimension_z_is_present:
                        dim_z_text = f'{self._meters_from_dm(obj.object_dimension_z.value.value):.2f}m'

                    object_logs.append(
                        f'obj#{object_count}: pos=({obj_x:.2f},{obj_y:.2f},{z_text}) '
                        f'dim=({dim_x_text},{dim_y_text},{dim_z_text})'
                    )

            base_log = (
                f'Received CPM from station_id={station_id} '
                f'ref=({ref_lat:.7f},{ref_lon:.7f}) perceived_objects={object_count}'
            )

            if object_logs:
                self.get_logger().info(base_log + ' | ' + ' | '.join(object_logs))
            else:
                self.get_logger().info(base_log)

        except Exception as exc:
            self.get_logger().error(f'Failed to parse incoming CPM: {exc}')


def main(args=None):
    rclpy.init(args=args)
    node = CpmListener()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()