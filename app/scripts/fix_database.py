# scripts/test_remote_connection.py
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

def test_remote_sql():
    """Test connection to your remote SQL Server"""
    
    # Get connection string from environment
    connection_string = os.getenv('MSSQL_CONNECTION_STRING')
    
    if not connection_string:
        print("❌ MSSQL_CONNECTION_STRING not found in environment file")
        return False
    
    print("🔍 Testing Remote SQL Server Connection...")
    print(f"Server: 192.96.222.38,30002")
    print(f"Database: ApelloKbDev")
    print(f"Username: ligapp")
    
    try:
        conn = pyodbc.connect(connection_string, timeout=15)
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT @@VERSION as version")
        version = cursor.fetchone()[0]
        print(f"✅ SUCCESS: Connected to SQL Server!")
        print(f"   Version: {version.split('\n')[0]}")
        
        # Check if tables already exist
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   Existing tables: {existing_tables}")
        
        # Check if our target tables exist and their row counts
        target_tables = ['parts', 'technical_guides', 'guide_parts']
        for table in target_tables:
            if table in existing_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   {table}: {count:,} rows")
            else:
                print(f"   {table}: Does not exist")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_remote_sql()