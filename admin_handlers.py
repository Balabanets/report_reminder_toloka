from slack_bolt import App, Ack, Say
from slack_bolt.context import BoltContext
import structlog
from db import Database
from scheduler import Scheduler
from notifier import Notifier

logger = structlog.get_logger()


class AdminHandlers:
    def __init__(self, app: App, db: Database, scheduler: Scheduler, notifier: Notifier):
        self.app = app
        self.db = db
        self.scheduler = scheduler
        self.notifier = notifier
        self.register_handlers()

    def register_handlers(self):
        """Регистрировать все обработчики"""
        self.app.command("/expert-add")(self.cmd_expert_add)
        self.app.command("/expert-remove")(self.cmd_expert_remove)
        self.app.command("/expert-list")(self.cmd_expert_list)
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
        self.app.command("/bot-status")(self.cmd_bot_status)

    def _check_admin(self, user_id: str) -> bool:
        """Проверить права администратора"""
        return self.db.is_admin(user_id)

    def cmd_help(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id

        help_text = """
*Команды администратора:*

*Эксперты:*
`/expert-add <worker_id> <slack_id> <name>` — добавить эксперта
`/expert-remove <worker_id>` — удалить эксперта
`/expert-list` — список экспертов
`/expert-toggle <worker_id>` — вкл/выкл эксперта

*Subitems:*
`/expert-subitem-add <worker_id> <subitem_id>` — добавить subitem
`/expert-subitem-remove <worker_id> <subitem_id>` — удалить subitem
`/expert-subitem-list <worker_id>` — список subitems
`/expert-subitem-toggle <worker_id> <subitem_id>` — вкл/выкл subitem

*Менеджеры:*
`/manager-add <slack_id> <name>` — добавить менеджера
`/manager-remove <slack_id>` — удалить менеджера
`/manager-list` — список менеджеров

*Администраторы:*
`/admin-add <slack_id>` — добавить админа
`/admin-remove <slack_id>` — удалить админа
`/admin-list` — список админов

*Управление ботом:*
`/bot-run-now` — запустить проверку сейчас
`/bot-status` — статус и логи запусков
        """
        self.notifier.send_ephemeral(command["channel_id"], user_id, help_text)

    def cmd_expert_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        logger.info("cmd_expert_add called", user_id=context.user_id)
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        parts = command["text"].split()
        if len(parts) < 3:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                "❌ Формат: `/expert-add <worker_id> <slack_id> <name>`"
            )
            return

        worker_id, slack_id, name = parts[0], parts[1], " ".join(parts[2:])
        success = self.db.add_expert(worker_id, slack_id, name)

        if success:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"✅ Эксперт {name} ({worker_id}) добавлен"
            )
            logger.info("Expert added via command", user_id=user_id, worker_id=worker_id, action="expert_add")
        else:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"❌ Эксперт {worker_id} уже существует"
            )

    def cmd_expert_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        worker_id = command["text"].strip()
        if not worker_id:
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Укажи worker_id")
            return

        success = self.db.remove_expert(worker_id)
        if success:
            logger.info("Expert removed via command", user_id=user_id, worker_id=worker_id, action="expert_remove")
        self.notifier.send_ephemeral(
            command["channel_id"],
            user_id,
            f"✅ Эксперт {worker_id} удалён" if success else "❌ Ошибка"
        )

    def cmd_expert_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        logger.info("cmd_expert_list called", user_id=context.user_id)
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        experts = self.db.get_all_experts()
        if not experts:
            self.notifier.send_ephemeral(command["channel_id"], user_id, "Экспертов нет")
            return

        text = "*Список экспертов:*\n"
        for e in experts:
            status = "✅" if e["active"] else "❌"
            text += f"{status} {e['name']} ({e['worker_id']}) - {e['slack_user_id']}\n"

        self.notifier.send_ephemeral(command["channel_id"], user_id, text)

    def cmd_expert_toggle(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        worker_id = command["text"].strip()
        result = self.db.toggle_expert(worker_id)

        if result is None:
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Эксперт не найден")
        else:
            status = "✅ включён" if result else "❌ отключён"
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"{status}"
            )

    def cmd_manager_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                "❌ Формат: `/manager-add <slack_id> <name>`"
            )
            return

        slack_id, name = parts[0], " ".join(parts[1:])
        success = self.db.add_manager(slack_id, name)

        if success:
            self.notifier.send_ephemeral(command["channel_id"], user_id, f"✅ Менеджер {name} добавлен")
        else:
            self.notifier.send_ephemeral(command["channel_id"], user_id, f"❌ Менеджер уже существует")

    def cmd_manager_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        slack_id = command["text"].strip()
        success = self.db.remove_manager(slack_id)
        self.notifier.send_ephemeral(
            command["channel_id"],
            user_id,
            f"✅ Менеджер удалён" if success else "❌ Ошибка"
        )

    def cmd_manager_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        managers = self.db.get_all_managers()
        if not managers:
            self.notifier.send_ephemeral(command["channel_id"], user_id, "Менеджеров нет")
            return

        text = "*Список менеджеров:*\n"
        for m in managers:
            status = "✅" if m["active"] else "❌"
            text += f"{status} {m['name']} - {m['slack_user_id']}\n"

        self.notifier.send_ephemeral(command["channel_id"], user_id, text)

    def cmd_admin_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        slack_id = command["text"].strip()
        success = self.db.add_admin(slack_id)
        self.notifier.send_ephemeral(
            command["channel_id"],
            user_id,
            f"✅ Админ добавлен" if success else "❌ Уже админ"
        )

    def cmd_admin_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        slack_id = command["text"].strip()
        success = self.db.remove_admin(slack_id)
        self.notifier.send_ephemeral(
            command["channel_id"],
            user_id,
            f"✅ Админ удалён" if success else "❌ Ошибка"
        )

    def cmd_admin_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        admins = self.db.get_all_admins()
        if not admins:
            self.notifier.send_ephemeral(command["channel_id"], user_id, "Админов нет")
            return

        text = "*Администраторы:*\n" + "\n".join([f"• {a}" for a in admins])
        self.notifier.send_ephemeral(command["channel_id"], user_id, text)

    def cmd_bot_run_now(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        logger.info("cmd_bot_run_now called", user_id=user_id, action="bot_run_now")
        self.notifier.send_ephemeral(command["channel_id"], user_id, "✅ Проверка запущена в фоне")

    def cmd_bot_status(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        runs = self.db.get_recent_runs(10)
        if not runs:
            self.notifier.send_ephemeral(command["channel_id"], user_id, "Логов нет")
            return

        text = "*Последние запуски:*\n"
        for r in runs:
            status_emoji = "✅" if r["status"] == "completed" else "❌"
            text += f"{status_emoji} {r['run_type']} ({r['run_date']}) - {r['status']}\n"

        self.notifier.send_ephemeral(command["channel_id"], user_id, text)

    # ===== EXPERT SUBITEMS =====

    def cmd_expert_subitem_add(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                "❌ Формат: `/expert-subitem-add <worker_id> <subitem_id>`"
            )
            return

        worker_id, subitem_id = parts[0], int(parts[1])

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["channel_id"], user_id, f"❌ Эксперт {worker_id} не найден")
            return

        success = self.db.add_expert_subitem(expert['id'], subitem_id)
        if success:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"✅ Subitem {subitem_id} добавлен для {expert['name']}"
            )
        else:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"❌ Subitem {subitem_id} уже существует"
            )

    def cmd_expert_subitem_remove(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                "❌ Формат: `/expert-subitem-remove <worker_id> <subitem_id>`"
            )
            return

        worker_id, subitem_id = parts[0], int(parts[1])

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["channel_id"], user_id, f"❌ Эксперт {worker_id} не найден")
            return

        self.db.remove_expert_subitem(expert['id'], subitem_id)
        self.notifier.send_ephemeral(
            command["channel_id"],
            user_id,
            f"✅ Subitem {subitem_id} удалён"
        )

    def cmd_expert_subitem_list(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        worker_id = command["text"].strip()
        if not worker_id:
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Укажи worker_id")
            return

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["channel_id"], user_id, f"❌ Эксперт {worker_id} не найден")
            return

        subitems = self.db.get_subitems_for_expert(expert['id'])
        if not subitems:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"📋 {expert['name']}: нет subitems"
            )
            return

        active_count = sum(1 for s in subitems if s['active'])
        text = f"📋 Subitems для {expert['name']} ({worker_id}):\n"
        for s in subitems:
            status = "✅" if s['active'] else "❌"
            text += f"{status} {s['monday_subitem_id']}\n"
        text += f"\nВсего: {len(subitems)} (активных: {active_count})"

        self.notifier.send_ephemeral(command["channel_id"], user_id, text)

    def cmd_expert_subitem_toggle(self, ack: Ack, command: dict, say: Say, context: BoltContext):
        ack()
        user_id = context.user_id
        if not self._check_admin(user_id):
            self.notifier.send_ephemeral(command["channel_id"], user_id, "❌ Нет доступа")
            return

        parts = command["text"].split()
        if len(parts) < 2:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                "❌ Формат: `/expert-subitem-toggle <worker_id> <subitem_id>`"
            )
            return

        worker_id, subitem_id = parts[0], int(parts[1])

        expert = self.db.get_expert_by_worker_id(worker_id)
        if not expert:
            self.notifier.send_ephemeral(command["channel_id"], user_id, f"❌ Эксперт {worker_id} не найден")
            return

        result = self.db.toggle_expert_subitem(expert['id'], subitem_id)
        if result is None:
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"❌ Subitem {subitem_id} не найден"
            )
        else:
            status = "✅ включён" if result else "❌ отключён"
            self.notifier.send_ephemeral(
                command["channel_id"],
                user_id,
                f"{status}"
            )
