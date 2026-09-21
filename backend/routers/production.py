from fastapi import APIRouter
import pandas as pd

try:
    from ..database import get_db_connection, resolve_suivpro_table
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection, resolve_suivpro_table
    from schemas import FilterRequest

router = APIRouter(prefix="/api/kpi", tags=["Production KPI"])

def build_where_clause(filters: FilterRequest) -> str:
    where_clauses = ["1=1"]
    
    if filters.start_date and filters.start_date.strip():
        where_clauses.append(f"CAST(DEBEQU AS DATE) >= '{filters.start_date.strip()}'")
    if filters.end_date and filters.end_date.strip():
        where_clauses.append(f"CAST(DEBEQU AS DATE) <= '{filters.end_date.strip()}'")
        
    if filters.shift and filters.shift.strip():
        where_clauses.append(f"RTRIM(LTRIM(CAST(REFEQUIPE AS VARCHAR(50)))) = '{filters.shift.strip()}'")

    if filters.workshop and filters.workshop.strip():
        where_clauses.append(f"RTRIM(LTRIM(CAST(REFATEL AS VARCHAR(50)))) = '{filters.workshop.strip()}'")
        
    if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
        formatted_machines = "', '".join([m.strip() for m in filters.machines])
        where_clauses.append(f"RTRIM(LTRIM(CAST(REFMAC AS VARCHAR(50)))) IN ('{formatted_machines}')")

    if filters.molds and len(filters.molds) > 0 and "ALL" not in filters.molds:
        formatted_molds = "', '".join([m.strip() for m in filters.molds])
        where_clauses.append(f"RTRIM(LTRIM(CAST(REFOUT AS VARCHAR(50)))) IN ('{formatted_molds}')")

    if filters.articles and len(filters.articles) > 0 and "ALL" not in filters.articles:
        formatted_articles = "', '".join([a.strip() for a in filters.articles])
        where_clauses.append(f"RTRIM(LTRIM(CAST(REFPROD AS VARCHAR(50)))) IN ('{formatted_articles}')")
        
    return " AND ".join(where_clauses)

@router.post("/machines")
def get_filtered_machines(filters: FilterRequest):
    try:
        conn = get_db_connection("SUIVPRO")
        res_table = resolve_suivpro_table(conn)
        where_str = build_where_clause(filters)
        
        query = f"""
            SELECT TOP 100
                RTRIM(LTRIM(CAST(REFMAC AS VARCHAR(50)))) AS KodStroje,
                RTRIM(LTRIM(CAST(ISNULL(LIBMAC, REFMAC) AS VARCHAR(100)))) AS NazevStroje,
                SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT)) AS Vyrobeno_Ks,
                SUM(CAST(ISNULL(QTEREBUT, 0) AS BIGINT)) AS Zmetky_Ks,
                ROUND(
                    CASE 
                        WHEN SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT)) = 0 THEN 0 
                        ELSE (CAST(SUM(CAST(ISNULL(QTEREBUT, 0) AS BIGINT)) AS FLOAT) / SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT))) * 100 
                    END, 2
                ) AS Zmetkovitost_Percent,
                ROUND(AVG(CAST(ISNULL(TXM, 0) AS FLOAT)) * 100, 2) AS Dostupnost_Percent,
                ROUND(AVG(CAST(ISNULL(TXP, 0) AS FLOAT)) * 100, 2) AS Vykon_Percent,
                ROUND(AVG(CAST(ISNULL(TXQ, 0) AS FLOAT)) * 100, 2) AS Kvalita_Percent,
                ROUND(
                    CASE 
                        WHEN SUM(CAST(ISNULL(TPSOUV, 0) AS FLOAT)) = 0 THEN 0 
                        ELSE (CAST(SUM(CAST(ISNULL(TPSUTIL, 0) AS FLOAT)) AS FLOAT) / SUM(CAST(ISNULL(TPSOUV, 0) AS FLOAT))) * 100 
                    END, 2
                ) AS OEE_Percent
            FROM {res_table}
            WHERE {where_str}
            GROUP BY REFMAC, LIBMAC
            ORDER BY SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT)) DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()

        records = df.to_dict(orient="records")

        if not df.empty:
            vyrobeno_col = [c for c in df.columns if c.lower() == 'vyrobeno_ks'][0]
            zmetky_col = [c for c in df.columns if c.lower() == 'zmetky_ks'][0]
            oee_col = [c for c in df.columns if c.lower() == 'oee_percent'][0]
            
            total_vyrobeno = int(df[vyrobeno_col].sum())
            total_zmetky = int(df[zmetky_col].sum())
            total_zmetkovitost = round((total_zmetky / total_vyrobeno * 100), 2) if total_vyrobeno > 0 else 0.0

            if total_vyrobeno > 0:
                weighted_oee = (df[oee_col] * df[vyrobeno_col]).sum() / total_vyrobeno
            else:
                weighted_oee = df[oee_col].mean()

            summary = {
                "KodStroje": "CELKEM",
                "NazevStroje": "Souhrn za výběr",
                "Vyrobeno_Ks": total_vyrobeno,
                "Zmetky_Ks": total_zmetky,
                "Zmetkovitost_Percent": total_zmetkovitost,
                "OEE_Percent": round(weighted_oee, 2)
            }
        else:
            summary = None

        return {"status": "success", "data": records, "summary": summary}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/molds")
def get_filtered_molds(filters: FilterRequest):
    try:
        conn = get_db_connection("SUIVPRO")
        res_table = resolve_suivpro_table(conn)
        where_str = build_where_clause(filters)
        
        query = f"""
            SELECT TOP 30
                RTRIM(LTRIM(CAST(ISNULL(REFOUT, 'Nespecifikováno') AS VARCHAR(50)))) AS KodFormy,
                RTRIM(LTRIM(CAST(ISNULL(LIBOUT, REFOUT) AS VARCHAR(100)))) AS NazevFormy,
                SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT)) AS Vyrobeno_Ks,
                SUM(CAST(ISNULL(QTEREBUT, 0) AS BIGINT)) AS Zmetky_Ks,
                ROUND(
                    CASE 
                        WHEN SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT)) = 0 THEN 0 
                        ELSE (CAST(SUM(CAST(ISNULL(QTEREBUT, 0) AS BIGINT)) AS FLOAT) / SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT))) * 100 
                    END, 2
                ) AS Zmetkovitost_Percent,
                ROUND(
                    CASE 
                        WHEN SUM(CAST(ISNULL(TPSOUV, 0) AS FLOAT)) = 0 THEN 0 
                        ELSE (CAST(SUM(CAST(ISNULL(TPSUTIL, 0) AS FLOAT)) AS FLOAT) / SUM(CAST(ISNULL(TPSOUV, 0) AS FLOAT))) * 100 
                    END, 2
                ) AS OEE_Percent
            FROM {res_table}
            WHERE {where_str}
            GROUP BY REFOUT, LIBOUT
            ORDER BY SUM(CAST(ISNULL(QTEFAB, 0) AS BIGINT)) DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"status": "error", "message": str(e)}
