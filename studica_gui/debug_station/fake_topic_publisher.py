#!/usr/bin/env python3
# developed by coopers — Team India
"""
FAKE TOPIC PUBLISHER — Dashboard Testing
Publishes dummy data to ALL topics that kiwi_server subscribes to.
Run this alongside kiwi_server.py to test the full dashboard without a real robot.

  source /opt/ros/humble/setup.bash
  python3 fake_topic_publisher.py

TOPICS PUBLISHED:
  /cmd_vel                                        ← Twist
  /odom                                           ← Odometry
  /dis_data                                       ← Float32MultiArray  (IR1 IR2 US1 US2)
  /imu                                            ← Imu
  /kiwi/gripper                                   ← Bool
  /kiwi/waypoints                                 ← String (JSON tree)
  /kiwi/cancel                                    ← String
  /camera/colour                                  ← String (RED/GREEN/BLUE/...)
  /camera/qr                                      ← String (QR text)
  /ascamera_hp60c/camera_publisher/rgb0/image     ← Image (solid colour frame)
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, Image
from geometry_msgs.msg import Twist, Quaternion
from std_msgs.msg import String, Bool, Float32MultiArray

import math, time, json, random, itertools
import numpy as np

# ── Tuning ─────────────────────────────────────────────────────────────────
CAMERA_W   = 320
CAMERA_H   = 240
LOOP_HZ    = 10          # general update rate
COLOURS    = ["RED", "GREEN", "BLUE", "ORANGE", "YELLOW", "BLACK", "NONE"]
COLOUR_BG  = {           # BGR values for camera frame background per colour
    "RED":    (0,   0,   200),
    "GREEN":  (0,   200, 0  ),
    "BLUE":   (200, 0,   0  ),
    "ORANGE": (0,   140, 255),
    "YELLOW": (0,   230, 230),
    "BLACK":  (30,  30,  30 ),
    "NONE":   (20,  20,  40 ),
}
WAYPOINT_TREES = [
    json.dumps({"tree": {"type": "sequence", "children": [
        {"node": "goto", "x": 0.42, "y": -0.78, "yaw": 0},
        {"node": "detect_color"}
    ]}}),
    json.dumps({"tree": {"type": "sequence", "children": [
        {"node": "goto", "x": 0.56, "y": -0.16, "yaw": 0},
        {"node": "goto", "x": 0.45, "y": -0.80, "yaw": 270},
        {"node": "goto", "x": 0.08, "y": -1.30, "yaw": 270},
        {"node": "detect_color"},
        {"node": "goto", "x": 0.42, "y": -1.90, "yaw": 270},
        {"node": "goto", "x": -0.03,"y": -1.36, "yaw": 180},
        {"node": "goto", "x": 0.58, "y": -0.64, "yaw": 0}
    ]}}),
]
# ───────────────────────────────────────────────────────────────────────────


class FakePublisherNode(Node):

    def __init__(self):
        super().__init__('fake_topic_publisher')

        # ── Publishers ────────────────────────────────────────────────────
        self.pub_cmdvel  = self.create_publisher(Twist,              '/cmd_vel',           10)
        self.pub_odom    = self.create_publisher(Odometry,           '/odom',              10)
        self.pub_dis     = self.create_publisher(Float32MultiArray,  '/dis_data',          10)
        self.pub_imu     = self.create_publisher(Imu,                '/imu',               10)
        self.pub_gripper = self.create_publisher(Bool,               '/kiwi/gripper',      10)
        self.pub_wp      = self.create_publisher(String,             '/kiwi/waypoints',    10)
        self.pub_cancel  = self.create_publisher(String,             '/kiwi/cancel',       10)
        self.pub_colour  = self.create_publisher(String,             '/camera/colour',     10)
        self.pub_qr      = self.create_publisher(String,             '/camera/qr',         10)
        self.pub_camera  = self.create_publisher(
            Image, '/ascamera_hp60c/camera_publisher/rgb0/image', 10)

        # ── State ─────────────────────────────────────────────────────────
        self._t           = 0.0
        self._colour_cyc  = itertools.cycle(COLOURS)
        self._colour_cur  = "NONE"
        self._colour_tick = 0
        self._wp_tick     = 0
        self._wp_cyc      = itertools.cycle(WAYPOINT_TREES)
        self._cancel_tick = 0
        self._qr_tick     = 0
        self._qr_active   = False
        self._gripper_st  = False
        self._gripper_tick= 0

        self.create_timer(1.0 / LOOP_HZ, self._loop)
        self.get_logger().info("━" * 50)
        self.get_logger().info("  🤖 FAKE TOPIC PUBLISHER — all topics live!")
        self.get_logger().info("  Open dashboard → http://localhost:8080")
        self.get_logger().info("━" * 50)

    # ── Main loop ──────────────────────────────────────────────────────────
    def _loop(self):
        self._t += 1.0 / LOOP_HZ
        t = self._t

        self._pub_cmdvel(t)
        self._pub_odom(t)
        self._pub_dis(t)
        self._pub_imu(t)
        self._pub_camera()
        self._pub_colour_cycle()
        self._pub_qr_cycle()
        self._pub_gripper_cycle()
        self._pub_waypoint_cycle()
        self._pub_cancel_cycle()

    # ── /cmd_vel ───────────────────────────────────────────────────────────
    def _pub_cmdvel(self, t):
        msg = Twist()
        msg.linear.x  = round(0.3 * math.sin(t * 0.5), 3)
        msg.angular.z = round(0.5 * math.sin(t * 0.3), 3)
        self.pub_cmdvel.publish(msg)

    # ── /odom ──────────────────────────────────────────────────────────────
    def _pub_odom(self, t):
        msg = Odometry()
        msg.pose.pose.position.x = round(1.5 * math.sin(t * 0.2), 3)
        msg.pose.pose.position.y = round(1.0 * math.cos(t * 0.2), 3)
        yaw = t * 0.2
        msg.pose.pose.orientation.z = round(math.sin(yaw / 2), 4)
        msg.pose.pose.orientation.w = round(math.cos(yaw / 2), 4)
        self.pub_odom.publish(msg)

    # ── /dis_data ──────────────────────────────────────────────────────────
    def _pub_dis(self, t):
        msg = Float32MultiArray()
        msg.data = [
            round(20.0 + 10.0 * math.sin(t * 0.7),        2),   # IR1 / FL
            round(15.0 + 8.0  * math.sin(t * 0.9 + 1.0),  2),   # IR2 / FR
            round(35.0 + 15.0 * math.sin(t * 0.4 + 0.5),  2),   # US1 / L
            round(40.0 + 12.0 * math.sin(t * 0.6 + 1.5),  2),   # US2 / R
        ]
        self.pub_dis.publish(msg)

    # ── /imu ───────────────────────────────────────────────────────────────
    def _pub_imu(self, t):
        msg = Imu()
        yaw = t * 0.3
        msg.orientation.z = round(math.sin(yaw / 2), 4)
        msg.orientation.w = round(math.cos(yaw / 2), 4)
        msg.angular_velocity.z    = round(0.3 * math.sin(t), 4)
        msg.linear_acceleration.x = round(-0.1 * math.sin(t * 0.5), 4)
        msg.linear_acceleration.y = round(-0.8 * math.cos(t * 0.3), 4)
        msg.linear_acceleration.z = round(9.81 + 0.05 * math.sin(t), 4)
        self.pub_imu.publish(msg)

    # ── /camera/colour — cycles every 3s ──────────────────────────────────
    def _pub_colour_cycle(self):
        self._colour_tick += 1
        if self._colour_tick >= LOOP_HZ * 3:   # every 3 seconds
            self._colour_tick = 0
            self._colour_cur  = next(self._colour_cyc)
            self.get_logger().info(f"🎨 colour → {self._colour_cur}")
        msg = String(); msg.data = self._colour_cur
        self.pub_colour.publish(msg)

    # ── /camera/qr — activates briefly every 10s ──────────────────────────
    def _pub_qr_cycle(self):
        self._qr_tick += 1
        if self._qr_tick >= LOOP_HZ * 10:      # every 10 seconds
            self._qr_tick   = 0
            self._qr_active = True
        if self._qr_active:
            msg = String(); msg.data = "https://teamindiarobotics.com/kiwi"
            self.pub_qr.publish(msg)
            if self._qr_tick >= LOOP_HZ * 2:   # QR visible for 2 seconds
                self._qr_active = False
                msg2 = String(); msg2.data = ""
                self.pub_qr.publish(msg2)
                self.get_logger().info("🔲 QR → cleared")
        else:
            msg = String(); msg.data = ""
            self.pub_qr.publish(msg)

    # ── /kiwi/gripper — toggles every 5s ──────────────────────────────────
    def _pub_gripper_cycle(self):
        self._gripper_tick += 1
        if self._gripper_tick >= LOOP_HZ * 5:
            self._gripper_tick = 0
            self._gripper_st   = not self._gripper_st
            self.get_logger().info(f"🦾 gripper → {'OPEN' if self._gripper_st else 'CLOSED'}")
        msg = Bool(); msg.data = self._gripper_st
        self.pub_gripper.publish(msg)

    # ── /kiwi/waypoints — sends a new tree every 15s ──────────────────────
    def _pub_waypoint_cycle(self):
        self._wp_tick += 1
        if self._wp_tick == 1 or self._wp_tick >= LOOP_HZ * 15:
            self._wp_tick = 1
            tree = next(self._wp_cyc)
            msg = String(); msg.data = tree
            self.pub_wp.publish(msg)
            self.get_logger().info("📍 waypoints → sent")

    # ── /kiwi/cancel — sends cancel every 20s ─────────────────────────────
    def _pub_cancel_cycle(self):
        self._cancel_tick += 1
        if self._cancel_tick >= LOOP_HZ * 20:
            self._cancel_tick = 0
            msg = String(); msg.data = "cancel"
            self.pub_cancel.publish(msg)
            self.get_logger().info("❌ cancel → sent")

    # ── /ascamera_hp60c/.../rgb0/image — coloured frame ───────────────────
    def _pub_camera(self):
        colour = self._colour_cur if self._colour_cur != "NONE" else "NONE"
        bgr    = COLOUR_BG.get(colour, (20, 20, 40))

        # Build a solid colour BGR8 frame with a simple grid overlay
        frame = np.full((CAMERA_H, CAMERA_W, 3), bgr, dtype=np.uint8)

        # Draw a simple crosshair
        cx, cy = CAMERA_W // 2, CAMERA_H // 2
        frame[cy-1:cy+2, :] = (80, 80, 80)
        frame[:, cx-1:cx+2] = (80, 80, 80)

        msg              = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.height       = CAMERA_H
        msg.width        = CAMERA_W
        msg.encoding     = 'bgr8'
        msg.step         = CAMERA_W * 3
        msg.data         = frame.tobytes()
        self.pub_camera.publish(msg)


def main():
    rclpy.init()
    try:
        node = FakePublisherNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[FAKE] Shutting down...")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
