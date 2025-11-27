from typing import List, Dict
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class TripEntry(BaseModel):
    day_index: int = Field(description="Index dňa v zozname pracovných dní (0 až N)")
    destination_name: str = Field(description="Názov cieľového mesta")
    distance_one_way: float = Field(description="Vzdialenosť tam v km")
    departure_time: str = Field(description="Čas odchodu (HH:MM) medzi 06:00-08:00")
    return_departure_time: str = Field(
        description="Čas odchodu späť (HH:MM), tak aby celkový čas bol >8h"
    )
    description: str = Field(description="Stručný 3–6-slovný popis pracovnej aktivity súvisiacej s podnikaním a IT.")


class TripSchedule(BaseModel):
    plan: List[TripEntry] = Field(description="Zoznam jázd pre daný mesiac")
    reasoning: str = Field(
        description="Krátke vysvetlenie, ako sa model snažil trafiť cieľové kilometre"
    )


class CityList(BaseModel):
    cities: List[str] = Field(
        description="Zoznam maximálne 10 miest nad 5000 obyvateľov v okruhu 300 km od východzieho mesta"
    )


class AgentState(TypedDict):
    # Vstupy
    start_city: str
    start_odo: int
    end_odo: int
    target_km: int
    month: int
    year: int

    # Interná logika
    workdays: List[str]              # ISO dátumy pracovných dní
    available_destinations: List[Dict]  # Mestá s dist/dur
    #Vypocitana vzdialenost celkova
    final_distance_km: float
    
    # Riadenie cyklu
    retry_count: int
    feedback_message: str
    max_retries: int
    next_step: str
    final_sum_km: float

    # AI output
    ai_trip_plan: List[TripEntry]

    # Finálny output
    final_csv: str
    final_xlsx_bytes: bytes
