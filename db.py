import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import structlog

logger = structlog.get_logger()


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_dir()

    def _ensure_dir(self):
        """Создать директорию для БД если её нет"""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

    def init(self):
        """Инициализация БД и создание таблиц"""
        with sqlite3.connect(self.db_path) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS experts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT NOT NULL UNIQUE,
                    slack_user_id TEXT NOT NULL UNIQUE,
                    name TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS managers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slack_user_id TEXT NOT NULL UNIQUE,
                    name TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slack_user_id TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS run_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_date, run_type)
                );

                CREATE TABLE IF NOT EXISTS expert_subitems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expert_id INTEGER NOT NULL,
                    monday_subitem_id BIGINT NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(expert_id, monday_subitem_id),
                    FOREIGN KEY(expert_id) REFERENCES experts(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_experts_worker_id ON experts(worker_id);
                CREATE INDEX IF NOT EXISTS idx_experts_slack_user_id ON experts(slack_user_id);
                CREATE INDEX IF NOT EXISTS idx_managers_slack_user_id ON managers(slack_user_id);
                CREATE INDEX IF NOT EXISTS idx_run_log_date_type ON run_log(run_date, run_type);
                CREATE INDEX IF NOT EXISTS idx_expert_subitems_expert_id ON expert_subitems(expert_id);
                CREATE INDEX IF NOT EXISTS idx_expert_subitems_active ON expert_subitems(active);
            """)
            db.commit()
            logger.info("Database initialized")

    # ===== EXPERTS =====
    def add_expert(self, worker_id: str, slack_user_id: str, name: str) -> bool:
        """Добавить эксперта"""
        try:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    """INSERT INTO experts (worker_id, slack_user_id, name, active)
                       VALUES (?, ?, ?, 1)""",
                    (worker_id, slack_user_id, name)
                )
                db.commit()
                logger.info("Expert added", worker_id=worker_id, slack_user_id=slack_user_id)
                return True
        except sqlite3.IntegrityError:
            logger.error("Expert already exists", worker_id=worker_id)
            return False

    def remove_expert(self, worker_id: str) -> bool:
        """Удалить эксперта"""
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM experts WHERE worker_id = ?", (worker_id,))
            db.commit()
            logger.info("Expert removed", worker_id=worker_id)
            return True

    def toggle_expert(self, worker_id: str) -> Optional[bool]:
        """Переключить статус эксперта (вкл/выкл)"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                "SELECT active FROM experts WHERE worker_id = ?", (worker_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            new_active = 1 - row[0]
            db.execute(
                "UPDATE experts SET active = ? WHERE worker_id = ?",
                (new_active, worker_id)
            )
            db.commit()
            logger.info("Expert toggled", worker_id=worker_id, active=new_active)
            return bool(new_active)

    def get_expert_by_worker_id(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Получить эксперта по worker_id"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                "SELECT * FROM experts WHERE worker_id = ?", (worker_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_expert_by_slack_id(self, slack_user_id: str) -> Optional[Dict[str, Any]]:
        """Получить эксперта по slack_user_id"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                "SELECT * FROM experts WHERE slack_user_id = ?", (slack_user_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_experts(self) -> List[Dict[str, Any]]:
        """Получить всех активных экспертов"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                "SELECT * FROM experts WHERE active = 1 ORDER BY name"
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_experts(self) -> List[Dict[str, Any]]:
        """Получить всех экспертов"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute("SELECT * FROM experts ORDER BY name")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ===== MANAGERS =====
    def add_manager(self, slack_user_id: str, name: str) -> bool:
        """Добавить менеджера"""
        try:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT INTO managers (slack_user_id, name, active) VALUES (?, ?, 1)",
                    (slack_user_id, name)
                )
                db.commit()
                logger.info("Manager added", slack_user_id=slack_user_id)
                return True
        except sqlite3.IntegrityError:
            logger.error("Manager already exists", slack_user_id=slack_user_id)
            return False

    def remove_manager(self, slack_user_id: str) -> bool:
        """Удалить менеджера"""
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "DELETE FROM managers WHERE slack_user_id = ?", (slack_user_id,)
            )
            db.commit()
            logger.info("Manager removed", slack_user_id=slack_user_id)
            return True

    def get_active_managers(self) -> List[Dict[str, Any]]:
        """Получить всех активных менеджеров"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                "SELECT * FROM managers WHERE active = 1 ORDER BY name"
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_managers(self) -> List[Dict[str, Any]]:
        """Получить всех менеджеров"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute("SELECT * FROM managers ORDER BY name")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ===== ADMINS =====
    def add_admin(self, slack_user_id: str) -> bool:
        """Добавить администратора"""
        try:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT INTO admins (slack_user_id) VALUES (?)",
                    (slack_user_id,)
                )
                db.commit()
                logger.info("Admin added", slack_user_id=slack_user_id)
                return True
        except sqlite3.IntegrityError:
            return False

    def remove_admin(self, slack_user_id: str) -> bool:
        """Удалить администратора"""
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "DELETE FROM admins WHERE slack_user_id = ?", (slack_user_id,)
            )
            db.commit()
            logger.info("Admin removed", slack_user_id=slack_user_id)
            return True

    def get_all_admins(self) -> List[str]:
        """Получить всех администраторов"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute("SELECT slack_user_id FROM admins")
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def is_admin(self, slack_user_id: str) -> bool:
        """Проверить, является ли пользователь администратором"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                "SELECT 1 FROM admins WHERE slack_user_id = ? LIMIT 1",
                (slack_user_id,)
            )
            row = cursor.fetchone()
            return row is not None

    # ===== RUN_LOG =====
    def log_run(self, run_date: str, run_type: str, status: str) -> bool:
        """Записать лог запуска"""
        try:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    """INSERT OR REPLACE INTO run_log (run_date, run_type, status, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (run_date, run_type, status, datetime.now().isoformat())
                )
                db.commit()
                logger.info("Run logged", run_date=run_date, run_type=run_type, status=status)
                return True
        except Exception as e:
            logger.error("Failed to log run", error=str(e))
            return False

    def run_log_exists(self, run_date: str, run_type: str) -> bool:
        """Проверить, был ли уже запуск в этот день"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                "SELECT 1 FROM run_log WHERE run_date = ? AND run_type = ? LIMIT 1",
                (run_date, run_type)
            )
            row = cursor.fetchone()
            return row is not None

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить последние запуски"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                "SELECT * FROM run_log ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ===== EXPERT SUBITEMS =====
    def add_expert_subitem(self, expert_id: int, monday_subitem_id: int) -> bool:
        """Добавить monday_subitem_id для эксперта"""
        try:
            with sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT INTO expert_subitems (expert_id, monday_subitem_id, active) VALUES (?, ?, 1)",
                    (expert_id, monday_subitem_id)
                )
                db.commit()
                logger.info("Subitem added", expert_id=expert_id, subitem_id=monday_subitem_id)
                return True
        except sqlite3.IntegrityError:
            logger.error("Subitem already exists", expert_id=expert_id, subitem_id=monday_subitem_id)
            return False

    def remove_expert_subitem(self, expert_id: int, monday_subitem_id: int) -> bool:
        """Удалить monday_subitem_id"""
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "DELETE FROM expert_subitems WHERE expert_id = ? AND monday_subitem_id = ?",
                (expert_id, monday_subitem_id)
            )
            db.commit()
            logger.info("Subitem removed", expert_id=expert_id, subitem_id=monday_subitem_id)
            return True

    def toggle_expert_subitem(self, expert_id: int, monday_subitem_id: int) -> Optional[bool]:
        """Включить/отключить subitem"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                "SELECT active FROM expert_subitems WHERE expert_id = ? AND monday_subitem_id = ?",
                (expert_id, monday_subitem_id)
            )
            row = cursor.fetchone()
            if not row:
                return None

            new_active = 1 - row[0]
            db.execute(
                "UPDATE expert_subitems SET active = ? WHERE expert_id = ? AND monday_subitem_id = ?",
                (new_active, expert_id, monday_subitem_id)
            )
            db.commit()
            logger.info("Subitem toggled", expert_id=expert_id, subitem_id=monday_subitem_id, active=new_active)
            return bool(new_active)

    def get_subitems_for_expert(self, expert_id: int) -> List[Dict[str, Any]]:
        """Получить все subitems для эксперта"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                "SELECT * FROM expert_subitems WHERE expert_id = ? ORDER BY created_at",
                (expert_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_active_subitems_for_expert(self, worker_id: str) -> List[int]:
        """Получить список АКТИВНЫХ monday_subitem_id для эксперта по worker_id"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute(
                """SELECT expert_subitems.monday_subitem_id
                   FROM expert_subitems
                   JOIN experts ON expert_subitems.expert_id = experts.id
                   WHERE experts.worker_id = ? AND expert_subitems.active = 1
                   ORDER BY expert_subitems.created_at""",
                (worker_id,)
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def get_expert_by_id(self, expert_id: int) -> Optional[Dict[str, Any]]:
        """Получить эксперта по ID (для других операций)"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(
                "SELECT * FROM experts WHERE id = ?", (expert_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
