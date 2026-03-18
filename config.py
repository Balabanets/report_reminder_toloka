import os
from dotenv import load_dotenv

load_dotenv()

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")  # Optional for Socket Mode, required for HTTP webhooks

# Databricks
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

# Database
DB_PATH = os.getenv("DB_PATH", "./data/bot.db")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")
INITIAL_ADMIN_SLACK_ID = os.getenv("INITIAL_ADMIN_SLACK_ID")

# Validation
if not all([SLACK_BOT_TOKEN, SLACK_APP_TOKEN, DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN]):
    raise ValueError("Missing required environment variables. Check .env file.")
