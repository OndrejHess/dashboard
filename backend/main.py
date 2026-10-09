from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

try:
    from .routers import (
        filters,
        production,
        downtimes,
        scraps,
        energy,
        operators,
        orders,
        legacy,
        mold_changes,
        materials
    )
except (ImportError, ValueError):
    from routers import (
        filters,
        production,
        downtimes,
        scraps,
        energy,
        operators,
        orders,
        legacy,
        mold_changes,
        materials
    )

app = FastAPI(
    title="Výrobní Dashboard - MES & SCADA",
    description="Sjednocený výrobní portál pro sledování OEE, prostojů, zmetků, energetiky, SAP zakázek a polyvalence operátorů.",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrace routerů
app.include_router(filters.router)
app.include_router(production.router)
app.include_router(downtimes.router)
app.include_router(scraps.router)
app.include_router(energy.router)
app.include_router(operators.router)
app.include_router(orders.router)
app.include_router(legacy.router)
app.include_router(mold_changes.router)
app.include_router(materials.router)

# Cesty k frontendu
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "frontend"))
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")

if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return "<h1>Chyba: index.html nebyl nalezen.</h1>"

@app.get("/energy", response_class=HTMLResponse)
def read_energy():
    energy_path = os.path.join(FRONTEND_DIR, "energy.html")
    if os.path.exists(energy_path):
        with open(energy_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return "<h1>Chyba: energy.html nebyl nalezen.</h1>"

@app.get("/polyvalence", response_class=HTMLResponse)
def read_polyvalence():
    poly_path = os.path.join(FRONTEND_DIR, "polyvalence.html")
    if os.path.exists(poly_path):
        with open(poly_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return "<h1>Chyba: polyvalence.html nebyl nalezen.</h1>"

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Vyrobni Dashboard v2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
