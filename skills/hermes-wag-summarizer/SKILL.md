---
name: hermes-wag-summarizer
description: Plug & play guide to set up automatic WhatsApp group summaries with Hermes Agent — pairing, bot behavior config, parser script, wrapper, and cron job in one place.
version: 2.0.0
metadata:
  hermes:
    tags: [whatsapp, cron, summary, digest, group, plug-and-play, onboarding]
    related_skills: [whatsapp-jsonl-cron-digest, whatsapp-group-reply-gating, whatsapp-bridge-watchdog, whatsapp-bridge-diagnostics]
---

# Hermes WAG Summarizer

End-to-end guide to get Hermes automatically summarizing a WhatsApp group on a schedule and delivering the digest back to the same group (or anywhere else).

**What you get when done:**
- Hermes bot in your WhatsApp group, stays silent unless @mentioned
- Only you (the owner) can DM the bot — other contacts are blocked
- Automatic digest every 12 hours (configurable), delivered to the group
- Short, scannable format — 150–400 words, bulleted, readable in 30 seconds on mobile

**For production details, advanced config, and incident history of a live setup, see `whatsapp-jsonl-cron-digest`.**

---

## Prerequisites

- Hermes Agent running on a VPS (Linux)
- A phone number dedicated to the bot (recommended) or your own number
- The Hermes gateway running (`hermes gateway start` or via systemd)

---

## Step 1 — Pair WhatsApp

```bash
hermes whatsapp
```

Scan the QR code with the bot's WhatsApp. Wait for "WhatsApp connected" in the logs. The bridge starts at `http://localhost:3000`.

Verify:
```bash
curl -s http://localhost:3000/health
# expected: {"status":"connected", ...}
```

---

## Step 2 — Configure bot behavior

This is the most important config step. Without it, the bot responds to every message in every group.

**What each setting does:**
- `require_mention: true` — bot only responds when @mentioned, replied to, or a message starts with `/`. Ordinary group chatter is ignored.
- `group_policy: open` — allows groups to trigger the bot at all. The default is `pairing` which silently blocks all groups.
- `dm_policy: allowlist` — only numbers in `allow_from` can DM the bot.
- `allow_from` — your phone number (without `+`, with country code). Everyone else is blocked.

**Edit `~/.hermes/config.yaml`** (use shell or `hermes config`, do NOT use agent patch/write_file on this file):

```yaml
whatsapp:
  require_mention: true
  group_policy: open
  dm_policy: allowlist
  allow_from:
    - "628XXXXXXXXX"   # your phone number, no + sign
  extra:
    group_policy: open
    dm_policy: allowlist
    allow_from:
      - "628XXXXXXXXX"
```

**Edit `~/.hermes/.env`**:

```bash
WHATSAPP_ALLOWED_USERS=628XXXXXXXXX
WHATSAPP_REQUIRE_MENTION=true
WHATSAPP_GROUP_POLICY=open
WHATSAPP_DM_POLICY=allowlist
```

**Also set in config.yaml** (prevents LLM response wrapping in group deliveries):

```yaml
cron:
  wrap_response: false
```

Restart gateway after making changes (ask your Hermes operator / confirm first):
```bash
systemctl --user restart hermes-gateway.service
```

**Verify behavior:**
- Send a plain message in the group → bot stays silent ✓
- @mention the bot → bot responds ✓
- DM from your number → bot responds ✓
- DM from another number → bot stays silent ✓

---

## Step 3 — Verify messages.jsonl is live

The summary cron reads messages from `~/.hermes/whatsapp/messages.jsonl`. This file must grow as new messages arrive.

```bash
# Check file exists and is recent
ls -lh ~/.hermes/whatsapp/messages.jsonl

# Send a test message to any group, then:
tail -2 ~/.hermes/whatsapp/messages.jsonl | python3 -m json.tool
```

**If the file is missing or never updates**, the bridge.js in your Hermes version may not have JSONL logging. See `whatsapp-jsonl-cron-digest` → "Data source" section and `references/bridge-js-jsonl-patch.md` for the fix.

---

## Step 4 — Find your group chat ID

```bash
python3 - << 'EOF'
import json
from pathlib import Path

seen = {}
with open(Path.home() / ".hermes/whatsapp/messages.jsonl") as f:
    for line in f:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("isGroup") and obj.get("chatId") not in seen:
            seen[obj["chatId"]] = obj.get("chatName", "?")

for cid, name in seen.items():
    print(f"{cid}  →  {name}")
EOF
```

Note down the `chatId` for your target group (format: `120363XXXXXXXXXXXXXXX@g.us`).

---

## Step 5 — Deploy scripts and create the cron job

**5a. Copy the parser script to your scripts directory:**

```bash
mkdir -p ~/.hermes/scripts
cp ~/.hermes/skills/productivity/hermes-wag-summarizer/scripts/whatsapp-group-summary.py \
   ~/.hermes/scripts/
```

Smoke test:
```bash
cd ~/.hermes/scripts
python3 whatsapp-group-summary.py "120363XXXXXXXXXXXXXXX@g.us" 12 | python3 -m json.tool | head -20
# Should show message_count > 0 if the group had activity in the last 12h
```

**5b. Create a wrapper script for your group:**

Copy `scripts/wrapper-template.py` from this skill and edit it:

```bash
cp ~/.hermes/skills/productivity/hermes-wag-summarizer/scripts/wrapper-template.py \
   ~/.hermes/scripts/mygroupname-summary.py
```

Edit the two values at the top:
```python
TARGET_CHAT = "120363XXXXXXXXXXXXXXX@g.us"  # your group chat ID
HOURS_BACK = 12
```

**5c. Create the cron job** (ask Hermes to create it, or use the template below):

```
Name:     My Group 12-jam summary
Script:   mygroupname-summary.py
Schedule: 0 5,17 * * *        ← 12:00 & 00:00 WIB
Deliver:  whatsapp:120363XXXXXXXXXXXXXXX@g.us
Workdir:  ~/.hermes/scripts
Skills:   productivity/hermes-wag-summarizer
```

Or tell Hermes:
> Buat cron job: nama "VibeDev ID 12-jam summary", script vibedev-summary.py, schedule "0 5,17 * * *", deliver ke whatsapp:120363XXXXXXXXXXXXXXX@g.us, workdir ~/.hermes/scripts, skill hermes-wag-summarizer

---

## Cron prompt template

Use this as the prompt when creating the cron job. Replace `[Nama Grup]` with your group name.

```
Kamu menerima data JSON dari script pre-run yang berisi pesan-pesan WhatsApp dari grup [Nama Grup] untuk 12 jam terakhir.

Tugas: Buat ringkasan SINGKAT, PADAT, dan TO THE POINT dalam Bahasa Indonesia.
Target panjang: 150-400 kata total. Orang baca di HP, harus bisa scan dalam 30 detik.

Struktur output:

*Ringkasan [Nama Grup] - 12 Jam Terakhir* [1 emoji]

• [Topik 1: 1-2 kalimat langsung ke inti]
• [Topik 2: ...]
• [dst — gabungkan obrolan serupa, lewati yang trivial]

*Pertanyaan terbuka:*
- [pertanyaan yang belum terjawab, atau "—" kalau gak ada]

*Link:*
- [url + konteks 1 baris, atau "—" kalau gak ada]

Aturan:
- Setiap topik MAXIMAL 2 kalimat. Bukan paragraf panjang.
- Gunakan • (bullet) untuk topik.
- Jangan pakai sub-heading per topik.
- Gunakan *teks* (satu bintang) untuk penekanan. JANGAN **bold**.
- Emoji maksimal 2-3 total.
- Gabungkan obrolan kecil/santai jadi 1 bullet kalau perlu disebut.
- Abaikan spam/stiker/emoji-only.
- JANGAN respond dengan [SILENT].
- Kalau message_count: 0, kirim: judul + "Belum ada aktivitas chat di grup selama 12 jam terakhir."
```

---

## Output format example

```
*Ringkasan VibeDev ID - 12 Jam Terakhir* 🚀

• *Kimi K3 open-weight resmi rilis* — Moonshot AI drop 2.8T params, context 1M, native vision. Independent testing nemu 51% hallucination rate yang gak ada di benchmark resmi.

• *Karakter China muncul di output Opus 5* — dicurigai ribuan akun pakai API Anthropic dari Asia Tenggara untuk distilasi model ke China.

• *fastworks-mcp* dari Indra — bisa dicolok ke Hermes buat agent tawar-menawar otomatis sama client.

• Obrolan kecil: ada member kena WA ban, rekomen cap.so sebagai screen recorder.

*Pertanyaan terbuka:*
- Biteship API untuk kirim barang — belum ada yang jawab.

*Link:*
- https://kimi.com/blog/kimi-k3 — official Kimi K3 announcement
```

---

## Config reference (complete)

```yaml
# ~/.hermes/config.yaml

whatsapp:
  require_mention: true        # only respond to @mention / reply / leading /
  group_policy: open           # allow groups (default 'pairing' = blocks all groups!)
  dm_policy: allowlist         # only allow_from numbers can DM
  allow_from:
    - "628XXXXXXXXX"           # owner phone, no + sign
  extra:
    group_policy: open         # must be set in both places
    dm_policy: allowlist
    allow_from:
      - "628XXXXXXXXX"

cron:
  wrap_response: false         # clean delivery without "Cronjob Response:" header
```

```bash
# ~/.hermes/.env

WHATSAPP_ALLOWED_USERS=628XXXXXXXXX
WHATSAPP_REQUIRE_MENTION=true
WHATSAPP_GROUP_POLICY=open
WHATSAPP_DM_POLICY=allowlist
```

---

## Pitfalls

**`group_policy` defaults to `pairing` which silently blocks ALL groups.** This is the most common reason the bot never replies in a group. Always set it to `open`.

**`messages.jsonl` may not exist on modern Hermes installs.** The bridge.js JSONL logger was removed from newer versions. Summaries will always return 0 messages. Fix: see `references/bridge-js-jsonl-patch.md` in `whatsapp-jsonl-cron-digest`.

**Cron script arguments don't work.** The scheduler treats the entire `script` field as a file path. Passing `whatsapp-group-summary.py 120363...@g.us 12` will fail with "Script not found". Always use a zero-argument wrapper per group.

**Bridge can show `connected` but summaries return 0 messages.** Bridge enters a stuck state after crash/decrypt failure where health looks fine but it stopped writing to jsonl. Fix: restart gateway. Set up `whatsapp-bridge-watchdog` for proactive alerts.

**`group_policy: open` without `require_mention: true` makes the bot respond to everything.** Always pair them together.

**Do NOT set `WHATSAPP_ALLOWED_USERS=*`** — opens the bot to everyone at the bridge level.

---

## Troubleshooting

| Symptom | Check | Fix |
|---------|-------|-----|
| Bot never replies when @mentioned in group | `group_policy` in config + .env | Set `group_policy: open` in both places |
| Bot replies to every message | `require_mention` | Set `require_mention: true` |
| Summary always shows 0 messages | `ls -lh ~/.hermes/whatsapp/messages.jsonl` | Apply bridge.js JSONL patch |
| Script not found error in cron | Wrapper filename | Use zero-argument wrapper, not script with args |
| Bridge health OK but jsonl stale | `tail ~/.hermes/whatsapp/messages.jsonl` | Restart gateway |
| Bot replies to DMs from strangers | `dm_policy` + `allow_from` | Set `dm_policy: allowlist` + your number |

---

## For production setups

Once running, load `whatsapp-jsonl-cron-digest` for:
- Live inventory of your active cron jobs
- Advanced parser diagnostics
- Bridge watchdog setup
- Failed delivery recovery recipes
- Known incident post-mortems
