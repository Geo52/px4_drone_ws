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

Now that we are sending px4 our heartbeat, we can switch modes.

## step 2: changing to offboard mode ([px4 flight modes](https://docs.px4.io/main/en/flight_modes_mc/))