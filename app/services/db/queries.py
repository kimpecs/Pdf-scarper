import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Any

from app.utils.config import settings


class DatabaseManager:
    """Central database access class for the parts catalog."""

    def __init__(self):
        self.db_path = self._resolve_db_path()

    def _resolve_db_path(self) -> Path:
        """Resolve the database path from settings, creating directories if needed."""
        data_dir = Path(settings.DATA_DIR)
        if not data_dir.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            data_dir = project_root / data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "catalog.db"

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def get_connection(self) -> sqlite3.Connection:
        """Return an open sqlite3 connection with row_factory set."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def connection(self):
        """Context manager that auto-closes the connection."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Parts write operations
    # ------------------------------------------------------------------

    def insert_part(self, part_data: dict) -> int:
        """
        Insert a single part into the database.
        Uses INSERT OR IGNORE so duplicate (catalog_name, part_number, page)
        rows are silently skipped.
        Returns the new row id, or 0 if the row was ignored as a duplicate.
        """
        sql = """
            INSERT OR IGNORE INTO parts
                (catalog_name, catalog_type, part_type, part_number,
                 description, category, page, image_path, page_text,
                 pdf_path, machine_info, specifications, oe_numbers,
                 applications, features)
            VALUES
                (:catalog_name, :catalog_type, :part_type, :part_number,
                 :description, :category, :page, :image_path, :page_text,
                 :pdf_path, :machine_info, :specifications, :oe_numbers,
                 :applications, :features)
        """
        # Ensure every expected key exists so the query never raises KeyError
        defaults = {
            "catalog_name":  None,
            "catalog_type":  None,
            "part_type":     None,
            "part_number":   None,
            "description":   None,
            "category":      None,
            "page":          None,
            "image_path":    None,
            "page_text":     None,
            "pdf_path":      None,
            "machine_info":  None,
            "specifications": None,
            "oe_numbers":    None,
            "applications":  None,
            "features":      None,
        }
        row = {**defaults, **part_data}

        with self.connection() as conn:
            cur = conn.execute(sql, row)
            conn.commit()
            return cur.lastrowid or 0

    def update_part_image(self, part_id: int, image_path: str) -> None:
        """Update the image_path for a single part."""
        with self.connection() as conn:
            conn.execute(
                "UPDATE parts SET image_path = ? WHERE id = ?",
                (image_path, part_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Parts read queries
    # ------------------------------------------------------------------

    def search_parts(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        part_type: Optional[str] = None,
        catalog_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[sqlite3.Row]:
        """Search parts using FTS5 when a query is provided, LIKE otherwise."""
        with self.connection() as conn:
            where: List[str] = []
            params: List[Any] = []

            if query and query.strip():
                # Try FTS first; fall back to LIKE on any error
                try:
                    fts_sql = """
                        SELECT p.*
                        FROM parts_fts
                        JOIN parts p ON p.id = parts_fts.rowid
                        WHERE parts_fts MATCH ?
                        {extra}
                        ORDER BY rank
                        LIMIT ?
                    """
                    fts_params: List[Any] = [f'"{query.strip()}"*']
                    extra_conditions: List[str] = []

                    if category:
                        extra_conditions.append("p.category = ?")
                        fts_params.append(category)
                    if part_type:
                        extra_conditions.append("p.part_type = ?")
                        fts_params.append(part_type)
                    if catalog_name:
                        extra_conditions.append("p.catalog_name = ?")
                        fts_params.append(catalog_name)

                    extra_clause = (
                        "AND " + " AND ".join(extra_conditions)
                        if extra_conditions
                        else ""
                    )
                    fts_params.append(limit)
                    rows = conn.execute(
                        fts_sql.format(extra=extra_clause), fts_params
                    ).fetchall()

                    if rows:
                        return rows
                except Exception:
                    pass  # fall through to LIKE search

                # LIKE fallback
                where.append("(p.part_number LIKE ? OR p.description LIKE ?)")
                term = f"%{query}%"
                params.extend([term, term])

            if category:
                where.append("p.category = ?")
                params.append(category)
            if part_type:
                where.append("p.part_type = ?")
                params.append(part_type)
            if catalog_name:
                where.append("p.catalog_name = ?")
                params.append(catalog_name)

            where_clause = "WHERE " + " AND ".join(where) if where else ""
            sql = f"""
                SELECT p.*,
                       (SELECT COUNT(*) FROM part_images pi WHERE pi.part_id = p.id) AS image_count
                FROM parts p
                {where_clause}
                ORDER BY p.part_number
                LIMIT ?
            """
            params.append(limit)
            return conn.execute(sql, params).fetchall()

    def get_part_by_id(self, part_id: int) -> Optional[sqlite3.Row]:
        """Fetch a single part by primary key."""
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM parts WHERE id = ?", (part_id,)
            ).fetchone()

    def get_categories_with_counts(self) -> List[sqlite3.Row]:
        """Return each category with its part count."""
        with self.connection() as conn:
            return conn.execute(
                """
                SELECT category, COUNT(*) AS part_count
                FROM parts
                WHERE category IS NOT NULL AND category != ''
                GROUP BY category
                ORDER BY part_count DESC
                """
            ).fetchall()

    def get_distinct_categories(self) -> List[str]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM parts WHERE category IS NOT NULL ORDER BY category"
            ).fetchall()
            return [r[0] for r in rows]

    def get_distinct_part_types(self) -> List[str]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT part_type FROM parts WHERE part_type IS NOT NULL ORDER BY part_type"
            ).fetchall()
            return [r[0] for r in rows]

    def get_distinct_catalog_types(self) -> List[str]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT catalog_type FROM parts WHERE catalog_type IS NOT NULL ORDER BY catalog_type"
            ).fetchall()
            return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Health / stats
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if the database is reachable."""
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_counts(self) -> dict:
        """Return row counts for key tables."""
        with self.connection() as conn:
            part_count = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
            guide_count = conn.execute(
                "SELECT COUNT(*) FROM technical_guides WHERE is_active = 1"
            ).fetchone()[0]
            catalog_count = conn.execute(
                "SELECT COUNT(DISTINCT catalog_name) FROM parts"
            ).fetchone()[0]
            return {
                "parts": part_count,
                "guides": guide_count,
                "catalogs": catalog_count,
            }