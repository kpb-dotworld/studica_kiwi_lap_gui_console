#!/usr/bin/env python3
"""
kiwi_teleop.py  —  Pure Python dual-joystick GUI for 3-wheel Omni (Kiwi) robot
================================================================================
Run:
    python3 kiwi_teleop.py

Requirements:
    pip install pygame
    source /opt/ros/<distro>/setup.bash   (ROS2 must be sourced)

ROS2 Topics:
    PUBLISHES  /cmd_vel    geometry_msgs/Twist
    SUBSCRIBES /dis_data   std_msgs/Float32MultiArray  [left, right, fl, fr]
    SUBSCRIBES /odom       nav_msgs/Odometry

Kiwi wheel angles:  FL=30 deg   FR=150 deg   BK=270 deg

Controls:
    Drag LEFT  joystick  —  Vx (forward/back)  Vy (strafe)
    Drag RIGHT joystick  —  Wz (rotation, horizontal only)
    W/S   forward / back         Q/E   rotate CCW / CW
    A/D   strafe left / right    SPACE stop
    F1    emergency stop         +/-   linear speed
    [/]   angular speed          R     reset trail map
    H     help overlay           ESC   quit
"""

import math, sys, threading, time, collections
import pygame

# ── ROS2 ──────────────────────────────────────────────────────────────────────
try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from std_msgs.msg import Float32MultiArray
    ROS_OK = True
except ImportError:
    ROS_OK = False

# ── Colours ───────────────────────────────────────────────────────────────────
BG       = (10,  13,  18)
SURFACE  = (15,  20,  28)
CARD     = (18,  26,  38)
BORDER   = (32,  50,  68)
CYAN     = ( 0, 210, 255)
CYAN_D   = ( 0,  70,  90)
ORANGE   = (255,120,  40)
GREEN    = ( 40,230, 100)
YELLOW   = (255,210,   0)
RED      = (255, 45,  80)
RED_D    = ( 90, 14,  28)
MUTED    = ( 55, 85, 108)
TEXT     = (180,205, 220)
DIM      = ( 38, 60,  78)

def lerpC(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

# ── Kiwi kinematics ───────────────────────────────────────────────────────────
WA  = [math.radians(d) for d in (30.0, 150.0, 270.0)]
L   = 0.15   # body radius metres — adjust to your robot
WNAMES = ["FL 30°","FR 150°","BK 270°"]

def wheel_speeds(vx, vy, wz):
    return [-math.sin(t)*vx + math.cos(t)*vy + L*wz for t in WA]

# ── ROS2 node ─────────────────────────────────────────────────────────────────
class KiwiNode(Node):
    def __init__(self):
        super().__init__('kiwi_teleop')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Float32MultiArray, '/dis_data', self._dis_cb, 10)
        self.create_subscription(Odometry, '/odom', self._odom_cb, 10)

        self._lock     = threading.Lock()
        self.dist      = [None]*4
        self.odom_x    = self.odom_y = self.odom_yaw = 0.0
        self.odom_spd  = self.odom_vx = self.odom_vy = self.odom_wz = 0.0
        self.dis_cnt   = self.odom_cnt = self.cmd_cnt = 0
        self.log       = collections.deque(maxlen=200)
        self._lg("ok",   "ROS2 node started")
        self._lg("info", "PUB  /cmd_vel  [geometry_msgs/Twist]")
        self._lg("info", "SUB  /dis_data [std_msgs/Float32MultiArray]")
        self._lg("info", "SUB  /odom     [nav_msgs/Odometry]")

    def _lg(self, lvl, msg):
        self.log.append((time.strftime("%H:%M:%S"), lvl, msg))
        print(f"[{lvl.upper():4}] {msg}")

    def pub_vel(self, vx, vy, wz):
        m = Twist()
        m.linear.x  = float(f"{vx:.5f}")
        m.linear.y  = float(f"{vy:.5f}")
        m.angular.z = float(f"{wz:.5f}")
        self.pub.publish(m)
        self.cmd_cnt += 1

    def _dis_cb(self, msg):
        with self._lock:
            if len(msg.data) >= 4:
                self.dist = list(msg.data[:4])
            self.dis_cnt += 1
            if self.dis_cnt == 1:
                self._lg("ok", f"/dis_data FIRST MSG  len={len(msg.data)}")
            if self.dis_cnt % 100 == 0:
                self._lg("data", "/dis_data #%d [%s]" % (self.dis_cnt,
                    ", ".join(f"{v:.3f}" for v in self.dist)))

    def _odom_cb(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        t = msg.twist.twist
        yaw = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        with self._lock:
            self.odom_x   = p.x
            self.odom_y   = p.y
            self.odom_yaw = yaw
            self.odom_spd = math.sqrt(t.linear.x**2+t.linear.y**2)
            self.odom_vx  = t.linear.x
            self.odom_vy  = t.linear.y
            self.odom_wz  = t.angular.z
            self.odom_cnt += 1
            if self.odom_cnt == 1:
                self._lg("ok", f"/odom FIRST MSG  frame='{msg.header.frame_id}'")
            if self.odom_cnt % 100 == 0:
                self._lg("data", f"/odom #{self.odom_cnt}: x={p.x:.4f} y={p.y:.4f} yaw={math.degrees(yaw):.2f}°")

def ros_spin(node):
    rclpy.spin(node)

# ── Virtual joystick ──────────────────────────────────────────────────────────
class Joystick:
    def __init__(self, cx, cy, r, x_only=False, color=CYAN):
        self.cx=cx; self.cy=cy; self.r=r
        self.x_only=x_only; self.color=color
        self.nx=0.0; self.ny=0.0
        self.active=False; self._fid=None

    def _ctr(self): return self.cx, self.cy

    def _update(self, px, py):
        dx=px-self.cx; dy=0 if self.x_only else (py-self.cy)
        d=math.sqrt(dx*dx+dy*dy); mr=self.r-self.r//3
        if d>mr: sc=mr/d; dx*=sc; dy*=sc
        self.nx=dx/mr; self.ny=-dy/mr

    def handle(self, ev):
        W,H=pygame.display.get_surface().get_size()
        def fp(e): return int(e.x*W), int(e.y*H)
        def near(pos): dx=pos[0]-self.cx;dy=pos[1]-self.cy;return math.sqrt(dx*dx+dy*dy)<=self.r*1.3
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if near(ev.pos): self.active=True; self._update(*ev.pos)
        elif ev.type==pygame.MOUSEBUTTONUP and ev.button==1:
            self.active=False; self.nx=self.ny=0.0
        elif ev.type==pygame.MOUSEMOTION:
            if self.active: self._update(*ev.pos)
        elif ev.type==pygame.FINGERDOWN:
            p=fp(ev)
            if near(p): self.active=True; self._fid=ev.finger_id; self._update(*p)
        elif ev.type==pygame.FINGERUP:
            if ev.finger_id==self._fid: self.active=False; self._fid=None; self.nx=self.ny=0.0
        elif ev.type==pygame.FINGERMOTION:
            if ev.finger_id==self._fid: self._update(*fp(ev))

    def draw(self, surf):
        mr=self.r-self.r//3
        tx=int(self.cx+self.nx*mr); ty=int(self.cy-self.ny*mr)
        cdim=lerpC(self.color,BG,0.72)
        # outer ring
        pygame.draw.circle(surf, BORDER, (self.cx,self.cy), self.r, 2)
        # guide rings
        pygame.draw.circle(surf, DIM, (self.cx,self.cy), self.r*2//3, 1)
        pygame.draw.circle(surf, DIM, (self.cx,self.cy), self.r//3, 1)
        # crosshair
        pygame.draw.line(surf, DIM, (self.cx-self.r+6,self.cy),(self.cx+self.r-6,self.cy),1)
        if not self.x_only:
            pygame.draw.line(surf, DIM, (self.cx,self.cy-self.r+6),(self.cx,self.cy+self.r-6),1)
        # direction line
        if self.active and (abs(self.nx)>0.02 or abs(self.ny)>0.02):
            pygame.draw.line(surf, cdim, (self.cx,self.cy),(tx,ty),2)
        # thumb
        tr=self.r//3
        col=self.color if self.active else lerpC(self.color,BORDER,0.62)
        pygame.draw.circle(surf, lerpC(col,BG,0.55),(tx,ty), tr)
        pygame.draw.circle(surf, col, (tx,ty), tr, 2)
        pygame.draw.circle(surf, col, (tx,ty), tr//3)
        # center dot
        pygame.draw.circle(surf, MUTED, (self.cx,self.cy), 3)

# ── Helpers ───────────────────────────────────────────────────────────────────
def draw_bar(s, rect, frac, fg, bg=DIM):
    pygame.draw.rect(s, bg,   rect, border_radius=3)
    if frac>0:
        f=pygame.Rect(rect.x,rect.y,max(int(rect.w*min(frac,1.0)),4),rect.h)
        pygame.draw.rect(s, fg, f, border_radius=3)

def lbl(s, fnt, txt, pos, col=MUTED, anchor="topleft"):
    r=fnt.render(str(txt), True, col)
    s.blit(r, r.get_rect(**{anchor:pos}))

def scol(v):
    if v is None: return MUTED
    if v<0.20: return RED
    if v<0.50: return YELLOW
    return GREEN

# ── Trail map ─────────────────────────────────────────────────────────────────
class Trail:
    def __init__(self): self.pts=[]; self.ox=0.0; self.oy=0.0; self.sc=55
    def add(self,x,y):
        self.pts.append((x,y))
        if len(self.pts)>4000: self.pts.pop(0)
    def reset(self,x,y): self.pts.clear(); self.ox=x; self.oy=y
    def w2p(self,x,y,W,H):
        return W//2+int((x-self.ox)*self.sc), H//2-int((y-self.oy)*self.sc)
    def draw(self, surf, rect, rx,ry,ryaw, fnt):
        W,H=rect.w,rect.h
        s=pygame.Surface((W,H))
        s.fill((6,10,14))
        gs=self.sc
        ox0=W//2-int(self.ox*self.sc); oy0=H//2+int(self.oy*self.sc)
        for gx in range(ox0%gs,W,gs): pygame.draw.line(s,DIM,(gx,0),(gx,H),1)
        for gy in range(oy0%gs,H,gs): pygame.draw.line(s,DIM,(0,gy),(W,gy),1)
        x0,y0=self.w2p(0,0,W,H)
        pygame.draw.line(s,CYAN_D,(x0-8,y0),(x0+8,y0),1)
        pygame.draw.line(s,CYAN_D,(x0,y0-8),(x0,y0+8),1)
        if len(self.pts)>1:
            pts2=[self.w2p(x,y,W,H) for x,y in self.pts]
            pygame.draw.lines(s,(0,150,180),False,pts2,2)
        rpx,rpy=self.w2p(rx,ry,W,H)
        al=12; aa=math.pi/2+ryaw
        tip=(int(rpx+al*math.cos(aa)), int(rpy-al*math.sin(aa)))
        l2=(int(rpx+7*math.cos(aa-2.4)), int(rpy-7*math.sin(aa-2.4)))
        l3=(int(rpx+7*math.cos(aa+2.4)), int(rpy-7*math.sin(aa+2.4)))
        if 0<=rpx<W and 0<=rpy<H:
            pygame.draw.polygon(s, ORANGE, [tip,l2,(rpx,rpy),l3])
        surf.blit(s,(rect.x,rect.y))
        pygame.draw.rect(surf,BORDER,rect,1,border_radius=4)

# ── GUI ───────────────────────────────────────────────────────────────────────
class GUI:
    def __init__(self):
        pygame.init()
        self.W, self.H = 1280, 720
        self.screen = pygame.display.set_mode((self.W,self.H), pygame.RESIZABLE)
        pygame.display.set_caption("KIWIBOT — 3-Wheel Omni Teleop")
        self.clock = pygame.time.Clock()

        self.fT = pygame.font.SysFont("monospace",15,bold=True)
        self.fM = pygame.font.SysFont("monospace",14,bold=True)
        self.fS = pygame.font.SysFont("monospace",11)
        self.fX = pygame.font.SysFont("monospace",10)

        self.vx=self.vy=self.wz=0.0
        self.lin_max=0.50; self.ang_max=1.00; self.hz=20
        self.estop=False; self.kdown=set(); self.help=False

        self.node=None
        if ROS_OK:
            try:
                rclpy.init()
                self.node=KiwiNode()
                threading.Thread(target=ros_spin,args=(self.node,),daemon=True).start()
            except Exception as e:
                print(f"[ERR] ROS2 init failed: {e}")

        self.trail=Trail()
        self.log=collections.deque(maxlen=8)
        self._lg("ok",  "KIWIBOT Teleop ready" + ("" if ROS_OK else "  [DEMO — no rclpy]"))
        self._lg("info",f"Wheel angles FL=30° FR=150° BK=270°  L={L}m")
        if not ROS_OK:
            self._lg("warn","source /opt/ros/<distro>/setup.bash  then re-run")

        self.jL=Joystick(0,0,130,x_only=False,color=CYAN)
        self.jR=Joystick(0,0,130,x_only=True, color=ORANGE)
        self._last_pub=time.time()
        self.frame=0

    def _lg(self, lvl, msg):
        self.log.append((time.strftime("%H:%M:%S"),lvl,msg))
        print(f"[{lvl.upper():4}] {msg}")

    def _publish(self):
        now=time.time()
        if now-self._last_pub < 1.0/self.hz: return
        self._last_pub=now
        if self.node and not self.estop:
            self.node.pub_vel(self.vx,self.vy,self.wz)

    def _kbd(self):
        vx=vy=wz=0.0
        if pygame.K_w in self.kdown: vx= self.lin_max
        if pygame.K_s in self.kdown: vx=-self.lin_max
        if pygame.K_a in self.kdown: vy= self.lin_max
        if pygame.K_d in self.kdown: vy=-self.lin_max
        if pygame.K_q in self.kdown: wz= self.ang_max
        if pygame.K_e in self.kdown: wz=-self.ang_max
        return vx,vy,wz

    def _events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return False
            self.jL.handle(ev); self.jR.handle(ev)
            if ev.type==pygame.KEYDOWN:
                self.kdown.add(ev.key)
                if ev.key==pygame.K_SPACE:
                    self.vx=self.vy=self.wz=0.0
                    self._lg("info","SPACE — stop")
                elif ev.key==pygame.K_F1:
                    self.estop=not self.estop
                    if self.estop:
                        self.vx=self.vy=self.wz=0.0
                        if self.node: self.node.pub_vel(0,0,0)
                        self._lg("err","E-STOP ON")
                    else:
                        self._lg("ok","E-STOP OFF")
                elif ev.key==pygame.K_ESCAPE: return False
                elif ev.key==pygame.K_h: self.help=not self.help
                elif ev.key==pygame.K_r:
                    ox=self.node.odom_x if self.node else 0.0
                    oy=self.node.odom_y if self.node else 0.0
                    self.trail.reset(ox,oy); self._lg("info","Trail reset")
                elif ev.key in (pygame.K_EQUALS,pygame.K_PLUS):
                    self.lin_max=min(2.0,round(self.lin_max+0.1,2))
                    self._lg("info",f"Lin max={self.lin_max:.2f} m/s")
                elif ev.key==pygame.K_MINUS:
                    self.lin_max=max(0.1,round(self.lin_max-0.1,2))
                    self._lg("info",f"Lin max={self.lin_max:.2f} m/s")
                elif ev.key==pygame.K_RIGHTBRACKET:
                    self.ang_max=min(3.0,round(self.ang_max+0.1,2))
                    self._lg("info",f"Ang max={self.ang_max:.2f} r/s")
                elif ev.key==pygame.K_LEFTBRACKET:
                    self.ang_max=max(0.1,round(self.ang_max-0.1,2))
                    self._lg("info",f"Ang max={self.ang_max:.2f} r/s")
            elif ev.type==pygame.KEYUP:
                self.kdown.discard(ev.key)
            elif ev.type==pygame.VIDEORESIZE:
                self.W,self.H=ev.w,ev.h
        return True

    # ── draw helpers ──────────────────────────────────────────────────────────
    def _panel(self, x,y,w,h, title, tcol=CYAN, dot_ok=None):
        s=self.screen
        pygame.draw.rect(s,CARD,  (x,y,w,h),border_radius=7)
        pygame.draw.rect(s,BORDER,(x,y,w,h),1,border_radius=7)
        lbl(s,self.fM,title,(x+10,y+7),tcol)
        if dot_ok is not None:
            dc=GREEN if dot_ok else MUTED
            pygame.draw.circle(s,dc,(x+w-12,y+12),4)

    # ── header ────────────────────────────────────────────────────────────────
    def _hdr(self):
        s=self.screen
        pygame.draw.rect(s,SURFACE,(0,0,self.W,44))
        pygame.draw.line(s,BORDER,(0,44),(self.W,44),1)
        lbl(s,self.fT,"KIWIBOT  3-WHEEL OMNI TELEOP",(14,14),CYAN)
        lbl(s,self.fX,"FL=30°  FR=150°  BK=270°",(14,30),MUTED)
        # ROS status
        ros_live=self.node is not None
        dc=GREEN if ros_live else RED
        pygame.draw.circle(s,dc,(self.W//2,22),6)
        lbl(s,self.fS,"ROS2 OK" if ros_live else "NO ROS2 (DEMO)",(self.W//2+12,16),dc)
        if self.node:
            lbl(s,self.fX,f"cmd:{self.node.cmd_cnt}  dis:{self.node.dis_cnt}  odom:{self.node.odom_cnt}",
                (self.W//2+12,28),MUTED)
        # estop
        if self.estop:
            pygame.draw.rect(s,RED_D,(self.W-158,5,144,34),border_radius=5)
            pygame.draw.rect(s,RED,  (self.W-158,5,144,34),2,border_radius=5)
            lbl(s,self.fM,"E-STOP  [F1]",(self.W-86,22),RED,"center")
        else:
            pygame.draw.rect(s,BORDER,(self.W-158,5,144,34),1,border_radius=5)
            lbl(s,self.fX,"F1 = E-STOP",(self.W-86,22),MUTED,"center")

    # ── sensors panel ─────────────────────────────────────────────────────────
    def _sensors(self):
        s=self.screen
        px,py,pw,ph=10,54,228,310
        dis_ok=self.node and self.node.dis_cnt>0
        self._panel(px,py,pw,ph,"/dis_data",ORANGE,dis_ok)
        dist=self.node.dist if self.node else [None]*4

        # Mini robot diagram
        dcx,dcy=px+pw//2, py+120
        pygame.draw.rect(s,SURFACE,(dcx-28,dcy-32,56,62),border_radius=5)
        pygame.draw.rect(s,BORDER, (dcx-28,dcy-32,56,62),1,border_radius=5)
        lbl(s,self.fX,"KIWI",(dcx,dcy),MUTED,"center")
        for deg in [30,150,270]:
            r=math.radians(deg)
            wx=int(dcx+40*math.sin(r)); wy=int(dcy-40*math.cos(r))
            pygame.draw.circle(s,MUTED,(wx,wy),5)
            pygame.draw.circle(s,BORDER,(wx,wy),5,1)

        # Sensor values around robot
        spos=[(dcx-66,dcy,"L",dist[0]),(dcx+66,dcy,"R",dist[1]),
              (dcx+18,dcy-64,"FL",dist[2]),(dcx-18,dcy-64,"FR",dist[3])]
        for sx,sy,sl,v in spos:
            col=scol(v)
            lbl(s,self.fX,sl,(sx,sy-8),MUTED,"center")
            lbl(s,self.fS,f"{v:.2f}" if v is not None else "--.-",(sx,sy+2),col,"center")

        # Bars
        by=py+200; SMAX=4.0
        for nm,v in zip(["LEFT","RGHT","F-LT","F-RT"],dist):
            lbl(s,self.fX,nm,(px+10,by+2),MUTED)
            br=pygame.Rect(px+48,by,pw-92,11)
            draw_bar(s,br,min(v/SMAX,1.0) if v else 0.0, scol(v))
            lbl(s,self.fX,f"{v:.3f}m" if v else "  ---",(px+pw-8,by+1),scol(v),"topright")
            by+=28

    # ── odom panel ────────────────────────────────────────────────────────────
    def _odom(self):
        s=self.screen
        px,py,pw,ph=self.W-238,54,228,310
        odom_ok=self.node and self.node.odom_cnt>0
        self._panel(px,py,pw,ph,"/odom",CYAN,odom_ok)
        if self.node:
            ox,oy=self.node.odom_x,self.node.odom_y
            yaw=self.node.odom_yaw; spd=self.node.odom_spd
            tvx,tvy,twz=self.node.odom_vx,self.node.odom_vy,self.node.odom_wz
        else:
            ox=oy=yaw=spd=tvx=tvy=twz=0.0

        rows=[("pos.x", f"{ox:+.5f} m",  CYAN),
              ("pos.y", f"{oy:+.5f} m",  CYAN),
              ("yaw",   f"{math.degrees(yaw):+.3f}°", ORANGE),
              ("speed", f"{spd:+.5f} m/s",GREEN),
              ("vel.x", f"{tvx:+.5f}",   TEXT),
              ("vel.y", f"{tvy:+.5f}",   TEXT),
              ("ang.z", f"{twz:+.5f}",   TEXT)]
        ry=py+28
        for lab,val,col in rows:
            lbl(s,self.fX,lab,(px+10,ry),MUTED)
            lbl(s,self.fS,val,(px+pw-8,ry),col,"topright")
            ry+=20

        # Trail map
        trect=pygame.Rect(px+5,ry+4,pw-10,140)
        lbl(s,self.fX,"R=reset map",(px+pw-8,ry-1),MUTED,"topright")
        if self.node: self.trail.add(ox,oy)
        self.trail.draw(s,trect,ox,oy,yaw,self.fX)

    # ── joysticks ─────────────────────────────────────────────────────────────
    def _joysticks(self):
        s=self.screen
        cx=self.W//2
        jcy=min(self.H-250, 430)
        self.jL.cx=cx-200; self.jL.cy=jcy
        self.jR.cx=cx+200; self.jR.cy=jcy
        # labels
        lbl(s,self.fM,"MOVE  —  Vx / Vy",(cx-200,62),CYAN,"center")
        lbl(s,self.fX,"W/S=fwd  A/D=strafe",(cx-200,78),MUTED,"center")
        lbl(s,self.fM,"ROTATE  —  Wz",(cx+200,62),ORANGE,"center")
        lbl(s,self.fX,"Q=CCW  E=CW",(cx+200,78),MUTED,"center")
        self.jL.draw(s); self.jR.draw(s)
        # readouts under joysticks
        uy=jcy+self.jL.r+14
        lbl(s,self.fX,"Vx",(cx-244,uy),MUTED)
        lbl(s,self.fM,f"{self.vx:+.5f}",(cx-200,uy+10),CYAN,"center")
        lbl(s,self.fX,"Vy",(cx-244,uy+26),MUTED)
        lbl(s,self.fM,f"{self.vy:+.5f}",(cx-200,uy+36),CYAN,"center")
        lbl(s,self.fX,"Wz",(cx+156,uy),MUTED)
        lbl(s,self.fM,f"{self.wz:+.5f}",(cx+200,uy+10),ORANGE,"center")

    # ── cmd_vel box ───────────────────────────────────────────────────────────
    def _cmdvel(self):
        s=self.screen
        cx=self.W//2; py=self.H-195; pw=370; ph=65
        px=cx-pw//2
        cmd_ok=self.node and self.node.cmd_cnt>0
        self._panel(px,py,pw,ph,"/cmd_vel  published",CYAN,cmd_ok)
        vals=[("linear.x",f"{self.vx:+.5f}",CYAN),
              ("linear.y",f"{self.vy:+.5f}",CYAN),
              ("angular.z",f"{self.wz:+.5f}",ORANGE)]
        cw=pw//3
        for i,(lab,val,col) in enumerate(vals):
            cx2=px+cw*i+cw//2
            lbl(s,self.fX,lab,(cx2,py+24),MUTED,"center")
            lbl(s,self.fM,val,(cx2,py+38),col,"center")

    # ── wheel bars ────────────────────────────────────────────────────────────
    def _wheels(self):
        s=self.screen
        cx=self.W//2; by=self.H-118
        ws=wheel_speeds(self.vx,self.vy,self.wz)
        mx=max(abs(w) for w in ws) or 0.001
        for i,(w,nm) in enumerate(zip(ws,WNAMES)):
            bx=cx-138+i*95
            lbl(s,self.fX,nm,(bx+44,by),MUTED,"center")
            lbl(s,self.fS,f"{w:+.2f}",(bx+44,by+13),CYAN if w>=0 else ORANGE,"center")
            draw_bar(s,pygame.Rect(bx,by+27,88,12),abs(w)/mx,CYAN if w>=0 else ORANGE)

    # ── speed info ────────────────────────────────────────────────────────────
    def _speeds(self):
        s=self.screen; cx=self.W//2; py=self.H-58
        lbl(s,self.fX,f"+/- Lin:{self.lin_max:.2f}m/s  [/] Ang:{self.ang_max:.2f}r/s  Hz:{self.hz}",(cx,py),MUTED,"center")
        lbl(s,self.fX,"H=help  R=reset-map  F1=estop  ESC=quit",(cx,py+14),MUTED,"center")

    # ── debug log ─────────────────────────────────────────────────────────────
    def _logpanel(self):
        s=self.screen
        cx=self.W//2; py=self.H-195; pw=370; px=cx-pw//2
        logy=py+70; logh=70
        pygame.draw.rect(s,SURFACE,(px,logy,pw,logh),border_radius=5)
        pygame.draw.rect(s,BORDER, (px,logy,pw,logh),1,border_radius=5)
        lbl(s,self.fX,"DEBUG LOG",(px+8,logy+3),MUTED)
        COL={"ok":GREEN,"info":CYAN,"warn":YELLOW,"err":RED,"data":MUTED}
        all_log=list(self.node.log)[-6:] if self.node else list(self.log)
        for j,entry in enumerate(all_log[-6:]):
            ts,lvl,msg=entry
            ly=logy+14+j*9
            col=COL.get(lvl,TEXT)
            lbl(s,self.fX,f"[{ts}] {lvl.upper():4}  {msg}",(px+8,ly),col)

    # ── help overlay ──────────────────────────────────────────────────────────
    def _helpov(self):
        s=self.screen
        ow,oh=440,290; ox=(self.W-ow)//2; oy=(self.H-oh)//2
        pygame.draw.rect(s,(12,18,26),(ox,oy,ow,oh),border_radius=10)
        pygame.draw.rect(s,CYAN,(ox,oy,ow,oh),2,border_radius=10)
        lbl(s,self.fT,"KEYBOARD CONTROLS",(ox+ow//2,oy+12),CYAN,"center")
        items=[("W/S","Forward / Back"),("A/D","Strafe L / R"),
               ("Q/E","Rotate CCW / CW"),("SPACE","Stop"),
               ("F1","E-Stop toggle"),
               ("+/-","Linear speed"),("[/]","Angular speed"),
               ("R","Reset trail"),("H","This help"),("ESC","Quit")]
        for i,(k,v) in enumerate(items):
            iy=oy+40+i*23
            lbl(s,self.fM,k,(ox+18,iy),YELLOW)
            lbl(s,self.fS,v,(ox+155,iy+1),TEXT)

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        running=True
        while running:
            running=self._events()
            self.frame+=1
            # velocity from joystick or keyboard
            if self.jL.active or self.jR.active:
                self.vx=  self.jL.ny*self.lin_max
                self.vy= -self.jL.nx*self.lin_max
                self.wz=  self.jR.nx*self.ang_max
            else:
                self.vx,self.vy,self.wz=self._kbd()
            if self.estop: self.vx=self.vy=self.wz=0.0
            self._publish()

            self.screen.fill(BG)
            self._hdr()
            self._sensors()
            self._odom()
            self._joysticks()
            self._cmdvel()
            self._wheels()
            self._logpanel()
            self._speeds()
            if self.help: self._helpov()

            pygame.display.flip()
            self.clock.tick(60)

        if self.node:
            self.node.pub_vel(0,0,0)
            self.node.destroy_node()
        if ROS_OK and rclpy.ok(): rclpy.shutdown()
        pygame.quit(); sys.exit(0)

if __name__=="__main__":
    GUI().run()
