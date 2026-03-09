#!/usr/bin/env python3
# deveoped by coopers   
"""
╔══════════════════════════════════════════════════════════════════════════╗
║           KIWI BOT DASHBOARD  v4  —  ROS2 Humble                        ║
║           100% Offline  |  Single Python File                            ║
╠══════════════════════════════════════════════════════════════════════════╣
║  FEATURES:                                                               ║
║    • In-browser Map Editor  (draw box → add walls → save PGM+YAML)      ║
║    • Previously saved maps library (load any saved map)                  ║
║    • Robot TF triangle follows /odom                                     ║
║    • Joystick publishes /cmd_vel                                          ║
║    • Waypoint marking [P] + JSON export                                  ║
║                                                                          ║
║  SETUP:   pip3 install websockets pyyaml                                 ║
║  RUN:     python3 kiwi_dashboard_v5.py                                   ║
║  BROWSER: http://localhost:8080                                           ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import String, Bool, Float32MultiArray

import threading
import json
import math
import time
import hashlib
import base64
import struct
import http.server
import socketserver
import os
import glob
import struct as _struct
from typing import Set

HTTP_PORT   = 8080
MAPS_DIR    = os.path.expanduser("~/kiwi_maps")
WAYPOINTS_DIR = os.path.expanduser("~/kiwi_waypoints")
ANCHORS_DIR = os.path.expanduser("~/kiwi_anchors")
os.makedirs(MAPS_DIR, exist_ok=True)
os.makedirs(WAYPOINTS_DIR, exist_ok=True)
os.makedirs(ANCHORS_DIR, exist_ok=True)

state_lock   = threading.Lock()
shared_state = {"cmd_vel": {"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0},
                "cmd_vel_active": False,
                "estop": False,
                "estop_active": False,
                "pending_mission": None,
                "cancel_mission":  False,
                "pending_reset_odom": False}

ws_clients_lock = threading.Lock()
ws_clients: Set = set()

# ═══════════════════════════════════════════════════════════════════════════════
# STDLIB WEBSOCKET  (RFC 6455)
# ═══════════════════════════════════════════════════════════════════════════════
WS_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def _ws_accept_key(k):
    return base64.b64encode(hashlib.sha1(k.encode() + WS_MAGIC).digest()).decode()

def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c: raise ConnectionError
        buf += c
    return buf

def _ws_read_frame(sock):
    hdr = _recv_exact(sock, 2)
    op  = hdr[0] & 0x0F
    masked = (hdr[1] & 0x80) != 0
    plen   = hdr[1] & 0x7F
    if plen == 126: plen = _struct.unpack(">H", _recv_exact(sock,2))[0]
    elif plen == 127: plen = _struct.unpack(">Q", _recv_exact(sock,8))[0]
    mk  = _recv_exact(sock, 4) if masked else b""
    pl  = _recv_exact(sock, plen)
    if masked: pl = bytes(b ^ mk[i%4] for i,b in enumerate(pl))
    return op, pl

def _ws_send_frame(sock, payload: bytes, opcode=0x1):
    h = bytearray([0x80 | opcode])
    n = len(payload)
    if n < 126:     h.append(n)
    elif n < 65536: h += bytearray([126]) + _struct.pack(">H", n)
    else:           h += bytearray([127]) + _struct.pack(">Q", n)
    try: sock.sendall(bytes(h) + payload); return True
    except: return False

class _WSClient:
    def __init__(self, s, a):
        self.sock=s; self.addr=a; self._lk=threading.Lock()
    def send(self, t):
        with self._lk: return _ws_send_frame(self.sock, t.encode())
    def close(self):
        try: self.sock.close()
        except: pass

def _broadcast(data: dict):
    payload = json.dumps(data)
    dead = set()
    with ws_clients_lock: snap = set(ws_clients)
    for c in snap:
        if not c.send(payload): dead.add(c)
    if dead:
        with ws_clients_lock: ws_clients.difference_update(dead)

def _handle_ws(client: _WSClient):
    with ws_clients_lock: ws_clients.add(client)
    try:
        while True:
            op, pl = _ws_read_frame(client.sock)
            if op == 0x8: break
            if op == 0x9: _ws_send_frame(client.sock, pl, 0xA); continue
            if op in (0x1, 0x2):
                try:
                    msg = json.loads(pl.decode())
                    t   = msg.get("type","")
                    print(f"[WS] Received message type: {t}")
                    if t == "cmd_vel":
                        with state_lock:
                            shared_state["cmd_vel"] = {
                                "linear_x":  float(msg.get("linear_x",  0.0)),
                                "linear_y":  float(msg.get("linear_y",  0.0)),
                                "angular_z": float(msg.get("angular_z", 0.0)),
                            }
                            shared_state["cmd_vel_active"] = True
                    elif t == "run_waypoints":
                        wps = msg.get("waypoints", [])
                        with state_lock:
                            # Convert to new format
                            mission = normalize_mission({"waypoints": wps})
                            shared_state["pending_mission"] = mission
                    elif t == "run_mission":
                        mission_data = msg.get("data")
                        mission_seq = msg.get("sequence")
                        print(f"[WS] run_mission received: data={mission_data}, sequence={mission_seq}")
                        if mission_data and mission_seq:
                            # Already in new format
                            with state_lock:
                                shared_state["pending_mission"] = {"data": mission_data, "sequence": mission_seq}
                        else:
                            # Try old format
                            tree = msg.get("tree", {})
                            with state_lock:
                                mission = normalize_mission({"tree": tree})
                                shared_state["pending_mission"] = mission
                    elif t == "cancel_mission":
                        with state_lock:
                            shared_state["cancel_mission"] = True
                    elif t == "reset_odom":
                        with state_lock:
                            shared_state["pending_reset_odom"] = True
                    elif t == "save_map":
                        _save_map_from_ws(msg)
                    elif t == "list_maps":
                        _send_map_list(client)
                    elif t == "load_map":
                        _send_map_data(client, msg.get("name",""))
                    elif t == "save_waypoints":
                        _save_waypoints_from_ws(msg)
                    elif t == "list_waypoints":
                        _send_waypoints_list(client)
                    elif t == "load_waypoints":
                        _send_waypoints_data(client, msg.get("name",""))
                    elif t == "save_anchor":
                        _save_anchor_from_ws(msg)
                    elif t == "list_anchors":
                        _send_anchors_list(client)
                    elif t == "estop":
                        with state_lock:
                            shared_state["estop"] = bool(msg.get("data", False))
                            shared_state["estop_active"] = True
                except Exception as ex:
                    print(f"[WS] parse error: {ex}")
    except: pass
    finally:
        with ws_clients_lock: ws_clients.discard(client)
        client.close()

# ═══════════════════════════════════════════════════════════════════════════════
# MAP I/O  helpers
# ═══════════════════════════════════════════════════════════════════════════════
def _save_map_from_ws(msg):
    """Receive map data from browser and save PGM + YAML to disk."""
    try:
        name       = msg.get("name", "arena_map")
        width      = int(msg["cols"])
        height     = int(msg["rows"])
        resolution = float(msg["resolution"])   # m/cell
        pixels     = msg["pixels"]              # list of 0/254 row-major top→bottom

        base = os.path.join(MAPS_DIR, name)
        pgm  = base + ".pgm"
        yml  = base + ".yaml"

        with open(pgm, "wb") as f:
            f.write(f"P5\n{width} {height}\n255\n".encode())
            f.write(bytes(pixels))

        import yaml
        meta = {
            "image":           os.path.basename(pgm),
            "resolution":      resolution,
            "origin":          [0.0, 0.0, 0.0],
            "negate":          0,
            "occupied_thresh": 0.65,
            "free_thresh":     0.196,
            "mode":            "trinary",
        }
        with open(yml, "w") as f:
            yaml.dump(meta, f, default_flow_style=False, sort_keys=False)

        print(f"[MAP] Saved → {pgm}")
        _broadcast({"type": "map_saved", "name": name})
        # refresh list for all clients
        _broadcast_map_list()
    except Exception as e:
        print(f"[MAP] Save error: {e}")
        _broadcast({"type": "map_save_error", "msg": str(e)})

def _list_maps():
    maps = []
    for pgm in sorted(glob.glob(os.path.join(MAPS_DIR, "*.pgm"))):
        base = os.path.splitext(pgm)[0]
        yml  = base + ".yaml"
        name = os.path.basename(base)
        info = {"name": name, "pgm": pgm, "yaml": yml,
                "has_yaml": os.path.exists(yml)}
        # read dimensions from PGM header
        try:
            with open(pgm,"rb") as f:
                f.readline()  # P5
                dims = f.readline().decode().split()
                info["cols"] = int(dims[0])
                info["rows"] = int(dims[1])
        except: pass
        try:
            import yaml
            with open(yml) as f:
                y = yaml.safe_load(f)
                info["resolution"] = y.get("resolution", 0.05)
        except: pass
        maps.append(info)
    return maps

def _broadcast_map_list():
    _broadcast({"type": "map_list", "maps": _list_maps()})

def _send_map_list(client: _WSClient):
    client.send(json.dumps({"type": "map_list", "maps": _list_maps()}))

def _send_map_data(client: _WSClient, name: str):
    """Read PGM + YAML and send pixel array to browser."""
    print(f"[MAP] load_map request: name='{name}'")
    base = os.path.join(MAPS_DIR, name)
    pgm  = base + ".pgm"
    yml  = base + ".yaml"
    print(f"[MAP] Looking for: {pgm}")
    print(f"[MAP] File exists: {os.path.exists(pgm)}")
    try:
        if not os.path.exists(pgm):
            print(f"[MAP] Error: File not found: {pgm}")
            client.send(json.dumps({
                "type": "map_load_error",
                "name": name,
                "error": f"File not found: {pgm}"
            }))
            return
            
        with open(pgm, "rb") as f:
            magic = f.readline().strip()
            dims  = f.readline().decode().split()
            w, h  = int(dims[0]), int(dims[1])
            f.readline()  # maxval
            raw = f.read()
        pixels = list(raw[:w*h])
        
        print(f"[MAP] Loaded PGM: {w}×{h}, {len(pixels)} pixels")

        resolution = 0.05
        try:
            import yaml
            with open(yml) as f:
                y = yaml.safe_load(f)
                resolution = float(y.get("resolution", 0.05))
                print(f"[MAP] Resolution from YAML: {resolution}")
        except Exception as e:
            print(f"[MAP] Could not load YAML: {e}, using default {resolution}")

        print(f"[MAP] Sending map_data to client: {name}")
        client.send(json.dumps({
            "type": "map_data",
            "name": name,
            "cols": w,
            "rows": h,
            "resolution": resolution,
            "pixels": pixels
        }))
        print(f"[MAP] Successfully sent map_data: {name}")
    except Exception as e:
        print(f"[MAP] Load error: {e}")
        import traceback
        traceback.print_exc()
        client.send(json.dumps({
            "type": "map_load_error",
            "name": name,
            "error": str(e)
        }))


# ═══════════════════════════════════════════════════════════════════════════════
# MISSION FORMAT NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════
def normalize_mission(msg):
    """
    Convert any mission format to the new format: {"data": {...}, "sequence": [...]}
    Supports:
      - New format: {"data": {...}, "sequence": [...]}
      - Tree format: {"tree": {"type": "sequence", "children": [...]}}
      - Flat waypoint format: {"waypoints": [...]}
    """
    # Already in new format
    if "data" in msg and "sequence" in msg:
        return msg
    
    # Tree format: convert children to sequence
    if "tree" in msg:
        tree = msg["tree"]
        if tree.get("type") == "sequence":
            children = tree.get("children", [])
            data = {}
            sequence = []
            wp_counter = 1
            anchor_counter = 1
            for child in children:
                if child.get("node") == "goto":
                    wp_id = f"wp{wp_counter}"
                    data[wp_id] = {
                        "x": child.get("x", 0.0),
                        "y": child.get("y", 0.0),
                        "yaw": child.get("yaw", 0.0)
                    }
                    sequence.append(wp_id)
                    wp_counter += 1
                elif child.get("node") == "anchor":
                    anchor_id = f"anchor{anchor_counter}"
                    data[anchor_id] = {
                        "forward": child.get("forward", 0.0),
                        "lateral": child.get("lateral", 0.0)
                    }
                    sequence.append(anchor_id)
                    anchor_counter += 1
                else:
                    sequence.append(child)
            return {"data": data, "sequence": sequence}
    
    # Flat waypoint format: convert to new format
    if "waypoints" in msg:
        waypoints = msg["waypoints"]
        data = {}
        sequence = []
        for i, wp in enumerate(waypoints):
            wp_id = f"wp{i+1}"
            data[wp_id] = {
                "x": wp.get("x", 0.0),
                "y": wp.get("y", 0.0),
                "yaw": wp.get("yaw", 0.0)
            }
            sequence.append(wp_id)
        return {"data": data, "sequence": sequence}
    
    # Unknown format, return as-is
    return msg


# ═══════════════════════════════════════════════════════════════════════════════
# WAYPOINTS I/O helpers
# ═══════════════════════════════════════════════════════════════════════════════
def _save_waypoints_from_ws(msg):
    """Receive waypoints data from browser and save to JSON file."""
    try:
        name = msg.get("name", "waypoints")
        waypoints = msg.get("waypoints", [])
        map_info = msg.get("map_info", {})
        
        filepath = os.path.join(WAYPOINTS_DIR, f"{name}.json")
        
        data = {
            "name": name,
            "map_info": map_info,
            "waypoints": waypoints
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"[WP] Saved → {filepath}")
        _broadcast({"type": "waypoints_saved", "name": name})
        _broadcast_waypoints_list()
    except Exception as e:
        print(f"[WP] Save error: {e}")
        _broadcast({"type": "waypoints_save_error", "msg": str(e)})

def _list_waypoints():
    """List all saved waypoint JSON files."""
    wps = []
    for fp in sorted(glob.glob(os.path.join(WAYPOINTS_DIR, "*.json"))):
        name = os.path.splitext(os.path.basename(fp))[0]
        try:
            with open(fp, "r") as f:
                data = json.load(f)
                count = len(data.get("waypoints", []))
                wps.append({"name": name, "count": count})
        except:
            wps.append({"name": name, "count": 0})
    return wps

def _broadcast_waypoints_list():
    _broadcast({"type": "waypoints_list", "waypoints": _list_waypoints()})

def _send_waypoints_list(client: _WSClient):
    client.send(json.dumps({"type": "waypoints_list", "waypoints": _list_waypoints()}))

def _send_waypoints_data(client: _WSClient, name: str):
    """Read waypoint JSON and send to browser."""
    print(f"[WP] load_waypoints request: name='{name}'")
    filepath = os.path.join(WAYPOINTS_DIR, f"{name}.json")
    try:
        if not os.path.exists(filepath):
            print(f"[WP] Error: File not found: {filepath}")
            client.send(json.dumps({
                "type": "waypoints_load_error",
                "name": name,
                "error": f"File not found: {filepath}"
            }))
            return
        
        with open(filepath, "r") as f:
            data = json.load(f)
        
        print(f"[WP] Loaded waypoints: {name}, count={len(data.get('waypoints', []))}")
        client.send(json.dumps({
            "type": "waypoints_data",
            "name": name,
            "data": data
        }))
    except Exception as e:
        print(f"[WP] Load error: {e}")
        client.send(json.dumps({
            "type": "waypoints_load_error",
            "name": name,
            "error": str(e)
        }))


# ═══════════════════════════════════════════════════════════════════════════════
# ANCHOR SAVE/LOAD helpers
# ═══════════════════════════════════════════════════════════════════════════════
def _save_anchor_from_ws(msg):
    """Receive anchor data from browser and save to JSON file."""
    import datetime
    try:
        direction = msg.get("direction", "unknown")
        distance = float(msg.get("distance", 0.0))
        average = float(msg.get("average", 0.0))
        filename = msg.get("filename", None)
        
        # If no filename provided, create one with timestamp
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"anchor_{direction}_{timestamp}"
        
        # Ensure filename is safe and add .json extension
        filename = "".join(c for c in filename if c.isalnum() or c in "-_")
        if not filename:
            filename = "anchor_save"
        if not filename.endswith(".json"):
            filename = filename + ".json"
        
        filepath = os.path.join(ANCHORS_DIR, filename)
        
        anchor_data = {
            "direction": direction,
            "distance": distance,
            "average": average,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        with open(filepath, "w") as f:
            json.dump(anchor_data, f, indent=2)
        
        print(f"[ANCHOR] Saved → {filepath}")
        _broadcast({
            "type": "anchor_saved",
            "direction": direction,
            "distance": distance,
            "average": average,
            "filename": filename
        })
    except Exception as e:
        print(f"[ANCHOR] Save error: {e}")
        _broadcast({"type": "anchor_save_error", "msg": str(e)})

def _list_anchors():
    """List all saved anchor JSON files."""
    anchors = []
    for fp in sorted(glob.glob(os.path.join(ANCHORS_DIR, "*.json")), reverse=True):
        name = os.path.splitext(os.path.basename(fp))[0]
        try:
            with open(fp, "r") as f:
                data = json.load(f)
                anchors.append({
                    "name": name,
                    "direction": data.get("direction", "?"),
                    "distance": data.get("distance", 0),
                    "average": data.get("average", 0),
                    "timestamp": data.get("timestamp", "")
                })
        except:
            anchors.append({"name": name, "direction": "?", "distance": 0})
    return anchors

def _broadcast_anchors_list():
    _broadcast({"type": "anchors_list", "anchors": _list_anchors()})

def _send_anchors_list(client: _WSClient):
    client.send(json.dumps({"type": "anchors_list", "anchors": _list_anchors()}))


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD HTML FROM EXTERNAL FILE  (for easier editing/debugging)
# ═══════════════════════════════════════════════════════════════════════════════
def _load_dashboard_html():
    """Load dashboard HTML from external file."""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiwi_dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

HTML = _load_dashboard_html()


# ═══════════════════════════════════════════════════════════════════════════════
# (HTML content moved to kiwi_dashboard.html)
# ═══════════════════════════════════════════════════════════════════════════════
# HTTP + WEBSOCKET SERVER
# ═══════════════════════════════════════════════════════════════════════════════
class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Upgrade","").lower()=="websocket" and self.path=="/ws":
            self._upgrade_ws(); return
        body = _load_dashboard_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control",  "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _upgrade_ws(self):
        key = self.headers.get("Sec-WebSocket-Key","")
        if not key: self.send_response(400); self.end_headers(); return
        resp = (f"HTTP/1.1 101 Switching Protocols\r\n"
                f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {_ws_accept_key(key)}\r\n\r\n")
        self.wfile.write(resp.encode()); self.wfile.flush()
        sock = self.connection; sock.setblocking(True)
        client = _WSClient(sock, self.client_address)
        t = threading.Thread(target=_handle_ws, args=(client,), daemon=True)
        t.start(); t.join()

    def log_message(self, *_): pass

class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads      = True

def _run_server():
    srv = _Server(("", HTTP_PORT), _Handler)
    print(f"[HTTP+WS]  http://localhost:{HTTP_PORT}   ws://localhost:{HTTP_PORT}/ws")
    srv.serve_forever()


# ═══════════════════════════════════════════════════════════════════════════════
# ROS2 NODE
# ═══════════════════════════════════════════════════════════════════════════════
class KiwiDashboardNode(Node):
    def __init__(self):
        super().__init__("kiwi_dashboard")
        self._cmd_pub  = self.create_publisher(Twist,  "/cmd_vel",        10)
        self._wp_pub   = self.create_publisher(String, "/kiwi/waypoints", 10)
        self._can_pub  = self.create_publisher(String, "/kiwi/cancel",    10)
        self._reset_pub = self.create_publisher(Bool,  "/odom/reset",     10)
        self._estop_pub = self.create_publisher(Bool,  "/estop",          10)
        self.create_subscription(Odometry, "/odom",         self._odom_cb,   10)
        self.create_subscription(Twist,    "/cmd_vel",      self._cmd_vel_cb, 10)
        self.create_subscription(Float32MultiArray, "/dis_data", self._dis_cb, 10)
        self.create_subscription(String,   "/camera/colour", self._camera_colour_cb, 10)
        self.create_subscription(String,   "/camera/qr",     self._camera_qr_cb,     10)
        self.create_subscription(String,   "/kiwi/status",  self._status_cb, 10)
        self.create_timer(0.1, self._publish_cmd)
        self.create_timer(0.1, self._publish_estop)
        self.create_timer(0.2, self._check_mission)
        self.create_timer(0.1, self._check_reset_odom)
        self.get_logger().info(f"Team India Dashboard v4 started ✓  maps→ {MAPS_DIR}")

    def _publish_cmd(self):
        with state_lock:
            if not shared_state["cmd_vel_active"]:
                return
            cv = dict(shared_state["cmd_vel"])
            shared_state["cmd_vel_active"] = False
        t = Twist()
        t.linear.x  = cv["linear_x"]
        t.linear.y  = cv["linear_y"]
        t.angular.z = cv["angular_z"]
        self._cmd_pub.publish(t)

    def _publish_estop(self):
        with state_lock:
            if not shared_state["estop_active"]:
                return
            estop_val = shared_state["estop"]
            shared_state["estop_active"] = False
        msg = Bool()
        msg.data = estop_val
        self._estop_pub.publish(msg)

    def _odom_cb(self, msg: Odometry):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        # Extract yaw from quaternion using direct formula
        # yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        _broadcast({"type":"odom","x":x,"y":y,"yaw":yaw})

    def _cmd_vel_cb(self, msg: Twist):
        linear_x = msg.linear.x
        linear_y = msg.linear.y
        angular_z = msg.angular.z
        _broadcast({"type":"actual_cmd_vel","linear_x":linear_x,"linear_y":linear_y,"angular_z":angular_z})

    def _dis_cb(self, msg: Float32MultiArray):
        # Convert Float32MultiArray to list of values
        data_array = list(msg.data)
        _broadcast({"type":"dis_data","data":data_array})

    def _camera_colour_cb(self, msg: String):
        _broadcast({"type":"camera_colour","data":msg.data})

    def _camera_qr_cb(self, msg: String):
        _broadcast({"type":"camera_qr","data":msg.data})

    def _check_mission(self):
        with state_lock:
            mission = shared_state.get("pending_mission")
            cancel  = shared_state.get("cancel_mission", False)
            if mission is not None: shared_state["pending_mission"] = None
            if cancel:              shared_state["cancel_mission"]  = False
        if mission is not None:
            out      = String()
            out.data = json.dumps(mission)
            self._wp_pub.publish(out)
            self.get_logger().info(f"[MISSION] Published mission → /kiwi/waypoints: {out.data[:200]}")
        if cancel:
            out      = String()
            out.data = "cancel"
            self._can_pub.publish(out)
            self.get_logger().info("[MISSION] Cancel → /kiwi/cancel")

    def _check_reset_odom(self):
        with state_lock:
            reset = shared_state.get("pending_reset_odom", False)
            if reset:
                shared_state["pending_reset_odom"] = False
        if reset:
            msg = Bool()
            msg.data = True
            self._reset_pub.publish(msg)
            self.get_logger().info("[ODOM] Reset signal published → /odom/reset")

    def _status_cb(self, msg: String):
        try:
            data = json.loads(msg.data)
            _broadcast({"type": "mission_status", **data})
        except Exception:
            _broadcast({"type": "mission_status", "state": "error", "msg": msg.data})


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    threading.Thread(target=_run_server, daemon=True).start()
    time.sleep(0.2)
    print(f"[INFO]  Open browser → http://localhost:{HTTP_PORT}")
    print(f"[INFO]  Maps stored  → {MAPS_DIR}")
    rclpy.init()
    node = KiwiDashboardNode()
    print("[ROS2]  Spinning — Ctrl+C to quit")
    try:    rclpy.spin(node)
    except KeyboardInterrupt: print("\n[INFO]  Shutting down…")
    finally: node.destroy_node(); rclpy.shutdown()

if __name__ == "__main__":
    main()
