# Integration Health Monitor

> Autonomous endpoint health monitor with error analysis and self-healing via Ralph loop.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/skippersayshi/integration-health-monitor)

## Features

- Monitor multiple endpoints in one run
- Error analysis with auto-fix suggestions
- Ralph loop: monitor → analyze → fix → retry
- Clean status table with latency and error details

## Run Locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload
# Open http://localhost:8000
```

## Deploy

Click the Railway button above — `railway.toml` is pre-configured.
