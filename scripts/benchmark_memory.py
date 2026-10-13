"""Read-only CPU/RAM/storage sampler; run during desktop use and separately gaming."""
import argparse
import json
import os
from pathlib import Path
import statistics
import time
import psutil

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["normal", "gaming"], required=True)
parser.add_argument("--seconds", type=int, default=300)
parser.add_argument("--storage", type=Path, default=Path.home() / ".screenpipe")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if not 5 <= args.seconds <= 3600:
    parser.error("seconds must be 5–3600")
def disk_size():
    total = 0
    if args.storage.is_dir():
        for root, _, files in os.walk(args.storage):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    pass
    return total
targets = []
for p in psutil.process_iter(["name", "pid"]):
    if any(name in (p.info["name"] or "").lower() for name in ["screenpipe", "clicky", "matekscreencompanion"]):
        try:
            p.cpu_percent()
            targets.append(p)
        except psutil.Error:
            pass
start_size = disk_size()
samples = {p.pid: {"name": p.name(), "cpu": [], "rss": []} for p in targets}
started = time.monotonic()
while time.monotonic() - started < args.seconds:
    time.sleep(1)
    for p in targets:
        try:
            samples[p.pid]["cpu"].append(p.cpu_percent())
            samples[p.pid]["rss"].append(p.memory_info().rss)
        except psutil.Error:
            pass
report = {"mode_label": args.mode, "seconds": round(time.monotonic() - started, 2),
          "note": "Mode is operator supplied. This does not launch a game or measure FPS. CPU: 100% = one core.",
          "screenpipe_present": any("screenpipe" in row["name"].lower() for row in samples.values()),
          "storage_present": args.storage.is_dir(), "storage_start_bytes": start_size,
          "storage_end_bytes": disk_size(), "processes": []}
for pid, row in samples.items():
    if row["cpu"]:
        report["processes"].append({"pid": pid, "name": row["name"], "cpu_one_core_mean_percent": statistics.mean(row["cpu"]),
                                    "cpu_one_core_max_percent": max(row["cpu"]), "peak_rss_mb": max(row["rss"]) / 1024**2})
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
