from fastapi import APIRouter
import pandas as pd

try:
    from ..database import get_db_connection, resolve_suivpro_table
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection, resolve_suivpro_table
    from schemas import FilterRequest

router = APIRouter(prefix="/api/kpi", tags=["Scraps"])

@router.post("/scraps")
def get_scraps(filters: FilterRequest):
    try:
        conn = get_db_connection("SAVEPRO")
        res_table = resolve_suivpro_table(conn)
        
        where_clauses = ["r.BILRSEQU_QTEREBUTSAISIE > 0"]
        
        if filters.start_date and filters.start_date.strip():
            where_clauses.append(f"CAST(e.DEBEQU AS DATE) >= '{filters.start_date.strip()}'")
        if filters.end_date and filters.end_date.strip():
            where_clauses.append(f"CAST(e.DEBEQU AS DATE) <= '{filters.end_date.strip()}'")
            
        if filters.shift and filters.shift.strip():
            where_clauses.append(f"RTRIM(LTRIM(CAST(e.REFEQUIPE AS VARCHAR(50)))) = '{filters.shift.strip()}'")

        if filters.workshop and filters.workshop.strip():
            where_clauses.append(f"RTRIM(LTRIM(CAST(e.REFATEL AS VARCHAR(50)))) = '{filters.workshop.strip()}'")

        if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
            formatted_machines = "', '".join([m.strip() for m in filters.machines])
            where_clauses.append(f"RTRIM(LTRIM(CAST(e.REFMAC AS VARCHAR(50)))) IN ('{formatted_machines}')")

        if filters.molds and len(filters.molds) > 0 and "ALL" not in filters.molds:
            formatted_molds = "', '".join([m.strip() for m in filters.molds])
            where_clauses.append(f"RTRIM(LTRIM(CAST(e.REFOUT AS VARCHAR(50)))) IN ('{formatted_molds}')")

        if filters.articles and len(filters.articles) > 0 and "ALL" not in filters.articles:
            formatted_articles = "', '".join([a.strip() for a in filters.articles])
            where_clauses.append(f"RTRIM(LTRIM(CAST(e.REFPROD AS VARCHAR(50)))) IN ('{formatted_articles}')")

        where_str = " AND ".join(where_clauses)
        
        query = f"""
            SELECT TOP 15
                RTRIM(LTRIM(CAST(ISNULL(TYPREB_LIBREB, TYPREB_TYPREB) AS VARCHAR(100)))) AS TypVady,
                SUM(CAST(ISNULL(BILRSEQU_QTEREBUTSAISIE, 0) AS BIGINT)) AS Zmetky_Ks
            FROM SAVEPRO.dbo.RESULT_SAISIE_REBUTS r
            JOIN {res_table} e ON r.OF_REFOF = e.REFOF
            WHERE (r.PROD_REFPROD = e.REFPROD OR (r.PROD_REFPROD IS NULL AND e.REFPROD IS NULL))
              AND {where_str}
            GROUP BY TYPREB_LIBREB, TYPREB_TYPREB
            ORDER BY SUM(CAST(ISNULL(BILRSEQU_QTEREBUTSAISIE, 0) AS BIGINT)) DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"status": "error", "message": str(e)}
