import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode


class Takeoff(Node):
    """Node that tells the drone to takeoff to x meters, and land after its reached x meters"""

    def __init__(self):
        super().__init__("takeoff") 

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )

        self.timer = self.create_timer(0.1, self.timer_callback)

    def timer_callback(self):
        self.publish_offboard_control_heartbeat_signal()
        self.engage_offboard_mode()

    def publish_offboard_control_heartbeat_signal(self):
        msg = OffboardControlMode()
        msg.position = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_control_mode_publisher.publish(msg)        

def main():
    rclpy.init()
    takeoff = Takeoff()
    rclpy.spin(takeoff)
    takeoff.destroy_node()
