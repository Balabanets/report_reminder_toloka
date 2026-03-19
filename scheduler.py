from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
import structlog
import databricks_client
from db import Database
from notifier import Notifier

logger = structlog.get_logger()


class Scheduler:
    def __init__(self, db: Database, notifier: Notifier, timezone: str = "Europe/Berlin"):
        self.db = db
        self.notifier = notifier
        self.scheduler = BackgroundScheduler(timezone=timezone)

    def job_check_7pm(self):
        """7 PM — основная проверка активностей"""
        run_date = date.today().isoformat()

        # Защита от дублирования
        if self.db.run_log_exists(run_date, 'check_7pm'):
            logger.info("job_check_7pm already ran today, skipping")
            return

        logger.info("Starting job_check_7pm")

        try:
            experts = self.db.get_active_experts()
            if not experts:
                logger.warning("No active experts found")
                self.db.log_run(run_date, 'check_7pm', 'completed')
                return

            # Батчевый запрос для всех экспертов
            worker_ids = [e['worker_id'] for e in experts]
            activities_by_worker = databricks_client.get_all_activities_for_date(worker_ids)

            report_filled = []
            report_missing = []

            for expert in experts:
                activities = activities_by_worker.get(expert['worker_id'], [])

                # Получить активные subitems для этого эксперта
                active_subitems = self.db.get_active_subitems_for_expert(expert['worker_id'])

                if not active_subitems:
                    # Если subitems не установлены - пропустить эксперта
                    logger.warning(
                        "Expert has no subitems configured, skipping",
                        worker_id=expert['worker_id']
                    )
                    continue

                # Фильтровать активности по subitems
                filtered_activities = [
                    a for a in activities
                    if a.get('monday_subitem_id') in active_subitems
                ]

                if filtered_activities:
                    report_filled.append(expert)
                    logger.info(
                        "Expert has activities",
                        worker_id=expert['worker_id'],
                        total_activities=len(activities),
                        filtered_activities=len(filtered_activities),
                        subitems=active_subitems
                    )
                else:
                    # Отправляем напоминание в ЛС эксперту
                    self.notifier.send_reminder(expert, first=True)
                    report_missing.append(expert)
                    logger.info(
                        "Expert has no activities for configured subitems, reminder sent",
                        worker_id=expert['worker_id'],
                        configured_subitems=active_subitems
                    )

            # Отправляем отчёт всем активным менеджерам
            managers = self.db.get_active_managers()
            for manager in managers:
                self.notifier.send_manager_report(
                    manager, report_filled, report_missing
                )

            self.db.log_run(run_date, 'check_7pm', 'completed')
            logger.info(
                "job_check_7pm completed",
                filled=len(report_filled),
                missing=len(report_missing)
            )

        except Exception as e:
            logger.error("job_check_7pm failed", error=str(e), exc_info=True)
            self.db.log_run(run_date, 'check_7pm', 'failed')

    def add_jobs(self):
        """Добавить задачи в планировщик"""
        self.scheduler.add_job(
            self.job_check_7pm,
            'cron',
            hour=19,
            minute=0,
            id='check_7pm'
        )
        logger.info("Jobs added to scheduler")

    def start(self):
        """Запустить планировщик"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self):
        """Остановить планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown")
