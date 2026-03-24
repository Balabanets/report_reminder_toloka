import os
from dotenv import load_dotenv

load_dotenv()

# Slack (Socket Mode — signing_secret not required, auth via App Token)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Databricks (read-only access to activity data)
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

# Database
DB_PATH = os.getenv("DB_PATH", "./data/bot.db")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")
INITIAL_ADMIN_SLACK_ID = os.getenv("INITIAL_ADMIN_SLACK_ID")

# Validation — fail fast if any required credential is missing
_required = {
    "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
    "SLACK_APP_TOKEN": SLACK_APP_TOKEN,
    "DATABRICKS_HOST": DATABRICKS_HOST,
    "DATABRICKS_HTTP_PATH": DATABRICKS_HTTP_PATH,
    "DATABRICKS_TOKEN": DATABRICKS_TOKEN,
}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    raise ValueError(f"Missing required environment variables: {', '.join(_missing)}. Check .env file.")
