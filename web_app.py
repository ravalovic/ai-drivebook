# web_app.py
from typing import Dict, Any
from uuid import uuid4
import io

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from service import run_logbook

# In-memory storage výsledkov (jednoduché riešenie)
RESULT_STORE: Dict[str, Dict[str, Any]] = {}

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
# templates/ folder pre HTML šablóny
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # default hodnoty do formulára
    default_values = {
        "start_city": "Vrbové",
        "start_odo": 125654,
        "end_odo": 127243,
        "month": 11,
        "year": 2025,
    }
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "defaults": default_values},
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    start_city: str = Form(...),
    start_odo: int = Form(...),
    end_odo: int = Form(...),
    month: int = Form(...),
    year: int = Form(...),
):
    # spustíme backend službu
    df, csv_str, xlsx_bytes, total_km = await run_logbook(
        start_city=start_city,
        start_odo=start_odo,
        end_odo=end_odo,
        month=month,
        year=year,
    )

    # uložíme výsledky do pamäte pod job_id
    job_id = str(uuid4())
    RESULT_STORE[job_id] = {
        "csv": csv_str,
        "xlsx": xlsx_bytes,
        "month": month,
        "year": year,
        "total_km": total_km,
    }



    # premenné pre HTML – tabuľka z df
    table_html = df.to_html(classes="table table-striped", index=False)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "job_id": job_id,
            "table_html": table_html,
            "start_city": start_city,
            "start_odo": start_odo,
            "end_odo": end_odo,
            "month": month,
            "year": year,
            "target_km": end_odo - start_odo,
            "total_km": total_km,
           },
    )


@app.get("/download/csv/{job_id}")
async def download_csv(job_id: str):
    data = RESULT_STORE.get(job_id)
    if not data:
        return HTMLResponse("Neznámy job_id", status_code=404)

    csv_str = data["csv"]
    month = data.get("month", "xx")
    year = data.get("year", "xxxx")

    filename = f"kniha_jazd_ai_{month}_{year}.csv"

    return StreamingResponse(
        io.StringIO(csv_str),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.get("/download/xlsx/{job_id}")
async def download_xlsx(job_id: str):
    data = RESULT_STORE.get(job_id)
    if not data:
        return HTMLResponse("Neznámy job_id", status_code=404)

    xlsx_bytes = data["xlsx"]
    month = data.get("month", "xx")
    year = data.get("year", "xxxx")

    filename = f"kniha_jazd_ai_{month}_{year}.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

