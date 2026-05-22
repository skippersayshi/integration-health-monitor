"""Quick test run for Integration Health Monitor."""
import sys
from datetime import datetime, timezone
from health_monitor import (
    EndpointStatus, FixResult, ErrorAnalyzer, AutoFixer, Monitor, RalphLoop
)

def test_error_analyzer():
    analyzer = ErrorAnalyzer()
    s = EndpointStatus(url="https://x.com", status_code=500, latency_ms=100,
                       timestamp=datetime.now(timezone.utc))
    assert analyzer.classify(s) == ErrorAnalyzer.CATEGORY_SERVER_ERROR

    s2 = EndpointStatus(url="https://x.com", status_code=401, latency_ms=50,
                        timestamp=datetime.now(timezone.utc))
    assert analyzer.classify(s2) == ErrorAnalyzer.CATEGORY_AUTH

    s3 = EndpointStatus(url="https://x.com", error_type="timeout", latency_ms=10000,
                        timestamp=datetime.now(timezone.utc))
    assert analyzer.classify(s3) == ErrorAnalyzer.CATEGORY_TIMEOUT
    print("  ErrorAnalyzer: PASS")

def test_monitor_poll():
    monitor = Monitor()
    results = monitor.poll(["https://httpbin.org/status/200", "https://httpbin.org/status/404"])
    assert len(results) == 2
    assert results[0].status_code == 200
    assert results[1].status_code == 404
    print("  Monitor.poll: PASS")

def test_ralph_loop():
    from health_monitor import ErrorAnalyzer, AutoFixer, Monitor, RalphLoop
    monitor = Monitor()
    analyzer = ErrorAnalyzer()
    fixer = AutoFixer(max_retries=1)
    loop = RalphLoop(monitor, analyzer, fixer, db_path=":memory:")
    loop.run_cycle(["https://httpbin.org/status/200", "https://httpbin.org/status/500"])
    print("  RalphLoop.run_cycle: PASS")

if __name__ == "__main__":
    print("Running tests...")
    test_error_analyzer()
    test_monitor_poll()
    test_ralph_loop()
    print("All tests passed.")
