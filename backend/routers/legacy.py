from fastapi import APIRouter
import pandas as pd

try:
    from ..database import get_db_connection
except (ImportError, ValueError):
    from database import get_db_connection

router = APIRouter(prefix="/api", tags=["Legacy Compatibility"])

@router.get("/prostoje")
def get_prostoje_legacy():
    """Legacy endpoint preserved from earlier Flask/app.py iterations."""
    try:
        conn = get_db_connection("SAVEPRO")
        query = """
            SELECT TOP 100
                o.CODE_OF AS VyrobniPrikaz,
                a.DATE_DEBUT AS ZacatekProstoje,
                a.DATE_FIN AS KonecProstoje,
                a.DUREE AS Trvani,
                ar.MOTIF_ARRET AS DuvodProstoje
            FROM SAVEPRO.dbo.RESULT_SAISIE_ARRETS a
            LEFT JOIN SAVEPRO.dbo.RESULT_OF o ON a.ID_OF = o.ID
            LEFT JOIN SAVEPRO.dbo.RESULT_ARRET_OF ar ON a.ID_ARRET = ar.ID
            ORDER BY a.DATE_DEBUT DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}
