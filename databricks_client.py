import time
from datetime import date, timedelta
from databricks import sql
from typing import List, Dict, Any
import structlog
import config

logger = structlog.get_logger()


def get_activities_for_worker(worker_id: str, retries: int = 3) -> List[Dict[str, Any]]:
    """
    Возвращает список активностей эксперта за вчерашний день.
    Пустой список = нет активностей = нужно напоминание.
    """
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    query = """
        SELECT
            worker_id,
            monday_subitem_id,
            name,
            status,
            hours,
            jira_link,
            date
        FROM dmn_core_analytics.cdm.directus_activities_act
        WHERE worker_id = ?
          AND CAST(date AS DATE) = ?
    """

    for attempt in range(1, retries + 1):
        try:
            with sql.connect(
                server_hostname=config.DATABRICKS_HOST,
                http_path=config.DATABRICKS_HTTP_PATH,
                access_token=config.DATABRICKS_TOKEN,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, [worker_id, yesterday])
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    result = [dict(zip(columns, row)) for row in rows]
                    logger.info(
                        "Databricks query success",
                        worker_id=worker_id,
                        activities_count=len(result)
                    )
                    return result
        except Exception as e:
            logger.error(
                f"Databricks error (attempt {attempt}/{retries}) for worker {worker_id}",
                error=str(e)
            )
            if attempt < retries:
                time.sleep(2 ** attempt)  # exponential backoff: 2s, 4s
            else:
                raise


def get_all_activities_for_date(worker_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Батчевый запрос для всех экспертов сразу — эффективнее N отдельных запросов.
    Возвращает dict: {worker_id: [активности]}
    """
    if not worker_ids:
        return {}

    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    placeholders = ", ".join(["?" for _ in worker_ids])

    query = f"""
        SELECT
            worker_id,
            monday_subitem_id,
            name,
            status,
            hours,
            jira_link,
            date
        FROM dmn_core_analytics.cdm.directus_activities_act
        WHERE worker_id IN ({placeholders})
          AND CAST(date AS DATE) = ?
    """

    for attempt in range(1, 4):
        try:
            with sql.connect(
                server_hostname=config.DATABRICKS_HOST,
                http_path=config.DATABRICKS_HTTP_PATH,
                access_token=config.DATABRICKS_TOKEN,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, worker_ids + [yesterday])
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

            result = {wid: [] for wid in worker_ids}
            for row in rows:
                record = dict(zip(columns, row))
                wid = record["worker_id"]
                if wid in result:
                    result[wid].append(record)

            logger.info(
                "Databricks batch query success",
                worker_ids_count=len(worker_ids),
                records_fetched=sum(len(v) for v in result.values())
            )
            return result
        except Exception as e:
            logger.error(f"Databricks batch error (attempt {attempt}/3)", error=str(e))
            if attempt < 3:
                time.sleep(2 ** attempt)
            else:
                raise
