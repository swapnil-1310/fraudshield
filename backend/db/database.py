import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

class DatabaseManager:
    def __init__(self, db_path: Path = config.SQLITE_DB_PATH):
        self.db_path = db_path
        self._init_db()
        self._seed_advisors_if_needed()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Flags and reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_reports (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    title TEXT,
                    is_deepfake INTEGER NOT NULL,
                    deepfake_score REAL NOT NULL,
                    is_sebi_violation INTEGER NOT NULL,
                    sebi_risk_score REAL NOT NULL,
                    dual_verdict TEXT NOT NULL,
                    verdict_label TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    transcript TEXT,
                    reasons TEXT,
                    sebi_rules TEXT,
                    advisor_reg_no TEXT,
                    advisor_status TEXT,
                    status TEXT DEFAULT 'FLAGGED'
                )
            """)

            # SEBI Registered Advisors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sebi_advisors (
                    reg_no TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    valid_till TEXT,
                    company TEXT,
                    state TEXT,
                    registered_email TEXT
                )
            """)
            conn.commit()

    def _seed_advisors_if_needed(self):
        if not config.ADVISOR_JSON_PATH.exists():
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sebi_advisors")
            if cursor.fetchone()[0] == 0:
                try:
                    with open(config.ADVISOR_JSON_PATH, "r", encoding="utf-8") as f:
                        advisors = json.load(f)
                    for a in advisors:
                        cursor.execute("""
                            INSERT OR REPLACE INTO sebi_advisors 
                            (reg_no, name, category, status, valid_till, company, state, registered_email)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            a["reg_no"], a["name"], a["category"], a["status"],
                            a.get("valid_till", ""), a.get("company", ""),
                            a.get("state", ""), a.get("registered_email", "")
                        ))
                    conn.commit()
                except Exception as e:
                    print(f"Error seeding advisors: {e}")

    def save_scan_report(self, data: Dict[str, Any]) -> str:
        report_id = data.get("id") or f"FLAG-{uuid.uuid4().hex[:8].upper()}"
        timestamp = data.get("timestamp") or datetime.now().isoformat()
        
        reasons_json = json.dumps(data.get("reasons", []))
        sebi_rules_json = json.dumps(data.get("sebi_rules", []))
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scan_reports (
                    id, timestamp, media_type, title, is_deepfake, deepfake_score,
                    is_sebi_violation, sebi_risk_score, dual_verdict, verdict_label,
                    summary, transcript, reasons, sebi_rules, advisor_reg_no, advisor_status, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id, timestamp, data.get("media_type", "video"),
                data.get("title", "Scanned Media"),
                1 if data.get("is_deepfake") else 0,
                float(data.get("deepfake_score", 0.0)),
                1 if data.get("is_sebi_violation") else 0,
                float(data.get("sebi_risk_score", 0.0)),
                data.get("dual_verdict", "REAL_SEBI_COMPLIANT"),
                data.get("verdict_label", "SAFE"),
                data.get("summary", ""),
                data.get("transcript", ""),
                reasons_json, sebi_rules_json,
                data.get("advisor_reg_no", ""),
                data.get("advisor_status", "NOT_PROVIDED"),
                data.get("status", "FLAGGED")
            ))
            conn.commit()
        return report_id

    def list_reports(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scan_reports ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["reasons"] = json.loads(item["reasons"]) if item["reasons"] else []
                item["sebi_rules"] = json.loads(item["sebi_rules"]) if item["sebi_rules"] else []
                item["is_deepfake"] = bool(item["is_deepfake"])
                item["is_sebi_violation"] = bool(item["is_sebi_violation"])
                results.append(item)
            return results

    def get_advisor(self, reg_no: str) -> Optional[Dict[str, Any]]:
        reg_no_clean = reg_no.strip().upper()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sebi_advisors WHERE UPPER(reg_no) = ?", (reg_no_clean,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def delete_report(self, report_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scan_reports WHERE id = ?", (report_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM scan_reports")
            total_scans = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scan_reports WHERE is_deepfake = 1")
            total_deepfakes = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scan_reports WHERE is_sebi_violation = 1")
            total_sebi_violations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scan_reports WHERE dual_verdict = 'AI_SEBI_VIOLATION'")
            total_high_risk_scams = cursor.fetchone()[0]

            return {
                "total_scans": total_scans,
                "total_deepfakes": total_deepfakes,
                "total_sebi_violations": total_sebi_violations,
                "total_high_risk_scams": total_high_risk_scams,
            }
