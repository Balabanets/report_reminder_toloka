#!/usr/bin/env python3

import threading
import logging
import signal
import sys
import os
import atexit
from slack_bolt.app import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import structlog
import config
from db import Database
from notifier import Notifier
from scheduler import Scheduler
from admin_handlers import AdminHandlers

# Ensure only one instance runs
PIDFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "bot.pid")
if os.path.exists(PIDFILE):
    try:
        with open(PIDFILE, 'r') as f:
            old_pid = int(f.read().strip())
        os.kill(old_pid, 0)
        print(f"Bot already running (PID {old_pid}), exiting", file=sys.stderr)
        sys.exit(1)
    except (ProcessLookupError, ValueError):
        pass

def cleanup_pid():
    try:
        os.remove(PIDFILE)
    except OSError:
        pass

atexit.register(cleanup_pid)

with open(PIDFILE, 'w') as f:
    f.write(str(os.getpid()))

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

# Socket Mode uses WebSocket (App Token) for secure communication
# No signing_secret needed — it's only required for HTTP webhook mode
app = App(token=config.SLACK_BOT_TOKEN)

# Глобальные объекты
db = None
notifier = None
scheduler = None
handlers = None
handler = None

# Логировать ВСЕ события для отладки
@app.middleware
def log_request(body, next):
    logger.info("Incoming event", event_type=body.get("type"), command=body.get("command"))
    next()


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
    """Handle bot mentions"""
    say("👋 Hi! Use `/bot-help` to see the list of commands.")


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


def shutdown(signum=None, frame=None):
    """Graceful shutdown on SIGTERM/SIGINT"""
    logger.info("Shutting down...", signal=signum)
    if scheduler:
        scheduler.shutdown()
    if handler:
        handler.close()
    cleanup_pid()
    sys.exit(0)


def main():
    """Основная функция"""
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

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
        shutdown()


if __name__ == "__main__":
    main()

