"""
Skript pro diagnostiku a kontrolu dostupných databází a tabulek na instanci PLZ-SISE\\SQLSISE.
"""
try:
    import pyodbc
except ImportError:
    import pypyodbc as pyodbc

SERVER = 'PLZ-SISE\\SQLSISE'
USER = 'cyclades'
PASSWORD = 'cyclades'
DRIVER = '{SQL Server}'

def check_instance():
    print(f"=== Pripojovani k instanci {SERVER} ===")
    try:
        conn = pyodbc.connect(f"DRIVER={DRIVER};SERVER={SERVER};DATABASE=master;UID={USER};PWD={PASSWORD};")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name")
        dbs = [row[0] for row in cursor.fetchall()]
        print(f"Nalezeno {len(dbs)} uzivatelskych databazi:")
        for db in dbs:
            print(f"  - {db}")
        conn.close()
        return dbs
    except Exception as e:
        print(f"Chyba pripojeni: {e}")
        return []

def check_db_tables(db_name):
    print(f"\n=== Tabulky a pocty zaznamu v databazi [{db_name}] ===")
    try:
        conn = pyodbc.connect(f"DRIVER={DRIVER};SERVER={SERVER};DATABASE={db_name};UID={USER};PWD={PASSWORD};")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.NAME AS TableName, p.rows AS RowCounts
            FROM sys.tables t
            INNER JOIN sys.partitions p ON t.OBJECT_ID = p.OBJECT_ID
            WHERE p.index_id < 2 AND p.rows > 0
            ORDER BY p.rows DESC
        """)
        rows = cursor.fetchall()
        for r in rows[:20]:
            print(f"  {r[0]}: {r[1]:,} radku")
        conn.close()
    except Exception as e:
        print(f"Chyba v {db_name}: {e}")

if __name__ == "__main__":
    dbs = check_instance()
    for target_db in ['SUIVPRO', 'SAVEPRO', 'SAVEBIL', 'GPAO_PVL_SAP', 'CYCLADESV6']:
        if target_db in dbs:
            check_db_tables(target_db)
