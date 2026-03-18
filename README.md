# 🤖 Slack Activity Reminder Bot

**Activity Control System for Workforce Managers**

Slack bot designed for systematic tracking of off-platform expert activities — tasks and work performed outside the main working platforms that require manual confirmation in the form of a completed report. Automatically monitors submission status via Databricks, sends daily reminders to experts, and provides summary reports to workforce management teams at 7 PM.

**Status:** Production Ready | **Version:** 1.0

---

## 📋 What It Does

**For Workforce Managers:**
- **Report Tracking** — Monitors which experts submitted required reports for off-platform work
- **Daily Summaries** — 7 PM reports showing completion status and missing submissions
- **Automated Reminders** — Direct Slack DM notifications to experts who haven't completed reports
- **Coverage Assurance** — Ensures all off-platform activities are properly documented and confirmed

**Daily Workflow:**
1. **7 PM Check** — Queries Databricks for submitted reports on configured off-platform activities
2. **Smart Filtering** — Only checks `monday_subitem_id` (activity types) configured per expert
3. **Sends Reminders** — DM to experts who haven't submitted required reports
4. **Manager Reports** — Summary showing who submitted/missed reports sent to workforce managers
5. **Logs Everything** — Complete audit trail in systemd journalctl + SQLite for compliance

**Admin Management:**
- 17 slash commands for managing experts, subitems, managers, admins
- Enable/disable activity tracking per expert and per activity type
- Admin-only access (Slack User IDs verified from DB)

---

## 🏗️ Architecture

```
Slack Workspace (Socket Mode, WSS)
        ↓
Slack Reminder Bot (systemd service)
        ↓
    ┌───┴───┐
    ↓       ↓
  SQLite   Databricks
 (local)  (HTTPS, token)
```

**Database:** 5 tables (experts, expert_subitems, managers, admins, run_log)

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API** | Slack Bolt (Python) | Slack integration |
| **Scheduling** | APScheduler (asyncio) | Daily 7 PM check |
| **Database** | SQLite | Local persistence |
| **Data Source** | Databricks SQL | Activities warehouse |
| **Logging** | structlog | Structured logging to journalctl |
| **Process** | systemd | Auto-restart on failure |
| **Language** | Python 3.10+ | Runtime |

---

## 🔐 Security

### Q&A for Security Teams

#### **Can any Slack user run commands?**
**No.** Only admins. Check before every command:
```python
if not await self.db.is_admin(user_id):
    return "❌ No access"
```
Admin list stored in SQLite `admins` table (Slack User IDs only).

#### **How are tokens protected?**
- ✅ Stored in `.env` file (not in code, not in git)
- ✅ File permissions: `chmod 600` (owner only)
- ✅ Never logged in any output
- ✅ No token examples in documentation
- ⚠️ Manual rotation required (no automated key refresh)

#### **What if bot crashes?**
- Auto-restart via systemd (10 sec delay)
- `run_log` table has `UNIQUE(run_date, run_type)` constraint
- Prevents duplicate reminders on same day

#### **SQL Injection?**
**No.** All queries use parametrized statements:
```python
cursor.execute("SELECT * WHERE worker_id = ?", (worker_id,))
```

#### **Can Databricks token access other tables?**
- Token is SELECT-only (no INSERT/UPDATE/DELETE)
- Scope: one specific table `dmn_core_analytics.cdm.directus_activities_act`
- App-level filtering by worker_id and date
- No admin access to Databricks workspace

#### **Slack message security?**
- Command responses are ephemeral (private to user)
- Slack Bolt auto-verifies X-Slack-Signature
- Socket Mode uses WSS (encrypted WebSocket)
- No incoming ports exposed

#### **What happens if .env is compromised?**
- All three tokens (SLACK_BOT, SLACK_APP, DATABRICKS) would be exposed
- Immediate rotation required:
  - Create new tokens in respective platforms
  - Update .env
  - Restart service: `systemctl restart slack-reminder-bot`
- Recommend: backup .env separately + access monitoring

#### **Rate limiting?**
- Slack handles rate limits (built-in)
- Bot retries on failure: exponential backoff (2s → 4s → 8s)
- No custom rate limiting in code

#### **Separate prod/sandbox keys?**
- **No.** Single `.env` for all environments
- Recommend: separate `.env.prod` and `.env.sandbox` if expanding
- Current design assumes single-instance deployment

#### **Admin audit trail?**
- All commands logged to journalctl with user_id and action
- Example: `Expert added (user_id=U123, worker_id=abc, action=expert_add)`
- Never logs: names, emails, slack_ids, sensitive parameters

#### **Outbound connections only?**
- ✅ Socket Mode (WebSocket to Slack)
- ✅ HTTPS to Databricks
- ✅ No listening ports
- ✅ No incoming firewall rules needed

---

## 📊 Logging

**What's logged:**
- Command executions (user_id, action, resource_id)
- Daily check results (timestamp, count, status)
- Connection events (Slack Socket Mode, Databricks)
- Errors and retries (with exponential backoff info)

**Storage:**
- **systemd journalctl** — Real-time + searchable history
- **SQLite run_log** — Execution history with completion status
- **Slack** — Command confirmations in ephemeral messages

**What's NOT logged:**
- ❌ Slack/Databricks tokens
- ❌ Personal names or emails
- ❌ Full command parameters
- ❌ Expert slack_ids

**View logs:**
```bash
journalctl -u slack-reminder-bot -f          # Real-time
journalctl -u slack-reminder-bot -n 50       # Last 50
journalctl -u slack-reminder-bot | grep ERROR # Errors
```

---

## 📋 Commands (17 Total)

**Experts (4):** `/expert-add`, `/expert-remove`, `/expert-list`, `/expert-toggle`

**Subitems (4):** `/expert-subitem-add`, `/expert-subitem-remove`, `/expert-subitem-list`, `/expert-subitem-toggle`

**Managers (3):** `/manager-add`, `/manager-remove`, `/manager-list`

**Admins (3):** `/admin-add`, `/admin-remove`, `/admin-list`

**Bot (3):** `/bot-help`, `/bot-run-now`, `/bot-status`

---

## 🗄️ Database Schema

| Table | Purpose |
|-------|---------|
| `experts` | Employee records (worker_id, slack_user_id, name, active) |
| `expert_subitems` | Which monday subitems to track per expert |
| `managers` | Who receives daily reports |
| `admins` | Who can execute /commands |
| `run_log` | Execution history (prevents duplicate reminders) |

**Protection:** `UNIQUE(run_date, run_type)` in run_log prevents duplicate reminders if bot restarts same day.

---

## 🚀 Deployment

**Runs as systemd service on Linux:**
- Auto-start on boot
- Auto-restart on crash
- Logs to journalctl
- User: `creative`
- Python 3.10+

---

**Built for Toloka report tracking** 🎯
