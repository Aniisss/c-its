import math
import rclpy
from rclpy.node import Node
from typing import Optional

# Messages
import etsi_its_cpm_ts_msgs.msg as cpm_msg
from vanetza_msgs.msg import PositionVector
from visualization_msgs.msg import MarkerArray

class CpmValue:
    """ Represents a CPM value with scaling and range checking. """
    def __init__(self, value, scale=1.0, unavailable=math.nan):
        self.value = value
        self.scaling_factor = scale
        self.min_value = -math.inf
        self.max_value = math.inf
        self.out_of_range_value = unavailable
        self.unavailable_value = unavailable

    def range(self, min, max, out_of_range=None):
        self.min_value = min
        self.max_value = max
        if out_of_range is not None:
            self.out_of_range_value = out_of_range

    def get(self) -> int:
        if math.isfinite(self.value):
            value = round(self.value * self.scaling_factor)
            if value < self.min_value or value > self.max_value:
                return int(self.out_of_range_value)
            else:
                return int(value)
        else:
            return int(self.unavailable_value)

# --- Scaled Value Helper Classes ---
class CpmLatitudeValue(CpmValue):
    def __init__(self, value):
        super().__init__(value, 1e7, cpm_msg.Latitude.UNAVAILABLE)
        self.range(cpm_msg.Latitude.MIN, cpm_msg.Latitude.MAX)

class CpmLongitudeValue(CpmValue):
    def __init__(self, value):
        super().__init__(value, 1e7, cpm_msg.Longitude.UNAVAILABLE)
        self.range(cpm_msg.Longitude.MIN, cpm_msg.Longitude.MAX)

class CpmSemiAxisLengthValue(CpmValue):
    def __init__(self, value):
        super().__init__(value, 1e2, cpm_msg.SemiAxisLength.UNAVAILABLE)
        self.range(cpm_msg.SemiAxisLength.MIN, cpm_msg.SemiAxisLength.MAX, cpm_msg.SemiAxisLength.OUT_OF_RANGE)

class CpmAltitudeValue(CpmValue):
    def __init__(self, value):
        super().__init__(value, 1e2, cpm_msg.AltitudeValue.UNAVAILABLE)
        self.range(cpm_msg.AltitudeValue.MIN, cpm_msg.AltitudeValue.MAX)


class CpmProvider(Node):
    def __init__(self):
        super().__init__('cpm_provider')
        self.get_logger().info(f'Node "{self.get_name()}" started')

        # 1. Own Position Subscription
        self.position_vector: Optional[PositionVector] = None
        self.pos_vector_subscription = self.create_subscription(
            PositionVector, '/its/position_vector', self.position_update, 1)

        # 2. Lidar Detection Subscription
        self.latest_marker_array: Optional[MarkerArray] = None
        self.marker_subscription = self.create_subscription(
            MarkerArray, '/perception/detected_objects_markers', self.marker_callback, 10)

        # 3. CPM Publisher
        self.cpm_publisher = self.create_publisher(
            cpm_msg.CollectivePerceptionMessage, '/its/cpm_provided', 1)

        # Timer for 1Hz publication
        self.create_timer(timer_period_sec=1.0, callback=self.publish)

    def position_update(self, msg: PositionVector) -> None:
        self.position_vector = msg

    def marker_callback(self, msg: MarkerArray) -> None:
        """Store the latest detected objects from Lidar"""
        if msg.markers:
            self.latest_marker_array = msg

    def get_reference_position(self) -> cpm_msg.ReferencePosition:
        if self.position_vector is None:
            raise RuntimeError('No position vector available')

        pos = cpm_msg.ReferencePosition()
        pos.latitude.value = CpmLatitudeValue(self.position_vector.latitude).get()
        pos.longitude.value = CpmLongitudeValue(self.position_vector.longitude).get()
        pos.position_confidence_ellipse.semi_major_confidence.value = CpmSemiAxisLengthValue(self.position_vector.semi_major_confidence).get()
        pos.position_confidence_ellipse.semi_minor_confidence.value = CpmSemiAxisLengthValue(self.position_vector.semi_minor_confidence).get()
        pos.altitude.altitude_value.value = CpmAltitudeValue(self.position_vector.altitude).get()
        pos.altitude.altitude_confidence.value = cpm_msg.AltitudeConfidence.UNAVAILABLE
        return pos

    def generate_perceived_object_cpm(self) -> cpm_msg.CollectivePerceptionMessage:
        """Generate CPM. Uses Lidar data if available, else uses Hardcoded Defaults."""
        
        # --- Default Values (Used if Lidar is quiet) ---
        obj_x, obj_y, obj_z = 8.0, -5.0, 0.0 # Meters
        dim_x, dim_y, dim_z = 3.0, 2.0, 1.0  # Meters
        
        # --- Override with Lidar Data if available ---
        if self.latest_marker_array and self.latest_marker_array.markers:
            m = self.latest_marker_array.markers[0]
            obj_x, obj_y, obj_z = m.pose.position.x, m.pose.position.y, m.pose.position.z
            dim_x, dim_y, dim_z = m.scale.x, m.scale.y, m.scale.z
            self.get_logger().info(f'CPM using REAL LIDAR data: x={obj_x:.2f}')
        else:
            self.get_logger().warn('No Lidar markers received yet - using hardcoded defaults')

        # Mapping to ETSI CPM structure
        perceived_object = cpm_msg.PerceivedObject()
        perceived_object.measurement_delta_time.value = 1
        
        # Position (ETSI uses cm or dm depending on version, here using your scale logic)
        # Note: 1 unit in your original code = 0.01m (800 = 8m)
        perceived_object.position.x_coordinate.value.value = int(obj_x * 100)
        perceived_object.position.x_coordinate.confidence.value = 1
        perceived_object.position.y_coordinate.value.value = int(obj_y * 100)
        perceived_object.position.y_coordinate.confidence.value = 1
        
        perceived_object.position.z_coordinate_is_present = True
        perceived_object.position.z_coordinate.value.value = round(obj_z * 100)
        perceived_object.position.z_coordinate.confidence.value = 1

        # Dimensions
        perceived_object.object_dimension_z_is_present = True
        perceived_object.object_dimension_z.value.value = int(dim_z * 10)
        perceived_object.object_dimension_z.confidence.value = 1
        
        perceived_object.object_dimension_y_is_present = True
        perceived_object.object_dimension_y.value.value = int(dim_y * 10)
        perceived_object.object_dimension_y.confidence.value = 1
        
        perceived_object.object_dimension_x_is_present = True
        perceived_object.object_dimension_x.value.value = int(dim_x * 10)
        perceived_object.object_dimension_x.confidence.value = 1

        # Container Assembly
        container = cpm_msg.WrappedCpmContainer()
        container.container_id.value = cpm_msg.WrappedCpmContainer.CHOICE_CONTAINER_DATA_PERCEIVED_OBJECT_CONTAINER
        container.container_data_perceived_object_container = cpm_msg.PerceivedObjectContainer()
        container.container_data_perceived_object_container.number_of_perceived_objects.value = 1
        container.container_data_perceived_object_container.perceived_objects.array = [perceived_object]

        cpm = cpm_msg.CollectivePerceptionMessage()
        cpm.payload.management_container.reference_position = self.get_reference_position()
        cpm.payload.cpm_containers.value.array = [container]
        return cpm

    def publish(self) -> None:
        if self.position_vector:
            try:
                cpm = self.generate_perceived_object_cpm()
                self.cpm_publisher.publish(cpm)
            except Exception as e:
                self.get_logger().error(f'Failed to publish CPM: {str(e)}')


def main(args=None):
    rclpy.init(args=args)
    node = CpmProvider()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()