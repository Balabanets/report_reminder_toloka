# 🤖 Slack Activity Reminder Bot

A Slack bot that automatically checks expert activities in Databricks and sends daily reminders via Slack. Designed for tracking expert report submissions and managing team performance.

**Status:** Production Ready | **Version:** 1.0 | **License:** MIT

---

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Commands](#commands)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

- **Daily Activity Checks** — Automated checks at 7 PM (19:00) for expert activities
- **Smart Filtering** — Filter activities by `monday_subitem_id` per expert
- **Direct Notifications** — Send private Slack messages to experts who haven't completed reports
- **Manager Reports** — Daily summary reports sent to managers showing who filled/missed reports
- **Subitems Management** — Enable/disable tracking of specific monday subitems per expert
- **Admin Controls** — 17 slash commands for managing experts, managers, and administrators
- **Audit Logging** — Complete logging of all actions to systemd journalctl
- **Automatic Restart** — Systemd service with auto-restart on failure

---

## 🏗️ Architecture

### Components

```
┌─────────────────────────────────────┐
│  Slack Workspace                    │
│  (Socket Mode WebSocket)            │
└────────────────┬────────────────────┘
                 │ (WSS)
         ┌───────▼────────┐
         │                │
    ┌────┴────────────────┴───┐
    │ Slack Reminder Bot      │
    │ (systemd service)       │
    └────┬──────────────┬─────┘
         │              │
    ┌────▼──────┐  ┌────▼────────────────┐
    │  SQLite   │  │  Databricks         │
    │  (local)  │  │  (HTTPS, token auth)│
    └───────────┘  └─────────────────────┘
```

### Tech Stack

- **Framework:** Slack Bolt (Python)
- **Scheduling:** APScheduler (asyncio)
- **Database:** SQLite (local)
- **Data Warehouse:** Databricks SQL Connector
- **Logging:** structlog + systemd journalctl
- **Process Management:** systemd service

### Database Schema

```sql
-- Experts to track
CREATE TABLE experts (
    id INTEGER PRIMARY KEY,
    worker_id TEXT UNIQUE,
    slack_user_id TEXT,
    name TEXT,
    active INTEGER DEFAULT 1
);

-- Slack user IDs for those who can execute admin commands
CREATE TABLE admins (
    id INTEGER PRIMARY KEY,
    slack_user_id TEXT UNIQUE
);

-- Managers who receive daily reports
CREATE TABLE managers (
    id INTEGER PRIMARY KEY,
    slack_user_id TEXT UNIQUE,
    name TEXT
);

-- Monday.com subitem IDs to track per expert
CREATE TABLE expert_subitems (
    id INTEGER PRIMARY KEY,
    expert_id INTEGER,
    monday_subitem_id TEXT,
    active INTEGER DEFAULT 1,
    UNIQUE(expert_id, monday_subitem_id),
    FOREIGN KEY(expert_id) REFERENCES experts(id)
);

-- Execution log (prevents duplicate reminders on restart)
CREATE TABLE run_log (
    id INTEGER PRIMARY KEY,
    run_date TEXT,
    run_type TEXT,
    status TEXT,
    UNIQUE(run_date, run_type)
);
```

---

## 🚀 Installation

### Prerequisites

- Python 3.10+
- Slack workspace (you must be an admin)
- Databricks account with SQL warehouse access
- Linux/Unix system with systemd

### Step 1: Clone Repository

```bash
git clone https://github.com/Balabanets/report_reminder_toloka.git
cd report_reminder_toloka
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Set Up Slack App

1. Go to https://api.slack.com/apps
2. Create New App → From scratch
3. App name: `Activity Reminder Bot`
4. Enable Socket Mode
5. Create App-Level Token with `connections:write` + `connections:read`
6. Add OAuth Scopes:
   - `chat:write`
   - `chat:write.public`
   - `commands`
   - `users:read`
   - `users:read.email`
   - `app_mentions:read`
7. Create 17 slash commands (see [Commands](#commands))
8. Subscribe to Bot Events: `app_mention`, `message.im`
9. Install app to your workspace

### Step 4: Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
nano .env
```

**Required variables:**
```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
DATABRICKS_HOST=adb-xxxxxxxx.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxxx
DATABRICKS_TOKEN=dapi...
DB_PATH=./data/bot.db
TIMEZONE=Europe/Berlin
INITIAL_ADMIN_SLACK_ID=U0XXXXXX
```

### Step 5: Initialize Database

```bash
python3 << 'EOF'
from db import Database
import asyncio

async def init():
    db = Database("./data/bot.db")
    await db.init()

asyncio.run(init())
EOF
```

### Step 6: Install as Systemd Service

```bash
sudo cp slack-reminder-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable slack-reminder-bot
sudo systemctl start slack-reminder-bot
```

### Step 7: Verify Installation

```bash
sudo systemctl status slack-reminder-bot
journalctl -u slack-reminder-bot -f
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token | ✅ Yes |
| `SLACK_APP_TOKEN` | Slack App-Level Token (Socket Mode) | ✅ Yes |
| `SLACK_SIGNING_SECRET` | Slack Request Signing Secret | ⚠️ Optional (Socket Mode) |
| `DATABRICKS_HOST` | Databricks workspace hostname | ✅ Yes |
| `DATABRICKS_HTTP_PATH` | SQL warehouse HTTP path | ✅ Yes |
| `DATABRICKS_TOKEN` | Personal API token | ✅ Yes |
| `DB_PATH` | SQLite database path | ⚠️ Default: `./data/bot.db` |
| `TIMEZONE` | Timezone for scheduling | ⚠️ Default: `Europe/Berlin` |
| `INITIAL_ADMIN_SLACK_ID` | First admin's Slack User ID | ⚠️ Optional |

### Scheduling

The bot checks at **7 PM (19:00)** every day in your configured timezone.

To change: Edit `scheduler.py` line 153-158 and restart the service.

---

## 📖 Usage

### Adding Experts

```
/expert-add <worker_id> <slack_id> <name>

Example:
/expert-add abc123xyz U123456 "John Doe"
```

### Configuring Activity Tracking

```
# Add monday subitem to track for an expert
/expert-subitem-add <worker_id> <subitem_id>

# Example:
/expert-subitem-add abc123xyz 7297335207
```

### Toggling Subitems

```
# Temporarily disable subitem tracking (don't delete)
/expert-subitem-toggle <worker_id> <subitem_id>

# Re-enable with same command
/expert-subitem-toggle abc123xyz 7297335207
```

### Daily Workflow

1. **7 PM (19:00)** — Bot checks Databricks for activities
2. Bot filters by expert's active `monday_subitem_id`
3. If no activity found → sends reminder to expert's DM
4. Sends summary report to all managers
5. Logs everything to `journalctl`

---

## 🔧 Commands

### 👥 Expert Management (4 commands)

- `/expert-add <worker_id> <slack_id> <name>` — Add expert
- `/expert-remove <worker_id>` — Remove expert
- `/expert-list` — Show all experts
- `/expert-toggle <worker_id>` — Enable/disable expert

### 📌 Subitem Management (4 NEW commands)

- `/expert-subitem-add <worker_id> <subitem_id>` — Add activity to track
- `/expert-subitem-remove <worker_id> <subitem_id>` — Delete activity from tracking
- `/expert-subitem-list <worker_id>` — Show all subitems (active/disabled)
- `/expert-subitem-toggle <worker_id> <subitem_id>` — Temporarily disable/enable

### 👔 Manager Management (3 commands)

- `/manager-add <slack_id> <name>` — Add manager for reports
- `/manager-remove <slack_id>` — Remove manager
- `/manager-list` — Show all managers

### 👨‍💼 Admin Management (3 commands)

- `/admin-add <slack_id>` — Add administrator
- `/admin-remove <slack_id>` — Remove administrator
- `/admin-list` — Show all administrators

### 🤖 Bot Management (3 commands)

- `/bot-help` — Show command help
- `/bot-run-now` — Run activity check immediately (for testing)
- `/bot-status` — Show bot status and recent logs

---

## 🔒 Security

### Authentication & Authorization

- ✅ **Slack Bolt signature verification** — Automatic protection against MITM
- ✅ **Admin-only commands** — Stored in SQLite, checked before execution
- ✅ **Ephemeral responses** — Command responses visible only to user
- ✅ **Socket Mode** — WebSocket instead of HTTP webhooks (no exposed ports)
- ✅ **Parametrized SQL** — Protection against SQL injection

### Secrets Management

- ✅ Tokens stored in `.env` file (not in code)
- ✅ `.env` in `.gitignore` (never committed)
- ✅ File permissions: `chmod 600` (owner only)
- ❌ Not in secrets manager (recommended for production)

### Data Access

- ✅ **Databricks:** SELECT only on activities table
- ✅ **Slack:** Minimal scopes (no history, files, or admin access)
- ✅ **Database:** Local SQLite, user `creative` only

### Logging

- ✅ Command audit logging (who executed what)
- ✅ No sensitive data logged (tokens, emails)
- ❌ Logs stored on server (recommend backup)

For detailed security info, see `SECURITY_AUDIT_RESPONSES.md`

---

## 📊 Monitoring

### View Real-Time Logs

```bash
journalctl -u slack-reminder-bot -f
```

### Check Service Status

```bash
systemctl status slack-reminder-bot
```

### View Recent Check History

```bash
cd /path/to/bot && python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./data/bot.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM run_log ORDER BY id DESC LIMIT 10")
for row in cursor.fetchall():
    print(row)
conn.close()
EOF
```

### Common Log Patterns

```bash
# View only errors
journalctl -u slack-reminder-bot | grep ERROR

# View command executions
journalctl -u slack-reminder-bot | grep "command"

# Last 50 lines
journalctl -u slack-reminder-bot -n 50

# Since specific time
journalctl -u slack-reminder-bot --since "2 hours ago"
```

---

## 🐛 Troubleshooting

### Bot not responding to commands

```bash
# Check if service is running
systemctl status slack-reminder-bot

# Check for connection errors
journalctl -u slack-reminder-bot | grep -i "error\|connection"

# Try restart
sudo systemctl restart slack-reminder-bot
```

### "No active experts found" warning

```bash
# Check if experts are added
/expert-list

# Check if they have subitems configured
/expert-subitem-list <worker_id>

# At least one subitem per expert is required
/expert-subitem-add <worker_id> <subitem_id>
```

### Slack token issues

```bash
# Verify tokens are in .env
grep SLACK .env

# Check if token is valid (should see "⚡️ Bolt app is running!")
journalctl -u slack-reminder-bot | grep "Bolt"
```

### Database errors

```bash
# Check database exists
ls -la data/bot.db

# Check database integrity
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./data/bot.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cursor.fetchall())
conn.close()
EOF
```

---

## 📚 Documentation

- `SECURITY_AUDIT_RESPONSES.md` — Security Q&A
- `SECURITY_AND_INFRASTRUCTURE_REPORT.md` — Detailed security audit
- `SLACK_QUICK_SETUP.md` — 5-minute Slack setup guide
- `SLACK_BOT_SETUP.md` — Complete technical setup
- `MONDAY_SUBITEM_DESIGN.md` — Subitem feature design
- `SLACK_BOT_COMMANDS_UPDATED.md` — All 17 commands documented

---

## 🤝 Contributing

1. Test changes locally before committing
2. Update documentation if adding features
3. Don't commit `.env` or database files
4. Follow existing code style

---

## 📝 License

MIT License - see LICENSE file

---

## ❓ Support

For issues or questions:
1. Check logs: `journalctl -u slack-reminder-bot -f`
2. See troubleshooting section above
3. Check documentation files in repo

---

**Made with ❤️ for team productivity**
