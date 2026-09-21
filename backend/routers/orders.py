from fastapi import APIRouter
from typing import Optional
import pandas as pd

try:
    from ..database import get_db_connection
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection
    from schemas import FilterRequest

router = APIRouter(prefix="/api/orders", tags=["SAP Orders"])

@router.post("/sap")
def get_sap_orders(filters: Optional[FilterRequest] = None):
    """Returns SAP production orders and progress from GPAO_PVL_SAP."""
    try:
        conn = get_db_connection("GPAO_PVL_SAP")
        where_clauses = ["1=1"]
        
        if filters:
            if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
                formatted_macs = "', '".join([m.strip() for m in filters.machines])
                where_clauses.append(f"RTRIM(LTRIM(CAST(o.mac_refmac AS VARCHAR(50)))) IN ('{formatted_macs}')")
            if filters.molds and len(filters.molds) > 0 and "ALL" not in filters.molds:
                formatted_molds = "', '".join([m.strip() for m in filters.molds])
                where_clauses.append(f"RTRIM(LTRIM(CAST(o.out_refout AS VARCHAR(50)))) IN ('{formatted_molds}')")

        where_str = " AND ".join(where_clauses)
        
        query = f"""
            SELECT TOP 50
                RTRIM(LTRIM(CAST(o.of_refof AS VARCHAR(50)))) AS VyrobniPrikaz,
                RTRIM(LTRIM(CAST(ISNULL(o.mac_refmac, '-') AS VARCHAR(50)))) AS Stroj,
                RTRIM(LTRIM(CAST(ISNULL(o.mac_libmac, o.mac_refmac) AS VARCHAR(100)))) AS NazevStroje,
                RTRIM(LTRIM(CAST(ISNULL(o.out_refout, '-') AS VARCHAR(50)))) AS Forma,
                RTRIM(LTRIM(CAST(ISNULL(o.out_libout, o.out_refout) AS VARCHAR(100)))) AS NazevFormy,
                CAST(ISNULL(o.of_nbrcoups, 0) AS BIGINT) AS Planovano_Zdvihu,
                o.of_datedebprev AS PlanovanyZacatek,
                o.of_datefinof AS PlanovanyKonec,
                RTRIM(LTRIM(CAST(ISNULL(o.status, '-') AS VARCHAR(20)))) AS Status,
                CAST(ISNULL(f.of_gpao_pieces_fab, 0) AS BIGINT) AS Vyrobeno_Ks,
                ROUND(
                    CASE 
                        WHEN CAST(ISNULL(o.of_nbrcoups, 0) AS BIGINT) = 0 THEN 0
                        ELSE (CAST(ISNULL(f.of_gpao_pieces_fab, 0) AS FLOAT) / CAST(o.of_nbrcoups AS FLOAT)) * 100
                    END, 1
                ) AS ProcentoSplneni
            FROM OFGPAO o
            LEFT JOIN GP_FIN_OF f ON o.of_refof = f.of_refof
            WHERE {where_str}
            ORDER BY o.of_id DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"status": "error", "message": str(e)}
