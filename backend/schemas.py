from pydantic import BaseModel
from typing import List, Optional

class FilterRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    shift: Optional[str] = None
    workshop: Optional[str] = None
    machines: Optional[List[str]] = None
    molds: Optional[List[str]] = None
    articles: Optional[List[str]] = None

class PolyvalenceFilterRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    operator: Optional[str] = None

class EnergyAlertFilterRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    machines: Optional[List[str]] = None
