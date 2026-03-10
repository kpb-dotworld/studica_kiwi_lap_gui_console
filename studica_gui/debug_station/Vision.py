#!/usr/bin/env python3
"""
OBJECT DETECTOR - Auto Capture + Train + Detect
✅ Auto captures every 1 second while you move camera
✅ Extracts & trains features from every captured frame
✅ Bounding box with homography + RANSAC
✅ Smooth detection (5 frame history)
✅ 100% offline - no downloads needed

INSTALL: pip install opencv-python numpy
"""

import cv2
import numpy as np
import json
import os
import time

# ===============================
# 🔵 CHANGE THESE
# ===============================
CAMERA_ID      = 1
SAVE_DIR       = "/home/user/final codes/vision/cv"
INTERVAL       = 1.0     # seconds between auto-captures
TARGET_SAMPLES = 50      # how many samples to collect
MIN_MATCHES    = 12      # detection sensitivity
# ===============================

DATA_FILE = os.path.join(SAVE_DIR, "db.json")
os.makedirs(SAVE_DIR, exist_ok=True)

orb = cv2.ORB_create(
    nfeatures     = 1500,
    scaleFactor   = 1.2,
    nlevels       = 6,
    edgeThreshold = 15,
)
bf = cv2.BFMatcher(cv2.NORM_HAMMING)
DETECT_W = 320   # resize for faster detection

# =============================================
# DB
# =============================================
def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DATA_FILE, "w") as f:
        json.dump(db, f)

# =============================================
# AUTO CAPTURE + TRAIN (MERGED)
# =============================================
def auto_capture_and_train(cap):
    db    = load_db()
    label = input("\nObject name: ").strip().lower()

    if not label:
        return

    if label not in db:
        db[label] = []

    obj_dir = os.path.join(SAVE_DIR, label)
    os.makedirs(obj_dir, exist_ok=True)

    existing  = len(db[label])
    count     = 0
    capturing = False
    last_time = 0

    print(f"\n  Object  : {label}")
    print(f"  Target  : {TARGET_SAMPLES} samples")
    print(f"  Existing: {existing} samples")
    print(f"  Interval: every {INTERVAL}s\n")
    print("  ═══════════════════════════════════")
    print("  SPACE = start / pause auto-capture")
    print("  Q     = finish & save")
    print("  ═══════════════════════════════════")
    print("\n  Move camera around object while capturing!\n")

    while count < TARGET_SAMPLES:
        ret, frame = cap.read()
        if not ret:
            continue

        now  = time.time()
        h, w = frame.shape[:2]

        # ---- AUTO CAPTURE ----
        if capturing and (now - last_time) >= INTERVAL:
            gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            kp, des = orb.detectAndCompute(gray, None)

            if des is not None and len(des) >= 15:
                idx      = existing + count
                img_name = f"{label}_{idx}.jpg"
                img_path = os.path.join(obj_dir, img_name)
                cv2.imwrite(img_path, frame)

                kp_data = [[k.pt[0], k.pt[1], k.size,
                            k.angle, k.response, k.octave] for k in kp]

                db[label].append({
                    "img"  : img_path,
                    "kp"   : kp_data,
                    "des"  : des.tolist(),
                    "shape": [h, w]
                })

                count    += 1
                last_time = now
                print(f"  📸 [{count}/{TARGET_SAMPLES}] {img_name}  features:{len(kp)}")

                # flash
                flash = frame.copy()
                cv2.rectangle(flash, (0,0), (w,h), (0,255,0), 15)
                cv2.putText(flash, f"CAPTURED! {count}/{TARGET_SAMPLES}",
                            (w//2-180, h//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 3)
                cv2.imshow("AUTO CAPTURE + TRAIN", flash)
                cv2.waitKey(300)
                continue
            else:
                print("  ⚠ Not enough features — improve lighting")
                last_time = now

        # ---- DISPLAY ----
        show   = frame.copy()
        status = "● CAPTURING" if capturing else "⏸ PAUSED"
        color  = (0, 0, 255)  if capturing else (0, 200, 255)

        # live feature count
        gray_show    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp_show, _   = orb.detectAndCompute(gray_show, None)
        feat_count   = len(kp_show) if kp_show else 0

        cv2.putText(show, f"{status}  |  {label}",
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        cv2.putText(show, f"saved: {count}/{TARGET_SAMPLES}  features:{feat_count}  every {INTERVAL}s",
                    (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200,200,200), 1)
        cv2.putText(show, "SPACE=start/pause  Q=finish",
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180,180,180), 1)

        # countdown bar
        if capturing:
            elapsed = min(now - last_time, INTERVAL)
            bar_w   = int((elapsed / INTERVAL) * w)
            cv2.rectangle(show, (0, h-8), (bar_w, h), (0,255,0), -1)
            cv2.rectangle(show, (0, h-8), (w, h), (60,60,60), 1)

        # progress bar top
        prog_w = int((count / TARGET_SAMPLES) * w)
        cv2.rectangle(show, (0, 0), (prog_w, 6), (0,200,255), -1)

        cv2.imshow("AUTO CAPTURE + TRAIN", show)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):
            capturing = not capturing
            last_time = time.time()
            state = "▶ Started" if capturing else "⏸ Paused"
            print(f"\n  {state} — move camera around object!\n")

        elif key == ord('q'):
            break

    # save
    save_db(db)
    cv2.destroyAllWindows()
    total = len(db[label])
    print(f"\n  ✅ Done! '{label}' → {total} total samples")
    print(f"  📁 Images: {obj_dir}\n")

# =============================================
# MATCH + BOUNDING BOX
# =============================================
# pre-built index per name for fast matching
_index_cache = {}

def build_index(db):
    """Build fast BFMatcher index — called once, not every frame."""
    global _index_cache
    _index_cache = {}
    for name, samples in db.items():
        all_des = []
        all_kp  = []
        all_sh  = []
        for s in samples:
            d = np.array(s["des"], dtype=np.uint8)
            all_des.append(d)
            all_kp.append(s["kp"])
            all_sh.append(s["shape"])
        _index_cache[name] = {
            "des": all_des,
            "kp" : all_kp,
            "sh" : all_sh,
        }

def get_best_match(des_frame, kp_frame, db):
    if des_frame is None or len(des_frame) < 2:
        return None, 0, None

    best_name  = None
    best_score = 0
    best_box   = None

    for name, data in _index_cache.items():
        for idx, ref_des in enumerate(data["des"]):
            if len(ref_des) < 2:
                continue
            try:
                matches = bf.knnMatch(des_frame, ref_des, k=2)
            except:
                continue

            good = [m for pair in matches
                    if len(pair)==2
                    for m,n in [pair]
                    if m.distance < 0.70 * n.distance]

            if len(good) < MIN_MATCHES:
                continue

            ref_kp = [cv2.KeyPoint(
                x=k[0], y=k[1], size=k[2],
                angle=k[3], response=k[4], octave=int(k[5])
            ) for k in data["kp"][idx]]

            src_pts = np.float32([ref_kp[m.trainIdx].pt
                                  for m in good]).reshape(-1,1,2)
            dst_pts = np.float32([kp_frame[m.queryIdx].pt
                                  for m in good]).reshape(-1,1,2)

            try:
                H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 4.0)
            except:
                continue

            if H is None:
                continue

            inliers = int(mask.sum()) if mask is not None else 0
            score   = inliers * 2 + len(good)

            if score > best_score:
                best_score = score
                best_name  = name
                sh, sw = data["sh"][idx]
                corners = np.float32(
                    [[0,0],[sw,0],[sw,sh],[0,sh]]
                ).reshape(-1,1,2)
                try:
                    proj = cv2.perspectiveTransform(corners, H)
                    x, y, bw, bh = cv2.boundingRect(proj)
                    best_box = (x, y, bw, bh)
                except:
                    best_box = None

    return best_name, best_score, best_box

# =============================================
# DETECT
# =============================================
def detect(cap):
    db = load_db()
    if not db:
        print("\n  No trained objects! Train first.\n")
        return

    print(f"\n  Detecting: {list(db.keys())}")
    print("  ESC = quit\n")

    build_index(db)

    from collections import Counter
    history     = []
    HISTORY_LEN = 5
    last_name   = None
    last_score  = 0
    last_box    = None
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame_count += 1
        fh, fw = frame.shape[:2]

        # run detection every 3rd frame only — display all frames
        if frame_count % 3 == 0:
            scale = 320 / fw
            small = cv2.resize(frame, (320, int(fh * scale)))
            gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            kp, des = orb.detectAndCompute(gray, None)
            name, score, box = get_best_match(des, kp, db)

            if box:
                x, y, bw, bh = box
                box = (int(x/scale), int(y/scale),
                       int(bw/scale), int(bh/scale))

            last_name  = name
            last_score = score
            last_box   = box

            history.append(name if score >= MIN_MATCHES else None)
            if len(history) > HISTORY_LEN:
                history.pop(0)

            if score >= MIN_MATCHES:
                print(f"  ✅ {name} detected  score:{int(score)}")

        # confirm detection from history
        confirmed = None
        counts = Counter(h for h in history if h is not None)
        if counts:
            top, freq = counts.most_common(1)[0]
            if freq >= HISTORY_LEN // 2 + 1:
                confirmed = top

        # always draw on every frame = smooth video
        display = frame.copy()

        if confirmed and last_box:
            x, y, bw, bh = last_box
            if 0 <= x < fw and 0 <= y < fh and bw > 20 and bh > 20:
                x2 = min(x+bw, fw)
                y2 = min(y+bh, fh)
                # plain bounding box
                cv2.rectangle(display, (x,y), (x2,y2), (0,255,0), 3)
                # label above box
                cv2.putText(display, confirmed,
                            (x, max(30, y-10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2)
        else:
            cv2.putText(display, "Searching...",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255), 2)



        cv2.rectangle(display, (0,0), (fw,28), (30,30,30), -1)
        cv2.putText(display,
                    f"objects:{list(db.keys())}  score:{int(last_score)}  ESC=quit",
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

        cv2.imshow("DETECT", display)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cv2.destroyAllWindows()

# =============================================
# MAIN
# =============================================
def main():
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print(f"  ❌ Cannot open camera {CAMERA_ID} — try CAMERA_ID=0")
        return

    while True:
        print("\n╔══════════════════════════════╗")
        print("║     OBJECT DETECTOR          ║")
        print("╠══════════════════════════════╣")
        print("║  1 → Auto Capture & Train    ║")
        print("║  2 → detect                  ║")
        print("║  3 → Show trained objects    ║")
        print("║  4 → Clear database          ║")
        print("║  Q → Quit                    ║")
        print("╚══════════════════════════════╝")

        choice = input("\nChoice: ").strip().lower()

        if choice == "1":
            auto_capture_and_train(cap)
        elif choice == "2":
            detect(cap)
        elif choice == "3":
            db = load_db()
            if not db:
                print("\n  Nothing trained yet!")
            else:
                print("\n  Trained objects:")
                for n, s in db.items():
                    print(f"    {n}  →  {len(s)} samples  📁 {SAVE_DIR}/{n}/")
        elif choice == "4":
            import shutil
            if os.path.exists(SAVE_DIR):
                shutil.rmtree(SAVE_DIR)
                os.makedirs(SAVE_DIR)
                print("  ✅ Cleared!")
        elif choice == "q":
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\n  Bye!\n")

if __name__ == "__main__":
    main()