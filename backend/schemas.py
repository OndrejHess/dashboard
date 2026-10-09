from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any

# =============================================================================
# REQUEST SCHEMAS (Filtry a parametry)
# =============================================================================

class FilterRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    shift: Optional[str] = None
    workshop: Optional[str] = None
    machines: Optional[List[str]] = None
    molds: Optional[List[str]] = None
    articles: Optional[List[str]] = None
    material: Optional[str] = None

class MaterialFilterRequest(FilterRequest):
    pass

class PolyvalenceFilterRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    operator: Optional[str] = None
    machine: Optional[str] = None

class EnergyAlertFilterRequest(FilterRequest):
    pass


# =============================================================================
# FILTERS RESPONSE SCHEMAS
# =============================================================================

class MachineFilterOption(BaseModel):
    model_config = ConfigDict(extra="allow")
    REFMAC: str
    LIBMAC: Optional[str] = None

class ArticleFilterOption(BaseModel):
    model_config = ConfigDict(extra="allow")
    REFPROD: str
    LIBPROD: Optional[str] = None

class MoldFilterOption(BaseModel):
    model_config = ConfigDict(extra="allow")
    REFOUT: str
    LIBOUT: Optional[str] = None

class FiltersResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    table_used: Optional[str] = None
    machines: List[MachineFilterOption] = []
    shifts: List[str] = []
    workshops: List[str] = []
    articles: List[ArticleFilterOption] = []
    molds: List[MoldFilterOption] = []
    message: Optional[str] = None


# =============================================================================
# PRODUCTION & MOLDS KPI SCHEMAS
# =============================================================================

class MachineKPIRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    KodStroje: str
    NazevStroje: Optional[str] = None
    Vyrobeno_Ks: int = 0
    Zmetky_Ks: int = 0
    Zmetkovitost_Percent: float = 0.0
    Dostupnost_Percent: Optional[float] = 0.0
    Vykon_Percent: Optional[float] = 0.0
    Kvalita_Percent: Optional[float] = 0.0
    OEE_Percent: float = 0.0

class MachineKPISummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    KodStroje: str = "CELKEM"
    NazevStroje: str = "Souhrn za výběr"
    Vyrobeno_Ks: int = 0
    Zmetky_Ks: int = 0
    Zmetkovitost_Percent: float = 0.0
    OEE_Percent: float = 0.0

class MachineKPIResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[MachineKPIRow] = []
    summary: Optional[MachineKPISummary] = None
    message: Optional[str] = None

class MoldKPIRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    KodFormy: str
    NazevFormy: Optional[str] = None
    Vyrobeno_Ks: int = 0
    Zmetky_Ks: int = 0
    Zmetkovitost_Percent: float = 0.0
    OEE_Percent: float = 0.0

class MoldKPIResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[MoldKPIRow] = []
    message: Optional[str] = None


# =============================================================================
# DOWNTIMES & SCRAPS SCHEMAS (PARETO)
# =============================================================================

class DowntimeRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    DuvodProstoje: str
    Trvani_Hodin: float
    Pocet_Zastaveni: int
    DisponibilniDoba: Optional[float] = None
    Podil_NonOEE: float = 0.0

class DowntimeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[DowntimeRow] = []
    message: Optional[str] = None

class ScrapRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    TypVady: str
    Zmetky_Ks: int
    Podil_NonOEE: float = 0.0

class ScrapResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[ScrapRow] = []
    message: Optional[str] = None


# =============================================================================
# ENERGY SCHEMAS (LIVE & ALERTS & STOPS)
# =============================================================================

class EnergyLiveRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    Stroj: str
    Timestamp: str
    Vykon_kW: float

class EnergyLiveResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    timestamp: str = ""
    total_kw: float = 0.0
    active_machines_count: int = 0
    total_machines_count: int = 0
    data: List[EnergyLiveRow] = []
    message: Optional[str] = None

class EnergyAlertRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    BILOFEQU_REFMAC: str
    EQUI_REFEQUIPE: Optional[str] = "-"
    BILOFEQU_DEBALERTE: Optional[str] = "-"
    BILOFEQU_FINALERTE: Optional[str] = "-"
    BILOFEQU_CONSO_KWH: float = 0.0
    BILOFEQU_DEBEQU: Optional[str] = None
    BILOFEQU_FINEQU: Optional[str] = None

class EnergyAlertResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[EnergyAlertRow] = []
    message: Optional[str] = None

class EnergyStopRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    Stroj: str
    DuvodZastaveni: Optional[str] = None
    Spotreba_kWh: float = 0.0
    Zacatek: Optional[str] = None
    Konec: Optional[str] = None

class EnergyStopResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[EnergyStopRow] = []
    message: Optional[str] = None


# =============================================================================
# OPERATORS & POLYVALENCE SCHEMAS
# =============================================================================

class PolyvalenceRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    op: str
    label: str
    time_seconds: int

class PolyvalenceResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    count: int = 0
    records: List[PolyvalenceRow] = []
    message: Optional[str] = None

class OperatorsListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    operators: List[str] = []
    message: Optional[str] = None


# =============================================================================
# SAP ORDERS SCHEMAS
# =============================================================================

class SapOrderRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    VyrobniPrikaz: str
    Stroj: str = "-"
    NazevStroje: Optional[str] = None
    Forma: str = "-"
    NazevFormy: Optional[str] = None
    Planovano_Zdvihu: int = 0
    Planovano_Ks: int = 0
    Vyrobeno_Ks: int = 0
    Zmetky_Ks: int = 0
    ProcentoSplneni: float = 0.0
    Status: str = "-"
    StatusKod: str = "D"
    IsActive: bool = False
    Zacatek: str = "-"

class SapOrderResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[SapOrderRow] = []
    message: Optional[str] = None


# =============================================================================
# MOLD CHANGES SCHEMAS (MODUL F)
# =============================================================================

class MoldChangeDetailRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    KodStroje: str
    StaraForma: str
    NovaForma: str
    KodVyrobku: Optional[str] = ""
    KonecVyrobyStareFormy: Optional[str] = None
    ZacatekVyrobyNoveFormy: Optional[str] = None
    ZdrojCasu: str = "PROSTOJ"
    DobaVymeny_Min: int = 0

class MoldChangeQuality(BaseModel):
    model_config = ConfigDict(extra="allow")
    presne_z_prostoje: int = 0
    odhad_debequ: int = 0

class MoldChangesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    count: int = 0
    quality: Optional[MoldChangeQuality] = None
    data: List[MoldChangeDetailRow] = []
    message: Optional[str] = None

class MoldChangeKPIRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    KodStroje: str
    PocetVymen: int = 0
    PocetPresnych: int = 0
    Prumer_Min: float = 0.0
    Min_Min: float = 0.0
    Max_Min: float = 0.0
    StdDev_Min: Optional[float] = 0.0

class MoldChangeKPISummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    CelkemVymen: int = 0
    CelkovyPrumer_Min: float = 0.0

class MoldChangeKPIResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    summary: Optional[MoldChangeKPISummary] = None
    data: List[MoldChangeKPIRow] = []
    message: Optional[str] = None

class MoldChangeTrendRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    Datum: str
    PocetVymen: int = 0
    Prumer_Min: float = 0.0

class MoldChangeTrendResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[MoldChangeTrendRow] = []
    message: Optional[str] = None


# =============================================================================
# MATERIALS CONSUMPTION & PLANNING SCHEMAS (MODUL G)
# =============================================================================

class MaterialListItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    KodMaterialu: str
    NazevMaterialu: str
    Jednotka: str = "KG"
    Typ: Optional[str] = "Ostatní"

class MaterialsListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: List[MaterialListItem] = []
    message: Optional[str] = None

class PlannedMaterialOrderItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    CisloZakazky: str
    Stroj: str = "-"
    NazevStroje: Optional[str] = ""
    Forma: Optional[str] = "-"
    KodVyrobku: str
    NazevVyrobku: Optional[str] = ""
    KodMaterialu: str
    NazevMaterialu: Optional[str] = ""
    Jednotka: str = "KG"
    DavkaNaKus: float = 0.0
    Planovano_Ks: int = 0
    Vyrobeno_Ks: int = 0
    Zmetky_Ks: int = 0
    ZbyvaVyrobit_Ks: int = 0
    PlanovanaSpotreba_Celkem: float = 0.0
    DosudSpotrebovano_Kg: float = 0.0
    PotrebaNaDokonceni_Kg: float = 0.0
    StatusKod: str = "D"
    StatusNazev: Optional[str] = ""

class MaterialOrderItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    CisloZakazky: str
    Stroj: str
    NazevStroje: Optional[str] = ""
    KodVyrobku: str
    NazevVyrobku: Optional[str] = ""
    KodMaterialu: str
    NazevMaterialu: Optional[str] = ""
    Jednotka: str = "KG"
    DavkaNaKus: float = 0.0
    Vyrobeno_Ks: int = 0
    Dobre_Ks: int = 0
    Zmetky_Ks: int = 0
    Spotreba_Celkem: float = 0.0
    Spotreba_Dobre: float = 0.0
    Spotreba_Zmetky: float = 0.0
    PrvniVyroba: Optional[str] = ""
    PosledniVyroba: Optional[str] = ""

class MaterialTrendItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    Datum: str
    Spotreba_Kg: float = 0.0
    Vyrobeno_Ks: int = 0
    PocetZakazek: int = 0

class MaterialSummaryItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    KodMaterialu: str
    NazevMaterialu: str
    Jednotka: str = "KG"
    PocetZakazek: int = 0
    PocetStroju: int = 0
    Spotreba_Celkem: float = 0.0
    Spotreba_Zmetky: float = 0.0

class MaterialConsumptionSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    PotrebaNaDokonceni_Kg: float = 0.0
    PlanovanaSpotreba_Aktivni_Kg: float = 0.0
    DosudVyrobeno_Aktivni_Kg: float = 0.0
    ZbyvaVyrobit_Aktivni_Ks: int = 0
    PocetAktivnichZakazek: int = 0
    PocetAktivnichStroju: int = 0
    Spotreba_Celkem: float = 0.0
    Spotreba_Dobre: float = 0.0
    Spotreba_Zmetky: float = 0.0
    Podil_Zmetku_Pct: float = 0.0
    Vyrobeno_Ks: int = 0
    PocetZakazek: int = 0
    PocetStroju: int = 0

class MaterialConsumptionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    summary: MaterialConsumptionSummary
    planned_orders: List[PlannedMaterialOrderItem] = []
    orders: List[MaterialOrderItem] = []
    trend: List[MaterialTrendItem] = []
    materials_summary: List[MaterialSummaryItem] = []
    message: Optional[str] = None
