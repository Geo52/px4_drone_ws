This doc will walk you through using the ros client library and px4 to create your own offboard scripts. 

Pre-reqs:
1. ROS jazzy, Gazebo Harmonic, and PX4 SITL.
### Step 0: This will be our starting point
```py
import rclpy 
from rclpy.node import Node 
from px4_msgs.msg import OffboardControlMode


class Takeoff(Node):
    def __init__(self):
        super().__init__('takeoff') # specify the name of your node in the quotes

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )

    
def main():
    rclpy.init()
    takeoff = Takeoff()
    rclpy.spin(takeoff)
    takeoff.destroy_node()
```
## step 1: establish a heartbeat 
```py
self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )
        
```

Here we specify the type of message we will be sending, the topic we want to publish to, and the quality of service which we will talk about later.  

The publisher object will serve two purposes. 
1. Its intended purpose which is to tell px4 what type of setpoints we will be sending 
2. It also doubles as a "heartbeat" that lets px4 know our script is alive. If the heartbeat was to stop, px4 would switch back to hold mode to keep the drone from falling out of the sky. 

Also don't let the name of the topic confuse you. This is not where we tell px4 to change to offboard mode! However px4 does need to be receiving a steady stream of these messages before being sent any commands, including switching flight modes.

> Note: all the topic we publish and subscribe to are provided by the uXRCE-DDS bridge ([topics provided by the bridge](https://docs.px4.io/main/en/middleware/dds_topics)). create_publiser doesnt create the topic it just joins the existing topic provdied by the bridge. You can see these topics by running the cmds bellow in seperate terminals.
```
MicroXRCEAgent udp4 -p 8888
ros2 topic list
```
> All topics denoted /fmu/in/... are used when we want to tell the fc/px4 something in this case to switch to offboard mode, and all topics denoted /fmu/out/... are when we want to get information from the fc/px4, for example the drone position in space from the GPS.

The code above merely initializes the publisher, to actually publish to it we need to use the .publish() method like so:
```py
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode


class Takeoff(Node):
    def __init__(self):
        super().__init__("takeoff") 

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )

    def publish_offboard_control_heartbeat_signal(self): 
        msg = OffboardControlMode()
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_control_mode_publisher.publish(msg) 

def main():
    rclpy.init()
    takeoff = Takeoff()
    rclpy.spin(takeoff)
    takeoff.destroy_node()
```
Here we specify that we will be sending **position** setpoints. With position setpoints you send x, y, and z values where x is north, y is east, and z is down and px4 handles everything for you i.e how fast to move (velocity/acceleration), which way to pitch and roll (attitude), etc. Its the simplest form of control.

However, you could provide these values yourself by setting them to True. You probably dont want to do that though unless you have too.
> [learn more about offboard mode](https://docs.px4.io/main/en/flight_modes/offboard)

Now we just need to publish at a steady rate. We do this using a callback.
```py
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode


class Takeoff(Node):
    def __init__(self):
        super().__init__("takeoff") 

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )

        self.timer = self.create_timer(0.1, self.timer_callback) 


    def publish_offboard_control_heartbeat_signal(self):
        msg = OffboardControlMode()
        msg.position = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_control_mode_publisher.publish(msg)

    def timer_callback(self): 
        self.publish_offboard_control_heartbeat_signal()


def main():
    rclpy.init()
    takeoff = Takeoff()
    rclpy.spin(takeoff)
    takeoff.destroy_node()
```

Notice when you run 
```
ros2 topic info /fmu/in/offboard_control_mode
```
 the publisher count is 0, but after running the code with
```
ros2 run <pkg> <node>
```
the publisher count increases to 1. Also when you run 
```
ros2 topic echo /fmu/in/offboard_control_mode" 
```
position is set to true.


## step 2: changing to offboard mode ([px4 flight modes](https://docs.px4.io/main/en/flight_modes_mc/))
Now that we are sending px4 our heartbeat, we can switch modes
```py
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode, VehicleCommand # NEW


class Takeoff(Node):
    """Node that tells the drone to takeoff to x meters, and land after its reached x meters"""

    def __init__(self):
        super().__init__("takeoff") 

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )

        self.vehicle_command_publisher = self.create_publisher( # NEW
            VehicleCommand, "/fmu/in/vehicle_command", 1
        )

        self.counter = 0 # NEW
        self.timer = self.create_timer(0.1, self.timer_callback)

    def timer_callback(self):
        self.publish_offboard_control_heartbeat_signal()

        if self.counter == 10:
            self.engage_offboard_mode() # NEW
        if self.counter < 11:
            self.counter += 1

    def publish_offboard_control_heartbeat_signal(self):
        msg = OffboardControlMode()
        msg.position = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_control_mode_publisher.publish(msg)       

    def engage_offboard_mode(self): # NEW
        msg = VehicleCommand()
        msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
        msg.param1 = 1.0
        msg.param2 = 6.0
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.vehicle_command_publisher.publish(msg)

def main():
    rclpy.init()
    takeoff = Takeoff()
    rclpy.spin(takeoff)
    takeoff.destroy_node()
```

We use a counter as to not send a mode switch commound every 10 hz. Thats unneccsary.

Verify that it worked by check qgc and seeing that the mode is now offboard.

> [learn more about VehicleCommand](https://docs.px4.io/main/en/msg_docs/VehicleCommand)


## step 3: arm

```py
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode, VehicleCommand


class Takeoff(Node):
    """Node that tells the drone to takeoff to x meters, and land after its reached x meters"""

    def __init__(self):
        super().__init__("takeoff")

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )

        self.vehicle_command_publisher = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", 1
        )

        self.counter = 0
        self.timer = self.create_timer(0.1, self.timer_callback)

    def timer_callback(self):
        self.publish_offboard_control_heartbeat_signal()
        if self.counter == 10:
            self.engage_offboard_mode()
            self.arm() # NEW
        if self.counter < 11:
            self.counter += 1

    def publish_offboard_control_heartbeat_signal(self):
        msg = OffboardControlMode()
        msg.position = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_control_mode_publisher.publish(msg)

    def engage_offboard_mode(self):
        msg = VehicleCommand()
        msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_MODE
        msg.param1 = 1.0
        msg.param2 = 6.0
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.vehicle_command_publisher.publish(msg)

    def arm(self): # NEW
        msg = VehicleCommand()
        msg.command = VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM
        msg.param1 = 1.0
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.vehicle_command_publisher.publish(msg)


def main():
    rclpy.init()
    takeoff = Takeoff()
    rclpy.spin(takeoff)
    takeoff.destroy_node()
```

again verify it worked by checking qgc. Should have switched from ready to armed.

Before we get started with takeoff, notice
```py
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.vehicle_command_publisher.publish(msg)
```
Is getting repeated. Lets clean this up by making a function for it.

```py
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode, VehicleCommand


class Takeoff(Node):
    """Node that tells the drone to takeoff to x meters, and land after its reached x meters"""

    def __init__(self):
        super().__init__("takeoff")

        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 1
        )

        self.vehicle_command_publisher = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", 1
        )

        self.counter = 0
        self.timer = self.create_timer(0.1, self.timer_callback)

    def timer_callback(self):
        self.publish_offboard_control_heartbeat_signal()
        if self.counter == 10:
            self.engage_offboard_mode()
            self.arm()
        if self.counter < 11:
            self.counter += 1

    def publish_offboard_control_heartbeat_signal(self):
        msg = OffboardControlMode()
        msg.position = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_control_mode_publisher.publish(msg)

    def engage_offboard_mode(self):
        self.publish_vehicle_command( # NEW
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE, param1=1.0, param2=6.0
        )

    def arm(self):
        self.publish_vehicle_command( # NEW
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=1.0
        )

    def publish_vehicle_command(self, command, **params): # NEW
        """Publish a vehicle command."""
        msg = VehicleCommand()
        msg.command = command
        msg.param1 = params.get("param1", 0.0)
        msg.param2 = params.get("param2", 0.0)
        msg.param3 = params.get("param3", 0.0)
        msg.param4 = params.get("param4", 0.0)
        msg.param5 = params.get("param5", 0.0)
        msg.param6 = params.get("param6", 0.0)
        msg.param7 = params.get("param7", 0.0)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.vehicle_command_publisher.publish(msg)


def main():
    rclpy.init()
    takeoff = Takeoff()
    rclpy.spin(takeoff)
    takeoff.destroy_node()
```

Thats better.
## step 4: takeoff
Now where getting to the good stuff.