#!/usr/bin/env python3
"""
Helper script to create a new WhatsApp group summary wrapper.

Generates a zero-argument wrapper script for a specific group, ready to use
as a cron job 'script' field in Hermes.

Usage:
    python create-group-wrapper.py \\
        --chat-id "120363402262217562@g.us" \\
        --group-name "VibeDev ID" \\
        --hours 12
"""

import argparse
import os
from pathlib import Path

TEMPLATE = '''#!/usr/bin/env python3
"""Auto-generated wrapper for {group_name} WhatsApp Group Summary."""
import json
import subprocess
import sys
import time
import urllib.request

TARGET_CHAT = "{chat_id}"
HOURS_BACK = {hours_back}

result = subprocess.run(
    [sys.executable, "whatsapp-group-summary.py", TARGET_CHAT, str(HOURS_BACK)],
    capture_output=True,
    text=True,
)


def logging_verified_for_current_bridge(output: str) -> bool:
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

print(json.dumps({{"wakeAgent": logging_verified_for_current_bridge(result.stdout)}}))

sys.exit(result.returncode)
'''


def main():
    parser = argparse.ArgumentParser(description="Create WhatsApp group summary wrapper")
    parser.add_argument("--chat-id", required=True, help="WhatsApp group chat ID (e.g. 12036...@g.us)")
    parser.add_argument("--group-name", required=True, help="Group name (used for filename and display)")
    parser.add_argument("--hours", type=int, default=12, help="Hours back to summarize (default: 12)")
    args = parser.parse_args()

    safe_name = args.group_name.lower().replace(" ", "-").replace("_", "-")
    filename = f"{safe_name}-summary.py"
    scripts_dir = Path.home() / ".hermes" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    output_path = scripts_dir / filename

    content = TEMPLATE.format(
        group_name=args.group_name,
        chat_id=args.chat_id,
        hours_back=args.hours,
    )

    output_path.write_text(content)
    os.chmod(output_path, 0o755)

    print(f"✅ Wrapper created: {output_path}")
    print(f"   Chat ID : {args.chat_id}")
    print(f"   Hours   : {args.hours}")
    print()
    print("Next step — ask Hermes to create the cron job:")
    print(f'  Buat cron job: nama "{args.group_name} {args.hours}-jam summary",')
    print(f'  script "{filename}", schedule "0 5,17 * * *",')
    print(f'  deliver ke whatsapp:{args.chat_id},')
    print(f'  workdir ~/.hermes/scripts, skill hermes-wag-summarizer')


if __name__ == "__main__":
    main()
