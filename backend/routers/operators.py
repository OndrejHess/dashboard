from fastapi import APIRouter, Query
from typing import Optional
import pandas as pd

try:
    from ..database import get_db_connection
except (ImportError, ValueError):
    from database import get_db_connection

router = APIRouter(prefix="/api", tags=["Operators & Polyvalence"])

@router.get("/polyvalence-data")
def get_polyvalence_data(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    operator: Optional[str] = None
):
    """
    Returns time spent by each operator on each machine / station for the ILUO skill matrix.
    Aggregated from SAVEPRO.dbo.RESULT_INFO_OPERATEUR.
    """
    try:
        conn = get_db_connection("SAVEPRO")
        where_clauses = ["infoop_codeop IS NOT NULL", "infoop_dureeposte > 0"]
        
        if from_date and from_date.strip():
            where_clauses.append(f"CAST(infoop_datedebequ AS DATE) >= '{from_date.strip()}'")
        if to_date and to_date.strip():
            where_clauses.append(f"CAST(infoop_datedebequ AS DATE) <= '{to_date.strip()}'")
        if operator and operator.strip():
            where_clauses.append(f"RTRIM(LTRIM(CAST(infoop_codeop AS VARCHAR(50)))) = '{operator.strip()}'")

        where_str = " AND ".join(where_clauses)
        
        query = f"""
            SELECT
                RTRIM(LTRIM(CAST(infoop_codeop AS VARCHAR(50)))) AS op,
                RTRIM(LTRIM(CAST(infoop_refmac AS VARCHAR(50)))) AS label,
                SUM(CAST(infoop_dureeposte AS BIGINT)) AS time_seconds
            FROM RESULT_INFO_OPERATEUR
            WHERE {where_str}
            GROUP BY infoop_codeop, infoop_refmac
            ORDER BY SUM(CAST(infoop_dureeposte AS BIGINT)) DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return {
            "status": "success",
            "count": len(df),
            "records": df.to_dict(orient="records")
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "records": []}

@router.get("/operators/list")
def get_operators_list():
    """Returns list of distinct operator IDs active in the system."""
    try:
        conn = get_db_connection("SAVEPRO")
        query = """
            SELECT DISTINCT 
                RTRIM(LTRIM(CAST(infoop_codeop AS VARCHAR(50)))) AS op
            FROM RESULT_INFO_OPERATEUR
            WHERE infoop_codeop IS NOT NULL AND LTRIM(RTRIM(infoop_codeop)) <> ''
            ORDER BY RTRIM(LTRIM(CAST(infoop_codeop AS VARCHAR(50)))) ASC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return {"status": "success", "operators": df["op"].tolist()}
    except Exception as e:
        return {"status": "error", "message": str(e), "operators": []}
