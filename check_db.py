# check_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("catalog.db")


def print_tables(cur):
    print("=== Database Structure ===")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    print("Tables:", tables)
    return tables


def print_table_info(cur, table_name: str):
    print(f"\n=== {table_name} Table Structure ===")
    cur.execute(f"PRAGMA table_info({table_name});")
    columns = cur.fetchall()
    for col in columns:
        # col = (cid, name, type, notnull, dflt_value, pk)
        pk = " PRIMARY KEY" if col[5] else ""
        nn = " NOT NULL" if col[3] else ""
        print(f"  {col[1]} ({col[2]}){nn}{pk}")


def print_sample_parts(cur, limit: int = 30):
    print(f"\n=== First {limit} Parts ===")
    cur.execute("""
        SELECT id, catalog_type, part_type, part_number, description, category, page
        FROM parts
        ORDER BY page, part_number
        LIMIT ?;
    """, (limit,))
    rows = cur.fetchall()

    if not rows:
        print("No parts found in the database. Extraction may have failed.")
        return

    for row in rows:
        print(f"ID: {row[0]}, Catalog: {row[1]}, Type: {row[2]}, "
              f"Part: {row[3]}, Category: {row[5]}, Page: {row[6]}")
        if row[4]:
            print(f"  Description: {row[4][:80]}...")


def print_distribution(cur, field: str, label: str):
    print(f"\n=== Parts by {label} ===")
    cur.execute(f"SELECT {field}, COUNT(*) FROM parts GROUP BY {field} ORDER BY COUNT(*) DESC;")
    for val, count in cur.fetchall():
        print(f"  {val}: {count} parts")


def main():
    if not DB_PATH.exists():
        print("Database not found. Run db_setup.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Print tables and schema
    tables = print_tables(cur)
    if "parts" in tables:
        print_table_info(cur, "parts")

    # Sample parts
    print_sample_parts(cur, limit=30)

    # Distributions
    print_distribution(cur, "catalog_type", "Catalog")
    print_distribution(cur, "category", "Category")
    print_distribution(cur, "page", "Page")

    conn.close()


if __name__ == "__main__":
    main()
