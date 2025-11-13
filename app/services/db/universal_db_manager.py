# app/services/db/universal_db_manager.py
import os
import pyodbc
import sqlite3
from app.utils.config import settings

class UniversalDBManager:
    def __init__(self):
        self.use_mssql = hasattr(settings, 'MSSQL_CONNECTION_STRING') and settings.MSSQL_CONNECTION_STRING
        
    def get_connection(self):
        if self.use_mssql:
            return pyodbc.connect(settings.MSSQL_CONNECTION_STRING)
        else:
            # Fall back to SQLite
            return sqlite3.connect('data/catalog.db')
    
    def execute_query(self, query, params=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                # For SQL Server, get column names
                if self.use_mssql:
                    columns = [column[0] for column in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
                else:
                    # SQLite
                    return cursor.fetchall()
            else:
                conn.commit()
                return cursor.rowcount
        finally:
            conn.close()