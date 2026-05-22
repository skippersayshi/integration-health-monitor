# Integration Health Monitor

Autonomous API health monitoring with self-healing and Ralph loop (self-improving feedback cycle).

## What it does

- Polls HTTP endpoints on a configurable interval
- Classifies failures: timeout, auth, rate_limit, server_error, network
- Autonomously attempts fixes (retry, backoff, escalation)
- Ralph loop: compares predicted vs actual fix outcomes and sharpens detection rules over time
- SQLite-backed rule stats — gets smarter with every run

## Install

```bash
pip install httpx pydantic
```

## Run

```bash
python health_monitor.py
```

## Components

| Class | Role |
|---|---|
| `Monitor` | Async HTTP polling daemon |
| `ErrorAnalyzer` | Classifies error categories |
| `AutoFixer` | Autonomous remediation |
| `RalphLoop` | Orchestrates + learns from every cycle |

## Extend

- Add `escalation_hook` to `AutoFixer` for Slack/email alerts
- Replace `httpbin.org` endpoints in `main()` with your real APIs
- Call `monitor.start_daemon(endpoints)` for continuous monitoring
