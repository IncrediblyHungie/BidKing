"""
Database layer for storing scraped SAM.gov data

Uses SQLite for simplicity and portability. Can handle millions of records.
Includes resume capability through tracking of scraped opportunity IDs.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Set
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite database for SAM.gov opportunity data"""

    def __init__(self, db_path: str = "sam_opportunities.db"):
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main opportunities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    opportunity_id TEXT PRIMARY KEY,
                    solicitation_number TEXT,
                    title TEXT,
                    description TEXT,
                    type TEXT,
                    type_code TEXT,
                    posted_date TEXT,
                    modified_date TEXT,
                    response_deadline TEXT,
                    response_timezone TEXT,
                    is_active INTEGER,
                    is_canceled INTEGER,
                    agency_name TEXT,
                    sub_agency_name TEXT,
                    office_name TEXT,
                    naics_code TEXT,
                    psc_code TEXT,
                    set_aside_type TEXT,
                    set_aside_description TEXT,
                    place_city TEXT,
                    place_state TEXT,
                    place_state_code TEXT,
                    place_country TEXT,
                    place_country_code TEXT,
                    sam_gov_link TEXT,
                    award_amount REAL,
                    award_awardee TEXT,
                    award_awardee_uei TEXT,
                    contacts_json TEXT,
                    attachments_json TEXT,
                    raw_data_json TEXT,
                    scraped_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Attachments table for tracking downloaded files
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id TEXT,
                    resource_id TEXT,
                    filename TEXT,
                    mime_type TEXT,
                    file_size INTEGER,
                    access_level TEXT,
                    posted_date TEXT,
                    download_url TEXT,
                    local_path TEXT,
                    downloaded INTEGER DEFAULT 0,
                    download_error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (opportunity_id) REFERENCES opportunities(opportunity_id),
                    UNIQUE(opportunity_id, resource_id)
                )
            """)

            # Scrape progress tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    started_at TEXT,
                    completed_at TEXT,
                    total_pages INTEGER DEFAULT 0,
                    last_page INTEGER DEFAULT 0,
                    total_opportunities INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    config_json TEXT,
                    error_message TEXT
                )
            """)

            # Create indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opp_posted ON opportunities(posted_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opp_agency ON opportunities(agency_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opp_naics ON opportunities(naics_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opp_active ON opportunities(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opp_response ON opportunities(response_deadline)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_att_opp ON attachments(opportunity_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_att_downloaded ON attachments(downloaded)")

            conn.commit()
            logger.info(f"Database initialized: {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_opportunity(self, data: Dict[str, Any]) -> bool:
        """
        Save or update an opportunity record.

        Returns True if saved successfully.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Extract place of performance
                pop = data.get("placeOfPerformance", {}) or {}

                # Extract award info
                award = data.get("award", {}) or {}

                cursor.execute("""
                    INSERT OR REPLACE INTO opportunities (
                        opportunity_id, solicitation_number, title, description,
                        type, type_code, posted_date, modified_date,
                        response_deadline, response_timezone, is_active, is_canceled,
                        agency_name, sub_agency_name, office_name,
                        naics_code, psc_code, set_aside_type, set_aside_description,
                        place_city, place_state, place_state_code, place_country, place_country_code,
                        sam_gov_link, award_amount, award_awardee, award_awardee_uei,
                        contacts_json, attachments_json, raw_data_json,
                        scraped_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    data.get("opportunityId"),
                    data.get("solicitationNumber"),
                    data.get("title"),
                    data.get("description"),
                    data.get("type"),
                    data.get("typeCode"),
                    data.get("postedDate"),
                    data.get("modifiedDate"),
                    data.get("responseDeadline"),
                    data.get("responseTimeZone"),
                    1 if data.get("isActive") else 0,
                    1 if data.get("isCanceled") else 0,
                    data.get("agencyName"),
                    data.get("subAgencyName"),
                    data.get("officeName"),
                    data.get("naicsCode"),
                    data.get("pscCode"),
                    data.get("setAsideType"),
                    data.get("setAsideDescription"),
                    pop.get("city"),
                    pop.get("state"),
                    pop.get("stateCode"),
                    pop.get("country"),
                    pop.get("countryCode"),
                    data.get("samGovLink"),
                    award.get("amount"),
                    award.get("awardee"),
                    award.get("awardeeUei"),
                    json.dumps(data.get("contacts", [])),
                    json.dumps(data.get("attachments", [])),
                    json.dumps(data),
                    data.get("scrapedAt"),
                ))

                # Save attachments separately
                for att in data.get("attachments", []):
                    cursor.execute("""
                        INSERT OR REPLACE INTO attachments (
                            opportunity_id, resource_id, filename, mime_type,
                            file_size, access_level, posted_date, download_url,
                            local_path, downloaded, download_error
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data.get("opportunityId"),
                        att.get("resourceId"),
                        att.get("filename"),
                        att.get("type"),
                        att.get("size"),
                        att.get("accessLevel"),
                        att.get("postedDate"),
                        att.get("downloadUrl"),
                        att.get("localPath"),
                        1 if att.get("localPath") else 0,
                        att.get("downloadError"),
                    ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save opportunity {data.get('opportunityId')}: {e}")
            return False

    def get_scraped_ids(self) -> Set[str]:
        """Get set of all opportunity IDs already scraped"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT opportunity_id FROM opportunities")
            return {row[0] for row in cursor.fetchall()}

    def get_opportunity_count(self) -> int:
        """Get total number of opportunities in database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM opportunities")
            return cursor.fetchone()[0]

    def get_attachment_count(self, downloaded_only: bool = False) -> int:
        """Get total number of attachments"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if downloaded_only:
                cursor.execute("SELECT COUNT(*) FROM attachments WHERE downloaded = 1")
            else:
                cursor.execute("SELECT COUNT(*) FROM attachments")
            return cursor.fetchone()[0]

    # Session management for resume capability
    def create_session(self, session_id: str, config: Dict) -> None:
        """Create a new scrape session"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scrape_sessions (session_id, started_at, config_json, status)
                VALUES (?, ?, ?, 'running')
            """, (session_id, datetime.utcnow().isoformat(), json.dumps(config)))
            conn.commit()

    def update_session_progress(self, session_id: str, page: int, total_opps: int) -> None:
        """Update session progress"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scrape_sessions
                SET last_page = ?, total_opportunities = ?
                WHERE session_id = ?
            """, (page, total_opps, session_id))
            conn.commit()

    def complete_session(self, session_id: str, total_pages: int, total_opps: int) -> None:
        """Mark session as completed"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scrape_sessions
                SET completed_at = ?, status = 'completed',
                    total_pages = ?, total_opportunities = ?
                WHERE session_id = ?
            """, (datetime.utcnow().isoformat(), total_pages, total_opps, session_id))
            conn.commit()

    def fail_session(self, session_id: str, error: str) -> None:
        """Mark session as failed"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scrape_sessions
                SET status = 'failed', error_message = ?
                WHERE session_id = ?
            """, (error, session_id))
            conn.commit()

    def get_last_session(self) -> Optional[Dict]:
        """Get the most recent session info for resume"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scrape_sessions
                ORDER BY started_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_stats(self) -> Dict:
        """Get database statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total opportunities
            cursor.execute("SELECT COUNT(*) FROM opportunities")
            stats["total_opportunities"] = cursor.fetchone()[0]

            # Active opportunities
            cursor.execute("SELECT COUNT(*) FROM opportunities WHERE is_active = 1")
            stats["active_opportunities"] = cursor.fetchone()[0]

            # Total attachments
            cursor.execute("SELECT COUNT(*) FROM attachments")
            stats["total_attachments"] = cursor.fetchone()[0]

            # Downloaded attachments
            cursor.execute("SELECT COUNT(*) FROM attachments WHERE downloaded = 1")
            stats["downloaded_attachments"] = cursor.fetchone()[0]

            # By agency (top 10)
            cursor.execute("""
                SELECT agency_name, COUNT(*) as count
                FROM opportunities
                WHERE agency_name IS NOT NULL
                GROUP BY agency_name
                ORDER BY count DESC
                LIMIT 10
            """)
            stats["top_agencies"] = [{"agency": row[0], "count": row[1]} for row in cursor.fetchall()]

            # By NAICS (top 10)
            cursor.execute("""
                SELECT naics_code, COUNT(*) as count
                FROM opportunities
                WHERE naics_code IS NOT NULL
                GROUP BY naics_code
                ORDER BY count DESC
                LIMIT 10
            """)
            stats["top_naics"] = [{"naics": row[0], "count": row[1]} for row in cursor.fetchall()]

            # Date range
            cursor.execute("SELECT MIN(posted_date), MAX(posted_date) FROM opportunities")
            row = cursor.fetchone()
            stats["date_range"] = {"earliest": row[0], "latest": row[1]}

            return stats


if __name__ == "__main__":
    # Test database
    logging.basicConfig(level=logging.INFO)

    db = Database("test_sam.db")
    print(f"\nDatabase Stats:")
    stats = db.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
