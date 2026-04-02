import rclpy
from rclpy.node import Node
from px4_msgs import OffboardControlMode


class Takeoff(Node):
    """Node that tells the drone to takeoff to x meters, and land after its reached x meters"""

    def __init__(self):

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )
