#!/usr/bin/env python3

import threading
import logging
import sys
from slack_bolt.app import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import structlog
import config
from db import Database
from notifier import Notifier
from scheduler import Scheduler
from admin_handlers import AdminHandlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()  # Console вывод вместо JSON для разработки
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Инициализация Slack приложения
# signing_secret для защиты от MITM атак (требуется для HTTP webhooks)
# Socket Mode использует WebSocket для безопасной коммуникации
app = App(
    token=config.SLACK_BOT_TOKEN,
    signing_secret=config.SLACK_SIGNING_SECRET if config.SLACK_SIGNING_SECRET else None
)

# Глобальные объекты
db = None
notifier = None
scheduler = None
handlers = None
handler = None


def initialize():
    """Инициализация приложения"""
    global db, notifier, scheduler, handlers

    logger.info("Initializing bot...")

    # Инициализировать БД
    db = Database(config.DB_PATH)
    db.init()

    # Инициализировать первого админа если нужно
    if config.INITIAL_ADMIN_SLACK_ID:
        admins = db.get_all_admins()
        if not admins:
            db.add_admin(config.INITIAL_ADMIN_SLACK_ID)
            logger.info("Initial admin added", slack_id=config.INITIAL_ADMIN_SLACK_ID)

    # Инициализировать notifier
    notifier = Notifier(app)

    # Инициализировать scheduler (с asyncio event loop)
    scheduler = Scheduler(db, notifier, timezone=config.TIMEZONE)
    scheduler.add_jobs()
    scheduler.start()

    # Регистрировать обработчики команд
    handlers = AdminHandlers(app, db, scheduler, notifier)

    logger.info("Bot initialized successfully")


@app.event("app_mention")
def handle_mention(body, say):
    """Обработчик упоминаний бота"""
    say("👋 Привет! Используй `/bot-help` для списка команд.")


@app.command("/bot-help")
def handle_help(ack, command, body, context):
    """Обработчик команды /bot-help"""
    logger.info("handle_help called")
    ack()
    user_id = context.user_id
    text = "✅ БОТ РАБОТАЕТ!\n\nКоманды активны. Используй /expert-list или другие команды."
    app.client.chat_postEphemeral(
        channel=command["channel_id"],
        user=user_id,
        text=text
    )


def start_slack_handler():
    """Запустить Slack Socket Mode handler в основном потоке"""
    global handler
    try:
        logger.info("Starting Socket Mode handler...")
        handler = SocketModeHandler(app, config.SLACK_APP_TOKEN)
        handler.start()
    except KeyboardInterrupt:
        logger.info("Socket handler interrupted")
    except Exception as e:
        logger.error("Socket handler error", error=str(e), exc_info=True)


def main():
    """Основная функция"""
    initialize()

    # Запустить Slack handler в отдельном потоке
    slack_thread = threading.Thread(target=start_slack_handler, daemon=True)
    slack_thread.start()

    logger.info("Bot running. Press Ctrl+C to stop.")

    # Держать основной поток активным
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if scheduler:
            scheduler.shutdown()
        if handler:
            handler.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped")

