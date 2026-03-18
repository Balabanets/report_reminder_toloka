from typing import Dict, List, Any
from slack_bolt import App
import structlog

logger = structlog.get_logger()


class Notifier:
    def __init__(self, app: App):
        self.app = app

    async def send_reminder(self, expert: Dict[str, Any], first: bool = True):
        """Отправить напоминание эксперту"""
        slack_user_id = expert["slack_user_id"]
        name = expert.get("name", "Expert")

        if first:
            text = (
                f"👋 Привет! Напоминаю, что нужно заполнить отчёт по задаче.\n"
                f"Пожалуйста, заполни до 22:00."
            )
        else:
            text = (
                f"⚠️ Последнее напоминание! Отчёт так и не заполнен.\n"
                f"Заполни его как можно скорее."
            )

        try:
            self.app.client.chat_postMessage(
                channel=slack_user_id,
                text=text,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text
                        }
                    }
                ]
            )
            logger.info(
                "Reminder sent to expert",
                slack_user_id=slack_user_id,
                first=first
            )
        except Exception as e:
            logger.error(
                "Failed to send reminder",
                slack_user_id=slack_user_id,
                error=str(e)
            )

    async def send_manager_report(
        self,
        manager: Dict[str, Any],
        report_filled: List[Dict[str, Any]],
        report_missing: List[Dict[str, Any]]
    ):
        """Отправить отчёт менеджеру"""
        slack_user_id = manager["slack_user_id"]

        filled_text = "\n".join(
            [f"• {e['name']} ({e['worker_id']})" for e in report_filled]
        ) or "нет"

        missing_text = "\n".join(
            [f"• {e['name']} ({e['worker_id']})" for e in report_missing]
        ) or "нет"

        text = (
            f"📊 Отчёт по заполненным активностям\n\n"
            f"✅ Отчёт заполнен ({len(report_filled)}):\n{filled_text}\n\n"
            f"❌ Отчёт не заполнен ({len(report_missing)}):\n{missing_text}"
        )

        try:
            self.app.client.chat_postMessage(
                channel=slack_user_id,
                text=text,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text
                        }
                    }
                ]
            )
            logger.info(
                "Report sent to manager",
                slack_user_id=slack_user_id,
                filled_count=len(report_filled),
                missing_count=len(report_missing)
            )
        except Exception as e:
            logger.error(
                "Failed to send manager report",
                slack_user_id=slack_user_id,
                error=str(e)
            )

    def send_ephemeral(self, channel: str, user_id: str, text: str):
        """Отправить эфемерное сообщение (видит только получатель)"""
        try:
            self.app.client.chat_postEphemeral(
                channel=channel,
                user=user_id,
                text=text
            )
        except Exception as e:
            logger.error(
                "Failed to send ephemeral message",
                channel=channel,
                user=user_id,
                error=str(e)
            )
