#!/usr/bin/env python3
"""
Parser script for WhatsApp group summary cron job.

Reads ~/.hermes/whatsapp/messages.jsonl, filters messages for the target group
within the last N hours, and outputs JSON to stdout for the AI to summarize.

Usage: python whatsapp-group-summary.py <chat_id> [<hours_back>]
  chat_id:    e.g. 120363402262217562@g.us
  hours_back: default 12

Deploy to: ~/.hermes/scripts/whatsapp-group-summary.py
Do NOT call this directly from a cron job — use a zero-argument wrapper.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def sanitize_text(text: str) -> str:
    """Remove invisible Unicode characters that can trigger cron prompt-injection scanner."""
    if not isinstance(text, str):
        return text
    invisible_chars = {
        '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
        '\u202a', '\u202b', '\u202c', '\u202d', '\u202e'
    }
    for char in invisible_chars:
        text = text.replace(char, '')
    return text


def get_messages_file():
    """Find the messages.jsonl file, checking rotated backups if needed."""
    home = Path.home()
    base = home / ".hermes" / "whatsapp" / "messages.jsonl"
    if base.exists():
        return base
    backup = home / ".hermes" / "whatsapp" / "messages.jsonl.1"
    if backup.exists():
        return backup
    return base  # will trigger "not found" below


def main():
    if len(sys.argv) < 2:
        print("Usage: whatsapp-group-summary.py <chat_id> [hours_back]", file=sys.stderr)
        sys.exit(1)

    target_chat = sys.argv[1].strip()
    hours_back = int(sys.argv[2]) if len(sys.argv) > 2 else 12

    messages_file = get_messages_file()
    if not messages_file.exists():
        print(json.dumps({
            "error": "messages.jsonl not found — bridge may not have JSONL logging enabled. "
                     "See whatsapp-jsonl-cron-digest skill for the bridge.js patch.",
            "checked_path": str(messages_file),
            "message_count": 0,
            "messages": [],
        }))
        sys.exit(0)

    now_dt = datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    cutoff_ts = now_ts - (hours_back * 3600)

    messages = []
    total_lines = 0
    source_latest_chat_ts = None

    try:
        with open(messages_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_lines += 1
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                chat_id = obj.get("chatId", "")
                if chat_id != target_chat:
                    continue

                # Track most recent message timestamp for wake gate
                received_at = obj.get("receivedAt")
                msg_timestamp = obj.get("timestamp")

                ts_sec = None
                if isinstance(received_at, (int, float)) and received_at > 1_000_000_000_000:
                    ts_sec = received_at / 1000.0
                elif isinstance(msg_timestamp, (int, float)):
                    ts_sec = msg_timestamp

                if ts_sec is not None:
                    if source_latest_chat_ts is None or ts_sec > source_latest_chat_ts:
                        source_latest_chat_ts = ts_sec

                # Time window filter
                if ts_sec is None or ts_sec < cutoff_ts:
                    continue

                messages.append({
                    "senderName": sanitize_text(obj.get("senderName", "Unknown")),
                    "senderId": obj.get("senderId", ""),
                    "body": sanitize_text(obj.get("body", "")),
                    "timestamp": ts_sec,
                    "hasMedia": obj.get("hasMedia", False),
                    "mediaType": obj.get("mediaType", ""),
                })
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "message_count": 0,
            "messages": [],
        }))
        sys.exit(0)

    messages.sort(key=lambda m: m["timestamp"])

    output = {
        "target_chat": target_chat,
        "hours_back": hours_back,
        "now_utc": now_dt.isoformat(),
        "cutoff_utc": datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).isoformat(),
        "source_latest_chat_timestamp": source_latest_chat_ts,
        "source_latest_chat_utc": (
            datetime.fromtimestamp(source_latest_chat_ts, tz=timezone.utc).isoformat()
            if source_latest_chat_ts else None
        ),
        "source_file_mtime_utc": datetime.fromtimestamp(
            messages_file.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
        "total_lines_scanned": total_lines,
        "matched_messages": len(messages),
        "message_count": len(messages),
        "messages": messages,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
