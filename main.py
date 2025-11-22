import asyncio

from models import AgentState
from llm_cities import get_candidate_cities_from_llm
from mcp_client import get_map_data_from_mcp
from map_service import MapService
from utils import get_workdays
from workflow import build_workflow


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    # otázka áno/nie z konzoly
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "áno", "ano")


def _ask_int(prompt: str, default: int) -> int:
    #Spýta sa na celé číslo, pri Enter / chybe vráti default
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Neplatné číslo, používam pôvodnú hodnotu {default}.")
        return default


def _ask_str(prompt: str, default: str) -> str:
    #Spýta sa na string, pri Enter vráti default
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def main():
    print("=== AI AGENT LOGBOOK (OpenAI + MCP Cyklus) ===")

    # Preddefinované vstupy (fallback / default)
    inputs: AgentState = {
        "start_city": "Vrbové",
        "start_odo": 125654,
        "end_odo": 127243,
        "month": 11,
        "year": 2025,
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

    #  Ručné zadanie vstupov
    if _ask_yes_no("Chceš zadať vstupné hodnoty ručne?", default=False):
        print("\nZadaj hodnoty (alebo stlač Enter pre ponechanie defaultu):")
        inputs["start_city"] = _ask_str("Východzie mesto", inputs["start_city"])
        inputs["start_odo"] = _ask_int("Počiatočný stav tachometra (start_odo)", inputs["start_odo"])
        inputs["end_odo"] = _ask_int("Konečný stav tachometra (end_odo)", inputs["end_odo"])
        inputs["month"] = _ask_int("Mesiac (1-12)", inputs["month"])
        inputs["year"] = _ask_int("Rok", inputs["year"])
        print("Vstupy nastavené.\n")
    else:
        print("Používam preddefinované vstupné hodnoty.\n")

    # 1. Vypočítame pracovné dni a cieľové km
    inputs["workdays"] = get_workdays(inputs["year"], inputs["month"])
    inputs["target_km"] = inputs["end_odo"] - inputs["start_odo"]
    print(f"Cieľová vzdialenosť (target_km): {inputs['target_km']} km")
    print(f"Počet pracovných dní: {len(inputs['workdays'])}")

    # 2. Získame mestá z LLM a mapové dáta z MCP
    city_map = None
    try:
        candidate_cities = get_candidate_cities_from_llm(inputs["start_city"])
        city_map = asyncio.run(get_map_data_from_mcp(inputs["start_city"], candidate_cities))
    except Exception as e:
        print(f"VAROVANIE: Nepodarilo sa použiť MCP/LLM mapové dáta: {e}")
        print("Prechádzam na statické fallback hodnoty.")

    # 3. Inicializujeme MapService (dynamicky alebo fallback)
    map_tool = MapService(city_map)
    inputs["available_destinations"] = map_tool.get_destinations(inputs["start_city"])

    # 4. Build workflow a spustenie agenta
    app = build_workflow()

    try:
        result = app.invoke(inputs)
        #for key, value in result.items(): print(f"{key}: {value}")

        file_name_csv = "kniha_jazd_ai_"+str(result["month"])+"_"+str(result["year"])+".csv"
        file_name_xlsx = "kniha_jazd_ai_"+str(result["month"])+"_"+str(result["year"])+".xlsx"

        print("\n=== VÝSTUP (CSV) ===")
        print(result["final_csv"])

        print("\n=== CSV súbor ===")
        with open(file_name_csv, "w", encoding="utf-8") as f:
            f.write(result["final_csv"])
        print(f'CSV uložené do "{file_name_csv}".')

        print("\n=== XLSX súbor  ===")
        with open(file_name_xlsx, "wb") as f:
            f.write(result["final_xlsx_bytes"])
        print(f'Uložené do "{file_name_xlsx}".')

    except Exception as e:
        print(f"Chyba pri spúšťaní agenta: {e}")
        print("Skontroluj nastavenie OPENAI_API_KEY v .env súbore.")


if __name__ == "__main__":
    main()
