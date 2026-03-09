#!/usr/bin/env python3

"""
╔══════════════════════════════════════════════════════════════════╗
║           KIWI BOT  —  Mission Executor (RPi)                    ║
║                                                                  ║
║  TOPICS:                                                         ║
║    SUB  /kiwi/waypoints  std_msgs/String  (JSON mission)         ║
║    SUB  /kiwi/cancel     std_msgs/String  (any msg = cancel)     ║
║    SUB  /camera/colour   std_msgs/String  (detected color)       ║
║    PUB  /kiwi/status     std_msgs/String  (JSON status)          ║
║                                                                  ║
║  INCOMING MISSION JSON:                                          ║
║    {                                                             ║
║      "data": {                                                   ║
║        "wp1": {"x": 1.0, "y": 0.5, "yaw": 0.0},                ║
║        "wp2": {"x": 2.0, "y": 1.0, "yaw": 90.0},               ║
║        "anchor1": {"x": 3.0, "y": 1.5, "yaw": 180.0}           ║
║      },                                                          ║
║      "sequence": [                                               ║
║        {"node": "goto", "target": "wp1"},                        ║
║        {"node": "detect_color"},                                 ║
║        {                                                         ║
║          "node": "switch_color",                                 ║
║          "cases": {                                              ║
║            "RED": [{"node": "goto", "target": "wp2"}],          ║
║            "GREEN": [{"node": "goto", "target": "wp3"}],        ║
║            "BLUE": [{"node": "goto", "target": "wp1"}]          ║
║          },                                                      ║
║          "default": [{"node": "goto", "target": "wp1"}]         ║
║        }                                                         ║
║      ]                                                           ║
║    }                                                             ║
║                                                                  ║
║  OUTGOING STATUS JSON:                                           ║
║    {"state":"idle"}                                              ║
║    {"state":"running","step":1,"total":5,"msg":"..."}            ║
║    {"state":"done","step":5,"total":5,"msg":"..."}               ║
║    {"state":"error","step":2,"total":5,"msg":"..."}              ║
║    {"state":"cancelled","msg":"..."}                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String
from geometry_msgs.msg import Twist
import json
import threading
import time

# Import your navigation classes
from studica_go_to_goal import GoToGoal
# from colour_detect import ColourDetect  # Optional if using dedicated color node


class MissionExecutor(Node):

    def __init__(self):
        super().__init__('kiwi_mission_executor')

        # ── Publishers ────────────────────────────────────────────────────────
        self.status_pub = self.create_publisher(String, '/kiwi/status', 10)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(String, '/kiwi/waypoints', self._mission_cb, 10)
        self.create_subscription(String, '/kiwi/cancel', self._cancel_cb, 10)
        self.create_subscription(String, '/camera/colour', self._color_cb, 10)

        # ── Runtime state ─────────────────────────────────────────────────────
        self._mission_thread = None
        self._cancel_flag = False
        self._running = False
        self._last_color = None
        self._active_nodes = []

        self.get_logger().info("MissionExecutor ready — waiting for /kiwi/waypoints")
        self._publish_status({"state": "idle", "msg": "Ready"})


    # ──────────────────────────────────────────────────────────────────────────
    # CALLBACKS
    # ──────────────────────────────────────────────────────────────────────────

    def _color_cb(self, msg: String):
        """Camera color detection callback."""
        self._last_color = msg.data
        self.get_logger().info(f"[CAMERA] Color detected: {self._last_color}")


    def _mission_cb(self, msg: String):
        """Receive mission and start execution in background thread."""
        if self._running:
            self.get_logger().warn("Mission already running — ignoring. Send /kiwi/cancel first.")
            self._publish_status({"state": "error", "msg": "Already running"})
            return

        try:
            mission = json.loads(msg.data)
            wp_db = mission.get("data", {})
            sequence = mission.get("sequence", [])

            if not sequence:
                self.get_logger().error("Empty sequence in mission")
                self._publish_status({"state": "error", "msg": "Empty sequence"})
                return

            self.get_logger().info(
                f"[MISSION] Received: {len(wp_db)} waypoint(s), {len(sequence)} step(s)"
            )

        except json.JSONDecodeError as e:
            self.get_logger().error(f"Invalid mission JSON: {e}")
            self._publish_status({"state": "error", "msg": f"Bad JSON: {e}"})
            return
        except Exception as e:
            self.get_logger().error(f"Mission parsing error: {e}")
            self._publish_status({"state": "error", "msg": f"Parse error: {e}"})
            return

        # Start mission in background thread
        self._cancel_flag = False
        self._last_color = None
        self._mission_thread = threading.Thread(
            target=self._run_sequence,
            args=(sequence, wp_db),
            daemon=True
        )
        self._mission_thread.start()


    def _cancel_cb(self, msg: String):
        """Cancel current mission."""
        if self._running:
            self.get_logger().warn("Cancel signal received")
            self._cancel_flag = True
            self._stop_robot()
        else:
            self.get_logger().info("Cancel received but no mission running")


    # ──────────────────────────────────────────────────────────────────────────
    # MISSION EXECUTION
    # ──────────────────────────────────────────────────────────────────────────

    def _run_sequence(self, sequence, wp_db):
        """
        Execute a sequence of steps.
        Supports:
          - {"node": "goto", "target": "wp1"}
          - {"node": "detect_color"}
          - {"node": "switch_color", "cases": {...}, "default": [...]}
        """
        self._running = True
        total = len(sequence)

        self._publish_status({
            "state": "running",
            "step": 0,
            "total": total,
            "msg": f"Mission started — {total} step(s)"
        })

        step_idx = 0
        while step_idx < len(sequence):

            # ── Check cancel signal ───────────────────────────────────
            if self._cancel_flag:
                self.get_logger().warn(f"Mission cancelled at step {step_idx + 1}/{total}")
                self._publish_status({
                    "state": "cancelled",
                    "step": step_idx,
                    "total": total,
                    "msg": f"Cancelled"
                })
                self._running = False
                return

            step = sequence[step_idx]
            current = step_idx + 1

            try:
                if not isinstance(step, dict):
                    raise ValueError(f"Step {current} is not a dict: {step}")

                node_type = step.get("node")

                if node_type == "goto":
                    success = self._run_goto(step, wp_db, current, total)
                    if not success:
                        self._running = False
                        return

                elif node_type == "detect_color":
                    success = self._run_detect_color(current, total)
                    if not success:
                        self._running = False
                        return

                elif node_type == "switch_color":
                    # Execute conditional branch
                    success = self._run_switch_color(step, wp_db, current, total)
                    if not success:
                        self._running = False
                        return

                else:
                    raise ValueError(f"Unknown node type: {node_type}")

                # Step complete
                self.get_logger().info(f"✅ Step {current}/{total} done")
                self._publish_status({
                    "state": "running",
                    "step": current,
                    "total": total,
                    "msg": f"Step {current}/{total} done ✅"
                })

            except Exception as e:
                self.get_logger().error(f"Error at step {current}: {e}")
                self._publish_status({
                    "state": "error",
                    "step": current,
                    "total": total,
                    "msg": f"Error: {e}"
                })
                self._running = False
                return

            step_idx += 1

        # ── Mission complete ──────────────────────────────────────────
        self.get_logger().info(f"🏁 Mission complete ({total} steps)")
        self._publish_status({
            "state": "done",
            "step": total,
            "total": total,
            "msg": "All steps complete 🏁"
        })
        self._running = False


    # ──────────────────────────────────────────────────────────────────────────
    # STEP EXECUTION
    # ──────────────────────────────────────────────────────────────────────────

    def _run_goto(self, step, wp_db, current, total):
        """Execute goto (waypoint or anchor) step."""
        try:
            target = step.get("target")
            if not target:
                raise ValueError("goto step missing 'target'")

            if target not in wp_db:
                raise ValueError(f"Waypoint/anchor '{target}' not found in data")

            item = wp_db[target]

            # Waypoint (has x, y, yaw)
            if "x" in item and "y" in item:
                x = float(item.get("x", 0.0))
                y = float(item.get("y", 0.0))
                yaw = float(item.get("yaw", 0.0))

                self.get_logger().info(
                    f"[GOTO] Step {current}/{total} → {target} ({x:.2f}, {y:.2f}, {yaw:.0f}°)"
                )
                self._publish_status({
                    "state": "running",
                    "step": current,
                    "total": total,
                    "msg": f"[{current}/{total}] goto {target}"
                })

                return self._execute_waypoint(x, y, yaw)

            # Anchor (has forward, lateral)
            elif "forward" in item and "lateral" in item:
                forward = float(item.get("forward", 0.0))
                lateral = float(item.get("lateral", 0.0))

                self.get_logger().info(
                    f"[ANCHOR] Step {current}/{total} → {target} (fwd={forward:.2f}, lat={lateral:.2f})"
                )
                self._publish_status({
                    "state": "running",
                    "step": current,
                    "total": total,
                    "msg": f"[{current}/{total}] anchor {target}"
                })

                return self._execute_anchor(forward, lateral)

            else:
                raise ValueError(f"Unknown item format for '{target}': {item}")

        except Exception as e:
            self.get_logger().error(f"goto error: {e}")
            self._publish_status({
                "state": "error",
                "step": current,
                "total": total,
                "msg": f"goto error: {e}"
            })
            return False


    def _run_detect_color(self, current, total):
        """Wait for color detection."""
        try:
            self.get_logger().info(f"[COLOR] Step {current}/{total} → Waiting for color detection...")
            self._publish_status({
                "state": "running",
                "step": current,
                "total": total,
                "msg": f"[{current}/{total}] Detecting color..."
            })

            self._last_color = None
            start_time = time.time()
            timeout = 10  # seconds

            # Wait for color detection
            while not self._last_color and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if not self._last_color:
                self.get_logger().warn(f"Color detection timeout after {timeout}s")
                self._publish_status({
                    "state": "error",
                    "step": current,
                    "total": total,
                    "msg": f"Color detection timeout"
                })
                return False

            self.get_logger().info(f"✅ Color detected: {self._last_color}")
            return True

        except Exception as e:
            self.get_logger().error(f"detect_color error: {e}")
            self._publish_status({
                "state": "error",
                "step": current,
                "total": total,
                "msg": f"Color detection error: {e}"
            })
            return False


    def _run_switch_color(self, step, wp_db, current, total):
        """Execute conditional branching based on detected color."""
        try:
            cases = step.get("cases", {})
            default = step.get("default", [])
            color = self._last_color

            self.get_logger().info(f"[SWITCH] Evaluating color '{color}'...")

            # Find matching branch
            branch = cases.get(color, default)

            if not branch:
                self.get_logger().warn(f"No branch for color '{color}', executing default: {default}")
                branch = default

            if not branch:
                self.get_logger().warn("No branch and no default — skipping")
                return True

            self.get_logger().info(f"  → Executing branch: {branch}")
            self._publish_status({
                "state": "running",
                "step": current,
                "total": total,
                "msg": f"[{current}/{total}] Branch: {color} → {branch}"
            })

            # Recursively execute the branch sequence
            self._run_sequence(branch, wp_db)
            return True

        except Exception as e:
            self.get_logger().error(f"switch_color error: {e}")
            self._publish_status({
                "state": "error",
                "step": current,
                "total": total,
                "msg": f"Conditional branching error: {e}"
            })
            return False


    # ──────────────────────────────────────────────────────────────────────────
    # EXECUTION HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _execute_waypoint(self, x, y, yaw):
        """
        Execute goto waypoint using GoToGoal.
        Returns True on success, False on failure.
        """
        try:
            goal_node = GoToGoal(xg=x, yg=y, thg_deg=yaw)
            self._active_nodes.append(goal_node)
            goal_node.run()
            return True

        except Exception as e:
            self.get_logger().error(f"GoToGoal exception: {e}")
            return False


    def _execute_anchor(self, forward, lateral):
        """
        Execute anchor localization.
        TODO: Integrate with your anchor localization class if available.
        """
        try:
            self.get_logger().info(f"Executing anchor: forward={forward:.3f}, lateral={lateral:.3f}")
            # TODO: Call your anchor localization function here
            # For now, just log it
            return True

        except Exception as e:
            self.get_logger().error(f"Anchor execution error: {e}")
            return False


    def _stop_robot(self):
        """Publish zero velocity to stop robot immediately."""
        try:
            stop_cmd = Twist()
            stop_cmd.linear.x = 0.0
            stop_cmd.linear.y = 0.0
            stop_cmd.linear.z = 0.0
            stop_cmd.angular.x = 0.0
            stop_cmd.angular.y = 0.0
            stop_cmd.angular.z = 0.0
            self.cmd_vel_pub.publish(stop_cmd)
            self.get_logger().info("[STOP] Published zero velocity")
        except Exception as e:
            self.get_logger().error(f"Failed to stop robot: {e}")


    def _publish_status(self, data: dict):
        """Publish status JSON to /kiwi/status."""
        try:
            msg = String()
            msg.data = json.dumps(data)
            self.status_pub.publish(msg)
            self.get_logger().info(f"[STATUS] {msg.data}")
        except Exception as e:
            self.get_logger().error(f"Failed to publish status: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    rclpy.init()
    node = MissionExecutor()
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down MissionExecutor")
    finally:
        for active_node in node._active_nodes:
            try:
                active_node.destroy_node()
            except:
                pass
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
