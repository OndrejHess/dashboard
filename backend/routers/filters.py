from fastapi import APIRouter
from typing import Optional
import pandas as pd

try:
    from ..database import get_db_connection, resolve_suivpro_table
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection, resolve_suivpro_table
    from schemas import FilterRequest

router = APIRouter(prefix="/api", tags=["Filters"])

@router.post("/filters")
def get_filter_options(filters: Optional[FilterRequest] = None):
    try:
        conn = get_db_connection("SUIVPRO")
        res_table = resolve_suivpro_table(conn)
        
        query_machines = f"""
            SELECT DISTINCT 
                RTRIM(LTRIM(CAST(REFMAC AS VARCHAR(50)))) AS REFMAC, 
                RTRIM(LTRIM(CAST(ISNULL(LIBMAC, REFMAC) AS VARCHAR(100)))) AS LIBMAC 
            FROM {res_table} 
            WHERE REFMAC IS NOT NULL AND LTRIM(RTRIM(REFMAC)) <> ''
            ORDER BY RTRIM(LTRIM(CAST(ISNULL(LIBMAC, REFMAC) AS VARCHAR(100)))) ASC
        """
        
        query_shifts = f"""
            SELECT DISTINCT 
                RTRIM(LTRIM(CAST(REFEQUIPE AS VARCHAR(50)))) AS shift_name 
            FROM {res_table} 
            WHERE REFEQUIPE IS NOT NULL AND LTRIM(RTRIM(REFEQUIPE)) <> ''
            ORDER BY RTRIM(LTRIM(CAST(REFEQUIPE AS VARCHAR(50)))) ASC
        """

        query_workshops = f"""
            SELECT DISTINCT 
                RTRIM(LTRIM(CAST(REFATEL AS VARCHAR(50)))) AS workshop_name 
            FROM {res_table} 
            WHERE REFATEL IS NOT NULL AND LTRIM(RTRIM(REFATEL)) <> ''
            ORDER BY RTRIM(LTRIM(CAST(REFATEL AS VARCHAR(50)))) ASC
        """

        article_where = ["REFPROD IS NOT NULL AND LTRIM(RTRIM(REFPROD)) <> ''"]
        if filters:
            if filters.workshop and filters.workshop.strip():
                article_where.append(f"RTRIM(LTRIM(CAST(REFATEL AS VARCHAR(50)))) = '{filters.workshop.strip()}'")
            if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
                formatted_macs = "', '".join([m.strip() for m in filters.machines])
                article_where.append(f"RTRIM(LTRIM(CAST(REFMAC AS VARCHAR(50)))) IN ('{formatted_macs}')")
            if filters.molds and len(filters.molds) > 0 and "ALL" not in filters.molds:
                formatted_molds = "', '".join([m.strip() for m in filters.molds])
                article_where.append(f"RTRIM(LTRIM(CAST(REFOUT AS VARCHAR(50)))) IN ('{formatted_molds}')")

        article_where_str = " AND ".join(article_where)

        query_articles = f"""
            SELECT DISTINCT 
                RTRIM(LTRIM(CAST(REFPROD AS VARCHAR(50)))) AS REFPROD, 
                RTRIM(LTRIM(CAST(ISNULL(LIBPROD, REFPROD) AS VARCHAR(100)))) AS LIBPROD 
            FROM {res_table} 
            WHERE {article_where_str}
            ORDER BY RTRIM(LTRIM(CAST(ISNULL(LIBPROD, REFPROD) AS VARCHAR(100)))) ASC
        """

        mold_where = ["REFOUT IS NOT NULL AND LTRIM(RTRIM(REFOUT)) <> ''"]
        if filters:
            if filters.workshop and filters.workshop.strip():
                mold_where.append(f"RTRIM(LTRIM(CAST(REFATEL AS VARCHAR(50)))) = '{filters.workshop.strip()}'")
            if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
                formatted_macs = "', '".join([m.strip() for m in filters.machines])
                mold_where.append(f"RTRIM(LTRIM(CAST(REFMAC AS VARCHAR(50)))) IN ('{formatted_macs}')")

        mold_where_str = " AND ".join(mold_where)

        query_molds = f"""
            SELECT DISTINCT 
                RTRIM(LTRIM(CAST(REFOUT AS VARCHAR(50)))) AS REFOUT, 
                RTRIM(LTRIM(CAST(ISNULL(LIBOUT, REFOUT) AS VARCHAR(100)))) AS LIBOUT 
            FROM {res_table} 
            WHERE {mold_where_str}
            ORDER BY RTRIM(LTRIM(CAST(ISNULL(LIBOUT, REFOUT) AS VARCHAR(100)))) ASC
        """

        machines = pd.read_sql(query_machines, conn)
        shifts = pd.read_sql(query_shifts, conn)
        workshops = pd.read_sql(query_workshops, conn)
        articles = pd.read_sql(query_articles, conn)
        molds = pd.read_sql(query_molds, conn)
        conn.close()
        
        return {
            "status": "success",
            "table_used": res_table,
            "machines": machines.to_dict(orient="records"),
            "shifts": [str(s) for s in shifts['shift_name'].tolist() if pd.notna(s)],
            "workshops": [str(w) for w in workshops['workshop_name'].tolist() if pd.notna(w)],
            "articles": articles.to_dict(orient="records"),
            "molds": molds.to_dict(orient="records")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
