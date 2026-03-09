#!/usr/bin/env python3
# developed by coopers — Team India
"""
╔══════════════════════════════════════════════════════════════════════╗
║        KIWI DEBUG STATION — All-in-One Server                       ║
║        ROS2 + WebSocket + HTTP  |  No rosbridge needed              ║
╠══════════════════════════════════════════════════════════════════════╣
║  RUN:     source /opt/ros/humble/setup.bash                         ║
║           python3 kiwi_server.py                                    ║
║  BROWSER: http://localhost:8080  (auto opens dashboard)             ║
║                                                                     ║
║  Put kiwi_debug_dashboard.html in the same folder as this script.  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, Image
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Bool, Float32MultiArray

import threading, json, math, time, base64, subprocess, re
import hashlib, struct, http.server, socketserver, os
from typing import Set

HTTP_PORT = 8080
WS_MAGIC  = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

ws_clients_lock = threading.Lock()
ws_clients: Set = set()
ros_node_ref    = None

# ── Load HTML from same directory as this script ──
def _load_html():
    here      = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(here, "kiwi_debug_dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

HTML = _load_html()   # cached for speed, reloaded per-request below too

# ═══════════════════════════════════════════
# WebSocket helpers (RFC 6455, stdlib only)
# ═══════════════════════════════════════════
def _ws_accept(key):
    return base64.b64encode(hashlib.sha1(key.encode()+WS_MAGIC).digest()).decode()

def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c: raise ConnectionError
        buf += c
    return buf

def _read_frame(sock):
    h      = _recv_exact(sock, 2)
    op     = h[0] & 0x0F
    masked = bool(h[1] & 0x80)
    plen   = h[1] & 0x7F
    if plen == 126: plen = struct.unpack(">H", _recv_exact(sock,2))[0]
    elif plen == 127: plen = struct.unpack(">Q", _recv_exact(sock,8))[0]
    mask = _recv_exact(sock, 4) if masked else b""
    data = _recv_exact(sock, plen)
    if masked: data = bytes(b ^ mask[i%4] for i,b in enumerate(data))
    return op, data

def _make_frame(payload, opcode=0x1):
    n = len(payload)
    h = bytearray([0x80 | opcode])
    if n < 126:      h.append(n)
    elif n < 65536:  h += bytearray([126]) + struct.pack(">H", n)
    else:            h += bytearray([127]) + struct.pack(">Q", n)
    return bytes(h) + payload

class WSClient:
    def __init__(self, s, a):
        self.sock = s; self.addr = a; self._lk = threading.Lock()
    def send(self, data):
        with self._lk:
            try:
                self.sock.sendall(_make_frame(data if isinstance(data, bytes) else data.encode()))
                return True
            except: return False
    def close(self):
        try: self.sock.close()
        except: pass

def _broadcast(data: dict):
    payload = json.dumps(data).encode()
    dead = set()
    with ws_clients_lock: snap = set(ws_clients)
    for c in snap:
        if not c.send(payload): dead.add(c)
    if dead:
        with ws_clients_lock: ws_clients.difference_update(dead)

estop_active = False   # global estop state

def _handle_from_browser(msg: dict):
    global estop_active
    op    = msg.get("op", "")
    topic = msg.get("topic", "")
    data  = msg.get("msg", {})
    if op == "publish" and topic == "/estop" and ros_node_ref:
        engage = bool(data.get("data", False))
        estop_active = engage
        m = Bool(); m.data = engage
        ros_node_ref.estop_pub.publish(m)
        print(f"[ROS] /estop → {'ENGAGED' if engage else 'RELEASED'}")
        if engage:
            # immediately zero out cmd_vel
            zero = Twist()
            ros_node_ref.cmd_vel_pub.publish(zero)
            print("[ROS] /cmd_vel → ZEROED (estop engaged)")

def _handle_ws(client: WSClient):
    with ws_clients_lock: ws_clients.add(client)
    print(f"[WS] + connected {client.addr}  (total={len(ws_clients)})")
    try:
        while True:
            op, data = _read_frame(client.sock)
            if op == 0x8: break
            if op == 0x9: client.sock.sendall(_make_frame(data, 0xA)); continue
            if op in (0x1, 0x2):
                try: _handle_from_browser(json.loads(data.decode()))
                except Exception as e: print(f"[WS] error: {e}")
    except: pass
    finally:
        with ws_clients_lock: ws_clients.discard(client)
        client.close()
        print(f"[WS] - disconnected {client.addr}")

# ═══════════════════════════════════════════
# HTTP + WebSocket on same port 8080
# ═══════════════════════════════════════════
class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Upgrade","").lower() == "websocket" and self.path in ("/ws", "/wstest"):
            key  = self.headers.get("Sec-WebSocket-Key","")
            resp = (f"HTTP/1.1 101 Switching Protocols\r\n"
                    f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {_ws_accept(key)}\r\n\r\n")
            self.wfile.write(resp.encode()); self.wfile.flush()
            print(f"[WS] Upgrade OK for {self.path} from {self.client_address}")
            self.connection.setblocking(True)
            c = WSClient(self.connection, self.client_address)
            t = threading.Thread(target=_handle_ws, args=(c,), daemon=True)
            t.start(); t.join()
        else:
            try:
                body = _load_html().encode("utf-8")   # fresh read every time
            except Exception as e:
                body = f"<h1>Error loading dashboard: {e}</h1>".encode()
            self.send_response(200)
            self.send_header("Content-Type",   "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control",  "no-cache")
            self.end_headers()
            self.wfile.write(body)
    def log_message(self, *_): pass

class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads      = True

def _run_server():
    srv = _Server(("", HTTP_PORT), _Handler)
    print(f"[HTTP+WS]  Serving on http://localhost:{HTTP_PORT}")
    srv.serve_forever()

# ═══════════════════════════════════════════
# ROS2 Node — subscribes to all topics
# ═══════════════════════════════════════════
class KiwiServerNode(Node):
    def __init__(self):
        super().__init__("kiwi_debug_server")
        self.estop_pub   = self.create_publisher(Bool,  "/estop", 10)
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel",    10)
        self.create_subscription(Twist,   "/cmd_vel",        self._cmdvel_cb,  10)
        self.create_subscription(Odometry, "/odom",           self._odom_cb,    10)
        self.create_subscription(Float32MultiArray, "/dis_data",       self._dis_cb,     10)
        self.create_subscription(Imu,      "/imu",            self._imu_cb,     10)
        self.create_subscription(Bool,     "/kiwi/gripper",   self._gripper_cb, 10)
        self.create_subscription(String,   "/kiwi/waypoints", self._wp_cb,      10)
        self.create_subscription(String,   "/kiwi/cancel",    self._cancel_cb,  10)
        self.create_subscription(String,   "/camera/colour",       self._colour_cb,   10)
        self.create_subscription(String,   "/camera/qr",           self._qr_cb,       10)
        self.create_subscription(Image,    "/ascamera_hp60c/camera_publisher/rgb0/image",
                                           self._camera_cb, 10)
        self.get_logger().info("━"*50)
        self.get_logger().info("  KIWI Debug Server — No rosbridge needed!")
        self.get_logger().info(f"  Open browser → http://localhost:{HTTP_PORT}")
        self.get_logger().info("━"*50)
        self.get_logger().info("  SUB /odom  /dis_data(Float32MultiArray)  /imu  /cmd_vel")
        self.get_logger().info("  SUB /kiwi/gripper  /kiwi/waypoints  /kiwi/cancel  /camera/colour  /camera/qr")
        self.get_logger().info("  SUB /ascamera_hp60c/.../rgb0/image")
        self.get_logger().info("  PUB /estop  /cmd_vel(zero on estop)")
        self.get_logger().info("━"*50)

    def _cmdvel_cb(self, msg):
        global estop_active
        if estop_active:
            zero = Twist()
            self.cmd_vel_pub.publish(zero)
            print("[ROS] /cmd_vel blocked — estop active, publishing zero")
        _broadcast({
            "type": "cmd_vel",
            "lx": msg.linear.x,  "ly": msg.linear.y,  "lz": msg.linear.z,
            "ax": msg.angular.x, "ay": msg.angular.y, "az": msg.angular.z,
        })

    def _odom_cb(self, msg):
        x   = msg.pose.pose.position.x
        y   = msg.pose.pose.position.y
        q   = msg.pose.pose.orientation
        yaw = math.atan2(2.0*(q.w*q.z+q.x*q.y), 1.0-2.0*(q.y*q.y+q.z*q.z))
        _broadcast({"type": "odom", "x": x, "y": y, "yaw": yaw})

    def _dis_cb(self, msg):
        d = msg.data
        _broadcast({
            "type": "dis_data",
            "IR1": float(d[0]) if len(d) > 0 else 0.0,
            "IR2": float(d[1]) if len(d) > 1 else 0.0,
            "US1": float(d[2]) if len(d) > 2 else 0.0,
            "US2": float(d[3]) if len(d) > 3 else 0.0,
        })

    def _imu_cb(self, msg):
        q  = msg.orientation
        av = msg.angular_velocity
        la = msg.linear_acceleration
        _broadcast({
            "type": "imu",
            "orientation": {"x": q.x,  "y": q.y,  "z": q.z,  "w": q.w},
            "angular_velocity":    {"x": av.x, "y": av.y, "z": av.z},
            "linear_acceleration": {"x": la.x, "y": la.y, "z": la.z},
        })

    def _gripper_cb(self, msg):
        _broadcast({"type": "gripper", "data": msg.data})

    def _wp_cb(self, msg):
        _broadcast({"type": "waypoints", "data": msg.data})

    def _cancel_cb(self, msg):
        _broadcast({"type": "cancel", "data": msg.data})

    def _colour_cb(self, msg):
        _broadcast({"type": "detected_data", "color": msg.data, "qr": ""})

    def _qr_cb(self, msg):
        _broadcast({"type": "detected_data", "color": "NONE", "qr": msg.data})

    def _camera_cb(self, msg):
        try:
            b64 = base64.b64encode(bytes(msg.data)).decode("ascii")
            _broadcast({"type": "camera", "width": msg.width, "height": msg.height,
                        "encoding": msg.encoding, "data": b64})
        except Exception as e:
            self.get_logger().warn(f"Camera error: {e}")

# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
TRACKED_TOPICS = [
    '/estop',
    '/cmd_vel',
    '/odom',
    '/dis_data',
    '/imu',
    '/kiwi/gripper',
    '/kiwi/waypoints',
    '/kiwi/cancel',
    '/camera/colour',
    '/camera/qr',
    '/ascamera_hp60c/camera_publisher/rgb0/image',
]

def _get_topic_info(topic):
    """Run ros2 topic info <topic> and parse publisher/subscriber counts."""
    try:
        result = subprocess.run(
            ['ros2', 'topic', 'info', topic],
            capture_output=True, text=True, timeout=3
        )
        out = result.stdout
        pub_match = re.search(r'Publisher count:\s*(\d+)', out)
        sub_match = re.search(r'Subscription count:\s*(\d+)', out)
        pub_count = int(pub_match.group(1)) if pub_match else 0
        sub_count = int(sub_match.group(1)) if sub_match else 0
        return {"topic": topic, "publishers": pub_count, "subscribers": sub_count}
    except Exception:
        return {"topic": topic, "publishers": 0, "subscribers": 0}

def _topic_info_poller():
    """Poll topic info every 3 seconds and broadcast to dashboard."""
    time.sleep(2.0)  # wait for ROS to init
    while True:
        infos = [_get_topic_info(t) for t in TRACKED_TOPICS]
        _broadcast({"type": "topic_info", "topics": infos})
        time.sleep(3.0)

def main():
    global ros_node_ref
    threading.Thread(target=_run_server, daemon=True).start()
    threading.Thread(target=_topic_info_poller, daemon=True).start()
    time.sleep(0.3)
    rclpy.init()
    node = KiwiServerNode()
    ros_node_ref = node
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[KIWI] Shutting down...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
