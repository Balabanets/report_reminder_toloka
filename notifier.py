from typing import Dict, List, Any
from datetime import date, timedelta
from slack_bolt import App
import structlog
import requests

logger = structlog.get_logger()


SUBITEM_NAMES = {
    18384837243: "Samples creation",
    100000000546: "Management work",
    10000000924: "QA",
    100000002343: "Production",
    18384837445: "Claude subscription",
    100000001744: "Onboarding",
}


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
        report_filled: List[tuple],
        report_missing: List[Dict[str, Any]]
    ):
        """Send activity report to a manager.

        report_filled: list of (expert_dict, [filled_subitem_ids])
        """
        slack_user_id = manager["slack_user_id"]
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        filled_lines = []
        for expert, filled_subitem_ids in report_filled:
            names = ", ".join(
                SUBITEM_NAMES.get(sid, str(sid)) for sid in filled_subitem_ids
            )
            filled_lines.append(f"• {expert['name']} ({names})")
        filled_text = "\n".join(filled_lines) or "none"

        missing_text = "\n".join(
            [f"• {e['name']}" for e in report_missing]
        ) or "none"

        text = (
            f":bar_chart: *Daily Activity Report — {yesterday}*\n\n"
            f":white_check_mark: *Report filled ({len(report_filled)}):*\n{filled_text}\n\n"
            f":x: *Report missing ({len(report_missing)}):*\n{missing_text}"
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
