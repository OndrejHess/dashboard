from fastapi import APIRouter
import pandas as pd

try:
    from ..database import get_db_connection, resolve_suivpro_table
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection, resolve_suivpro_table
    from schemas import FilterRequest

router = APIRouter(prefix="/api/kpi", tags=["Downtimes"])

@router.post("/downtimes")
def get_downtimes(filters: FilterRequest):
    try:
        conn = get_db_connection("SAVEPRO")
        res_table = resolve_suivpro_table(conn)
        where_clauses = ["BSARREQU_DURARRET > 0"]
        
        if filters.start_date and filters.start_date.strip():
            where_clauses.append(f"CAST(BSARREQU_DATEDEBEQU AS DATE) >= '{filters.start_date.strip()}'")
        if filters.end_date and filters.end_date.strip():
            where_clauses.append(f"CAST(BSARREQU_DATEDEBEQU AS DATE) <= '{filters.end_date.strip()}'")
            
        if filters.shift and filters.shift.strip():
            where_clauses.append(f"RTRIM(LTRIM(CAST(EQUI_REFEQUIPE AS VARCHAR(50)))) = '{filters.shift.strip()}'")

        if filters.workshop and filters.workshop.strip():
            where_clauses.append(f"RTRIM(LTRIM(CAST(BSARREQU_REFMAC AS VARCHAR(50)))) IN (SELECT DISTINCT RTRIM(LTRIM(CAST(REFMAC AS VARCHAR(50)))) FROM {res_table} WHERE RTRIM(LTRIM(CAST(REFATEL AS VARCHAR(50)))) = '{filters.workshop.strip()}')")

        if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
            formatted_machines = "', '".join([m.strip() for m in filters.machines])
            where_clauses.append(f"RTRIM(LTRIM(CAST(BSARREQU_REFMAC AS VARCHAR(50)))) IN ('{formatted_machines}')")

        if filters.molds and len(filters.molds) > 0 and "ALL" not in filters.molds:
            formatted_molds = "', '".join([m.strip() for m in filters.molds])
            where_clauses.append(f"RTRIM(LTRIM(CAST(BSARREQU_REFMAC AS VARCHAR(50)))) IN (SELECT DISTINCT RTRIM(LTRIM(CAST(REFMAC AS VARCHAR(50)))) FROM {res_table} WHERE RTRIM(LTRIM(CAST(REFOUT AS VARCHAR(50)))) IN ('{formatted_molds}'))")

        where_str = " AND ".join(where_clauses)
        
        query = f"""
            SELECT TOP 15
                RTRIM(LTRIM(CAST(ISNULL(NULLIF(ARR_LIBARRET, ''), ARR_REFARRET) AS VARCHAR(100)))) AS DuvodProstoje,
                ROUND(SUM(CAST(ISNULL(BSARREQU_DURARRET, 0) AS FLOAT)) / 3600.0, 2) AS Trvani_Hodin,
                COUNT(*) AS Pocet_Zastaveni
            FROM SAVEPRO.dbo.RESULT_SAISIE_ARRETS
            WHERE {where_str}
            GROUP BY ARR_LIBARRET, ARR_REFARRET
            ORDER BY SUM(CAST(ISNULL(BSARREQU_DURARRET, 0) AS FLOAT)) DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()

        # Calculate total downtime for contribution percentage (handle case insensitivity from pyodbc)
        trvani_col = next((c for c in df.columns if c.lower() == 'trvani_hodin'), None)
        total_downtime = df[trvani_col].sum() if (not df.empty and trvani_col) else 0

        records = []
        for _, row in df.iterrows():
            duvod = str(row.get('duvodprostoje', row.get('DuvodProstoje', 'Neznámý')))
            trvani = round(float(row.get('trvani_hodin', row.get('Trvani_Hodin', 0.0))), 2)
            zastaveni = int(row.get('pocet_zastaveni', row.get('Pocet_Zastaveni', 0)))
            disponibilni = trvani  # placeholder, same as duration
            podil = round(float((trvani / total_downtime) * 100), 2) if total_downtime > 0 else 0.0
            records.append({
                "DuvodProstoje": duvod,
                "Trvani_Hodin": trvani,
                "Pocet_Zastaveni": zastaveni,
                "DisponibilniDoba": disponibilni,
                "Podil_NonOEE": podil,
                # lowercase for backward compatibility
                "duvodprostoje": duvod,
                "trvani_hodin": trvani,
                "pocet_zastaveni": zastaveni,
                "disponibilni_doba": disponibilni,
                "podil_non_oee": podil
            })

        return {"status": "success", "data": records}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}