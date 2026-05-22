"""
Integration Health Monitor
Autonomous API health monitoring with self-healing and Ralph loop.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional, Callable

import httpx
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class EndpointStatus(BaseModel):
    url: str
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: datetime


class FixResult(BaseModel):
    success: bool
    action_taken: str
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class Monitor:
    """Self-sufficient daemon that polls HTTP endpoints and returns status snapshots."""

    def __init__(self, interval_seconds: float = 30.0) -> None:
        self.interval_seconds = interval_seconds

    def poll(self, endpoints: list[str]) -> list[EndpointStatus]:
        """Poll every endpoint once and return status snapshots."""
        return asyncio.run(self._poll_all(endpoints))

    async def _poll_all(self, endpoints: list[str]) -> list[EndpointStatus]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [self._poll_single(client, url) for url in endpoints]
            return await asyncio.gather(*tasks)

    async def _poll_single(self, client: httpx.AsyncClient, url: str) -> EndpointStatus:
        start = time.monotonic()
        try:
            response = await client.get(url)
            latency = (time.monotonic() - start) * 1000
            return EndpointStatus(
                url=url,
                status_code=response.status_code,
                error_type=None,
                latency_ms=round(latency, 2),
                timestamp=datetime.now(timezone.utc),
            )
        except httpx.TimeoutException:
            return EndpointStatus(url=url, error_type="timeout",
                                  latency_ms=10000.0, timestamp=datetime.now(timezone.utc))
        except httpx.ConnectError:
            return EndpointStatus(url=url, error_type="connection_error",
                                  latency_ms=0.0, timestamp=datetime.now(timezone.utc))
        except Exception as e:
            return EndpointStatus(url=url, error_type=str(type(e).__name__),
                                  latency_ms=0.0, timestamp=datetime.now(timezone.utc))

    def start_daemon(self, endpoints: list[str]) -> None:
        """Continuously poll endpoints at configured interval until interrupted."""
        print(f"Starting monitor daemon (interval: {self.interval_seconds}s)")
        while True:
            statuses = self.poll(endpoints)
            for s in statuses:
                healthy = s.status_code and 200 <= s.status_code < 300
                icon = "✓" if healthy else "✗"
                print(f"  {icon} {s.url} — {s.status_code or s.error_type} ({s.latency_ms}ms)")
            time.sleep(self.interval_seconds)


# ---------------------------------------------------------------------------
# ErrorAnalyzer
# ---------------------------------------------------------------------------

class ErrorAnalyzer:
    """Classifies endpoint failures into canonical error categories."""

    CATEGORY_TIMEOUT = "timeout"
    CATEGORY_AUTH = "authentication"
    CATEGORY_RATE_LIMIT = "rate_limit"
    CATEGORY_SERVER_ERROR = "server_error"
    CATEGORY_CLIENT_ERROR = "client_error"
    CATEGORY_NETWORK = "network"
    CATEGORY_UNKNOWN = "unknown"

    def classify(self, status: EndpointStatus) -> str:
        if status.error_type == "timeout":
            return self.CATEGORY_TIMEOUT
        if status.error_type in ("connection_error", "ConnectError", "NetworkError"):
            return self.CATEGORY_NETWORK
        if status.status_code:
            return self._infer_from_status_code(status.status_code)
        if status.error_type:
            return self._infer_from_error_type(status.error_type)
        return self.CATEGORY_UNKNOWN

    def _infer_from_status_code(self, code: int) -> str:
        if code == 401 or code == 403:
            return self.CATEGORY_AUTH
        if code == 429:
            return self.CATEGORY_RATE_LIMIT
        if 500 <= code < 600:
            return self.CATEGORY_SERVER_ERROR
        if 400 <= code < 500:
            return self.CATEGORY_CLIENT_ERROR
        return self.CATEGORY_UNKNOWN

    def _infer_from_error_type(self, error_type: str) -> str:
        lower = error_type.lower()
        if "timeout" in lower:
            return self.CATEGORY_TIMEOUT
        if "connect" in lower or "network" in lower:
            return self.CATEGORY_NETWORK
        if "auth" in lower or "permission" in lower:
            return self.CATEGORY_AUTH
        return self.CATEGORY_UNKNOWN


# ---------------------------------------------------------------------------
# AutoFixer
# ---------------------------------------------------------------------------

class AutoFixer:
    """Autonomously attempts to remediate endpoint failures. Escalates only when stuck."""

    def __init__(self, max_retries: int = 3, escalation_hook: Optional[Callable] = None) -> None:
        self.max_retries = max_retries
        self.escalation_hook = escalation_hook
        self._analyzer = ErrorAnalyzer()

    def fix(self, status: EndpointStatus) -> FixResult:
        category = self._analyzer.classify(status)
        if category == ErrorAnalyzer.CATEGORY_TIMEOUT:
            return self._retry(status)
        if category == ErrorAnalyzer.CATEGORY_NETWORK:
            return self._retry(status)
        if category == ErrorAnalyzer.CATEGORY_RATE_LIMIT:
            time.sleep(2)
            return self._retry(status)
        if category == ErrorAnalyzer.CATEGORY_AUTH:
            return FixResult(success=False, action_taken="auth_escalation",
                             notes="Authentication error requires manual credential rotation")
        return self._escalate(status)

    def _retry(self, status: EndpointStatus) -> FixResult:
        for attempt in range(1, self.max_retries + 1):
            try:
                response = httpx.get(status.url, timeout=10.0)
                if 200 <= response.status_code < 300:
                    return FixResult(success=True, action_taken=f"retry_{attempt}",
                                     notes=f"Succeeded on attempt {attempt}")
            except Exception:
                pass
            time.sleep(attempt)
        return FixResult(success=False, action_taken=f"retry_{self.max_retries}",
                         notes="All retries exhausted")

    def _escalate(self, status: EndpointStatus) -> FixResult:
        if self.escalation_hook:
            self.escalation_hook(status)
        return FixResult(success=False, action_taken="escalated",
                         notes=f"Escalated: {status.url} — {status.error_type or status.status_code}")


# ---------------------------------------------------------------------------
# RalphLoop
# ---------------------------------------------------------------------------

class RalphLoop:
    """Fully autonomous observe -> analyze -> fix -> learn cycle."""

    def __init__(self, monitor: Monitor, analyzer: ErrorAnalyzer, fixer: AutoFixer,
                 db_path: str = "ralph_rules.db") -> None:
        self.monitor = monitor
        self.analyzer = analyzer
        self.fixer = fixer
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rule_stats (
                    category TEXT PRIMARY KEY,
                    predicted_success INTEGER DEFAULT 0,
                    actual_success INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0
                )
            """)

    def run_cycle(self, endpoints: list[str]) -> None:
        statuses = self.monitor.poll(endpoints)
        for status in statuses:
            if self._is_healthy(status):
                continue
            category = self.analyzer.classify(status)
            predicted = self._predict_fix_outcome(status, category)
            result = self.fixer.fix(status)
            self._refine_rules(status, category, predicted, result)
            icon = "✓ fixed" if result.success else "✗ escalated"
            print(f"  [{icon}] {status.url} ({category}) — {result.action_taken}")

    def _predict_fix_outcome(self, status: EndpointStatus, category: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT actual_success, total FROM rule_stats WHERE category = ?", (category,)
            ).fetchone()
        if not row or row[1] == 0:
            return True  # optimistic default
        return (row[0] / row[1]) >= 0.5

    def _refine_rules(self, status: EndpointStatus, category: str,
                      predicted: bool, actual: FixResult) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO rule_stats (category, predicted_success, actual_success, total)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(category) DO UPDATE SET
                    predicted_success = predicted_success + ?,
                    actual_success = actual_success + ?,
                    total = total + 1
            """, (category, int(predicted), int(actual.success),
                  int(predicted), int(actual.success)))

    def _is_healthy(self, status: EndpointStatus) -> bool:
        return (status.status_code is not None
                and 200 <= status.status_code < 300
                and status.error_type is None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Bootstrap and run the Integration Health Monitor."""
    endpoints = [
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/500",
        "https://httpbin.org/delay/2",
    ]

    monitor = Monitor(interval_seconds=30.0)
    analyzer = ErrorAnalyzer()
    fixer = AutoFixer(max_retries=3)
    loop = RalphLoop(monitor, analyzer, fixer)

    print("Running one cycle...")
    loop.run_cycle(endpoints)
    print("\nDone. Start daemon with: monitor.start_daemon(endpoints)")


if __name__ == "__main__":
    main()
