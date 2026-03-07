#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json


class WaypointListener(Node):

    def __init__(self):
        super().__init__('waypoint_listener')

        self.subscription = self.create_subscription(
            String,
            '/kiwi/waypoints',
            self.callback,
            10
        )

        self.get_logger().info("Listening to /kiwi/waypoints...")


    def callback(self, msg):

        try:
            data = json.loads(msg.data)

            print("\n=========== RECEIVED MISSION ===========")

            tree = data.get("tree", {})
            print("Tree Type :", tree.get("type"))

            children = tree.get("children", [])

            for i, node in enumerate(children, start=1):

                if node.get("node") == "goto":

                    x = node.get("x")
                    y = node.get("y")
                    yaw = node.get("yaw")

                    print(f"Step {i} : goto -> {x}, {y}, {yaw}")

                else:
                    print(f"Step {i} : {node.get('node')}")

            print("========================================\n")

        except Exception as e:
            print("JSON Parsing Error:", e)


def main(args=None):

    rclpy.init(args=args)
    node = WaypointListener()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()


# #!/usr/bin/env python3

# import rclpy
# from rclpy.node import Node
# from std_msgs.msg import String


# class WaypointListener(Node):

#     def __init__(self):
#         super().__init__('waypoint_listener')

#         self.subscription = self.create_subscription(
#             String,
#             '/kiwi/waypoints',
#             self.waypoint_callback,
#             10
#         )

#         self.get_logger().info("Listening to /kiwi/waypoints topic...")


#     def waypoint_callback(self, msg):
#         print("\nReceived Waypoints:")
#         print(msg.data)


# def main(args=None):
#     rclpy.init(args=args)

#     node = WaypointListener()

#     try:
#         rclpy.spin(node)
#     except KeyboardInterrupt:
#         pass

#     node.destroy_node()
#     rclpy.shutdown()


# if __name__ == '__main__':
#     main()