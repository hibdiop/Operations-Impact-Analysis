"""Audit logger — persists every analysis run to a SQLite database for reproducibility."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DB = os.path.join(os.path.dirname(__file__), "../../data/audit_log.db")
AUDIT_DB_PATH = os.environ.get("AUDIT_DB_PATH", DEFAULT_AUDIT_DB)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    market      TEXT,
    metric_name TEXT,
    intervention_name TEXT,
    treatment_start TEXT,
    treatment_end   TEXT,
    pre_period_days INTEGER,
    significance_level REAL,
    test_used   TEXT,
    pre_value   REAL,
    post_value  REAL,
    absolute_change REAL,
    relative_lift_pct REAL,
    p_value     REAL,
    ci_lower    REAL,
    ci_upper    REAL,
    is_significant INTEGER,
    confidence_score INTEGER,
    confidence_rating TEXT,
    warning_count INTEGER,
    runtime_ms  REAL,
    config_json TEXT,
    result_json TEXT,
    success     INTEGER DEFAULT 1
)
"""


@contextmanager
def _db():
    con = sqlite3.connect(AUDIT_DB_PATH)
    try:
        con.execute(_CREATE_TABLE)
        con.commit()
        yield con
    finally:
        con.close()


def log_run(
    run_id: str,
    config: Any,
    result: Any,
    runtime_ms: float,
    success: bool = True,
    error_message: Optional[str] = None,
) -> None:
    """Persist a completed analysis run to the audit database."""
    try:
        config_dict = config.model_dump(mode="json") if hasattr(config, "model_dump") else {}
        result_dict: Dict = {}
        if result is not None:
            sr = result.stat_result
            result_dict = {
                "pre_value": sr.pre_value,
                "post_value": sr.post_value,
                "absolute_change": sr.absolute_change,
                "relative_lift_pct": sr.relative_lift_pct,
                "p_value": sr.p_value,
                "ci_lower": sr.ci_lower,
                "ci_upper": sr.ci_upper,
                "is_significant": sr.is_significant,
                "confidence_score": result.confidence.score,
                "confidence_rating": result.confidence.rating,
                "warning_count": len(result.all_warnings),
                "test_used": result.test_used,
                "error": error_message,
            }

        row = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "market": getattr(config, "market", None),
            "metric_name": getattr(config, "metric_name", None),
            "intervention_name": getattr(config, "intervention_name", None),
            "treatment_start": str(getattr(config, "treatment_start", None)),
            "treatment_end": str(getattr(config, "treatment_end", None)),
            "pre_period_days": getattr(config, "pre_period_days", None),
            "significance_level": getattr(config, "significance_level", None),
            "test_used": result_dict.get("test_used"),
            "pre_value": result_dict.get("pre_value"),
            "post_value": result_dict.get("post_value"),
            "absolute_change": result_dict.get("absolute_change"),
            "relative_lift_pct": result_dict.get("relative_lift_pct"),
            "p_value": result_dict.get("p_value"),
            "ci_lower": result_dict.get("ci_lower"),
            "ci_upper": result_dict.get("ci_upper"),
            "is_significant": int(result_dict.get("is_significant", False)),
            "confidence_score": result_dict.get("confidence_score"),
            "confidence_rating": result_dict.get("confidence_rating"),
            "warning_count": result_dict.get("warning_count"),
            "runtime_ms": runtime_ms,
            "config_json": json.dumps(config_dict, default=str),
            "result_json": json.dumps(result_dict, default=str),
            "success": int(success),
        }

        with _db() as con:
            cols = ", ".join(row.keys())
            placeholders = ", ".join("?" for _ in row)
            con.execute(f"INSERT INTO analysis_runs ({cols}) VALUES ({placeholders})", list(row.values()))
            con.commit()

        logger.debug("Audit log written for run_id=%s", run_id)
    except Exception as e:
        logger.warning("Failed to write audit log: %s", e)


def get_recent_runs(limit: int = 50):
    """Fetch recent analysis runs for the admin view."""
    with _db() as con:
        cur = con.execute(
            "SELECT * FROM analysis_runs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
