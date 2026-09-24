# Výrobní Dashboard - MES & SCADA Portal (v2.0)

Sjednocený, modulární portál pro sledování efektivity výroby (OEE), analýzu prostojů a vad, energetický management v reálném čase, kvalifikační matici operátorů (Polyvalence ILUO) a plnění SAP výrobních zakázek.

---

## 1. Struktura projektu `dashboard/`

Projekt byl z původního umístění přímo v kořeni virtuálního prostředí `venv/` přetransformován do čisté modulární architektury:

```text
dashboard/
├── backend/
│   ├── main.py                     # Centrální FastAPI aplikace a routování
│   ├── database.py                 # Multi-databázové připojení k SQL Serveru (pyodbc / pypyodbc)
│   ├── schemas.py                  # Pydantic modely filtrů a datových struktur
│   ├── requirements.txt            # Python závislosti
│   └── routers/                    # Modulární API routery
│       ├── __init__.py
│       ├── filters.py              # Kaskádové filtry (stroje, směny, střediska, formy, výrobky)
│       ├── production.py           # OEE, statistiky strojů a forem
│       ├── downtimes.py            # Analýza prostojů (Pareto)
│       ├── scraps.py               # Analýza zmetků a vad (Pareto)
│       ├── energy.py               # Živý příkon (kW), spotřeba při prostojích a alerty
│       ├── operators.py            # Polyvalenční matice ILUO z výkazů operátorů
│       ├── orders.py               # Plnění SAP zakázek z GPAO
│       └── legacy.py               # Zpětná kompatibilita pro původní endpointy (/api/prostoje)
├── frontend/
│   ├── index.html                  # Jednotný portál s Bootstrap 5 záložkami (Tabs) a Chart.js
│   ├── energy.html                 # Specializovaný pohled na spotřebu stojících lisů
│   ├── polyvalence.html            # Specializovaný pohled na kvalifikační matici operátorů
│   └── assets/                     # Statické soubory
├── scripts/
│   ├── run_dashboard.bat           # Spouštěcí skript pro Windows jedním kliknutím
│   └── explore_db.py               # Diagnostický nástroj pro kontrolu SQL instancí a tabulek
└── README.md                       # Tato dokumentace
```

---

## 2. Průzkum databází na instanci `PLZ-SISE\SQLSISE`

Během analýzy serveru bylo identifikováno několik klíčových databází s bohatými reálnými daty:

| Databáze | Klíčové tabulky | Počet záznamů | Využití v dashboardu |
| :--- | :--- | :--- | :--- |
| **`SUIVPRO`** | `Resultat_equipe` (view/table) | Stovky tisíc | Výpočet OEE, dostupnosti, výkonu, kvality, počtu ks |
| | `PVL_CONSO_ENERGIE_INSTANTANNEE_HISTO` | **~2 950 000** | **Živý příkon lisů v reálném čase (kW)**, celkový výkon haly |
| | `PVL_CONSO_ENERGIE_ALERTES_EQUIPE` | **~60 700** | Detekce odběru proudu u strojů, které nevyrábí |
| | `PVL_CONSO_ENERGIE_ARRETS_EQUIPE` | **~336 400** | Spotřeba energie během evidovaných prostojů |
| **`SAVEPRO`** | `RESULT_SAISIE_ARRETS` | **~404 000** | Důvody a trvání prostojů pro Paretovu analýzu |
| | `RESULT_SAISIE_REBUTS` | **~720 000** | Kódy a typy vad zmetků pro Paretovu analýzu |
| | `RESULT_INFO_OPERATEUR` | **~209 500** | Evidence času operátorů na strojích pro matici Polyvalence |
| **`GPAO_PVL_SAP`**| `OFGPAO` & `GP_OF` | Desítky tisíc | Výrobní příkazy, plánované cykly, formy, přiřazené lisy |
| | `GP_FIN_OF` | Záznamy SAP | Reálně odvedené a schválené kusy v SAPu |
| | `GPAO_MO` | Setkání normohodin | Vykazování práce na zakázky |
| **`SAVEBIL`** | `PVL_SUIVI_ALERTES_CONSO_ENERGIE` | ~4 800 | Historické bilance spotřeb energií |
| **`CYCLADESV6`**| `EQUIPEMENT`, `EQUIPEMENT_JOURNAL...` | Desítky tisíc | Evidence strojů, periferií a servisních zásahů |
| **`SAVESPC32`** | `CARTES`, `MESURES`, `LIMITES_CONTROLE` | Parametry SPC | Statistické řízení procesu a měření rozměrů |

---

## 3. Implementovaná a navržená rozšíření

### Modul A: Výroba & OEE (Core)
- Kaskádové filtry (výběr dílny filtruje stroje, výběr stroje filtruje formy a výrobky).
- 4 hlavní KPI karty: **Celkem vyrobeno (ks)**, **Celkem zmetky (ks)**, **Zmetkovitost (%)**, **Vážené OEE (%)**.
- Interaktivní tabulka strojů (řazení kliknutím na hlavičku sloupce, barevné odznaky dle OEE).
- Kliknutím na řádek stroje se automaticky aplikuje filtr na daný lis.

### Modul B: Analýza ztrát (Pareto prostojů & vad)
- **Pareto prostojů**: Graf a tabulka seřazená podle propálených hodin a četnosti zastavení.
- **Pareto vad zmetků**: Přehled nejčastějších technologických vad.

### Modul C: Energetický management (Nové rozšíření)
- **Live Power Monitoring**: Dotazování na `PVL_CONSO_ENERGIE_INSTANTANNEE_HISTO`, které obsahuje minutové odečty příkonu všech lisů. Zobrazuje celkový okamžitý příkon lisovny (kW) a počet běžících strojů.
- **Stojící lisy**: Identifikace strojů, které stojí, ale jejich topení, hydraulika či chlazení stále odebírají energii (`PVL_CONSO_ENERGIE_ALERTES_EQUIPE`).

### Modul D: Polyvalence & Operátoři ILUO (Nové rozšíření)
- Propojení s tabulkou `RESULT_INFO_OPERATEUR`.
- Výpočet odpracovaných hodin každého operátora na jednotlivých typech lisů a pracovišť.
- Barevné zařazení do úrovní **I** (iniciální), **L** (limitovaný), **U** (způsobilý), **O** (operativní/mentor) s možností přizpůsobení hodinových limitů přímo v UI.

### Modul E: SAP Zakázky & Plnění plánu (Nové rozšíření)
- Napojení na `GPAO_PVL_SAP.dbo.OFGPAO` a `GP_FIN_OF`.
- Zobrazení aktuálně naplánovaných a běžících zakázek, plánovaných zdvihů vs. odvedených kusů v SAPu a procenta splnění s vizuálním progress barem.

---

## 4. Spuštění a instalace

### Rychlé spuštění na Windows:
Jednoduše spusťte skript:
```bat
scripts\run_dashboard.bat
```
Aplikace se otevře na adrese: `http://localhost:8000`

### Manuální spuštění přes terminál:
```powershell
cd C:\users\ondrej.novak\dashboard\backend
& "C:\users\ondrej.novak\venv\Scripts\activate.ps1"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 5. Přehled REST API endpointů

| Metoda | Endpoint | Popis |
| :--- | :--- | :--- |
| `POST` | `/api/filters` | Vrací seznamy pro dropdown filtry (stroje, směny, formy, dílny, výrobky) |
| `POST` | `/api/kpi/machines` | KPI statistiky pro lisy (vyrobeno, zmetky, OEE) |
| `POST` | `/api/kpi/molds` | Statistiky pro formy a nástroje |
| `POST` | `/api/kpi/downtimes` | Paretova analýza prostojů |
| `POST` | `/api/kpi/scraps` | Paretova analýza vad |
| `GET` | `/api/kpi/energy-live` | Aktuální příkon lisů v kW a souhrnný výkon haly |
| `POST` | `/api/kpi/energy-alerts` | Seznam energetických alertů stojících lisů |
| `POST` | `/api/kpi/energy-stops` | Spotřeba kWh během prostojů |
| `GET` | `/api/polyvalence-data` | Data pro kvalifikační matici operátorů |
| `POST` | `/api/orders/sap` | Seznam výrobních zakázek SAP a jejich plnění |
| `GET` | `/api/prostoje` | Zpětně kompatibilní endpoint |
