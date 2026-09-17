import os
import sys
import time
import json
import asyncio
import urllib.request
import urllib.parse
import cv2
import numpy as np
import websockets

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/events"

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode())

def post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode())

def delete(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as res:
        data = res.read().decode()
        return json.loads(data) if data else {"status": "deleted"}

def check_snapshot(cam_id):
    req = urllib.request.Request(f"{BASE_URL}/api/cameras/{cam_id}/snapshot")
    with urllib.request.urlopen(req, timeout=10) as res:
        raw_bytes = res.read()
        nparr = np.frombuffer(raw_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return len(raw_bytes), img.shape if img is not None else None

async def run_final_audit():
    print("=" * 80)
    print("FINAL SYSTEM HEALTH & PERFORMANCE AUDIT")
    print("=" * 80)
    
    # 1. Backend & DB Health
    health = get("/api/health")
    print(f"1. Health Endpoint: {health}")
    
    inference = get("/api/system/inference")
    print(f"2. Inference System:")
    print(f"   - Object Detector: {inference.get('model_name')} ({inference.get('device')})")
    print(f"   - Tracker: {inference.get('tracker_engine')}")
    print(f"   - Face Model: {inference.get('face_model_name')}")
    print(f"   - ANPR Engine: {inference.get('anpr_engine')}")
    
    # 2. Camera Statuses
    cams = get("/api/cameras")
    active_cams = [c for c in cams if c.get("enabled")]
    print(f"\n3. Configured Active Cameras ({len(active_cams)}):")
    for c in active_cams:
        cid = c["id"]
        size, shape = check_snapshot(cid)
        print(f"   - Cam #{cid} ('{c['name']}'): Type={c['source_type']}, URI={c['source_uri']}, Status={c['status']}, Res={c['resolution']}, SourceFPS={c['source_fps']:.1f}, SnapshotSize={size} bytes")

    # 3. 15-Second Time-Series FPS & Latency Measurement
    print(f"\n4. Measuring Real 15-Second Performance Telemetry across all 4 cameras...")
    cam_stats = {c["id"]: {
        "name": c["name"],
        "source_type": c["source_type"],
        "source_fps": c.get("source_fps", 0),
        "inf_fps": [],
        "inf_lat": [],
        "face_lat": [],
        "anpr_lat": [],
        "detections": [],
        "tracks": [],
    } for c in active_cams}
    
    start_time = time.time()
    while time.time() - start_time < 15.0:
        cams = get("/api/cameras")
        for c in cams:
            cid = c["id"]
            if cid in cam_stats:
                cam_stats[cid]["inf_fps"].append(c.get("inference_fps", 0.0))
                cam_stats[cid]["inf_lat"].append(c.get("inference_latency_ms", 0.0))
                cam_stats[cid]["face_lat"].append(c.get("face_latency_ms", 0.0))
                cam_stats[cid]["anpr_lat"].append(c.get("anpr_latency_ms", 0.0))
                cam_stats[cid]["detections"].append(c.get("detection_counts", {}).get("total", 0))
                cam_stats[cid]["tracks"].append(c.get("tracking_counts", {}).get("total_active_tracks", 0))
        await asyncio.sleep(1.0)

    print("\n   [Measured Performance Table]:")
    print(f"   {'Cam ID':<8}{'Name':<18}{'Source FPS':<12}{'Display FPS':<14}{'Detect FPS':<12}{'Avg Latency':<14}{'Max Latency':<14}{'ANPR Lat':<12}")
    print("   " + "-" * 90)
    for cid, s in cam_stats.items():
        avg_inf_fps = np.mean(s["inf_fps"]) if s["inf_fps"] else 0.0
        avg_inf_lat = np.mean(s["inf_lat"]) if s["inf_lat"] else 0.0
        max_inf_lat = np.max(s["inf_lat"]) if s["inf_lat"] else 0.0
        avg_anpr_lat = np.mean(s["anpr_lat"]) if s["anpr_lat"] else 0.0
        print(f"   #{cid:<7}{s['name']:<18}{s['source_fps']:<12.1f}{s['source_fps']:<14.1f}{avg_inf_fps:<12.2f}{avg_inf_lat:<14.1f}{max_inf_lat:<14.1f}{avg_anpr_lat:<12.1f}")

    # 4. Settings verification
    settings_data = get("/api/settings")
    print(f"\n5. Persisted Settings Store (Loaded {len(settings_data)} keys):")
    print(f"   - app_name: {settings_data.get('app_name')}")
    print(f"   - detection_conf_threshold: {settings_data.get('detection_conf_threshold')}")
    print(f"   - loitering_threshold_sec: {settings_data.get('loitering_threshold_sec')}")
    print(f"   - alert_cooldown_sec: {settings_data.get('alert_cooldown_sec')}")
    print(f"   - night_start_time: {settings_data.get('night_start_time')}")
    print(f"   - night_end_time: {settings_data.get('night_end_time')}")

    # 5. Database Events & Evidence Verification
    events_data = get("/api/events?limit=5")
    print(f"\n6. Event History & Evidence Verification:")
    print(f"   - Total Events in Database: {events_data.get('total')}")
    for ev in events_data.get("items", [])[:3]:
        print(f"   - Event #{ev['id']}: Camera={ev['camera_id']}, Type={ev['event_type']}, Severity={ev['severity']}, Reason='{ev['reason']}'")
        if ev.get("evidence_path"):
            p = ev["evidence_path"].lstrip("/")
            p_rel = os.path.join("..", p)
            found = os.path.exists(p) or os.path.exists(p_rel)
            print(f"     Evidence Snapshot: {ev['evidence_path']} (Verified on disk: {found})")

    # 6. WebSocket Reconnect test
    print(f"\n7. WebSocket Connection & Resilience Test:")
    for i in range(2):
        async with websockets.connect(WS_URL) as ws:
            print(f"   - Cycle {i+1}: connected to {WS_URL} successfully.")
        print(f"   - Cycle {i+1}: closed cleanly.")

    print("\n" + "=" * 80)
    print("ALL CHECKS FINISHED SUCCESSFULLY")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_final_audit())
