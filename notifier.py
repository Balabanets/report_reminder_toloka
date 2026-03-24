from typing import Dict, List, Any
from datetime import date, timedelta
from slack_bolt import App
import structlog
import requests

logger = structlog.get_logger()


class Notifier:
    def __init__(self, app: App):
        self.app = app

    ACTIVITY_URL = "https://swan.a9s.toloka.ai/annotation-studio/perform/swan.019a8257-df27-76b5-b17f-4f4b56203db5?project_id=swan.019a8257-dd6e-74fb-aeea-b19a3c5fdf8a"

    def send_reminder(self, expert: Dict[str, Any], first: bool = True):
        """Send a reminder to an expert"""
        slack_user_id = expert["slack_user_id"]
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        text = (
            f":bell: *Daily Activity Report Reminder*\n\n"
            f"This is a reminder to fill out your activity report for *{yesterday}*.\n\n"
            f":link: <{self.ACTIVITY_URL}|Open Activity Form>"
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

    def send_manager_report(
        self,
        manager: Dict[str, Any],
        report_filled: List[Dict[str, Any]],
        report_missing: List[Dict[str, Any]]
    ):
        """Send activity report to a manager"""
        slack_user_id = manager["slack_user_id"]

        filled_text = "\n".join(
            [f"• {e['name']} ({e['worker_id']})" for e in report_filled]
        ) or "none"

        missing_text = "\n".join(
            [f"• {e['name']} ({e['worker_id']})" for e in report_missing]
        ) or "none"

        text = (
            f"📊 Activity Report\n\n"
            f"✅ Report filled ({len(report_filled)}):\n{filled_text}\n\n"
            f"❌ Report missing ({len(report_missing)}):\n{missing_text}"
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

    def send_command_response(self, response_url: str, text: str):
        """Send a response to a slash command via response_url"""
        logger.info("send_command_response called", text_len=len(text))
        try:
            response = requests.post(
                response_url,
                json={"text": text},
                timeout=5
            )
            if response.status_code == 200:
                logger.info("Command response sent successfully")
            else:
                logger.error(
                    "Failed to send command response",
                    status_code=response.status_code
                )
        except Exception as e:
            logger.error("Failed to send command response", error=str(e))

    def send_ephemeral(self, response_url: str, text: str):
        """Send an ephemeral response to a command (via response_url)"""
        self.send_command_response(response_url, text)
