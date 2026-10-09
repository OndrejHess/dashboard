"""
Modul G: Spotřeba a plánovaná potřeba materiálu (Material Consumption & Planning)

Vychází z metodiky Cyklades:
  - Tabulka SUIVPRO.dbo.CONSOMMABLES (suroviny, např. PPM0360, jednotka KG)
  - Tabulka SUIVPRO.dbo.CONSOMMABLES_PRODUITS (dávka na kus CSP_QUANTITE, příznak recyklovatelnosti CSP_RECYCLABLE)
  - Tabulka SUIVPRO.dbo.Resultat_equipe (odvedená výroba per směna/datum/zakázka/lis)
  - Tabulka SUIVPRO.dbo.[OF] a LIGOF (aktivní přihlášené výrobní příkazy s plánovanými a dosud vyrobenými kusy)

Výpočty:
  1. Dosavadní spotřeba: CSP_QUANTITE * QTEFAB (resp. QTEBONNE)
  2. Budoucí potřeba na dokončení přihlášených zakázek:
     ZbyvaVyrobit_Ks = MAX(0, LIGOF_QTELANCE - LIGOF_QTEBONNE)
     PotrebaNaDokonceni_Kg = CSP_QUANTITE * ZbyvaVyrobit_Ks
"""
from fastapi import APIRouter
import pandas as pd

try:
    from ..database import get_db_connection, resolve_suivpro_table
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection, resolve_suivpro_table
    from schemas import FilterRequest

router = APIRouter(prefix="/api/materials", tags=["Material Consumption"])


def build_material_where(filters: FilterRequest) -> str:
    where_clauses = [
        "r.REFOF IS NOT NULL",
        "LTRIM(RTRIM(r.REFOF)) <> ''",
        "r.REFPROD IS NOT NULL",
        "LTRIM(RTRIM(r.REFPROD)) <> ''"
    ]
    
    if filters.start_date and filters.start_date.strip():
        where_clauses.append(f"CAST(r.DEBEQU AS DATE) >= '{filters.start_date.strip()}'")
    if filters.end_date and filters.end_date.strip():
        where_clauses.append(f"CAST(r.DEBEQU AS DATE) <= '{filters.end_date.strip()}'")

    if filters.shift and filters.shift.strip():
        where_clauses.append(f"RTRIM(LTRIM(CAST(r.REFEQUIPE AS VARCHAR(50)))) = '{filters.shift.strip()}'")

    if filters.workshop and filters.workshop.strip():
        where_clauses.append(f"RTRIM(LTRIM(CAST(r.REFATEL AS VARCHAR(50)))) = '{filters.workshop.strip()}'")

    if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
        formatted_machines = "', '".join([m.strip() for m in filters.machines])
        where_clauses.append(f"RTRIM(LTRIM(CAST(r.REFMAC AS VARCHAR(50)))) IN ('{formatted_machines}')")

    if filters.material and filters.material.strip() and filters.material.strip() != "ALL":
        mat = filters.material.strip().replace("'", "''")
        where_clauses.append(f"cp.CONS_REFCONS = '{mat}'")

    return " AND ".join(where_clauses)


def build_planned_where(filters: FilterRequest) -> str:
    where_clauses = [
        "o.OF_EVOLUTION IN ('L', 'D', 'P', 'S')",
        "o.OF_REFOF IS NOT NULL",
        "LTRIM(RTRIM(o.OF_REFOF)) <> ''",
        "l.PROD_REFPROD IS NOT NULL",
        "LTRIM(RTRIM(l.PROD_REFPROD)) <> ''"
    ]

    if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
        formatted_machines = "', '".join([m.strip() for m in filters.machines])
        where_clauses.append(f"RTRIM(LTRIM(CAST(o.MAC_REFMAC AS VARCHAR(50)))) IN ('{formatted_machines}')")

    if filters.material and filters.material.strip() and filters.material.strip() != "ALL":
        mat = filters.material.strip().replace("'", "''")
        where_clauses.append(f"cp.CONS_REFCONS = '{mat}'")

    return " AND ".join(where_clauses)


@router.get("/list")
def get_materials_list():
    """Vrací seznam dostupných materiálů/surovin pro výběrový filtr."""
    try:
        conn = get_db_connection("SUIVPRO")
        query = """
            SELECT 
                RTRIM(LTRIM(CAST(c.CONS_REFCONS AS VARCHAR(50)))) AS KodMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_LIBCONS, c.CONS_REFCONS) AS VARCHAR(100)))) AS NazevMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_UNITE, 'KG') AS VARCHAR(20)))) AS Jednotka,
                RTRIM(LTRIM(CAST(ISNULL(tc.TYPC_LIB0, 'Ostatní') AS VARCHAR(50)))) AS Typ
            FROM SUIVPRO.dbo.CONSOMMABLES c
            LEFT JOIN SUIVPRO.dbo.TYPES_CONSOMMABLES tc ON c.TYPC_TYPE = tc.TYPC_TYPE
            WHERE EXISTS (
                SELECT 1 FROM SUIVPRO.dbo.CONSOMMABLES_PRODUITS cp 
                WHERE cp.CONS_REFCONS = c.CONS_REFCONS
            )
            ORDER BY c.CONS_REFCONS ASC
        """
        df = pd.read_sql(query, conn)
        conn.close()

        records = []
        for _, row in df.iterrows():
            kod = str(row.get('kodmaterialu', row.get('KodMaterialu', '')))
            nazev = str(row.get('nazevmaterialu', row.get('NazevMaterialu', kod)))
            jednotka = str(row.get('jednotka', row.get('Jednotka', 'KG')))
            typ = str(row.get('typ', row.get('Typ', '')))
            records.append({
                "KodMaterialu": kod,
                "NazevMaterialu": nazev,
                "Jednotka": jednotka,
                "Typ": typ
            })
        return {"status": "success", "data": records}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


@router.post("/consumption")
def get_material_consumption(filters: FilterRequest):
    """
    Vrací:
      1. Budoucí potřebu na dokončení přihlášených zakázek (aktivní OFs v Cyklades)
      2. Historickou odvedenou spotřebu v zadaném období
      3. Rozpad zakázek (jak budoucích, tak historických)
      4. Denní trend
      5. Souhrnnou tabulku materiálů
    """
    try:
        conn = get_db_connection("SUIVPRO")
        res_table = resolve_suivpro_table(conn)
        where_hist = build_material_where(filters)
        where_plan = build_planned_where(filters)

        # -------------------------------------------------------------
        # A. BUDOUCÍ POTŘEBA: Přihlášené zakázky a kolik chybí vyrobit
        # -------------------------------------------------------------
        query_planned = f"""
            SELECT TOP 500
                RTRIM(LTRIM(CAST(o.OF_REFOF AS VARCHAR(50)))) AS CisloZakazky,
                RTRIM(LTRIM(CAST(ISNULL(o.MAC_REFMAC, '-') AS VARCHAR(50)))) AS Stroj,
                RTRIM(LTRIM(CAST(ISNULL(o.MAC_LIBMAC, o.MAC_REFMAC) AS VARCHAR(100)))) AS NazevStroje,
                RTRIM(LTRIM(CAST(ISNULL(o.OUT_REFOUT, '-') AS VARCHAR(50)))) AS Forma,
                RTRIM(LTRIM(CAST(l.PROD_REFPROD AS VARCHAR(50)))) AS KodVyrobku,
                RTRIM(LTRIM(CAST(ISNULL(p.PROD_LIBPROD, l.PROD_REFPROD) AS VARCHAR(100)))) AS NazevVyrobku,
                RTRIM(LTRIM(CAST(cp.CONS_REFCONS AS VARCHAR(50)))) AS KodMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_LIBCONS, cp.CONS_REFCONS) AS VARCHAR(100)))) AS NazevMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_UNITE, 'KG') AS VARCHAR(20)))) AS Jednotka,
                ROUND(CAST(cp.CSP_QUANTITE AS FLOAT), 4) AS DavkaNaKus,
                CAST(ISNULL(l.LIGOF_QTELANCE, 0) AS BIGINT) AS Planovano_Ks,
                CAST(ISNULL(l.LIGOF_QTEBONNE, 0) AS BIGINT) AS Vyrobeno_Ks,
                CAST(ISNULL(l.LIGOF_QTEREBUT, 0) AS BIGINT) AS Zmetky_Ks,
                CAST(CASE WHEN (ISNULL(l.LIGOF_QTELANCE, 0) - ISNULL(l.LIGOF_QTEBONNE, 0)) > 0 
                          THEN (ISNULL(l.LIGOF_QTELANCE, 0) - ISNULL(l.LIGOF_QTEBONNE, 0)) 
                          ELSE 0 END AS BIGINT) AS ZbyvaVyrobit_Ks,
                ROUND(CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(l.LIGOF_QTELANCE, 0) AS FLOAT), 2) AS PlanovanaSpotreba_Celkem,
                ROUND(CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(l.LIGOF_QTEBONNE, 0) AS FLOAT), 2) AS DosudSpotrebovano_Kg,
                ROUND(CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(
                    CASE WHEN (ISNULL(l.LIGOF_QTELANCE, 0) - ISNULL(l.LIGOF_QTEBONNE, 0)) > 0 
                         THEN (ISNULL(l.LIGOF_QTELANCE, 0) - ISNULL(l.LIGOF_QTEBONNE, 0)) 
                         ELSE 0 END AS FLOAT), 2) AS PotrebaNaDokonceni_Kg,
                RTRIM(LTRIM(CAST(o.OF_EVOLUTION AS VARCHAR(10)))) AS StatusKod,
                RTRIM(LTRIM(CAST(ISNULL(eo.OF_LIBEVOL0, o.OF_EVOLUTION) AS VARCHAR(50)))) AS StatusNazev
            FROM SUIVPRO.dbo.[OF] o
            INNER JOIN SUIVPRO.dbo.LIGOF l ON o.OF_REFOF = l.OF_REFOF
            LEFT JOIN SUIVPRO.dbo.PRODUIT p ON l.PROD_REFPROD = p.PROD_REFPROD
            INNER JOIN SUIVPRO.dbo.CONSOMMABLES_PRODUITS cp ON l.PROD_REFPROD = cp.PROD_REFPROD AND l.CSP_REVISION = cp.CSP_REVISION
            INNER JOIN SUIVPRO.dbo.CONSOMMABLES c ON cp.CONS_REFCONS = c.CONS_REFCONS
            LEFT JOIN SUIVPRO.dbo.EVOLUTIONS_OF eo ON o.OF_EVOLUTION = eo.OF_EVOLUTION
            WHERE {where_plan}
            ORDER BY PotrebaNaDokonceni_Kg DESC
        """
        df_plan = pd.read_sql(query_planned, conn)

        # -------------------------------------------------------------
        # B. HISTORICKÁ SPOTŘEBA V ZADANÉM OBDOBÍ
        # -------------------------------------------------------------
        query_orders = f"""
            SELECT TOP 500
                RTRIM(LTRIM(CAST(r.REFOF AS VARCHAR(50)))) AS CisloZakazky,
                RTRIM(LTRIM(CAST(r.REFMAC AS VARCHAR(50)))) AS Stroj,
                RTRIM(LTRIM(CAST(ISNULL(r.LIBMAC, r.REFMAC) AS VARCHAR(100)))) AS NazevStroje,
                RTRIM(LTRIM(CAST(r.REFPROD AS VARCHAR(50)))) AS KodVyrobku,
                RTRIM(LTRIM(CAST(ISNULL(r.LIBPROD, r.REFPROD) AS VARCHAR(100)))) AS NazevVyrobku,
                RTRIM(LTRIM(CAST(cp.CONS_REFCONS AS VARCHAR(50)))) AS KodMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_LIBCONS, cp.CONS_REFCONS) AS VARCHAR(100)))) AS NazevMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_UNITE, 'KG') AS VARCHAR(20)))) AS Jednotka,
                ROUND(CAST(AVG(CAST(cp.CSP_QUANTITE AS FLOAT)) AS FLOAT), 4) AS DavkaNaKus,
                CAST(SUM(CAST(ISNULL(r.QTEFAB, 0) AS BIGINT)) AS BIGINT) AS Vyrobeno_Ks,
                CAST(SUM(CAST(ISNULL(r.QTEBONNE, 0) AS BIGINT)) AS BIGINT) AS Dobre_Ks,
                CAST(SUM(CAST(ISNULL(r.QTEREBUT, 0) AS BIGINT)) AS BIGINT) AS Zmetky_Ks,
                ROUND(SUM(
                    CASE 
                        WHEN cp.CSP_RECYCLABLE = 0 THEN CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEFAB, 0) AS FLOAT)
                        ELSE CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEBONNE, 0) AS FLOAT)
                    END
                ), 2) AS Spotreba_Celkem,
                ROUND(SUM(CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEBONNE, 0) AS FLOAT)), 2) AS Spotreba_Dobre,
                ROUND(SUM(CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEREBUT, 0) AS FLOAT)), 2) AS Spotreba_Zmetky,
                CONVERT(VARCHAR(19), MIN(r.DEBEQU), 120) AS PrvniVyroba,
                CONVERT(VARCHAR(19), MAX(r.FINEQU), 120) AS PosledniVyroba
            FROM {res_table} r
            INNER JOIN SUIVPRO.dbo.CONSOMMABLES_PRODUITS cp 
                ON r.REFPROD = cp.PROD_REFPROD AND r.CSP_REVISION = cp.CSP_REVISION
            INNER JOIN SUIVPRO.dbo.CONSOMMABLES c 
                ON cp.CONS_REFCONS = c.CONS_REFCONS
            WHERE {where_hist}
            GROUP BY 
                r.REFOF, r.REFMAC, r.LIBMAC, r.REFPROD, r.LIBPROD, 
                cp.CONS_REFCONS, c.CONS_LIBCONS, c.CONS_UNITE
            HAVING SUM(CAST(ISNULL(r.QTEFAB, 0) AS BIGINT)) > 0
            ORDER BY Spotreba_Celkem DESC
        """
        df_orders = pd.read_sql(query_orders, conn)

        # -------------------------------------------------------------
        # C. DENNÍ TREND
        # -------------------------------------------------------------
        query_trend = f"""
            SELECT 
                CONVERT(VARCHAR(10), CAST(r.DEBEQU AS DATE), 120) AS Datum,
                ROUND(SUM(
                    CASE 
                        WHEN cp.CSP_RECYCLABLE = 0 THEN CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEFAB, 0) AS FLOAT)
                        ELSE CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEBONNE, 0) AS FLOAT)
                    END
                ), 2) AS Spotreba_Kg,
                CAST(SUM(CAST(ISNULL(r.QTEFAB, 0) AS BIGINT)) AS BIGINT) AS Vyrobeno_Ks,
                COUNT(DISTINCT r.REFOF) AS PocetZakazek
            FROM {res_table} r
            INNER JOIN SUIVPRO.dbo.CONSOMMABLES_PRODUITS cp 
                ON r.REFPROD = cp.PROD_REFPROD AND r.CSP_REVISION = cp.CSP_REVISION
            WHERE {where_hist}
            GROUP BY CAST(r.DEBEQU AS DATE)
            ORDER BY CAST(r.DEBEQU AS DATE) ASC
        """
        df_trend = pd.read_sql(query_trend, conn)

        # -------------------------------------------------------------
        # D. SOUHRN MATERIÁLŮ S POTŘEBOU NA DOKONČENÍ
        # -------------------------------------------------------------
        query_mats = f"""
            SELECT TOP 50
                RTRIM(LTRIM(CAST(cp.CONS_REFCONS AS VARCHAR(50)))) AS KodMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_LIBCONS, cp.CONS_REFCONS) AS VARCHAR(100)))) AS NazevMaterialu,
                RTRIM(LTRIM(CAST(ISNULL(c.CONS_UNITE, 'KG') AS VARCHAR(20)))) AS Jednotka,
                COUNT(DISTINCT r.REFOF) AS PocetZakazek,
                COUNT(DISTINCT r.REFMAC) AS PocetStroju,
                ROUND(SUM(
                    CASE 
                        WHEN cp.CSP_RECYCLABLE = 0 THEN CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEFAB, 0) AS FLOAT)
                        ELSE CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEBONNE, 0) AS FLOAT)
                    END
                ), 2) AS Spotreba_Celkem,
                ROUND(SUM(CAST(cp.CSP_QUANTITE AS FLOAT) * CAST(ISNULL(r.QTEREBUT, 0) AS FLOAT)), 2) AS Spotreba_Zmetky
            FROM {res_table} r
            INNER JOIN SUIVPRO.dbo.CONSOMMABLES_PRODUITS cp 
                ON r.REFPROD = cp.PROD_REFPROD AND r.CSP_REVISION = cp.CSP_REVISION
            INNER JOIN SUIVPRO.dbo.CONSOMMABLES c 
                ON cp.CONS_REFCONS = c.CONS_REFCONS
            WHERE {where_hist}
            GROUP BY cp.CONS_REFCONS, c.CONS_LIBCONS, c.CONS_UNITE
            ORDER BY Spotreba_Celkem DESC
        """
        df_mats = pd.read_sql(query_mats, conn)
        conn.close()

        # -------------------------------------------------------------
        # Formátování výstupních kolekcí
        # -------------------------------------------------------------
        planned_records = []
        for _, row in df_plan.iterrows():
            planned_records.append({
                "CisloZakazky": str(row.get('cislozakazky', row.get('CisloZakazky', ''))),
                "Stroj": str(row.get('stroj', row.get('Stroj', '-'))),
                "NazevStroje": str(row.get('nazevstroje', row.get('NazevStroje', ''))),
                "Forma": str(row.get('forma', row.get('Forma', '-'))),
                "KodVyrobku": str(row.get('kodvyrobku', row.get('KodVyrobku', ''))),
                "NazevVyrobku": str(row.get('nazevvyrobku', row.get('NazevVyrobku', ''))),
                "KodMaterialu": str(row.get('kodmaterialu', row.get('KodMaterialu', ''))),
                "NazevMaterialu": str(row.get('nazevmaterialu', row.get('NazevMaterialu', ''))),
                "Jednotka": str(row.get('jednotka', row.get('Jednotka', 'KG'))),
                "DavkaNaKus": round(float(row.get('davkanakus', row.get('DavkaNaKus', 0.0))), 4),
                "Planovano_Ks": int(row.get('planovano_ks', row.get('Planovano_Ks', 0))),
                "Vyrobeno_Ks": int(row.get('vyrobeno_ks', row.get('Vyrobeno_Ks', 0))),
                "Zmetky_Ks": int(row.get('zmetky_ks', row.get('Zmetky_Ks', 0))),
                "ZbyvaVyrobit_Ks": int(row.get('zbyvavyrobit_ks', row.get('ZbyvaVyrobit_Ks', 0))),
                "PlanovanaSpotreba_Celkem": round(float(row.get('planovanaspotreba_celkem', row.get('PlanovanaSpotreba_Celkem', 0.0))), 2),
                "DosudSpotrebovano_Kg": round(float(row.get('dosudspotrebovano_kg', row.get('DosudSpotrebovano_Kg', 0.0))), 2),
                "PotrebaNaDokonceni_Kg": round(float(row.get('potrebanadokonceni_kg', row.get('PotrebaNaDokonceni_Kg', 0.0))), 2),
                "StatusKod": str(row.get('statuskod', row.get('StatusKod', ''))),
                "StatusNazev": str(row.get('statusnazev', row.get('StatusNazev', '')))
            })

        orders_records = []
        for _, row in df_orders.iterrows():
            orders_records.append({
                "CisloZakazky": str(row.get('cislozakazky', row.get('CisloZakazky', ''))),
                "Stroj": str(row.get('stroj', row.get('Stroj', ''))),
                "NazevStroje": str(row.get('nazevstroje', row.get('NazevStroje', ''))),
                "KodVyrobku": str(row.get('kodvyrobku', row.get('KodVyrobku', ''))),
                "NazevVyrobku": str(row.get('nazevvyrobku', row.get('NazevVyrobku', ''))),
                "KodMaterialu": str(row.get('kodmaterialu', row.get('KodMaterialu', ''))),
                "NazevMaterialu": str(row.get('nazevmaterialu', row.get('NazevMaterialu', ''))),
                "Jednotka": str(row.get('jednotka', row.get('Jednotka', 'KG'))),
                "DavkaNaKus": round(float(row.get('davkanakus', row.get('DavkaNaKus', 0.0))), 4),
                "Vyrobeno_Ks": int(row.get('vyrobeno_ks', row.get('Vyrobeno_Ks', 0))),
                "Dobre_Ks": int(row.get('dobre_ks', row.get('Dobre_Ks', 0))),
                "Zmetky_Ks": int(row.get('zmetky_ks', row.get('Zmetky_Ks', 0))),
                "Spotreba_Celkem": round(float(row.get('spotreba_celkem', row.get('Spotreba_Celkem', 0.0))), 2),
                "Spotreba_Dobre": round(float(row.get('spotreba_dobre', row.get('Spotreba_Dobre', 0.0))), 2),
                "Spotreba_Zmetky": round(float(row.get('spotreba_zmetky', row.get('Spotreba_Zmetky', 0.0))), 2),
                "PrvniVyroba": str(row.get('prvnivyroba', row.get('PrvniVyroba', ''))),
                "PosledniVyroba": str(row.get('poslednivyroba', row.get('PosledniVyroba', '')))
            })

        trend_records = []
        for _, row in df_trend.iterrows():
            trend_records.append({
                "Datum": str(row.get('datum', row.get('Datum', ''))),
                "Spotreba_Kg": round(float(row.get('spotreba_kg', row.get('Spotreba_Kg', 0.0))), 2),
                "Vyrobeno_Ks": int(row.get('vyrobeno_ks', row.get('Vyrobeno_Ks', 0))),
                "PocetZakazek": int(row.get('pocetzakazek', row.get('PocetZakazek', 0)))
            })

        mats_records = []
        for _, row in df_mats.iterrows():
            mats_records.append({
                "KodMaterialu": str(row.get('kodmaterialu', row.get('KodMaterialu', ''))),
                "NazevMaterialu": str(row.get('nazevmaterialu', row.get('NazevMaterialu', ''))),
                "Jednotka": str(row.get('jednotka', row.get('Jednotka', 'KG'))),
                "PocetZakazek": int(row.get('pocetzakazek', row.get('PocetZakazek', 0))),
                "PocetStroju": int(row.get('pocetstroju', row.get('PocetStroju', 0))),
                "Spotreba_Celkem": round(float(row.get('spotreba_celkem', row.get('Spotreba_Celkem', 0.0))), 2),
                "Spotreba_Zmetky": round(float(row.get('spotreba_zmetky', row.get('Spotreba_Zmetky', 0.0))), 2)
            })

        # Souhrny pro plán (budoucí potřeba)
        future_needed = round(sum(r["PotrebaNaDokonceni_Kg"] for r in planned_records), 2)
        future_planned_total = round(sum(r["PlanovanaSpotreba_Celkem"] for r in planned_records), 2)
        future_done_so_far = round(sum(r["DosudSpotrebovano_Kg"] for r in planned_records), 2)
        future_remaining_pieces = sum(r["ZbyvaVyrobit_Ks"] for r in planned_records)
        future_active_orders_cnt = len(set(r["CisloZakazky"] for r in planned_records))
        future_active_machines_cnt = len(set(r["Stroj"] for r in planned_records if r["Stroj"] != '-'))

        # Souhrny pro minulost (odvedená spotřeba)
        total_spotreba = round(sum(r["Spotreba_Celkem"] for r in orders_records), 2)
        total_dobre = round(sum(r["Spotreba_Dobre"] for r in orders_records), 2)
        total_zmetky = round(sum(r["Spotreba_Zmetky"] for r in orders_records), 2)
        total_vyrobeno = sum(r["Vyrobeno_Ks"] for r in orders_records)
        total_zakazek = len(set(r["CisloZakazky"] for r in orders_records))
        total_stroju = len(set(r["Stroj"] for r in orders_records))

        summary = {
            # Budoucnost: Potřeba na dokončení
            "PotrebaNaDokonceni_Kg": future_needed,
            "PlanovanaSpotreba_Aktivni_Kg": future_planned_total,
            "DosudVyrobeno_Aktivni_Kg": future_done_so_far,
            "ZbyvaVyrobit_Aktivni_Ks": future_remaining_pieces,
            "PocetAktivnichZakazek": future_active_orders_cnt,
            "PocetAktivnichStroju": future_active_machines_cnt,

            # Minulost: Odvedená spotřeba
            "Spotreba_Celkem": total_spotreba,
            "Spotreba_Dobre": total_dobre,
            "Spotreba_Zmetky": total_zmetky,
            "Podil_Zmetku_Pct": round((total_zmetky / total_spotreba * 100), 2) if total_spotreba > 0 else 0.0,
            "Vyrobeno_Ks": total_vyrobeno,
            "PocetZakazek": total_zakazek,
            "PocetStroju": total_stroju
        }

        return {
            "status": "success",
            "summary": summary,
            "planned_orders": planned_records,
            "orders": orders_records,
            "trend": trend_records,
            "materials_summary": mats_records
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e), 
            "summary": {}, 
            "planned_orders": [], 
            "orders": [], 
            "trend": [], 
            "materials_summary": []
        }
