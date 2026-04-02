#!/usr/bin/env python3
"""
Offboard Collision Prevention Node
Flies forward at a hardcoded velocity, stops when obstacle detected.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleStatus,
)
import math


# --- Tunable parameters ---
CRUISE_VELOCITY_X = 1.0  # m/s forward (NED: +x = North)
STOP_DISTANCE = 3.0  # metres — stop if obstacle closer than this
SLOW_DISTANCE = 5.0  # metres — start slowing down
LIDAR_FOV_DEG = 30.0  # degrees either side of forward to check
# --------------------------


class OffboardCPNode(Node):
    def __init__(self):
        super().__init__("offboard_cp_node")

        qos_pub = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        qos_sub = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # Publishers
        self.offboard_mode_pub = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", qos_pub
        )
        self.setpoint_pub = self.create_publisher(
            TrajectorySetpoint, "/fmu/in/trajectory_setpoint", qos_pub
        )
        self.vehicle_command_pub = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", qos_pub
        )

        # Subscribers
        self.create_subscription(
            LaserScan,
            "/lidar/scan",  # remapped from gz bridge
            self.lidar_callback,
            qos_sub,
        )
        self.create_subscription(
            VehicleStatus,
            "/fmu/out/vehicle_status",
            self.status_callback,
            qos_sub,
        )

        self.nav_state = VehicleStatus.NAVIGATION_STATE_MAX
        self.min_forward_distance = float("inf")
        self.offboard_setpoint_counter = 0

        # Send setpoints at 20 Hz (PX4 requires >2 Hz to stay in offboard)
        self.timer = self.create_timer(0.05, self.timer_callback)
        self.get_logger().info("Offboard CP node started")

    def lidar_callback(self, msg: LaserScan):
        """Find minimum range in the forward FOV."""
        fov_rad = math.radians(LIDAR_FOV_DEG)
        angle = msg.angle_min
        min_dist = float("inf")

        for r in msg.ranges:
            if -fov_rad <= angle <= fov_rad:
                if msg.range_min < r < msg.range_max:
                    min_dist = min(min_dist, r)
            angle += msg.angle_increment

        self.min_forward_distance = min_dist

    def status_callback(self, msg: VehicleStatus):
        self.nav_state = msg.nav_state

    def timer_callback(self):
        self.publish_offboard_mode()

        # Send ~10 setpoints before arming + switching mode
        if self.offboard_setpoint_counter == 10:
            self.arm()
            self.engage_offboard_mode()

        self.publish_setpoint()

        if self.offboard_setpoint_counter < 11:
            self.offboard_setpoint_counter += 1

    def compute_safe_velocity(self) -> float:
        d = self.min_forward_distance

        if d <= STOP_DISTANCE:
            self.get_logger().warn(
                f"Obstacle at {d:.2f} m — STOPPING", throttle_duration_sec=1.0
            )
            return 0.0

        if d <= SLOW_DISTANCE:
            # Linear scale: full speed at SLOW_DISTANCE, zero at STOP_DISTANCE
            scale = (d - STOP_DISTANCE) / (SLOW_DISTANCE - STOP_DISTANCE)
            v = CRUISE_VELOCITY_X * scale
            self.get_logger().info(
                f"Obstacle at {d:.2f} m — slowing to {v:.2f} m/s",
                throttle_duration_sec=1.0,
            )
            return v

        return CRUISE_VELOCITY_X

    def publish_offboard_mode(self):
        msg = OffboardControlMode()
        msg.position = False
        msg.velocity = True
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        msg.timestamp = self.get_clock().now().nanoseconds // 1000
        self.offboard_mode_pub.publish(msg)

    def publish_setpoint(self):
        vx = self.compute_safe_velocity()

        msg = TrajectorySetpoint()
        msg.position = [float("nan"), float("nan"), float("nan")]
        msg.velocity = [vx, 0.0, 0.0]  # NED: x=North, y=East, z=Down
        msg.yaw = float("nan")
        msg.timestamp = self.get_clock().now().nanoseconds // 1000
        self.setpoint_pub.publish(msg)

    def arm(self):
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0
        )
        self.get_logger().info("Arm command sent")

    def engage_offboard_mode(self):
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)
        self.get_logger().info("Offboard mode command sent")

    def publish_vehicle_command(self, command, param1=0.0, param2=0.0):
        msg = VehicleCommand()
        msg.param1 = param1
        msg.param2 = param2
        msg.command = command
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = self.get_clock().now().nanoseconds // 1000
        self.vehicle_command_pub.publish(msg)


def main():
    rclpy.init()
    node = OffboardCPNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()