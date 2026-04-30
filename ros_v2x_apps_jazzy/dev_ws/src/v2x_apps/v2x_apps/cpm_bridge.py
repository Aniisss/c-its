import rclpy
from rclpy.node import Node
import numpy as np
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from visualization_msgs.msg import Marker, MarkerArray

class LidarObjectDetector(Node):
    def __init__(self):
        super().__init__('lidar_object_detector')
        
        # Sub: Raw Lidar Points
        self.subscription = self.create_subscription(
            PointCloud2,
            '/perception/lidar_object_detection/points_detected',
            self.lidar_callback,
            10)
        
        # Pub: Objects as Markers (Viewable in RViz)
        self.publisher = self.create_publisher(
            MarkerArray, 
            '/perception/detected_objects_markers', 
            10)

    def lidar_callback(self, msg):
        # 1. Convert PointCloud2 to Numpy
        gen = point_cloud2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True)
        points = np.array([[p[0], p[1], p[2]] for p in gen], dtype=np.float32)

        if points.size == 0:
            return

        # 2. Calculate Bounding Box
        p_min = np.min(points, axis=0)
        p_max = np.max(points, axis=0)
        center = (p_max + p_min) / 2
        size = p_max - p_min

        # 3. Create a Marker for the Box
        marker = Marker()
        marker.header = msg.header
        marker.ns = "detected_objects"
        marker.id = 1
        marker.type = Marker.CUBE
        marker.action = Marker.ADD
        
        # Position
        marker.pose.position.x = float(center[0])
        marker.pose.position.y = float(center[1])
        marker.pose.position.z = float(center[2])
        
        # Size
        marker.scale.x = float(size[0])
        marker.scale.y = float(size[1])
        marker.scale.z = float(size[2])
        
        # Color (Green, semi-transparent)
        marker.color.r = 0.0
        marker.color.g = 1.0
        marker.color.b = 0.0
        marker.color.a = 0.5

        # 4. Wrap and Publish
        marker_array = MarkerArray()
        marker_array.markers = [marker]
        
        self.publisher.publish(marker_array)
        self.get_logger().info(f'Published object box at {center[0]:.2f}m')

def main():
    rclpy.init()
    node = LidarObjectDetector()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()