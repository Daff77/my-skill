#!/usr/bin/env python3
"""
Wrapper script for WhatsApp group summary cron job.

HOW TO USE:
1. Copy this file to ~/.hermes/scripts/<yourgroup>-summary.py
2. Edit TARGET_CHAT and HOURS_BACK below
3. Use the copied filename as the 'script' field in your cron job
   (never pass arguments — the scheduler treats the whole field as a path)

Find your group chat ID by running:
  python3 ~/.hermes/scripts/whatsapp-group-summary.py list_groups  (or see SKILL.md Step 4)
"""
import json
import subprocess
import sys
import time
import urllib.request

# ─── EDIT THESE TWO VALUES ───────────────────────────────────────────────────
TARGET_CHAT = "120363XXXXXXXXXXXXXXX@g.us"  # your group chat ID
HOURS_BACK = 12                              # summary window in hours
# ─────────────────────────────────────────────────────────────────────────────

result = subprocess.run(
    [sys.executable, "whatsapp-group-summary.py", TARGET_CHAT, str(HOURS_BACK)],
    capture_output=True,
    text=True,
)


def logging_verified_for_current_bridge(output: str) -> bool:
    """
    Wake gate: only proceed with LLM run if bridge is connected AND
    at least one message from this group was logged after the current
    bridge session started (proves jsonl is live, not stale from a
    previous session).
    """
    try:
        payload = json.loads(output)
        latest_ts = payload.get("source_latest_chat_timestamp")
        if not isinstance(latest_ts, (int, float)):
            return False
        with urllib.request.urlopen("http://127.0.0.1:3000/health", timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8"))
        uptime = health.get("uptime")
        if health.get("status") != "connected" or not isinstance(uptime, (int, float)):
            return False
        return latest_ts >= time.time() - uptime
    except Exception:
        return False


if result.stdout:
    print(result.stdout, end="")
if result.stderr:
    print(result.stderr, end="", file=sys.stderr)

# The scheduler reads this final line as a wake gate.
# wakeAgent: false → skip LLM + skip delivery (bridge not proven live).
# wakeAgent: true  → proceed with summary.
print(json.dumps({"wakeAgent": logging_verified_for_current_bridge(result.stdout)}))

sys.exit(result.returncode)
