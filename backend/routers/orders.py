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
    """
    Returns production orders from SUIVPRO.dbo.[OF] and LIGOF with planned strokes,
    planned pieces, produced pieces, scrap, progress percentage, and running status.
    """
    try:
        conn = get_db_connection("SUIVPRO")
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
            SELECT TOP 100
                RTRIM(LTRIM(CAST(o.of_refof AS VARCHAR(50)))) AS VyrobniPrikaz,
                RTRIM(LTRIM(CAST(ISNULL(o.mac_refmac, '-') AS VARCHAR(50)))) AS Stroj,
                RTRIM(LTRIM(CAST(ISNULL(o.mac_libmac, o.mac_refmac) AS VARCHAR(100)))) AS NazevStroje,
                RTRIM(LTRIM(CAST(ISNULL(o.out_refout, '-') AS VARCHAR(50)))) AS Forma,
                RTRIM(LTRIM(CAST(ISNULL(o.out_libout, o.out_refout) AS VARCHAR(100)))) AS NazevFormy,
                CAST(ISNULL(o.of_nbrcoups, 0) AS INT) AS Planovano_Zdvihu,
                CAST(ISNULL(l.Planovano_Ks, 0) AS INT) AS Planovano_Ks,
                CAST(ISNULL(l.Vyrobeno_Ks, 0) AS INT) AS Vyrobeno_Ks,
                CAST(ISNULL(l.Zmetky_Ks, 0) AS INT) AS Zmetky_Ks,
                ROUND(
                    CASE 
                        WHEN ISNULL(l.Planovano_Ks, 0) = 0 THEN 
                            CASE WHEN ISNULL(o.of_nbrcoups, 0) = 0 THEN 0 
                                 ELSE (CAST(ISNULL(l.Vyrobeno_Ks, 0) AS FLOAT) / CAST(o.of_nbrcoups AS FLOAT)) * 100 
                            END
                        ELSE (CAST(ISNULL(l.Vyrobeno_Ks, 0) AS FLOAT) / CAST(l.Planovano_Ks AS FLOAT)) * 100
                    END, 1
                ) AS ProcentoSplneni,
                RTRIM(LTRIM(CAST(ISNULL(o.of_evolution, 'D') AS VARCHAR(10)))) AS StatusKod,
                o.of_datelancer AS SkutecnyZacatek,
                o.of_datelancep AS PlanovanyZacatek
            FROM SUIVPRO.dbo.[OF] o
            LEFT JOIN (
                SELECT 
                    of_refof, 
                    SUM(ISNULL(ligof_qtelance, 0)) AS Planovano_Ks,
                    SUM(ISNULL(ligof_qtebonne, 0)) AS Vyrobeno_Ks,
                    SUM(ISNULL(ligof_qterebut, 0)) AS Zmetky_Ks
                FROM SUIVPRO.dbo.LIGOF
                GROUP BY of_refof
            ) l ON o.of_refof = l.of_refof
            WHERE {where_str}
            ORDER BY 
                CASE WHEN o.of_evolution = 'L' THEN 0 WHEN o.of_evolution = 'D' THEN 1 ELSE 2 END ASC,
                o.of_autonum DESC
        """
        
        df = pd.read_sql(query, conn)
        conn.close()

        records = []
        for _, row in df.iterrows():
            prik = str(row.get('vyrobniprikaz', row.get('VyrobniPrikaz', '')))
            stroj = str(row.get('stroj', row.get('Stroj', '-')))
            libmac = str(row.get('nazevstroje', row.get('NazevStroje', stroj)))
            forma = str(row.get('forma', row.get('Forma', '-')))
            libout = str(row.get('nazevformy', row.get('NazevFormy', forma)))
            plan_zdvihu = int(row.get('planovano_zdvihu', row.get('Planovano_Zdvihu', 0)))
            plan_ks = int(row.get('planovano_ks', row.get('Planovano_Ks', 0)))
            vyr_ks = int(row.get('vyrobeno_ks', row.get('Vyrobeno_Ks', 0)))
            zmet_ks = int(row.get('zmetky_ks', row.get('Zmetky_Ks', 0)))
            pct = round(float(row.get('procentosplneni', row.get('ProcentoSplneni', 0.0))), 1)
            skod = str(row.get('statuskod', row.get('StatusKod', 'D'))).upper()
            
            # Lidsky srozumitelný stav
            if skod == 'L':
                status_text = "Běží"
                is_active = True
            elif skod == 'D':
                status_text = "Naplánováno"
                is_active = False
            elif skod in ('S', 'T'):
                status_text = "Dokončeno"
                is_active = False
            else:
                status_text = skod
                is_active = False

            zacatek = str(row.get('skutecnyzacatek', row.get('SkutecnyZacatek', row.get('planovanyzacatek', ''))))
            if zacatek.startswith('NaT') or zacatek == 'None':
                zacatek = '-'

            records.append({
                "VyrobniPrikaz": prik,
                "Stroj": stroj,
                "NazevStroje": libmac,
                "Forma": forma,
                "NazevFormy": libout,
                "Planovano_Zdvihu": plan_zdvihu,
                "Planovano_Ks": plan_ks,
                "Vyrobeno_Ks": vyr_ks,
                "Zmetky_Ks": zmet_ks,
                "ProcentoSplneni": pct,
                "Status": status_text,
                "StatusKod": skod,
                "IsActive": is_active,
                "Zacatek": zacatek,
                # Malá písmena pro univerzální přístup
                "vyrobniprikaz": prik,
                "stroj": stroj,
                "nazevstroje": libmac,
                "forma": forma,
                "nazevformy": libout,
                "planovano_zdvihu": plan_zdvihu,
                "planovano_ks": plan_ks,
                "vyrobeno_ks": vyr_ks,
                "zmetky_ks": zmet_ks,
                "procentosplneni": pct,
                "status": status_text,
                "is_active": is_active,
                "zacatek": zacatek
            })

        return {"status": "success", "data": records}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}
