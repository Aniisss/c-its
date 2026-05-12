import math
import rclpy
import numpy as np
import etsi_its_cpm_ts_msgs.msg as cpm_msg

from typing import Optional
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from vanetza_msgs.msg import PositionVector

# --- Helper Classes (Scaling/Range) from your working provider ---
class CpmValue:
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

class CpmLatitudeValue(CpmValue):
    def __init__(self, value):
        super().__init__(value, 1e7, cpm_msg.Latitude.UNAVAILABLE)
        self.range(cpm_msg.Latitude.MIN, cpm_msg.Latitude.MAX)

class CpmLongitudeValue(CpmValue):
    def __init__(self, value):
        super().__init__(value, 1e7, cpm_msg.Longitude.UNAVAILABLE)
        self.range(cpm_msg.Longitude.MIN, cpm_msg.Longitude.MAX)

# --- Main Bridge Node ---
class LidarToCpmBridge(Node):
    def __init__(self):
        super().__init__('lidar_to_cpm_bridge')
        
        self.position_vector: Optional[PositionVector] = None
        self.pos_sub = self.create_subscription(
            PositionVector, '/its/position_vector', self.position_update, 1)

        # ADAPTED: Subscriber changed back to PointCloud2
        self.lidar_sub = self.create_subscription(
            PointCloud2, 
            '/perception/lidar_object_detection/points_detected', 
            self.lidar_callback, 
            10)
            
        self.cpm_pub = self.create_publisher(
            cpm_msg.CollectivePerceptionMessage, '/its/cpm_provided', 1)

        self.get_logger().info('Lidar-to-CPM Bridge (PointCloud2) Started')

    def position_update(self, msg: PositionVector):
        self.position_vector = msg

    def get_reference_position(self) -> cpm_msg.ReferencePosition:
        if self.position_vector is None:
            raise RuntimeError('No position vector available')
        pos = cpm_msg.ReferencePosition()
        pos.latitude.value = CpmLatitudeValue(self.position_vector.latitude).get()
        pos.longitude.value = CpmLongitudeValue(self.position_vector.longitude).get()
        pos.position_confidence_ellipse.semi_major_confidence.value = cpm_msg.SemiAxisLength.OUT_OF_RANGE
        pos.position_confidence_ellipse.semi_minor_confidence.value = cpm_msg.SemiAxisLength.OUT_OF_RANGE
        pos.altitude.altitude_value.value = cpm_msg.AltitudeValue.UNAVAILABLE
        return pos

    def lidar_callback(self, msg: PointCloud2):
        if self.position_vector is None:
            return 

        # 1. Convert PointCloud2 to a numpy array (X, Y, Z)
        points = np.array(list(point_cloud2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True)))
        
        if len(points) == 0:
            return

        # 2. Calculate Bounding Box (Simple min/max clustering)
        # This treats all points in the topic as ONE object
        p_min = np.min(points, axis=0)
        p_max = np.max(p²oints, axis=0)
        
        center = (p_max + p_min) / 2
        size = p_max - p_min

        # 3. Create ETSI Perceived Object
        po = cpm_msg.PerceivedObject()
        po.object_id.value = 1
        po.measurement_delta_time.value = 1
        
        # Coordinates: Convert meters to cm (int)
        po.position.x_coordinate.value.value = int(center[0] * 100)
        po.position.y_coordinate.value.value = int(center[1] * 100)
        po.position.z_coordinate_is_present = True
        po.position.z_coordinate.value.value = int(center[2] * 100)

        # Dimensions: Convert meters to 0.1m units (int)
        po.object_dimension_x_is_present = True
        po.object_dimension_x.value.value = int(size[0] * 10)
        po.object_dimension_y_is_present = True
        po.object_dimension_y.value.value = int(size[1] * 10)
        po.object_dimension_z_is_present = True
        po.object_dimension_z.value.value = int(size[2] * 10)

        # 4. Container Assembly
        container = cpm_msg.WrappedCpmContainer()
        container.container_id.value = cpm_msg.WrappedCpmContainer.CHOICE_CONTAINER_DATA_PERCEIVED_OBJECT_CONTAINER
        container.container_data_perceived_object_container = cpm_msg.PerceivedObjectContainer()
        container.container_data_perceived_object_container.number_of_perceived_objects.value = 1
        container.container_data_perceived_object_container.perceived_objects.array = [po]

        # 5. Final Message Assembly
        cpm = cpm_msg.CollectivePerceptionMessage()
        cpm.payload.management_container.reference_position = self.get_reference_position()
        cpm.payload.cpm_containers.value.array = [container]

        self.cpm_pub.publish(cpm)
        self.get_logger().info(f'CPM Sent: Box of {len(points)} points at x={center[0]:.2f}m')

def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(LidarToCpmBridge())
    rclpy.shutdown()

if __name__ == '__main__':
    main()