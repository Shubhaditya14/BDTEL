import shutil
import subprocess
from pathlib import Path


HIVE_TABLE = "hospital_metrics"


def run_hive_query(query):
    hive_binary = shutil.which("hive")

    if hive_binary is None:
        return {
            "available": False,
            "stdout": "",
            "stderr": "Hive executable not found on PATH."
        }

    result = subprocess.run(
        [
            hive_binary,
            "-S",
            "-e",
            query
        ],
        capture_output=True,
        text=True
    )

    return {
        "available": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip()
    }


def refresh_hive_table(metrics_file):
    metrics_path = Path(metrics_file).resolve()

    if not metrics_path.exists():
        return {
            "available": False,
            "error": f"Metrics file not found: {metrics_path}"
        }

    query = f"""
    CREATE TABLE IF NOT EXISTS {HIVE_TABLE}(
        round INT,
        hospital STRING,
        accuracy FLOAT,
        trust FLOAT
    )
    ROW FORMAT DELIMITED
    FIELDS TERMINATED BY ','
    STORED AS TEXTFILE
    TBLPROPERTIES ("skip.header.line.count"="1");

    LOAD DATA LOCAL INPATH '{metrics_path}'
    OVERWRITE INTO TABLE {HIVE_TABLE};
    """

    result = run_hive_query(query)

    if not result["available"]:
        return {
            "available": False,
            "error": result["stderr"]
        }

    return {
        "available": True,
        "table": HIVE_TABLE
    }


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def query_hive_analytics(metrics_file):
    refresh_result = refresh_hive_table(metrics_file)

    if not refresh_result["available"]:
        return {
            "available": False,
            "error": refresh_result["error"],
            "table": HIVE_TABLE
        }

    summary_query = f"""
    SELECT
        AVG(trust),
        AVG(accuracy)
    FROM {HIVE_TABLE};
    """
    top_query = f"""
    SELECT
        hospital,
        AVG(trust) AS average_trust
    FROM {HIVE_TABLE}
    GROUP BY hospital
    ORDER BY average_trust DESC
    LIMIT 1;
    """

    summary_result = run_hive_query(summary_query)
    top_result = run_hive_query(top_query)

    if not summary_result["available"]:
        return {
            "available": False,
            "error": summary_result["stderr"],
            "table": HIVE_TABLE
        }

    if not top_result["available"]:
        return {
            "available": False,
            "error": top_result["stderr"],
            "table": HIVE_TABLE
        }

    summary_values = summary_result["stdout"].split()
    top_values = top_result["stdout"].split()

    return {
        "available": True,
        "table": HIVE_TABLE,
        "average_trust": parse_float(summary_values[0])
        if summary_values
        else 0.0,
        "average_accuracy": parse_float(summary_values[1])
        if len(summary_values) > 1
        else 0.0,
        "top_trusted_hospital": top_values[0]
        if top_values
        else None,
        "top_trusted_score": parse_float(top_values[1])
        if len(top_values) > 1
        else 0.0
    }
