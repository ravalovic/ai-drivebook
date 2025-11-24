# service.py
import io
from typing import Tuple

import pandas as pd

from models import AgentState
from llm_cities import get_candidate_cities_from_llm
from mcp_client import get_map_data_from_mcp
from map_service import MapService
from utils import get_workdays
from workflow import build_workflow


async def run_logbook(
    start_city: str,
    start_odo: int,
    end_odo: int,
    month: int,
    year: int,
) -> Tuple[pd.DataFrame, str, bytes]:
    """
    Spustí celý workflow a vráti:
      - DataFrame s výsledkami
      - CSV obsah (string)
      - XLSX obsah (bytes)

    Je ASYNC, takže sa volá z FastAPI endpointu ako:
        df, csv_str, xlsx_bytes = await run_logbook(...)
    """

    # --- 1. Príprava vstupného stavu pre LangGraph agent ---
    inputs: AgentState = {
        "start_city": start_city,
        "start_odo": start_odo,
        "end_odo": end_odo,
        "month": month,
        "year": year,
        "workdays": [],
        "available_destinations": [],
        "ai_trip_plan": [],
        "final_csv": "",
        "retry_count": 1,
        "feedback_message": "",
        "max_retries": 3,
        "next_step": "ai_planner",
        "target_km": 0,
        "final_sum_km": 0.0,
    }

    # pracovné dni & cieľové km
    inputs["workdays"] = get_workdays(year, month)
    inputs["target_km"] = end_odo - start_odo
    print(f"[service] target_km = {inputs['target_km']} km")

    # --- 2. LLM kandidátske mestá + MCP mapové dáta ---
    city_map = None
    try:
        # LLM výber miest – sync volanie OpenAI
        candidate_cities = get_candidate_cities_from_llm(start_city)

        # MCP volanie – async, preto await
        city_map = await get_map_data_from_mcp(start_city, candidate_cities)
    except Exception as e:
        print(f"[service] VAROVANIE: MCP/LLM zlyhalo: {e}")
        print("[service] Použijem statické fallback mapové dáta.")

    # --- 3. MapService + LangGraph workflow ---
    map_tool = MapService(city_map)
    inputs["available_destinations"] = map_tool.get_destinations(start_city)

    app = build_workflow()
    result = app.invoke(inputs)  # LangGraph je synchronný

    csv_str = result["final_csv"]

    # --- 4. CSV -> DataFrame ---
    df = pd.read_csv(io.StringIO(csv_str), sep=";")

    # --- 5. DataFrame -> XLSX (do pamäte) ---
    xlsx_buffer = io.BytesIO()
    df.to_excel(xlsx_buffer, index=False)
    xlsx_buffer.seek(0)
    xlsx_bytes = xlsx_buffer.getvalue()

    return df, csv_str, xlsx_bytes
