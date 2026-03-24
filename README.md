# Slack Activity Reminder Bot

Slack bot for tracking off-platform expert activities. Monitors report submission via Databricks, sends daily reminders to experts, and provides summary reports to managers at 7 PM.

**Status:** Production Ready | **Python:** 3.10+

---

## How It Works

1. **7 PM Daily Check** — Queries Databricks for submitted activity reports
2. **Smart Filtering** — Only checks `monday_subitem_id` configured per expert
3. **Sends Reminders** — DM to experts who haven't submitted reports (with activity form link)
4. **Manager Reports** — Summary of filled/missing reports sent to all active managers
5. **Audit Trail** — All admin actions logged to `audit_log` table

---

## Architecture

```
Slack Workspace (Socket Mode, WSS)
        |
Slack Reminder Bot (Python)
        |
    +---+---+
    |       |
  SQLite   Databricks
 (local)  (HTTPS, token)
```

| Component | Technology |
|-----------|-----------|
| Slack API | Slack Bolt (Socket Mode) |
| Scheduling | APScheduler (cron, 19:00 daily) |
| Database | SQLite |
| Data Source | Databricks SQL |
| Logging | structlog |

---

## Slash Commands

All commands require admin access (RBAC check on every call).

| Command | Description |
|---------|-------------|
| `/bot-help` | Show bot status |
| `/expert-add` | Add expert (worker_id, slack_id, name) |
| `/expert-remove` | Remove expert by worker_id |
| `/expert-list` | List all experts with status |
| `/expert-toggle` | Enable/disable expert |
| `/manager-add` | Add manager (slack_id, name) |
| `/manager-remove` | Remove manager |
| `/manager-list` | List managers |
| `/admin-add` | Add admin |
| `/admin-remove` | Remove admin |
| `/admin-list` | List admins |
| `/subitem-add` | Add monday subitem to expert |
| `/subitem-remove` | Remove subitem |
| `/subitem-list` | List subitems for expert |
| `/subitem-toggle` | Enable/disable subitem |
| `/bot-run-now` | Trigger 7 PM check manually |
| `/bot-status` | Show recent run log |
| `/audit-log` | View admin action history |

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `experts` | worker_id, slack_user_id, name, active |
| `expert_subitems` | monday_subitem_id per expert |
| `managers` | Who receives daily reports |
| `admins` | Who can execute commands |
| `run_log` | Execution history (UNIQUE per date+type) |
| `audit_log` | Admin action audit trail |

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd reminder_bot_toloka
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
chmod 600 .env
# Edit .env with your tokens
```

Required variables:
- `SLACK_BOT_TOKEN` — Bot User OAuth Token (`xoxb-...`)
- `SLACK_APP_TOKEN` — App-Level Token (`xapp-...`)
- `DATABRICKS_HOST` — Databricks workspace URL
- `DATABRICKS_HTTP_PATH` — SQL warehouse HTTP path
- `DATABRICKS_TOKEN` — Databricks PAT
- `INITIAL_ADMIN_SLACK_ID` — First admin's Slack User ID
- `TIMEZONE` — Scheduler timezone (default: `Europe/Berlin`)

### 3. Slack App Configuration

Required Bot Token Scopes:
- `commands` — Slash commands
- `chat:write` — Send messages
- `im:write` — Send DMs
- `users:read` — User info

Enable **Socket Mode** in app settings.

### 4. Run

```bash
python bot.py
```

For production, use `screen` or systemd:
```bash
# screen
screen -d -m -S reminder_bot bash -c './venv/bin/python bot.py'

# systemd (see slack-reminder-bot.service)
sudo systemctl enable slack-reminder-bot
sudo systemctl start slack-reminder-bot
```

---

## Security

- **RBAC** — Admin check on every command via `admins` table
- **Input Validation** — Regex validation for Slack IDs and worker IDs
- **Audit Logging** — All mutating admin actions recorded with user_id, action, details
- **Credentials** — `.env` file only, never logged, excluded from git
- **Socket Mode** — No incoming ports, outbound WSS only
- **SQL Injection** — All queries use parameterized statements
- **Single Instance** — PID file prevents duplicate processes
- **Duplicate Prevention** — `UNIQUE(run_date, run_type)` prevents double reminders

---

## Project Structure

```
bot.py                  # Entry point, Slack app init
admin_handlers.py       # All slash command handlers
scheduler.py            # APScheduler with daily 7 PM job
notifier.py             # Slack message sending
databricks_client.py    # Databricks SQL queries
db.py                   # SQLite database layer
config.py               # Environment config with validation
requirements.txt        # Python dependencies
.env.example            # Environment template
.gitignore              # Excludes .env, data/, *.db, *.pid
slack-reminder-bot.service  # systemd unit file
```
