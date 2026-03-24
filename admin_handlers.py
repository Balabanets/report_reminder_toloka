import re
from slack_bolt import App, Ack, Say
from slack_bolt.context import BoltContext
import structlog
from db import Database
from scheduler import Scheduler
from notifier import Notifier

SLACK_ID_RE = re.compile(r'^U[A-Z0-9]{8,12}$')
WORKER_ID_RE = re.compile(r'^[a-f0-9]{32}$|^[a-zA-Z0-9_]{3,50}$')

logger = structlog.get_logger()


class AdminHandlers:
    def __init__(self, app: App, db: Database, scheduler: Scheduler, notifier: Notifier):
        self.app = app
        self.db = db
        self.scheduler = scheduler
        self.notifier = notifier
        self.register_handlers()

    def register_handlers(self):
        """Register all command handlers"""
        logger.info("Registering command handlers...")
        self.app.command("/bot-help")(self.cmd_help)
        self.app.command("/expert-add")(self.cmd_expert_add)
        logger.info("Registered /expert-add")
        self.app.command("/expert-remove")(self.cmd_expert_remove)
        self.app.command("/expert-list")(self.cmd_expert_list)
        logger.info("Registered /expert-list")
        self.app.command("/expert-toggle")(self.cmd_expert_toggle)
        self.app.command("/expert-subitem-add")(self.cmd_expert_subitem_add)
        self.app.command("/expert-subitem-remove")(self.cmd_expert_subitem_remove)
        self.app.command("/expert-subitem-list")(self.cmd_expert_subitem_list)
        self.app.command("/expert-subitem-toggle")(self.cmd_expert_subitem_toggle)
        self.app.command("/manager-add")(self.cmd_manager_add)
        self.app.command("/manager-remove")(self.cmd_manager_remove)
        self.app.command("/manager-list")(self.cmd_manager_list)
        self.app.command("/admin-add")(self.cmd_admin_add)
        self.app.command("/admin-remove")(self.cmd_admin_remove)
        self.app.command("/admin-list")(self.cmd_admin_list)
        self.app.command("/bot-run-now")(self.cmd_bot_run_now)
        self.app.command("/bot-dry-run")(self.cmd_bot_dry_run)
        self.app.command("/bot-status")(self.cmd_bot_status)
        logger.info("Registered /bot-status")
        logger.info("All command handlers registered successfully")

    def _check_admin(self, user_id: str) -> bool:
        """Check admin permissions"""
        return self.db.is_admin(user_id)

    def cmd_help(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id

        help_text = """
*Admin Commands:*

*Experts:*
`/expert-add <worker_id> <slack_id> <name>` — add expert
`/expert-remove <worker_id>` — remove expert
`/expert-list` — list experts
`/expert-toggle <worker_id>` — enable/disable expert

*Subitems:*
`/expert-subitem-add <worker_id> <subitem_id>` — add subitem
`/expert-subitem-remove <worker_id> <subitem_id>` — remove subitem
`/expert-subitem-list <worker_id>` — list subitems
`/expert-subitem-toggle <worker_id> <subitem_id>` — enable/disable subitem

*Managers:*
`/manager-add <slack_id> <name>` — add manager
`/manager-remove <slack_id>` — remove manager
`/manager-list` — list managers

*Admins:*
`/admin-add <slack_id>` — add admin
`/admin-remove <slack_id>` — remove admin
`/admin-list` — list admins

*Bot Control:*
`/bot-dry-run` — preview report (no reminders sent, only you see it)
`/bot-run-now` — run daily check (sends reminders + manager report)
`/bot-status` — show recent run history
`/bot-help` — this help message
        """
        self.notifier.send_ephemeral(command["response_url"], help_text)

    def cmd_expert_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        logger.info("cmd_expert_add called", user_id=context.user_id)
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        parts = command["text"].split()
        if len(parts) < 3:
            self.notifier.send_ephemeral(
                command["response_url"],
                "❌ Format: `/expert-add <worker_id> <slack_id> <name>`"
            )
            return

        worker_id, slack_id, name = parts[0], parts[1], " ".join(parts[2:])
        if not WORKER_ID_RE.match(worker_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Invalid worker_id format")
            return
        if not SLACK_ID_RE.match(slack_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Invalid slack_id format (expected UXXXXXXXXXX)")
            return
        success = self.db.add_expert(worker_id, slack_id, name)

        if success:
            self.notifier.send_ephemeral(
                command["response_url"],
                f"✅ Expert {name} ({worker_id}) added"
            )
            self.db.log_audit(user_id, "expert_add", f"{name} ({worker_id})")
        else:
            self.notifier.send_ephemeral(
                command["response_url"],
                f"❌ Expert {worker_id} already exists"
            )

    def cmd_expert_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        worker_id = command["text"].strip()
        if not worker_id:
            self.notifier.send_ephemeral(command["response_url"], "❌ Specify worker_id")
            return

        success = self.db.remove_expert(worker_id)
        if success:
            self.db.log_audit(user_id, "expert_remove", worker_id)
        self.notifier.send_ephemeral(
            command["response_url"],
            f"✅ Expert {worker_id} removed" if success else "❌ Error"
        )

    def cmd_expert_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        logger.info("cmd_expert_list called", user_id=context.user_id)
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        experts = self.db.get_all_experts()
        if not experts:
            self.notifier.send_ephemeral(command["response_url"], "No experts found")
            return

        text = f"*Expert List ({len(experts)}):*\n"
        for e in experts:
            status = "✅" if e["active"] else "❌"
            wid = e['worker_id']
            wid_short = f"{wid[:6]}…{wid[-6:]}" if len(wid) > 14 else wid
            text += f"{status} {e['name']} — `{wid_short}` — <@{e['slack_user_id']}>\n"

        self.notifier.send_ephemeral(command["response_url"], text)

    def cmd_expert_toggle(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        worker_id = command["text"].strip()
        result = self.db.toggle_expert(worker_id)

        if result is None:
            self.notifier.send_ephemeral(command["response_url"], "❌ Expert not found")
        else:
            status = "✅ enabled" if result else "❌ disabled"
            self.db.log_audit(user_id, "expert_toggle", f"{worker_id} -> {status}")
            self.notifier.send_ephemeral(
                command["response_url"],
                f"{status}"
            )

    def cmd_manager_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["response_url"],
                "❌ Format: `/manager-add <slack_id> <name>`"
            )
            return

        slack_id, name = parts[0], " ".join(parts[1:])
        if not SLACK_ID_RE.match(slack_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Invalid slack_id format (expected UXXXXXXXXXX)")
            return
        success = self.db.add_manager(slack_id, name)

        if success:
            self.db.log_audit(user_id, "manager_add", f"{name} ({slack_id})")
            self.notifier.send_ephemeral(command["response_url"], f"✅ Manager {name} added")
        else:
            self.notifier.send_ephemeral(command["response_url"], f"❌ Manager already exists")

    def cmd_manager_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        slack_id = command["text"].strip()
        success = self.db.remove_manager(slack_id)
        if success:
            self.db.log_audit(user_id, "manager_remove", slack_id)
        self.notifier.send_ephemeral(
            command["response_url"],
            f"✅ Manager removed" if success else "❌ Error"
        )

    def cmd_manager_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        managers = self.db.get_all_managers()
        if not managers:
            self.notifier.send_ephemeral(command["response_url"], "No managers found")
            return

        text = f"*Manager List ({len(managers)}):*\n"
        for m in managers:
            status = "✅" if m["active"] else "❌"
            text += f"{status} {m['name']} — <@{m['slack_user_id']}>\n"

        self.notifier.send_ephemeral(command["response_url"], text)

    def cmd_admin_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        slack_id = command["text"].strip()
        if not SLACK_ID_RE.match(slack_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Invalid slack_id format (expected UXXXXXXXXXX)")
            return
        success = self.db.add_admin(slack_id)
        if success:
            self.db.log_audit(user_id, "admin_add", slack_id)
        self.notifier.send_ephemeral(
            command["response_url"],
            f"✅ Admin added" if success else "❌ Already an admin"
        )

    def cmd_admin_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        slack_id = command["text"].strip()
        success = self.db.remove_admin(slack_id)
        if success:
            self.db.log_audit(user_id, "admin_remove", slack_id)
        self.notifier.send_ephemeral(
            command["response_url"],
            f"✅ Admin removed" if success else "❌ Error"
        )

    def cmd_admin_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        admins = self.db.get_all_admins()
        if not admins:
            self.notifier.send_ephemeral(command["response_url"], "No admins found")
            return

        lines = []
        for slack_id in admins:
            try:
                resp = self.app.client.users_info(user=slack_id)
                name = resp["user"].get("real_name", slack_id)
            except Exception:
                name = slack_id
            lines.append(f"• {name} — <@{slack_id}>")
        text = f"*Admin List ({len(admins)}):*\n" + "\n".join(lines)
        self.notifier.send_ephemeral(command["response_url"], text)

    def cmd_bot_run_now(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        self.db.log_audit(user_id, "bot_run_now", "")
        self.notifier.send_ephemeral(command["response_url"], "✅ Check started — reminders will be sent to experts")
        import threading
        threading.Thread(target=self.scheduler.job_check_7pm, kwargs={"manual": True}, daemon=True).start()

    def cmd_bot_dry_run(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        self.db.log_audit(user_id, "bot_dry_run", "")
        self.notifier.send_ephemeral(command["response_url"], "✅ Dry run started — report will be sent only to you, no expert reminders")
        import threading
        threading.Thread(
            target=self.scheduler.job_check_7pm,
            kwargs={"dry_run": True, "dry_run_user": user_id},
            daemon=True
        ).start()

    def cmd_bot_status(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        runs = self.db.get_recent_runs(10)
        if not runs:
            self.notifier.send_ephemeral(command["response_url"], "No logs found")
            return

        text = "*Recent Runs:*\n"
        for r in runs:
            status_emoji = "✅" if r["status"] == "completed" else "❌"
            text += f"{status_emoji} {r['run_type']} ({r['run_date']}) - {r['status']}\n"

        self.notifier.send_ephemeral(command["response_url"], text)

    # ===== EXPERT SUBITEMS =====

    def cmd_expert_subitem_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["response_url"],
                "❌ Format: `/expert-subitem-add <worker_id> <subitem_id>`"
            )
            return

        worker_id, subitem_id = parts[0], int(parts[1])

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["response_url"], f"❌ Expert {worker_id} not found")
            return

        success = self.db.add_expert_subitem(expert['id'], subitem_id)
        if success:
            self.db.log_audit(user_id, "subitem_add", f"{worker_id} subitem={subitem_id}")
            self.notifier.send_ephemeral(
                command["response_url"],
                f"✅ Subitem {subitem_id} added for {expert['name']}"
            )
        else:
            self.notifier.send_ephemeral(
                command["response_url"],
                f"❌ Subitem {subitem_id} already exists"
            )

    def cmd_expert_subitem_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["response_url"],
                "❌ Format: `/expert-subitem-remove <worker_id> <subitem_id>`"
            )
            return

        worker_id, subitem_id = parts[0], int(parts[1])

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["response_url"], f"❌ Expert {worker_id} not found")
            return

        self.db.remove_expert_subitem(expert['id'], subitem_id)
        self.db.log_audit(user_id, "subitem_remove", f"{worker_id} subitem={subitem_id}")
        self.notifier.send_ephemeral(
            command["response_url"],
            f"✅ Subitem {subitem_id} removed"
        )

    def cmd_expert_subitem_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        worker_id = command["text"].strip()
        if not worker_id:
            self.notifier.send_ephemeral(command["response_url"], "❌ Specify worker_id")
            return

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["response_url"], f"❌ Expert {worker_id} not found")
            return

        subitems = self.db.get_subitems_for_expert(expert['id'])
        if not subitems:
            self.notifier.send_ephemeral(
                command["response_url"],
                f"📋 {expert['name']}: no subitems"
            )
            return

        active_count = sum(1 for s in subitems if s['active'])
        text = f"📋 Subitems for {expert['name']} ({worker_id}):\n"
        for s in subitems:
            status = "✅" if s['active'] else "❌"
            text += f"{status} {s['monday_subitem_id']}\n"
        text += f"\nTotal: {len(subitems)} (active: {active_count})"

        self.notifier.send_ephemeral(command["response_url"], text)

    def cmd_expert_subitem_toggle(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["response_url"], "❌ Access denied")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["response_url"],
                "❌ Format: `/expert-subitem-toggle <worker_id> <subitem_id>`"
            )
            return

        worker_id, subitem_id = parts[0], int(parts[1])

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["response_url"], f"❌ Expert {worker_id} not found")
            return

        result = self.db.toggle_expert_subitem(expert['id'], subitem_id)
        if result is None:
            self.notifier.send_ephemeral(
                command["response_url"],
                f"❌ Subitem {subitem_id} not found"
            )
        else:
            status = "✅ enabled" if result else "❌ disabled"
            self.db.log_audit(user_id, "subitem_toggle", f"{worker_id} subitem={subitem_id} -> {status}")
            self.notifier.send_ephemeral(
                command["response_url"],
                f"{status}"
            )
