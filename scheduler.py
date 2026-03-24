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

    def job_check_7pm(self, dry_run: bool = False, dry_run_user: str = None, manual: bool = False):
        """7 PM — основная проверка активностей.

        dry_run=True: no reminders to experts, no run_log, report sent only to dry_run_user.
        manual=True: skip duplicate check (always run).
        """
        run_date = date.today().isoformat()

        if not dry_run and not manual:
            # Защита от дублирования (только авто, игнорирует ручные запуски)
            if self.db.run_log_exists(run_date, 'check_7pm_auto'):
                logger.info("job_check_7pm auto already ran today, skipping")
                return

        logger.info("Starting job_check_7pm", dry_run=dry_run)

        try:
            experts = self.db.get_active_experts()
            if not experts:
                logger.warning("No active experts found")
                if not dry_run:
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
                    filled_subitem_ids = sorted(set(
                        a['monday_subitem_id'] for a in filtered_activities
                    ))
                    report_filled.append((expert, filled_subitem_ids))
                else:
                    if not dry_run:
                        self.notifier.send_reminder(expert, first=True)
                    report_missing.append(expert)

            if dry_run and dry_run_user:
                # Send report only to the admin who triggered dry run
                dry_run_manager = {"slack_user_id": dry_run_user}
                self.notifier.send_manager_report(
                    dry_run_manager, report_filled, report_missing
                )
            else:
                # Send to all managers
                managers = self.db.get_active_managers()
                for manager in managers:
                    self.notifier.send_manager_report(
                        manager, report_filled, report_missing
                    )

            if not dry_run:
                run_type = 'check_7pm_manual' if manual else 'check_7pm_auto'
                self.db.log_run(run_date, run_type, 'completed')

            logger.info(
                "job_check_7pm completed",
                dry_run=dry_run,
                manual=manual,
                filled=len(report_filled),
                missing=len(report_missing)
            )

        except Exception as e:
            logger.error("job_check_7pm failed", error=str(e), exc_info=True)
            if not dry_run:
                run_type = 'check_7pm_manual' if manual else 'check_7pm_auto'
                self.db.log_run(run_date, run_type, 'failed')

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
