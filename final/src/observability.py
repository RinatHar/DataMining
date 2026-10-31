"""Структурные логи (JSONL) и отчёт о прогоне."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    def __init__(self, log_path: str):
        self.log_path = log_path
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        self.started_at = time.time()
        self.stats = {"total": 0, "codes": {}, "errors": 0, "retries": 0,
                      "latencies": [], "bytes": 0}

    def log(self, event: str, **kwargs):
        record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kwargs}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def record_request(self, status: int, latency: float, url: str, nbytes: int = 0):
        self.stats["total"] += 1
        self.stats["latencies"].append(latency)
        self.stats["bytes"] += nbytes
        key = str(status)
        self.stats["codes"][key] = self.stats["codes"].get(key, 0) + 1
        if status >= 400 or status == 0:
            self.stats["errors"] += 1
        self.log("request", url=url, status=status,
                 ms=round(latency * 1000, 1), bytes=nbytes)

    def build_report(self, collected: int, rejected: int) -> dict:
        lats = sorted(self.stats["latencies"])
        median = lats[len(lats) // 2] if lats else 0
        p95 = lats[int(len(lats) * 0.95)] if len(lats) >= 20 else (lats[-1] if lats else 0)
        return {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(time.time() - self.started_at, 2),
            "requests_total": self.stats["total"],
            "status_codes": self.stats["codes"],
            "error_share": round(self.stats["errors"] / max(self.stats["total"], 1), 4),
            "retries": self.stats["retries"],
            "latency_median_ms": round(median * 1000, 1),
            "latency_p95_ms": round(p95 * 1000, 1),
            "traffic_bytes": self.stats["bytes"],
            "records_collected": collected,
            "records_rejected": rejected,
        }