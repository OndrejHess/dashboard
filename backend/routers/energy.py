from fastapi import APIRouter
from typing import Optional
import pandas as pd

try:
    from ..database import get_db_connection
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection
    from schemas import FilterRequest

router = APIRouter(prefix="/api/kpi", tags=["Energy"])

@router.post("/energy-alerts")
def get_energy_alerts(filters: Optional[FilterRequest] = None):
    try:
        conn = get_db_connection("SUIVPRO")
        where_clauses = ["1=1"]
        
        if filters:
            if filters.start_date and filters.start_date.strip():
                where_clauses.append(f"CAST(BILOFEQU_DEBEQU AS DATE) >= '{filters.start_date.strip()}'")
            if filters.end_date and filters.end_date.strip():
                where_clauses.append(f"CAST(BILOFEQU_DEBEQU AS DATE) <= '{filters.end_date.strip()}'")
            if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
                formatted_machines = "', '".join([m.strip() for m in filters.machines])
                where_clauses.append(f"RTRIM(LTRIM(CAST(BILOFEQU_REFMAC AS VARCHAR(50)))) IN ('{formatted_machines}')")
                
        where_str = " AND ".join(where_clauses)
        
        query = f"""
            SELECT TOP 200
                BILOFEQU_DEBEQU, 
                BILOFEQU_FINEQU, 
                RTRIM(LTRIM(CAST(BILOFEQU_REFMAC AS VARCHAR(50)))) AS BILOFEQU_REFMAC, 
                RTRIM(LTRIM(CAST(EQUI_REFEQUIPE AS VARCHAR(50)))) AS EQUI_REFEQUIPE, 
                BILOFEQU_TYPEOF, 
                BILOFEQU_TYPEEVE, 
                BILOFEQU_DEBALERTE, 
                BILOFEQU_FINALERTE, 
                ROUND(CAST(ISNULL(BILOFEQU_CONSO_KWH, 0) AS FLOAT), 2) AS BILOFEQU_CONSO_KWH
            FROM SUIVPRO.dbo.PVL_CONSO_ENERGIE_ALERTES_EQUIPE
            WHERE {where_str}
            ORDER BY BILOFEQU_DEBEQU DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/energy-live")
def get_energy_live():
    """Returns real-time instantaneous machine power (kW / kWh) and total factory instantaneous power."""
    try:
        conn = get_db_connection("SUIVPRO")
        query = """
            SELECT 
                RTRIM(LTRIM(CAST(mac_refmac AS VARCHAR(50)))) AS Stroj,
                conso_timestamp AS Timestamp,
                ROUND(CAST(conso_inst_kwh AS FLOAT), 2) AS Vykon_kW
            FROM SUIVPRO.dbo.PVL_CONSO_ENERGIE_INSTANTANNEE_HISTO
            WHERE conso_timestamp = (
                SELECT MAX(conso_timestamp) 
                FROM SUIVPRO.dbo.PVL_CONSO_ENERGIE_INSTANTANNEE_HISTO
            )
            ORDER BY conso_inst_kwh DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()

        # Normalizace názvů sloupců
        cols_map = {c.lower(): c for c in df.columns}
        vykon_col = cols_map.get('vykon_kw', df.columns[2] if len(df.columns) > 2 else None)
        ts_col = cols_map.get('timestamp', df.columns[1] if len(df.columns) > 1 else None)
        stroj_col = cols_map.get('stroj', df.columns[0] if len(df.columns) > 0 else None)
        
        records = []
        for _, row in df.iterrows():
            records.append({
                "Stroj": str(row[stroj_col]),
                "Timestamp": str(row[ts_col]),
                "Vykon_kW": round(float(row[vykon_col] or 0), 2)
            })

        total_kw = round(float(df[vykon_col].sum()), 2) if not df.empty and vykon_col else 0.0
        active_machines = int((df[vykon_col] > 1.0).sum()) if not df.empty and vykon_col else 0
        latest_time = str(df[ts_col].iloc[0]) if not df.empty and ts_col else ""

        return {
            "status": "success",
            "timestamp": latest_time,
            "total_kw": total_kw,
            "active_machines_count": active_machines,
            "total_machines_count": len(df),
            "data": records
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/energy-stops")
def get_energy_during_stops(filters: Optional[FilterRequest] = None):
    """Energy consumed during downtime / idle machines."""
    try:
        conn = get_db_connection("SUIVPRO")
        where_clauses = ["bsarrequ_conso_kwh > 0"]
        if filters:
            if filters.start_date and filters.start_date.strip():
                where_clauses.append(f"CAST(bsarrequ_datedebequ AS DATE) >= '{filters.start_date.strip()}'")
            if filters.end_date and filters.end_date.strip():
                where_clauses.append(f"CAST(bsarrequ_datedebequ AS DATE) <= '{filters.end_date.strip()}'")
            if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
                formatted_machines = "', '".join([m.strip() for m in filters.machines])
                where_clauses.append(f"RTRIM(LTRIM(CAST(bsarrequ_refmac AS VARCHAR(50)))) IN ('{formatted_machines}')")

        where_str = " AND ".join(where_clauses)
        query = f"""
            SELECT TOP 50
                RTRIM(LTRIM(CAST(bsarrequ_refmac AS VARCHAR(50)))) AS Stroj,
                RTRIM(LTRIM(CAST(arr_refarret AS VARCHAR(50)))) AS DuvodZastaveni,
                bsarrequ_datedebarrequ AS Zacatek,
                bsarrequ_datefinarrequ AS Konec,
                ROUND(CAST(bsarrequ_conso_kwh AS FLOAT), 2) AS Spotreba_kWh
            FROM SUIVPRO.dbo.PVL_CONSO_ENERGIE_ARRETS_EQUIPE
            WHERE {where_str}
            ORDER BY bsarrequ_conso_kwh DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"status": "error", "message": str(e)}
