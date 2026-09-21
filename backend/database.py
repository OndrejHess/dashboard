"""
Database connection manager supporting multiple databases on the PLZ-SISE\\SQLSISE instance:
- GPAO_PVL_SAP (SAP orders, labor, articles)
- SUIVPRO (Production tracking, shifts, machines, instant energy, live alerts)
- SAVEPRO (Downtimes, scraps, operator history)
- SAVEBIL (Energy bilans and summaries)
- CYCLADESV6 (Asset management and maintenance)
"""
try:
    import pyodbc
except ImportError:
    import pypyodbc as pyodbc

DB_CONFIG = {
    'server': 'PLZ-SISE\\SQLSISE',
    'default_database': 'SUIVPRO',
    'user': 'cyclades',
    'password': 'cyclades',
    'driver': '{SQL Server}'
}

def get_db_connection(database: str = None):
    """
    Returns an active database connection to the specified database.
    Defaults to SUIVPRO.
    """
    db = database or DB_CONFIG['default_database']
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={db};"
        f"UID={DB_CONFIG['user']};"
        f"PWD={DB_CONFIG['password']};"
    )
    return pyodbc.connect(conn_str)

def resolve_suivpro_table(conn) -> str:
    """Helper returning the default production team results table / view."""
    return "SUIVPRO.dbo.[Resultat_equipe]"
