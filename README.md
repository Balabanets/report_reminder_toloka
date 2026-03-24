# Slack Activity Reminder Bot

Slack bot for tracking off-platform expert activities. Monitors report submission via Databricks, sends daily reminders to experts, and provides summary reports to managers at 7 PM.

---

## How It Works

1. **7 PM Daily Check** — Queries Databricks for submitted activity reports
2. **Smart Filtering** — Only checks activity types (subitems) configured per expert
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

## Access Model

**Experts** — tracked employees who fill out activity reports.
- Receive a DM reminder if their report is missing for the previous day
- Reminder includes a direct link to the activity form
- No access to any bot commands

**Managers** — team leads who monitor report completion.
- Receive a daily summary report at 19:00 showing who filled / who missed
- Filled experts are listed with specific subitem names (e.g. Samples creation, QA)
- No access to any bot commands

**Admins** — bot operators who manage configuration.
- Full access to all slash commands listed below
- Can add/remove experts, managers, and other admins
- Can trigger manual checks (`/bot-run-now`) and previews (`/bot-dry-run`)
- Do not receive any automated messages

---

## Slash Commands (Admin Only)

### Expert Management
| Command | Usage | Description |
|---------|-------|-------------|
| `/expert-add` | `[worker_id] [slack_id] [name]` | Add a new expert |
| `/expert-remove` | `[worker_id]` | Remove an expert |
| `/expert-list` | | List all experts with status |
| `/expert-toggle` | `[worker_id]` | Enable/disable an expert |

### Subitem Management
| Command | Usage | Description |
|---------|-------|-------------|
| `/expert-subitem-add` | `[worker_id] [subitem_id]` | Add activity subitem to expert |
| `/expert-subitem-remove` | `[worker_id] [subitem_id]` | Remove activity subitem |
| `/expert-subitem-list` | `[worker_id]` | List subitems for expert |
| `/expert-subitem-toggle` | `[worker_id] [subitem_id]` | Enable/disable a subitem |

### Manager & Admin Management
| Command | Usage | Description |
|---------|-------|-------------|
| `/manager-add` | `[slack_id] [full name]` | Add a report manager |
| `/manager-remove` | `[slack_id]` | Remove a manager |
| `/manager-list` | | List all managers |
| `/admin-add` | `[slack_id]` | Add a bot admin |
| `/admin-remove` | `[slack_id]` | Remove a bot admin |
| `/admin-list` | | List all admins |

### Bot Control
| Command | Description |
|---------|-------------|
| `/bot-dry-run` | Preview report (no reminders sent, only you see it) |
| `/bot-run-now` | Run daily check now (sends reminders + manager report) |
| `/bot-status` | Show recent run history |
| `/bot-help` | Show all available commands |

---

## Database

| Table | Purpose |
|-------|---------|
| `experts` | worker_id, slack_user_id, name, active |
| `expert_subitems` | Activity types tracked per expert |
| `managers` | Who receives daily reports |
| `admins` | Who can execute commands |
| `run_log` | Execution history (prevents duplicate runs) |
| `audit_log` | Admin action audit trail |

---

## Security

- **RBAC** — Admin check on every command
- **Input Validation** — Regex validation for Slack IDs and worker IDs
- **Audit Logging** — All admin actions recorded
- **Credentials** — `.env` file only, never logged, excluded from git
- **Socket Mode** — No incoming ports, outbound WSS only
- **SQL Injection** — All queries use parameterized statements
- **Single Instance** — PID file + systemd prevents duplicate processes
