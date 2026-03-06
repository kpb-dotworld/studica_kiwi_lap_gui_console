<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>KIWI — Dual Joystick</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
:root{--bg:#080b0f;--surface:#0d1117;--card:#111820;--border:#1c2a38;--border2:#243344;--cyan:#00d4ff;--orange:#ff7b35;--green:#2dff8a;--yellow:#ffd600;--red:#ff2d55;--muted:#3a5268;--text:#b8ccd8;}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{width:100%;height:100%;background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;overflow:hidden;touch-action:none;}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:999;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.05) 2px,rgba(0,0,0,0.05) 4px);}

/* HEADER */
header{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;border-bottom:1px solid var(--border);background:rgba(13,17,23,0.97);z-index:10;gap:10px;}
.logo{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:.95rem;letter-spacing:.2em;color:var(--cyan);white-space:nowrap;}
.logo em{color:var(--orange);font-style:normal;}
.hdr-c{display:flex;gap:6px;align-items:center;flex:1;justify-content:center;}
.ci{background:var(--surface);border:1px solid var(--border2);color:var(--text);font-family:'JetBrains Mono',monospace;font-size:.72rem;padding:4px 10px;border-radius:4px;outline:none;width:200px;}
.ci:focus{border-color:var(--cyan);}
.hbtn{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;padding:4px 12px;border-radius:4px;cursor:pointer;border:1px solid var(--cyan);color:var(--cyan);background:transparent;transition:all .15s;white-space:nowrap;}
.hbtn:hover{background:var(--cyan);color:var(--bg);}
.hbtn.disc{border-color:var(--muted);color:var(--muted);}
.hbtn.disc:hover{background:var(--red);border-color:var(--red);color:#fff;}
.hdr-r{display:flex;gap:10px;align-items:center;}
.ind{display:flex;align-items:center;gap:5px;}
.dot{width:8px;height:8px;border-radius:50%;background:var(--red);box-shadow:0 0 6px var(--red);transition:all .3s;flex-shrink:0;}
.dot.live{background:var(--green);box-shadow:0 0 10px var(--green);animation:pulse 1.8s infinite;}
.dot.connecting{background:var(--yellow);box-shadow:0 0 8px var(--yellow);animation:blink .5s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.ind-lbl{font-size:.65rem;color:var(--muted);letter-spacing:.08em;font-family:'JetBrains Mono',monospace;white-space:nowrap;}
.estop{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:.68rem;letter-spacing:.1em;padding:4px 12px;border-radius:4px;cursor:pointer;border:1px solid var(--red);color:var(--red);background:rgba(255,45,85,.08);transition:all .15s;white-space:nowrap;}
.estop:hover,.estop.active{background:var(--red);color:#fff;box-shadow:0 0 16px rgba(255,45,85,.5);}

/* LAYOUT */
.layout{display:grid;grid-template-columns:240px 1fr 240px;grid-template-rows:1fr auto;height:calc(100vh - 48px);}
.side{display:flex;flex-direction:column;gap:8px;padding:10px;border-right:1px solid var(--border);overflow-y:auto;}
.side.r{border-right:none;border-left:1px solid var(--border);}
.pc{background:var(--card);border:1px solid var(--border);border-radius:7px;overflow:hidden;}
.pch{display:flex;align-items:center;justify-content:space-between;padding:5px 10px;border-bottom:1px solid var(--border);background:rgba(0,0,0,.25);}
.pct{font-size:.58rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--cyan);font-family:'JetBrains Mono',monospace;}
.pct.orange{color:var(--orange);}
.topic-dot{width:6px;height:6px;border-radius:50%;background:var(--muted);flex-shrink:0;transition:all .3s;}
.topic-dot.ok{background:var(--green);box-shadow:0 0 6px var(--green);}
.topic-dot.err{background:var(--red);box-shadow:0 0 6px var(--red);}
.pcb{padding:8px 10px;}

/* SENSOR */
.sdiag{position:relative;width:150px;height:150px;margin:0 auto 8px;}
.rchass{position:absolute;width:76px;height:76px;top:50%;left:50%;transform:translate(-50%,-50%);background:linear-gradient(145deg,#151f2e,#0a1018);border:1px solid var(--border2);border-radius:6px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:2px;}
.rclbl{font-family:'JetBrains Mono',monospace;font-size:.48rem;color:var(--muted);letter-spacing:.1em;}
.wdot{position:absolute;width:9px;height:16px;background:var(--border2);border-radius:3px;}
.wfl{top:7px;right:20px;transform:rotate(30deg);}
.wfr{top:7px;left:20px;transform:rotate(-30deg);}
.wbk{bottom:7px;left:50%;transform:translateX(-50%) rotate(90deg);}
.sind{position:absolute;display:flex;align-items:center;gap:3px;}
.sind.sleft{left:0;top:50%;transform:translateY(-50%);flex-direction:row;}
.sind.sright{right:0;top:50%;transform:translateY(-50%);flex-direction:row-reverse;}
.sind.sfl{top:4px;right:8px;flex-direction:column;align-items:center;}
.sind.sfr{top:4px;left:8px;flex-direction:column;align-items:center;}
.sbadge{width:20px;height:9px;background:var(--surface);border:1px solid var(--orange);border-radius:2px;display:flex;align-items:center;justify-content:center;font-size:.36rem;color:var(--orange);font-family:'JetBrains Mono',monospace;}
.sv{font-family:'JetBrains Mono',monospace;font-size:.58rem;font-weight:700;color:var(--muted);white-space:nowrap;line-height:1;}
.sv.ok{color:var(--green);}.sv.w{color:var(--yellow);}.sv.d{color:var(--red);}
.sbrw{display:flex;align-items:center;gap:5px;margin-bottom:4px;}
.sbn{font-size:.55rem;color:var(--muted);width:26px;font-family:'JetBrains Mono',monospace;}
.sbt{flex:1;height:5px;background:rgba(0,0,0,.4);border-radius:3px;overflow:hidden;}
.sbf{height:100%;width:0%;background:var(--muted);border-radius:3px;transition:width .15s,background .2s;}
.sbf.ok{background:var(--green);}.sbf.w{background:var(--yellow);}.sbf.d{background:var(--red);}
.sbnum{font-family:'JetBrains Mono',monospace;font-size:.55rem;color:var(--text);width:42px;text-align:right;}

/* CMD_VEL */
.cvrow{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-bottom:7px;}
.oval{background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:5px;padding:5px 7px;}
.ovl{font-size:.5rem;color:var(--muted);letter-spacing:.08em;margin-bottom:2px;font-family:'JetBrains Mono',monospace;}
.ovn{font-family:'JetBrains Mono',monospace;font-size:.75rem;font-weight:700;color:var(--cyan);}
.oval.hi .ovn{color:var(--orange);}
.slrow{display:flex;align-items:center;gap:5px;margin-bottom:3px;}
.slnm{font-size:.5rem;color:var(--muted);width:52px;font-family:'JetBrains Mono',monospace;}
.slrow input[type=range]{flex:1;accent-color:var(--cyan);}
.slval{font-family:'JetBrains Mono',monospace;font-size:.55rem;color:var(--text);width:34px;text-align:right;}

/* ODOM */
.ovals{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:7px;}
.mwrap{position:relative;}
canvas#tmap{display:block;width:100%;background:#060a0e;border:1px solid var(--border);border-radius:5px;}
.mreset{position:absolute;top:4px;right:4px;font-family:'JetBrains Mono',monospace;font-size:.52rem;padding:2px 6px;border-radius:3px;background:rgba(8,11,15,.85);border:1px solid var(--border2);color:var(--muted);cursor:pointer;}
.mreset:hover{color:var(--cyan);border-color:var(--cyan);}

/* CENTER */
.center{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:14px;background:var(--surface);position:relative;}
.ksch{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:120px;height:120px;opacity:.055;pointer-events:none;}
.jrow{display:flex;gap:36px;align-items:flex-start;z-index:1;}
.jw{display:flex;flex-direction:column;align-items:center;gap:8px;}
.jlbl{font-family:'JetBrains Mono',monospace;font-size:.6rem;text-transform:uppercase;letter-spacing:.16em;}
.jlbl.m{color:var(--cyan);text-shadow:0 0 10px rgba(0,212,255,.4);}
.jlbl.r{color:var(--orange);text-shadow:0 0 10px rgba(255,123,53,.4);}
.jo{width:190px;height:190px;border-radius:50%;background:radial-gradient(circle at 40% 35%,#121e2c 0%,#080c12 70%);border:2px solid var(--border2);position:relative;cursor:grab;touch-action:none;box-shadow:0 4px 40px rgba(0,0,0,.6);transition:border-color .2s;}
.jo.m{border-color:rgba(0,212,255,.28);}
.jo.r{border-color:rgba(255,123,53,.28);}
.jo.m.drag{border-color:var(--cyan);box-shadow:0 0 28px rgba(0,212,255,.18);}
.jo.r.drag{border-color:var(--orange);box-shadow:0 0 28px rgba(255,123,53,.18);}
.jr1,.jr2{position:absolute;border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;}
.jo.m .jr1{width:66%;height:66%;border:1px dashed rgba(0,212,255,.1);}
.jo.m .jr2{width:33%;height:33%;border:1px dashed rgba(0,212,255,.07);}
.jo.r .jr1{width:66%;height:66%;border:1px dashed rgba(255,123,53,.1);}
.jo.r .jr2{width:33%;height:33%;border:1px dashed rgba(255,123,53,.07);}
.jch,.jcv{position:absolute;pointer-events:none;top:50%;left:50%;transform:translate(-50%,-50%);}
.jo.m .jch{width:90%;height:1px;background:rgba(0,212,255,.07);}
.jo.m .jcv{width:1px;height:90%;background:rgba(0,212,255,.07);}
.jo.r .jch{width:90%;height:1px;background:rgba(255,123,53,.07);}
.jo.r .jcv{width:1px;height:90%;background:rgba(255,123,53,.07);}
.jcd{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:5px;height:5px;border-radius:50%;pointer-events:none;}
.jo.m .jcd{background:rgba(0,212,255,.28);}
.jo.r .jcd{background:rgba(255,123,53,.28);}
.jt{position:absolute;width:64px;height:64px;border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;display:flex;align-items:center;justify-content:center;}
.jo.m .jt{background:radial-gradient(circle at 35% 30%,#1c3850,#0a1a28);border:2px solid rgba(0,212,255,.55);box-shadow:0 2px 12px rgba(0,0,0,.5);}
.jo.r .jt{background:radial-gradient(circle at 35% 30%,#3a1c0a,#1a0c04);border:2px solid rgba(255,123,53,.55);box-shadow:0 2px 12px rgba(0,0,0,.5);}
.jo.m.drag .jt{box-shadow:0 0 18px rgba(0,212,255,.4);}
.jo.r.drag .jt{box-shadow:0 0 18px rgba(255,123,53,.4);}
.tp{width:18px;height:18px;border-radius:50%;}
.jo.m .tp{background:radial-gradient(circle at 35% 30%,rgba(0,212,255,.55),rgba(0,100,160,.25));border:1px solid rgba(0,212,255,.38);}
.jo.r .tp{background:radial-gradient(circle at 35% 30%,rgba(255,123,53,.55),rgba(160,60,10,.25));border:1px solid rgba(255,123,53,.38);}
.jro{display:grid;gap:4px;width:190px;}
.jro.m{grid-template-columns:1fr 1fr;}
.jro.r{grid-template-columns:1fr;}
.jrb{background:rgba(0,0,0,.35);border:1px solid var(--border);border-radius:4px;padding:4px 7px;text-align:center;}
.jrl{font-size:.5rem;color:var(--muted);letter-spacing:.08em;margin-bottom:1px;font-family:'JetBrains Mono',monospace;}
.jrv{font-family:'JetBrains Mono',monospace;font-size:.75rem;font-weight:700;}
.jrv.c{color:var(--cyan);}.jrv.o{color:var(--orange);}
.wfrow{display:flex;gap:8px;align-items:center;z-index:1;}
.wfc{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:7px 10px;text-align:center;min-width:70px;}
.wfn{font-size:.52rem;color:var(--muted);letter-spacing:.08em;margin-bottom:3px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;}
.wfv{font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:700;color:var(--green);}
.wfbw{height:4px;background:rgba(0,0,0,.4);border-radius:2px;margin-top:3px;overflow:hidden;}
.wfb{height:100%;border-radius:2px;transition:width .1s,background .1s;}

/* DEBUG LOG PANEL */
.logpanel{grid-column:1/-1;height:120px;display:flex;flex-direction:column;border-top:1px solid var(--border);background:rgba(5,8,12,0.98);}
.logpanel-hdr{display:flex;align-items:center;justify-content:space-between;padding:4px 12px;border-bottom:1px solid var(--border);flex-shrink:0;}
.lph-title{font-family:'JetBrains Mono',monospace;font-size:.58rem;color:var(--cyan);letter-spacing:.15em;text-transform:uppercase;}
.lph-right{display:flex;gap:8px;align-items:center;}
.log-clear{font-family:'JetBrains Mono',monospace;font-size:.52rem;padding:2px 7px;border-radius:3px;background:transparent;border:1px solid var(--border2);color:var(--muted);cursor:pointer;}
.log-clear:hover{color:var(--red);border-color:var(--red);}
.logbody{flex:1;overflow-y:auto;padding:4px 10px;font-family:'JetBrains Mono',monospace;font-size:.6rem;line-height:1.65;}
.logbody::-webkit-scrollbar{width:4px;}
.logbody::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px;}
.le{display:flex;gap:8px;align-items:baseline;padding:1px 0;}
.le-ts{color:var(--muted);white-space:nowrap;flex-shrink:0;font-size:.55rem;}
.le-lvl{white-space:nowrap;flex-shrink:0;font-size:.58rem;font-weight:700;width:38px;}
.le-msg{color:var(--text);}
.le.info .le-lvl{color:var(--cyan);}
.le.ok   .le-lvl,.le.ok   .le-msg{color:var(--green);}
.le.warn .le-lvl,.le.warn .le-msg{color:var(--yellow);}
.le.err  .le-lvl,.le.err  .le-msg{color:var(--red);}
.le.data .le-lvl{color:var(--muted);}
.le.data .le-msg{color:rgba(184,204,216,.55);}

::-webkit-scrollbar{width:4px;}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px;}
</style>
</head>
<body>
<header>
  <div class="logo">KIWI<em>BOT</em></div>
  <div class="hdr-c">
    <input class="ci" id="wsurl" value="ws://localhost:9090" placeholder="ws://ROBOT_IP:9090">
    <button class="hbtn" id="cbtn" onclick="toggleConn()">CONNECT</button>
  </div>
  <div class="hdr-r">
    <div class="ind"><div class="dot" id="dot"></div><span class="ind-lbl" id="clbl">OFFLINE</span></div>
    <button class="estop" id="estop" onclick="eStop()">&#x2B21; E-STOP</button>
  </div>
</header>

<div class="layout">

  <!-- LEFT SIDE -->
  <div class="side">

    <!-- Sensors -->
    <div class="pc">
      <div class="pch">
        <span class="pct orange">&#x25C8; /dis_data</span>
        <div class="topic-dot" id="td-dis" title="/dis_data status"></div>
      </div>
      <div class="pcb">
        <div class="sdiag">
          <div class="rchass">
            <div class="wdot wfl"></div><div class="wdot wfr"></div><div class="wdot wbk"></div>
            <div class="rclbl">KIWI</div>
          </div>
          <div class="sind sleft"><div class="sbadge">US</div><div class="sv" id="sv-l">--</div></div>
          <div class="sind sright"><div class="sbadge">US</div><div class="sv" id="sv-r">--</div></div>
          <div class="sind sfl"><div class="sbadge">US</div><div class="sv" id="sv-fl">--</div></div>
          <div class="sind sfr"><div class="sbadge">US</div><div class="sv" id="sv-fr">--</div></div>
        </div>
        <div class="sbrw"><span class="sbn">LEFT</span><div class="sbt"><div class="sbf" id="sb-l"></div></div><span class="sbnum" id="sn-l">---</span></div>
        <div class="sbrw"><span class="sbn">RGHT</span><div class="sbt"><div class="sbf" id="sb-r"></div></div><span class="sbnum" id="sn-r">---</span></div>
        <div class="sbrw"><span class="sbn">F-LT</span><div class="sbt"><div class="sbf" id="sb-fl"></div></div><span class="sbnum" id="sn-fl">---</span></div>
        <div class="sbrw"><span class="sbn">F-RT</span><div class="sbt"><div class="sbf" id="sb-fr"></div></div><span class="sbnum" id="sn-fr">---</span></div>
      </div>
    </div>

    <!-- cmd_vel -->
    <div class="pc">
      <div class="pch">
        <span class="pct">&#x25B8; /cmd_vel</span>
        <div class="topic-dot" id="td-cmd" title="/cmd_vel pub status"></div>
      </div>
      <div class="pcb">
        <div class="cvrow">
          <div class="oval"><div class="ovl">lin.x</div><div class="ovn" id="cv-lx">+0.00000</div></div>
          <div class="oval"><div class="ovl">lin.y</div><div class="ovn" id="cv-ly">+0.00000</div></div>
          <div class="oval hi"><div class="ovl">ang.z</div><div class="ovn" id="cv-az">+0.00000</div></div>
        </div>
        <div class="slrow"><span class="slnm">LIN m/s</span><input type="range" id="ls" min="0.05" max="2" step="0.05" value="0.5"><span class="slval" id="lsv">0.50</span></div>
        <div class="slrow"><span class="slnm">ANG r/s</span><input type="range" id="as" min="0.05" max="3" step="0.05" value="1.0" style="accent-color:var(--orange)"><span class="slval" id="asv">1.00</span></div>
        <div class="slrow"><span class="slnm">PUB Hz</span><input type="range" id="hz" min="5" max="50" step="5" value="20" style="accent-color:var(--green)"><span class="slval" id="hzv">20</span></div>
      </div>
    </div>

  </div><!-- /left -->

  <!-- CENTER -->
  <div class="center">
    <svg class="ksch" viewBox="0 0 120 120" fill="none" stroke="rgba(0,212,255,1)" stroke-width="1.5">
      <circle cx="60" cy="60" r="55"/><circle cx="60" cy="60" r="35"/>
      <line x1="60" y1="60" x2="60" y2="5"/>
      <line x1="60" y1="60" x2="107" y2="82"/>
      <line x1="60" y1="60" x2="13" y2="82"/>
    </svg>

    <div class="jrow">
      <div class="jw">
        <div class="jlbl m">MOVE &nbsp; Vx / Vy</div>
        <div class="jo m" id="jL">
          <div class="jr1"></div><div class="jr2"></div>
          <div class="jch"></div><div class="jcv"></div>
          <div class="jcd"></div>
          <div class="jt" id="jLt"><div class="tp"></div></div>
        </div>
        <div class="jro m">
          <div class="jrb"><div class="jrl">Vx fwd</div><div class="jrv c" id="jLx">+0.00000</div></div>
          <div class="jrb"><div class="jrl">Vy str</div><div class="jrv c" id="jLy">+0.00000</div></div>
        </div>
      </div>

      <div class="jw">
        <div class="jlbl r">ROTATE &nbsp; Wz</div>
        <div class="jo r" id="jR">
          <div class="jr1"></div><div class="jr2"></div>
          <div class="jch"></div><div class="jcv"></div>
          <div class="jcd"></div>
          <div class="jt" id="jRt"><div class="tp"></div></div>
        </div>
        <div class="jro r">
          <div class="jrb"><div class="jrl">Wz angular</div><div class="jrv o" id="jRz">+0.00000</div></div>
        </div>
      </div>
    </div>

    <div class="wfrow">
      <div class="wfc"><div class="wfn">FL wheel<br><span style="font-size:.45rem;color:#2a3e50">30 deg</span></div><div class="wfv" id="wf-fl">+0.00</div><div class="wfbw"><div class="wfb" id="wb-fl" style="width:50%;background:var(--cyan)"></div></div></div>
      <div class="wfc"><div class="wfn">FR wheel<br><span style="font-size:.45rem;color:#2a3e50">150 deg</span></div><div class="wfv" id="wf-fr">+0.00</div><div class="wfbw"><div class="wfb" id="wb-fr" style="width:50%;background:var(--cyan)"></div></div></div>
      <div class="wfc"><div class="wfn">BACK<br><span style="font-size:.45rem;color:#2a3e50">270 deg</span></div><div class="wfv" id="wf-bk">+0.00</div><div class="wfbw"><div class="wfb" id="wb-bk" style="width:50%;background:var(--cyan)"></div></div></div>
    </div>
  </div>

  <!-- RIGHT: Odom -->
  <div class="side r">
    <div class="pc">
      <div class="pch">
        <span class="pct">&#x229E; /odom</span>
        <div class="topic-dot" id="td-odom" title="/odom status"></div>
      </div>
      <div class="pcb">
        <div class="ovals">
          <div class="oval"><div class="ovl">pos.x (m)</div><div class="ovn" id="ox">+0.00000</div></div>
          <div class="oval"><div class="ovl">pos.y (m)</div><div class="ovn" id="oy">+0.00000</div></div>
          <div class="oval hi"><div class="ovl">yaw (deg)</div><div class="ovn" id="oyaw">+0.000</div></div>
          <div class="oval"><div class="ovl">spd m/s</div><div class="ovn" id="ospd">+0.00000</div></div>
          <div class="oval"><div class="ovl">twist.vx</div><div class="ovn" id="ovx">+0.00000</div></div>
          <div class="oval"><div class="ovl">twist.vy</div><div class="ovn" id="ovy">+0.00000</div></div>
        </div>
        <div class="mwrap">
          <canvas id="tmap" width="210" height="155"></canvas>
          <button class="mreset" onclick="resetTrail()">CLR</button>
        </div>
      </div>
    </div>
  </div>

  <!-- DEBUG LOG -->
  <div class="logpanel">
    <div class="logpanel-hdr">
      <span class="lph-title">&#x25B6; DEBUG LOG</span>
      <div class="lph-right">
        <span id="msg-count" style="font-family:'JetBrains Mono',monospace;font-size:.52rem;color:var(--muted);">0 msgs</span>
        <button class="log-clear" onclick="clearLog()">CLEAR</button>
      </div>
    </div>
    <div class="logbody" id="logbody"></div>
  </div>

</div><!-- /layout -->

<script>
// ════════════════════════════════════════════════════
//  STATE
// ════════════════════════════════════════════════════
var ros=null, pub=null, disSub=null, odomSub=null;
var connected=false, estopped=false;
var linMax=0.5, angMax=1.0, pubHz=20;
var vx=0, vy=0, wz=0;
var ptimer=null;
var trail=[], tcx=0, tcy=0, tscale=55;
var ox=0, oy=0, oyaw=0;
var msgCount={dis:0, odom:0, cmd:0};
var disActive=false, odomActive=false;

// ════════════════════════════════════════════════════
//  DEBUG LOG
// ════════════════════════════════════════════════════
var logEntries=0;
function log(msg, level){
  level = level||'info';
  var body=document.getElementById('logbody');
  var now=new Date();
  var ts=now.toLocaleTimeString('en-GB',{hour12:false})+'.'+String(now.getMilliseconds()).padStart(3,'0');
  var row=document.createElement('div');
  row.className='le '+level;
  var lvlText={info:'INFO',ok:'OK',warn:'WARN',err:'ERROR',data:'DATA'}[level]||'INFO';
  row.innerHTML='<span class="le-ts">'+ts+'</span><span class="le-lvl">'+lvlText+'</span><span class="le-msg">'+msg+'</span>';
  body.appendChild(row);
  body.scrollTop=body.scrollHeight;
  logEntries++;
  if(logEntries>300){body.removeChild(body.firstChild);logEntries--;}
  document.getElementById('msg-count').textContent=logEntries+' msgs';
}
function clearLog(){
  document.getElementById('logbody').innerHTML='';
  logEntries=0;
  document.getElementById('msg-count').textContent='0 msgs';
  log('Log cleared','info');
}

// ════════════════════════════════════════════════════
//  JOYSTICK
// ════════════════════════════════════════════════════
function Joystick(elId, thumbId, xOnly){
  var el=document.getElementById(elId);
  var th=document.getElementById(thumbId);
  this.nx=0; this.ny=0;
  var active=false, MAXR=70, self=this;
  function ctr(){var r=el.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2};}
  function start(e){e.preventDefault();el.setPointerCapture(e.pointerId);active=true;el.classList.add('drag');move(e);}
  function move(e){
    if(!active)return;e.preventDefault();
    var c=ctr(),dx=e.clientX-c.x,dy=xOnly?0:(e.clientY-c.y);
    var dist=Math.sqrt(dx*dx+dy*dy),cl=Math.min(dist,MAXR),ang=Math.atan2(dy,dx);
    var cx=Math.cos(ang)*cl,cy=Math.sin(ang)*cl;
    self.nx=cx/MAXR; self.ny=-cy/MAXR;
    th.style.left=(50+(cx/(el.offsetWidth/2))*50)+'%';
    th.style.top=(50+(cy/(el.offsetHeight/2))*50)+'%';
  }
  function end(e){active=false;self.nx=0;self.ny=0;el.classList.remove('drag');th.style.left='50%';th.style.top='50%';}
  el.addEventListener('pointerdown',start,{passive:false});
  el.addEventListener('pointermove',move,{passive:false});
  el.addEventListener('pointerup',end);
  el.addEventListener('pointercancel',end);
}
var jL=new Joystick('jL','jLt',false);
var jR=new Joystick('jR','jRt',true);

// ════════════════════════════════════════════════════
//  ROSLIB LOADER — wait for library to be ready
// ════════════════════════════════════════════════════
function waitForROSLIB(cb){
  if(typeof ROSLIB !== 'undefined'){
    log('roslibjs loaded OK (v'+ROSLIB.VERSION+')','ok');
    cb();
  } else {
    log('Waiting for roslibjs to load...','warn');
    setTimeout(function(){waitForROSLIB(cb);},300);
  }
}

// ════════════════════════════════════════════════════
//  CONNECTION
// ════════════════════════════════════════════════════
function toggleConn(){connected?disconnect():connect();}

function connect(){
  if(typeof ROSLIB==='undefined'){
    log('roslibjs not loaded yet — cannot connect','err');
    return;
  }
  var url=document.getElementById('wsurl').value.trim();
  if(!url.startsWith('ws://')&&!url.startsWith('wss://')){
    log('URL must start with ws:// or wss://  Got: '+url,'err');
    return;
  }
  log('Attempting WebSocket connection to: '+url,'info');
  log('Make sure rosbridge is running:  ros2 launch rosbridge_server rosbridge_websocket_launch.xml','warn');
  setDot('connecting');

  try{
    ros=new ROSLIB.Ros({url:url});
  }catch(e){
    log('ROSLIB.Ros() threw: '+e.message,'err');
    setDot('offline'); return;
  }

  ros.on('connection',function(){
    connected=true;
    setDot('online');
    log('WebSocket CONNECTED to '+url,'ok');
    log('rosbridge handshake complete','ok');
    setupTopics();
    startLoop();
  });

  ros.on('error',function(e){
    log('WebSocket ERROR: '+String(e),'err');
    log('Check: (1) rosbridge running? (2) IP correct? (3) firewall/port 9090 open?','warn');
    setDot('offline');
  });

  ros.on('close',function(){
    connected=false;
    setDot('offline');
    log('WebSocket connection CLOSED','warn');
    stopLoop();
    setTopicDot('td-dis',  'off');
    setTopicDot('td-odom', 'off');
    setTopicDot('td-cmd',  'off');
    if(disSub) {try{disSub.unsubscribe();}catch(e){} disSub=null;}
    if(odomSub){try{odomSub.unsubscribe();}catch(e){} odomSub=null;}
    pub=null;
  });
}

function disconnect(){
  log('Disconnecting...','warn');
  if(ros){try{ros.close();}catch(e){log('Close error: '+e,'err');}}
}

function setDot(state){
  var d=document.getElementById('dot');
  var l=document.getElementById('clbl');
  var b=document.getElementById('cbtn');
  if(state==='online'){
    d.className='dot live';l.textContent='ONLINE';
    b.textContent='DISCONNECT';b.className='hbtn disc';
  }else if(state==='connecting'){
    d.className='dot connecting';l.textContent='CONNECTING';
    b.textContent='CANCEL';b.className='hbtn disc';
  }else{
    d.className='dot';l.textContent='OFFLINE';
    b.textContent='CONNECT';b.className='hbtn';
  }
}

function setTopicDot(id, state){
  var el=document.getElementById(id);
  el.className='topic-dot'+(state==='ok'?' ok':state==='err'?' err':'');
}

// ════════════════════════════════════════════════════
//  TOPIC SETUP
// ════════════════════════════════════════════════════
function setupTopics(){
  log('Setting up ROS topics...','info');

  // ── /cmd_vel publisher ──────────────────────────
  log('Creating publisher on /cmd_vel  [geometry_msgs/Twist]','info');
  try{
    pub=new ROSLIB.Topic({
      ros:ros, name:'/cmd_vel',
      messageType:'geometry_msgs/Twist'
    });
    setTopicDot('td-cmd','ok');
    log('/cmd_vel publisher READY','ok');
  }catch(e){
    log('/cmd_vel publisher FAILED: '+e.message,'err');
    setTopicDot('td-cmd','err');
  }

  // ── /dis_data subscriber ───────────────────────
  log('Subscribing to /dis_data  [std_msgs/Float32MultiArray]','info');
  try{
    disSub=new ROSLIB.Topic({
      ros:ros, name:'/dis_data',
      messageType:'std_msgs/Float32MultiArray',
      throttle_rate:100
    });
    disSub.subscribe(function(msg){
      if(!disActive){
        disActive=true;
        setTopicDot('td-dis','ok');
        log('/dis_data — first message received! data.length='+msg.data.length,'ok');
      }
      msgCount.dis++;
      if(msg.data&&msg.data.length>=4){
        updateSensors(msg.data[0],msg.data[1],msg.data[2],msg.data[3]);
        if(msgCount.dis%50===0)
          log('/dis_data msg #'+msgCount.dis+' — ['+msg.data.map(function(v){return v.toFixed(3);}).join(', ')+']','data');
      }else{
        log('/dis_data — unexpected data.length='+msg.data.length+' (expected >=4)','warn');
      }
    });
    log('/dis_data subscriber registered — waiting for messages...','info');
  }catch(e){
    log('/dis_data subscribe FAILED: '+e.message,'err');
    setTopicDot('td-dis','err');
  }

  // ── /odom subscriber ────────────────────────────
  log('Subscribing to /odom  [nav_msgs/Odometry]','info');
  try{
    odomSub=new ROSLIB.Topic({
      ros:ros, name:'/odom',
      messageType:'nav_msgs/Odometry',
      throttle_rate:100
    });
    odomSub.subscribe(function(msg){
      if(!odomActive){
        odomActive=true;
        setTopicDot('td-odom','ok');
        log('/odom — first message received!','ok');
        log('/odom frame_id="'+msg.header.frame_id+'"  child_frame="'+msg.child_frame_id+'"','info');
      }
      msgCount.odom++;
      var p=msg.pose.pose.position,q=msg.pose.pose.orientation,tw=msg.twist.twist;
      var yaw=Math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z));
      var spd=Math.sqrt(tw.linear.x*tw.linear.x+tw.linear.y*tw.linear.y);
      updateOdom(p.x,p.y,yaw,spd,tw.linear.x,tw.linear.y);
      if(msgCount.odom%30===0)
        log('/odom msg #'+msgCount.odom+' — x='+p.x.toFixed(4)+' y='+p.y.toFixed(4)+' yaw='+((yaw*180/Math.PI).toFixed(2))+'°','data');
    });
    log('/odom subscriber registered — waiting for messages...','info');
  }catch(e){
    log('/odom subscribe FAILED: '+e.message,'err');
    setTopicDot('td-odom','err');
  }

  // ── Topic check: list active topics ────────────
  setTimeout(function(){
    if(!disActive)  log('/dis_data — no messages after 3s. Is the topic publishing? Try: ros2 topic echo /dis_data','warn');
    if(!odomActive) log('/odom — no messages after 3s. Is the topic publishing? Try: ros2 topic echo /odom','warn');
  },3000);

  setTimeout(function(){
    if(!disActive)  log('/dis_data still silent after 8s. Check message type with: ros2 topic info /dis_data','err');
    if(!odomActive) log('/odom still silent after 8s. Check message type with: ros2 topic info /odom','err');
  },8000);

  log('All topics configured. Publish rate: '+pubHz+' Hz','info');
}

// ════════════════════════════════════════════════════
//  PUBLISH LOOP
// ════════════════════════════════════════════════════
function startLoop(){
  stopLoop();
  log('Starting cmd_vel publish loop at '+pubHz+' Hz','info');
  ptimer=setInterval(tick,1000/pubHz);
}
function stopLoop(){
  if(ptimer){clearInterval(ptimer);ptimer=null;}
}

var lastLoggedMoving=false;
function tick(){
  if(!connected||estopped)return;
  vx=jL.ny*linMax;
  vy=-jL.nx*linMax;
  wz=jR.nx*angMax;
  doPub();
  var moving=(Math.abs(vx)>0.001||Math.abs(vy)>0.001||Math.abs(wz)>0.001);
  if(moving&&!lastLoggedMoving){
    log('Joystick active — publishing motion: Vx='+f5(vx)+' Vy='+f5(vy)+' Wz='+f5(wz),'info');
    lastLoggedMoving=true;
  }else if(!moving&&lastLoggedMoving){
    log('Joystick released — publishing zero velocity','info');
    lastLoggedMoving=false;
  }
}

function doPub(){
  if(!pub)return;
  try{
    pub.publish(new ROSLIB.Message({linear:{x:vx,y:vy,z:0},angular:{x:0,y:0,z:wz}}));
    msgCount.cmd++;
    setTopicDot('td-cmd','ok');
  }catch(e){
    log('/cmd_vel publish error: '+e.message,'err');
    setTopicDot('td-cmd','err');
  }
  document.getElementById('cv-lx').textContent=f5(vx);
  document.getElementById('cv-ly').textContent=f5(vy);
  document.getElementById('cv-az').textContent=f5(wz);
  document.getElementById('jLx').textContent=f5(vx);
  document.getElementById('jLy').textContent=f5(vy);
  document.getElementById('jRz').textContent=f5(wz);
  updateWheels();
}

// ════════════════════════════════════════════════════
//  KIWI KINEMATICS (30,150,270 deg)
// ════════════════════════════════════════════════════
var WA=[30,150,270].map(function(d){return d*Math.PI/180;});
function wheelSpeeds(vx,vy,wz){
  return WA.map(function(th){return -Math.sin(th)*vx+Math.cos(th)*vy+wz;});
}
function updateWheels(){
  var ws=wheelSpeeds(vx,vy,wz);
  var ids=['fl','fr','bk'];
  var maxA=Math.max.apply(null,ws.map(Math.abs).concat([0.001]));
  ws.forEach(function(w,i){
    document.getElementById('wf-'+ids[i]).textContent=(w>=0?'+':'')+w.toFixed(2);
    var bar=document.getElementById('wb-'+ids[i]);
    bar.style.width=Math.min(Math.abs(w)/maxA*100,100)+'%';
    bar.style.background=w>=0?'var(--cyan)':'var(--orange)';
  });
}

// ════════════════════════════════════════════════════
//  SENSORS
// ════════════════════════════════════════════════════
var SMAX=4.0;
function updateSensors(left,right,fl,fr){
  [{id:'l',v:left},{id:'r',v:right},{id:'fl',v:fl},{id:'fr',v:fr}].forEach(function(s){
    var cls=s.v<0.2?'d':s.v<0.5?'w':'ok';
    var sv=document.getElementById('sv-'+s.id);
    sv.textContent=isFinite(s.v)?s.v.toFixed(2):'-';
    sv.className='sv '+cls;
    document.getElementById('sn-'+s.id).textContent=isFinite(s.v)?s.v.toFixed(3)+'m':'-';
    var pct=Math.min(s.v/SMAX*100,100);
    var bar=document.getElementById('sb-'+s.id);
    bar.style.width=pct+'%';
    bar.className='sbf '+cls;
  });
}

// ════════════════════════════════════════════════════
//  ODOMETRY
// ════════════════════════════════════════════════════
function updateOdom(x,y,yaw,spd,tvx,tvy){
  ox=x;oy=y;oyaw=yaw;
  document.getElementById('ox').textContent=f5(x);
  document.getElementById('oy').textContent=f5(y);
  document.getElementById('oyaw').textContent=(yaw*180/Math.PI>=0?'+':'')+( yaw*180/Math.PI).toFixed(3);
  document.getElementById('ospd').textContent=f5(spd);
  document.getElementById('ovx').textContent=f5(tvx);
  document.getElementById('ovy').textContent=f5(tvy);
  trail.push({x:x,y:y});
  if(trail.length>3000)trail.shift();
  drawTrail();
}
function resetTrail(){trail=[];tcx=ox;tcy=oy;drawTrail();log('Trail map cleared','info');}
var tc=document.getElementById('tmap'),tx=tc.getContext('2d');
function drawTrail(){
  var W=tc.width,H=tc.height;
  tx.clearRect(0,0,W,H);
  tx.strokeStyle='rgba(28,42,56,.9)';tx.lineWidth=1;
  var gs=tscale;
  var offx=((W/2-tcx*gs)%gs+gs)%gs,offy=((H/2+tcy*gs)%gs+gs)%gs;
  for(var gx=offx;gx<W;gx+=gs){tx.beginPath();tx.moveTo(gx,0);tx.lineTo(gx,H);tx.stroke();}
  for(var gy=offy;gy<H;gy+=gs){tx.beginPath();tx.moveTo(0,gy);tx.lineTo(W,gy);tx.stroke();}
  var ox0=W/2-tcx*gs,oy0=H/2+tcy*gs;
  tx.strokeStyle='rgba(0,212,255,.2)';
  tx.beginPath();tx.moveTo(ox0-7,oy0);tx.lineTo(ox0+7,oy0);tx.stroke();
  tx.beginPath();tx.moveTo(ox0,oy0-7);tx.lineTo(ox0,oy0+7);tx.stroke();
  if(trail.length>1){
    tx.beginPath();tx.strokeStyle='rgba(0,212,255,.5)';tx.lineWidth=1.5;
    trail.forEach(function(p,i){var px=W/2+(p.x-tcx)*gs,py=H/2-(p.y-tcy)*gs;i===0?tx.moveTo(px,py):tx.lineTo(px,py);});
    tx.stroke();
  }
  var rx=W/2+(ox-tcx)*gs,ry=H/2-(oy-tcy)*gs;
  tx.save();tx.translate(rx,ry);tx.rotate(-oyaw);
  tx.beginPath();tx.moveTo(0,-9);tx.lineTo(6,5);tx.lineTo(0,2);tx.lineTo(-6,5);tx.closePath();
  tx.fillStyle='#ff7b35';tx.shadowColor='#ff7b35';tx.shadowBlur=8;tx.fill();
  tx.restore();
}
drawTrail();

// ════════════════════════════════════════════════════
//  E-STOP
// ════════════════════════════════════════════════════
function eStop(){
  estopped=!estopped;
  var btn=document.getElementById('estop');
  if(estopped){
    vx=0;vy=0;wz=0;if(pub)doPub();
    btn.classList.add('active');btn.textContent='STOPPED';
    log('E-STOP ACTIVATED — zero velocity published','err');
  }else{
    btn.classList.remove('active');btn.textContent='\u2B21 E-STOP';
    log('E-STOP released — motion enabled','ok');
  }
}

// ════════════════════════════════════════════════════
//  SLIDERS
// ════════════════════════════════════════════════════
document.getElementById('ls').oninput=function(){linMax=+this.value;document.getElementById('lsv').textContent=linMax.toFixed(2);log('Linear speed limit → '+linMax.toFixed(2)+' m/s','info');};
document.getElementById('as').oninput=function(){angMax=+this.value;document.getElementById('asv').textContent=angMax.toFixed(2);log('Angular speed limit → '+angMax.toFixed(2)+' r/s','info');};
document.getElementById('hz').oninput=function(){pubHz=+this.value;document.getElementById('hzv').textContent=pubHz;log('Publish rate → '+pubHz+' Hz','info');if(connected)startLoop();};

// ════════════════════════════════════════════════════
//  UTILS
// ════════════════════════════════════════════════════
function f5(v){return(v>=0?'+':'')+v.toFixed(5);}

// ════════════════════════════════════════════════════
//  BOOT
// ════════════════════════════════════════════════════
log('KIWIBOT Control Station initialised','info');
log('roslibjs CDN loading...','info');
waitForROSLIB(function(){
  log('Ready — enter rosbridge URL and click CONNECT','ok');
  log('Default rosbridge port is 9090. Start with:','info');
  log('  ros2 launch rosbridge_server rosbridge_websocket_launch.xml','info');
});
</script>

<!-- roslibjs from CDN — loads asynchronously -->
<script src="https://cdn.jsdelivr.net/npm/roslib@1.3.0/build/roslib.min.js"
  onerror="document.getElementById('logbody').innerHTML+='<div class=\'le err\'><span class=\'le-ts\'>boot</span><span class=\'le-lvl\'>ERROR</span><span class=\'le-msg\'>roslibjs CDN load FAILED — check internet connection or use local copy</span></div>'">
</script>
</body>
</html>