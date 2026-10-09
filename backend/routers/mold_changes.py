"""
Modul F: Sledování doby výměny formy (Mold Change Time Tracking)

Logika detekce:
  1. Z SUIVPRO.dbo.Resultat_equipe detekujeme výměnu formy pomocí LAG() window
     function — pokud se REFOUT změní na stejném REFMAC, nastal přechod.
  2. KonecVyrobyStareFormy = FINEQU předchozího záznamu (konec výroby staré formy).
  3. ZacatekVyrobyNoveFormy = konec POSLEDNÍHO prostoje v přechodovém okně z
     SAVEPRO.dbo.RESULT_SAISIE_ARRETS (OUTER APPLY).
     → Toto odpovídá skutečnému prvnímu vyrobenému dílu nové formy.
     → Fallback: DEBEQU nového záznamu (začátek směny) pokud žádný prostoj nenajdeme.
  4. ZdrojCasu = 'PROSTOJ' (přesný) nebo 'DEBEQU' (approx.) — pro transparentnost.

Přechodové okno prostojů:
  - Hledáme prostoje od 30 minut PŘED koncem staré výroby (pokrytí překryvu)
  - až do 16 hodin PO konci staré výroby (max délka výměny = 8 h + rezerva).
"""
from fastapi import APIRouter
import pandas as pd

try:
    from ..database import get_db_connection
    from ..schemas import FilterRequest
except (ImportError, ValueError):
    from database import get_db_connection
    from schemas import FilterRequest

router = APIRouter(prefix="/api/kpi", tags=["Mold Changes"])

# Filtr anomálií — reálná délka výměny v minutách
MIN_CHANGE_MIN = 1
MAX_CHANGE_MIN = 480  # 8 hodin


# ---------------------------------------------------------------------------
# Helpery
# ---------------------------------------------------------------------------

def _date_clauses(filters: FilterRequest, date_col: str = "DEBEQU") -> list:
    clauses = []
    if filters.start_date and filters.start_date.strip():
        clauses.append(f"CAST({date_col} AS DATE) >= '{filters.start_date.strip()}'")
    if filters.end_date and filters.end_date.strip():
        clauses.append(f"CAST({date_col} AS DATE) <= '{filters.end_date.strip()}'")
    return clauses


def _machine_clause(filters: FilterRequest, col: str = "REFMAC") -> str:
    if filters.machines and len(filters.machines) > 0 and "ALL" not in filters.machines:
        macs = "', '".join([m.strip() for m in filters.machines])
        return f"AND RTRIM(LTRIM(CAST({col} AS VARCHAR(50)))) IN ('{macs}')"
    return ""


def _mold_clause(filters: FilterRequest) -> str:
    if filters.molds and len(filters.molds) > 0 and "ALL" not in filters.molds:
        molds = "', '".join([m.strip() for m in filters.molds])
        return f"AND RTRIM(LTRIM(CAST(REFOUT AS VARCHAR(50)))) IN ('{molds}')"
    return ""


def _build_changes_cte(where_str: str, machine_filter: str, mold_filter: str = "") -> str:
    """
    Vrátí SQL fragment se dvěma CTE:
      - ordered_records: záznamy Resultat_equipe s LAG pro detekci výměny
      - changes: filtrované přechody (změna REFOUT na stejném REFMAC)

    Výsledné sloupce changes CTE:
      KodStroje, StaraForma, NovaForma, KodVyrobku,
      KonecVyrobyStareFormy, ZacatekEkvipy (fallback)
    """
    return f"""
        ordered_records AS (
            SELECT
                RTRIM(LTRIM(CAST(REFMAC  AS VARCHAR(50))))              AS KodStroje,
                RTRIM(LTRIM(CAST(REFOUT  AS VARCHAR(50))))              AS KodFormy,
                RTRIM(LTRIM(CAST(ISNULL(REFPROD, '') AS VARCHAR(50))))  AS KodVyrobku,
                CAST(DEBEQU AS DATETIME)                                AS ZacatekEkvipy,
                LAG(RTRIM(LTRIM(CAST(REFOUT AS VARCHAR(50)))))
                    OVER (PARTITION BY REFMAC ORDER BY DEBEQU)          AS PredchoziForma,
                LAG(CAST(FINEQU AS DATETIME))
                    OVER (PARTITION BY REFMAC ORDER BY DEBEQU)          AS KonecPredchozi
            FROM SUIVPRO.dbo.[Resultat_equipe]
            WHERE {where_str} {machine_filter} {mold_filter}
        ),
        changes AS (
            SELECT
                KodStroje,
                PredchoziForma   AS StaraForma,
                KodFormy         AS NovaForma,
                KodVyrobku,
                KonecPredchozi   AS KonecVyrobyStareFormy,
                ZacatekEkvipy                                           -- fallback pokud žádný prostoj
            FROM ordered_records
            WHERE KodFormy <> PredchoziForma
              AND KonecPredchozi IS NOT NULL
        )"""


def _outer_apply_savepro() -> str:
    """
    OUTER APPLY do SAVEPRO — hledá konec posledního prostoje na stejném stroji
    v přechodovém okně. Konec prostoje = okamžik, kdy stroj znovu začal vyrábět
    = čas prvního dílu nové formy.

    Okno: od 30 min před koncem staré výroby do 16 h po ní.
    """
    return """
        OUTER APPLY (
            SELECT MAX(DATEADD(SECOND, a.BSARREQU_DURARRET,
                               a.BSARREQU_DATEDEBEQU)) AS KonecPoslednihoProstoje
            FROM SAVEPRO.dbo.RESULT_SAISIE_ARRETS a
            WHERE RTRIM(LTRIM(CAST(a.BSARREQU_REFMAC AS VARCHAR(50)))) = c.KodStroje
              AND a.BSARREQU_DURARRET > 0
              AND a.BSARREQU_DATEDEBEQU
                      >= DATEADD(MINUTE, -30, c.KonecVyrobyStareFormy)
              AND DATEADD(SECOND, a.BSARREQU_DURARRET, a.BSARREQU_DATEDEBEQU)
                      <= DATEADD(HOUR, 16, c.KonecVyrobyStareFormy)
        ) ps"""


# ---------------------------------------------------------------------------
# Endpointy
# ---------------------------------------------------------------------------

@router.post("/mold-changes")
def get_mold_changes(filters: FilterRequest):
    """
    Seznam jednotlivých detekovaných výměn forem (max 500 záznamů, sestupně).

    ZacatekVyrobyNoveFormy = konec posledního prostoje z SAVEPRO (přesný).
    Pokud žádný prostoj v okně nenajdeme, použijeme DEBEQU (začátek směny) jako odhad;
    v tom případě ZdrojCasu = 'DEBEQU'.
    """
    try:
        conn = get_db_connection("SUIVPRO")

        base_where = ["REFMAC IS NOT NULL", "REFOUT IS NOT NULL"] + _date_clauses(filters)
        where_str  = " AND ".join(base_where)
        mf  = _machine_clause(filters)
        mlf = _mold_clause(filters)

        query = f"""
            WITH {_build_changes_cte(where_str, mf, mlf)}
            SELECT TOP 500
                c.KodStroje,
                c.StaraForma,
                c.NovaForma,
                c.KodVyrobku,
                CONVERT(VARCHAR(19), c.KonecVyrobyStareFormy, 120)          AS KonecVyrobyStareFormy,
                CONVERT(VARCHAR(19),
                    ISNULL(ps.KonecPoslednihoProstoje, c.ZacatekEkvipy), 120) AS ZacatekVyrobyNoveFormy,
                CASE WHEN ps.KonecPoslednihoProstoje IS NOT NULL
                     THEN 'PROSTOJ' ELSE 'DEBEQU' END                        AS ZdrojCasu,
                DATEDIFF(MINUTE, c.KonecVyrobyStareFormy,
                    ISNULL(ps.KonecPoslednihoProstoje, c.ZacatekEkvipy))     AS DobaVymeny_Min
            FROM changes c
            {_outer_apply_savepro()}
            WHERE DATEDIFF(MINUTE, c.KonecVyrobyStareFormy,
                      ISNULL(ps.KonecPoslednihoProstoje, c.ZacatekEkvipy))
                  BETWEEN {MIN_CHANGE_MIN} AND {MAX_CHANGE_MIN}
            ORDER BY c.KonecVyrobyStareFormy DESC
        """

        df = pd.read_sql(query, conn)
        conn.close()

        # Statistika kvality dat (kolik záznamů má přesný čas vs. odhad)
        if not df.empty:
            zdroj_col = [c for c in df.columns if c.lower() == "zdrojcasu"][0]
            presne   = int((df[zdroj_col] == "PROSTOJ").sum())
            odhadnute = int((df[zdroj_col] == "DEBEQU").sum())
        else:
            presne = odhadnute = 0

        return {
            "status":   "success",
            "count":    len(df),
            "quality":  {"presne_z_prostoje": presne, "odhad_debequ": odhadnute},
            "data":     df.to_dict(orient="records"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


@router.post("/mold-changes/kpi")
def get_mold_change_kpi(filters: FilterRequest):
    """
    Agregované KPI výměn per stroj: počet, průměr, min, max, StdDev doby výměny.
    Počítá se z opravených časů (PROSTOJ), ale zahrnuje i záznamy s fallbackem DEBEQU.
    """
    try:
        conn = get_db_connection("SUIVPRO")

        base_where = ["REFMAC IS NOT NULL", "REFOUT IS NOT NULL"] + _date_clauses(filters)
        where_str  = " AND ".join(base_where)
        mf = _machine_clause(filters)

        query = f"""
            WITH {_build_changes_cte(where_str, mf)},
            durations AS (
                SELECT
                    c.KodStroje,
                    DATEDIFF(MINUTE, c.KonecVyrobyStareFormy,
                        ISNULL(ps.KonecPoslednihoProstoje, c.ZacatekEkvipy)) AS DobaVymeny_Min,
                    CASE WHEN ps.KonecPoslednihoProstoje IS NOT NULL
                         THEN 'PROSTOJ' ELSE 'DEBEQU' END                    AS ZdrojCasu
                FROM changes c
                {_outer_apply_savepro()}
                WHERE DATEDIFF(MINUTE, c.KonecVyrobyStareFormy,
                          ISNULL(ps.KonecPoslednihoProstoje, c.ZacatekEkvipy))
                      BETWEEN {MIN_CHANGE_MIN} AND {MAX_CHANGE_MIN}
            )
            SELECT
                KodStroje,
                COUNT(*)                                               AS PocetVymen,
                SUM(CASE WHEN ZdrojCasu = 'PROSTOJ' THEN 1 ELSE 0 END) AS PocetPresnych,
                ROUND(AVG(CAST(DobaVymeny_Min AS FLOAT)), 1)          AS Prumer_Min,
                ROUND(MIN(CAST(DobaVymeny_Min AS FLOAT)), 1)          AS Min_Min,
                ROUND(MAX(CAST(DobaVymeny_Min AS FLOAT)), 1)          AS Max_Min,
                ROUND(STDEV(CAST(DobaVymeny_Min AS FLOAT)), 1)        AS StdDev_Min
            FROM durations
            GROUP BY KodStroje
            ORDER BY Prumer_Min DESC
        """

        df = pd.read_sql(query, conn)
        conn.close()

        vymen_col = next((c for c in df.columns if c.lower() == "pocetvymen"), None)
        prumer_col = next((c for c in df.columns if c.lower() == "prumer_min"), None)

        total_changes = int(df[vymen_col].sum()) if (not df.empty and vymen_col) else 0
        if total_changes > 0 and prumer_col and vymen_col:
            overall_avg = round(
                float((df[prumer_col] * df[vymen_col]).sum() / total_changes), 1
            )
        else:
            overall_avg = 0.0

        records = []
        for _, row in df.iterrows():
            stroj = str(row.get('kodstroje', row.get('KodStroje', '')))
            pocet = int(row.get('pocetvymen', row.get('PocetVymen', 0)))
            presnych = int(row.get('pocetpresnych', row.get('PocetPresnych', 0)))
            prumer = round(float(row.get('prumer_min', row.get('Prumer_Min', 0.0))), 1)
            min_val = round(float(row.get('min_min', row.get('Min_Min', 0.0))), 1)
            max_val = round(float(row.get('max_min', row.get('Max_Min', 0.0))), 1)
            stddev = round(float(row.get('stddev_min', row.get('StdDev_Min', 0.0))), 1) if pd.notna(row.get('stddev_min', row.get('StdDev_Min', None))) else None
            records.append({
                "KodStroje": stroj,
                "PocetVymen": pocet,
                "PocetPresnych": presnych,
                "Prumer_Min": prumer,
                "Min_Min": min_val,
                "Max_Min": max_val,
                "StdDev_Min": stddev,
                "kodstroje": stroj,
                "pocetvymen": pocet,
                "prumer_min": prumer,
                "min_min": min_val,
                "max_min": max_val,
                "stddev_min": stddev
            })

        return {
            "status":  "success",
            "summary": {
                "CelkemVymen":       total_changes,
                "CelkovyPrumer_Min": overall_avg,
            },
            "data": records,
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}


@router.post("/mold-changes/trend")
def get_mold_change_trend(filters: FilterRequest):
    """
    Denní trend průměrné doby výměny formy — pro Chart.js line/bar chart.
    Datum je určen podle KonecVyrobyStareFormy (konec staré formy).
    """
    try:
        conn = get_db_connection("SUIVPRO")

        base_where = ["REFMAC IS NOT NULL", "REFOUT IS NOT NULL"] + _date_clauses(filters)
        where_str  = " AND ".join(base_where)
        mf = _machine_clause(filters)

        query = f"""
            WITH {_build_changes_cte(where_str, mf)},
            durations AS (
                SELECT
                    CAST(c.KonecVyrobyStareFormy AS DATE)                    AS Datum,
                    DATEDIFF(MINUTE, c.KonecVyrobyStareFormy,
                        ISNULL(ps.KonecPoslednihoProstoje, c.ZacatekEkvipy)) AS DobaVymeny_Min
                FROM changes c
                {_outer_apply_savepro()}
                WHERE DATEDIFF(MINUTE, c.KonecVyrobyStareFormy,
                          ISNULL(ps.KonecPoslednihoProstoje, c.ZacatekEkvipy))
                      BETWEEN {MIN_CHANGE_MIN} AND {MAX_CHANGE_MIN}
            )
            SELECT
                CONVERT(VARCHAR(10), Datum, 120)                       AS Datum,
                COUNT(*)                                               AS PocetVymen,
                ROUND(AVG(CAST(DobaVymeny_Min AS FLOAT)), 1)          AS Prumer_Min
            FROM durations
            GROUP BY Datum
            ORDER BY Datum ASC
        """

        df = pd.read_sql(query, conn)
        conn.close()
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}
