import datetime
import itertools
from io import BytesIO
import math
from typing import List

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from config import MODEL_NAME
from models import AgentState, TripEntry, TripSchedule


# --- AI PLANNER ---

def ai_planner_node(state: AgentState):
    print(f"--- 1. AI PLANNING (Pokus: {state['retry_count']}) ---")

    llm = ChatOpenAI(model=MODEL_NAME, temperature=0.1)

    target = state["target_km"]
    workdays = state["workdays"]
    num_workdays = len(workdays)

    # priemerná vzdialenosť destinácií
    if state["available_destinations"]:
        avg_dist = sum(c["dist"] for c in state["available_destinations"]) / len(state["available_destinations"])
    else:
        avg_dist = 50.0

    min_trips_needed = math.ceil(target / (avg_dist * 2))
    min_trips_needed = max(1, min(min_trips_needed, num_workdays))
    max_trips_allowed = num_workdays  # max jedna jazda na deň

    system_message = f"""
    Si EXPERT na logistiku a plánovanie ciest. Tvojou úlohou je vygenerovať plán jázd
    v JSON formáte podľa schémy TripSchedule.

    DÔLEŽITÉ:
    - Každý TripEntry predstavuje JEDNU služobnú cestu TAM A SPÄŤ v JEDNOM dni.
    - distance_one_way je VZDIALENOSŤ JEDNOSMERNE, takže príspevok do total_km
      pre jednu jazdu je distance_one_way * 2.
    - Políčko day_index je index do zoznamu PRACOVNÉ DNI (0 až {num_workdays - 1}).
    - V JEDEN DEŇ môže byť MAXIMÁLNE JEDNA jazda:
        * všetky hodnoty day_index v plan MUSIA byť unikátne.
    - Rovnaká trasa sa môže opakovať v rôznych dňoch ľubovoľný počet krát.

    CIEĽ:
    1. TOTAL_KM = sum(distance_one_way * 2) má byť čo najbližšie k {target} km,
       ideálne v [TARGET_KM - 50, TARGET_KM + 50].
    2. Počet jázd MUSÍ byť aspoň MIN_TRIPS_NEEDED = {min_trips_needed},
       a NESMIE prekročiť MAX_TRIPS_ALLOWED = {max_trips_allowed}.
    3. Môžeš cieľ mierne PREKROČIŤ (radšej nad ako hlboko pod).
    4. Vzdialenosti môžeš upravovať o ±5 km na každę mesto.
    5. Časy:
       - odchod ráno medzi 06:00–08:00,
       - návrat tak, aby celý výjazd trval > 8 hodín a < ako 13 hodín.
    7. Pridaj krátky popis účelu cesty v poli description (3–6 slov).
        - Pre každú jazdu doplň JSON-pole "description".
        - description musí mať max 6 slov.
        - musí byť všeobecný (bez osobných údajov a názvov firiem).
        - Popis sa má týkať podnikania a IT aktivít.
        - Príklady: "Servis IT infraštruktúry", "Kontrola technického vybavenia", "Obchodné rokovanie o IT", "Konzultácia vývoja softvéru", "Implementácia cloud riešenia", "Analýza bezpečnostných rizík".
    KONTROLA:
    - V reasoning vypíš aj TOTAL_KM_REAL: <súčet distance_one_way * 2>.
    - Skontroluj, že:
        * počet položiek plan je v rozsahu [MIN_TRIPS_NEEDED, MAX_TRIPS_ALLOWED],
        * day_index sú v rozsahu 0..{num_workdays - 1},
        * day_index sú bez duplicít.
    """

    city_distances = "\n".join(
        f"- {city['name']}: {city['dist']:.1f} km "
        f"(Rozsah úpravy: {city['dist'] - 5:.1f} km až {city['dist'] + 5:.1f} km)"
        for city in state["available_destinations"]
    )

    human_input = f"""
    {state['feedback_message']}

    TARGET_KM: {target}
    MIN_TRIPS_NEEDED: {min_trips_needed}
    MAX_TRIPS_ALLOWED: {max_trips_allowed}

    PRACOVNÉ DNI (Indexy 0 - {num_workdays - 1}):
    {workdays}

    DOSTUPNÉ DESTINÁCIE (môžeš ich používať opakovane v rôznych dňoch):
    {city_distances}

    Vygeneruj JSON plán jázd (TripSchedule), ktorý spĺňa tieto pravidlá.
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            ("human", human_input),
        ]
    )

    structured_llm = llm.with_structured_output(TripSchedule)
    chain = prompt | structured_llm
    response: TripSchedule = chain.invoke({})

    planned_km = sum(t.distance_one_way * 2 for t in response.plan)
    print(f"AI Reasoning: {response.reasoning}")
    print(f"AI naplánovala {len(response.plan)} jázd, vypočítaný TOTAL_KM_REAL: {planned_km:.1f} km.")

    return {
        "ai_trip_plan": response.plan,
        "retry_count": state["retry_count"] + 1,
        "feedback_message": "",
        "next_step": "validator",
    }


# --- VALIDATOR ---

def validator_node(state: AgentState):
    """
    Logika:
    - Pod targetom o viac ako 50 km -> späť na AI PLANNER
    - Pod targetom o max 50 km -> FINAL_CORRECTOR (pridá 1 jazdu do 50 km)
    - Nad targetom o max 50 km -> FINAL_CORRECTOR (nič nepridá)
    - Nad targetom o viac ako 50 km -> PY_TRIMMER (odstráni jazdy)
    """

    print(f"--- 2. VALIDÁCIA (Pokus: {state['retry_count'] - 1}) ---")

    trips = state["ai_trip_plan"]
    target = state["target_km"]

    current_km_sum = sum(trip.distance_one_way * 2 for trip in trips)
    diff = current_km_sum - target

    print(f"AI plánované km: {current_km_sum:.2f}, Cieľ: {target}, odchýlka: {diff:+.2f} km")

    if current_km_sum < target:
        deficit = -diff

        if deficit > 50:
            if state["retry_count"] - 1 >= state["max_retries"]:
                print("Maximálny počet pokusov, posielam do FINAL_CORRECTOR (nebude vedieť dorovnať všetko).")
                return {"next_step": "final_corrector", "feedback_message": ""}

            feedback = (
                f"Celkový súčet km ({current_km_sum:.1f}) je o {deficit:.1f} km pod cieľom {target}. "
                "Navrhni NOVÝ plán s viac jazdami alebo dlhšími trasami. "
                "KĽUDNE MÔŽEŠ CIEĽ PREKROČIŤ (je lepšie byť nad cieľom ako pod ním)."
            )
            print("Príliš veľký deficit, vraciam späť na AI_PLANNER.")
            return {"next_step": "ai_planner", "feedback_message": feedback}

        print("Deficit ≤ 50 km -> FINAL_CORRECTOR doplní krátku jazdu.")
        return {"next_step": "final_corrector", "feedback_message": ""}

    else:
        overshoot = diff

        if overshoot > 50:
            print("Prekročenie > 50 km -> PY_TRIMMER odstráni niektoré jazdy.")
            return {"next_step": "py_trimmer", "feedback_message": ""}

        print("Plán je nad targetom, ale v tolerancii ≤ 50 km -> FINAL_CORRECTOR bez úprav.")
        return {"next_step": "final_corrector", "feedback_message": ""}


# --- PYTHON TRIMMER (bez LLM) ---

def py_trimmer_node(state: AgentState):
    """
    PYTHON TRIMMER (nová verzia):
    - bez LLM, iteratívne odstraňuje jazdy
    - cieľ: dostať sa čo najbližšie k targetu
    - preferuje interval [target - 50, target + 50], ale je best-effort
    """

    print("--- 3. PYTHON TRIMMER (odstraňovanie jázd) ---")

    trips = list(state["ai_trip_plan"])  # pracujeme na kópii
    target = state["target_km"]

    def total_km(trip_list):
        return sum(t.distance_one_way * 2 for t in trip_list)

    current_sum = total_km(trips)
    print(f"PYTHON TRIMMER vstupný súčet: {current_sum:.1f} km, cieľ: {target} km")

    # Ak nie sme významne nad targetom, nie je čo trimmovať
    if current_sum <= target + 50:
        print("Súčet nie je významne nad targetom, trimmer nič nemení.")
        return {
            "ai_trip_plan": trips,
            "next_step": "final_corrector",
        }

    # Iteratívne odstraňovanie jázd
    # Budeme hľadať vždy takú jazdu, ktorej odstránenie nás najviac priblíži k targetu.
    while True:
        current_sum = total_km(trips)
        overshoot = current_sum - target

        print(f"  Aktuálny súčet: {current_sum:.1f} km (overshoot: {overshoot:+.1f} km)")

        # Sme v tolerancii? -> hotovo
        if abs(overshoot) <= 50:
            print("  Sme v tolerancii ±50 km, končím trimmovanie.")
            break

        if not trips or overshoot <= 0:
            # už nie je čo odstraňovať alebo sme pod targetom
            print("  Nie je čo odstraňovať alebo už nie sme nad targetom, končím.")
            break

        # Vyberieme najlepšiu jazdu na odstránenie
        best_index = None
        best_new_sum = None
        best_diff = None

        candidates = []
        for idx, trip in enumerate(trips):
            contrib = trip.distance_one_way * 2
            new_sum = current_sum - contrib
            diff = abs(new_sum - target)
            candidates.append((idx, new_sum, diff))

        # Preferujeme kandidátov, kde new_sum >= target - 50 (aby sme nepadli hlboko pod)
        preferred = [c for c in candidates if c[1] >= (target - 50)]
        if not preferred:
            # ak žiadny taký nie je, berieme všetkých – radšej byť výrazne bližšie,
            # aj keby sme spadli trochu pod target - 50
            preferred = candidates

        # vyber najlepší – minimálna odchýlka, pri rovnosti preferujeme súčet nad targetom
        def sort_key(c):
            idx, new_sum, diff = c
            # priorita: 1) menší diff, 2) či je nad targetom, 3) väčší new_sum
            above = 0 if new_sum >= target else 1
            return (diff, above, -new_sum)

        best_index, best_new_sum, best_diff = min(preferred, key=sort_key)

        removed_trip = trips.pop(best_index)
        print(
            f"  Odstraňujem jazdu: deň {removed_trip.day_index}, "
            f"{removed_trip.destination_name}, príspevok {removed_trip.distance_one_way * 2:.1f} km -> "
            f"nový súčet: {best_new_sum:.1f} km (odchýlka: {best_new_sum - target:+.1f} km)"
        )

        # bezpečnostná brzda – keby sa z nejakého dôvodu už nezlepšovala situácia
        if len(trips) == 0:
            print("  Všetky jazdy odstránené, končím.")
            break

    final_sum = total_km(trips)
    print(
        f"PYTHON TRIMMER výsledný súčet: {final_sum:.1f} km "
        f"(odchýlka: {final_sum - target:+.1f} km)"
    )

    return {
        "ai_trip_plan": trips,
        "next_step": "final_corrector",
        "final_distance_km": final_sum,
    }

# --- FINAL CORRECTOR ---

def final_corrector_node(state: AgentState):
    """
    Finálny korektor:
    - Ak je plán nad targetom, nič nepridáva.
    - Ak je plán pod targetom o MAX 50 km, doplní JEDNU servisnú jazdu
      (max 50 km tam+späť = max 25 km one-way).
    """

    print("--- 4. FINÁLNA PYTHON KOREKCIA (jemné doladenie) ---")

    trips = state["ai_trip_plan"]
    target = state["target_km"]
    workdays = state["workdays"]

    current_km_sum = sum(t.distance_one_way * 2 for t in trips)
    diff = current_km_sum - target

    print(f"FINAL_CORRECTOR vstupný súčet: {current_km_sum:.2f} km, "
          f"cieľ: {target}, odchýlka: {diff:+.2f} km")

    if current_km_sum >= target:
        print("Plán je nad alebo presne na targete – nekorigujem, len posúvam ďalej.")
        final_sum = current_km_sum
        return {"ai_trip_plan": trips, "final_sum_km": final_sum, "next_step": "processor"}

    deficit = target - current_km_sum
    if deficit <= 0 or deficit > 50:
        print("Deficit mimo 0–50 km – nekorigujem nič, len posúvam ďalej.")
        final_sum = current_km_sum
        return {"ai_trip_plan": trips, "final_sum_km": final_sum, "next_step": "processor"}

    one_way_dist = min(deficit / 2, 25.0)

    if workdays:
        day_index_for_fill = len(workdays) - 1
    else:
        day_index_for_fill = 0

    trips.append(
        TripEntry(
            day_index=day_index_for_fill,
            destination_name="Servisná Jazda (doladenie)",
            distance_one_way=round(one_way_dist, 1),
            departure_time="14:00",
            return_departure_time="15:00",
            description="Administratíva/rokovania"
        )
    )

    final_sum = sum(t.distance_one_way * 2 for t in trips)
    print(f"Pridaná servisná jazda {one_way_dist:.1f} km (one-way). "
          f"Nový súčet: {final_sum:.2f} km (odchýlka: {final_sum - target:+.2f} km).")

    return {"ai_trip_plan": trips, "final_sum_km": final_sum, "next_step": "processor", "final_distance_km": final_sum}


# --- PROCESSOR ---

def processor_node(state: AgentState):
    """
    Spracuje AI výstup, prepočíta tachometer a vytvorí CSV.
    """
    print("--- 5. PROCESSING & FORMATTING ---")

    trips = state["ai_trip_plan"]
    workdays = state["workdays"]
    current_odo = state["start_odo"]

    trips.sort(key=lambda x: x.day_index)

    data_rows = []
    total_dist_check = 0.0

    for trip in trips:
        if trip.day_index >= len(workdays):
            continue

        date_str = workdays[trip.day_index]

        # tu trvanie nevyužívaš na nič kritické, tak 60 min fallback OK
        duration_mins = 60

        dep_time_obj = datetime.datetime.strptime(trip.departure_time, "%H:%M")
        ret_dep_time_obj = datetime.datetime.strptime(trip.return_departure_time, "%H:%M")

        arr_time_obj = dep_time_obj + datetime.timedelta(minutes=duration_mins)
        ret_arr_time_obj = ret_dep_time_obj + datetime.timedelta(minutes=duration_mins)

        dist_one_way = trip.distance_one_way
        current_odo += dist_one_way
        data_rows.append(
            {
                "Dátum": date_str,
                "Odchod Miesto": state["start_city"],
                "Odchod Čas": trip.departure_time,
                "Cieľ Miesto": trip.destination_name,
                "Príchod Čas": arr_time_obj.strftime("%H:%M"),
                "Popis Cesty": trip.description,
                "Stav Tachometra": int(current_odo),
                "Km Jazda": dist_one_way,
            }
        )
        
        current_odo += dist_one_way
        data_rows.append(
            {
                "Dátum": date_str,
                "Odchod Miesto": trip.destination_name,
                "Odchod Čas": trip.return_departure_time,
                "Cieľ Miesto": state["start_city"],
                "Príchod Čas": ret_arr_time_obj.strftime("%H:%M"),
                "Popis Cesty": trip.description,
                "Stav Tachometra": int(current_odo),
                "Km Jazda": dist_one_way,
            }
        )
        
        total_dist_check += dist_one_way * 2

    df = pd.DataFrame(data_rows)
    csv_output = df.to_csv(sep=";", index=False)
    
    #XLSX vystup 
    # Explicitné to_excel do pamäte
    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Jazdy")
    buffer.seek(0)
    xlsx_bytes = buffer.getvalue()


    print(f"Skontrolovaný súčet km: {total_dist_check:.2f}")

    return {
        "final_csv": csv_output, 
        "final_xlsx_bytes": xlsx_bytes,
    }


# --- ROUTE PLANNER PRE LANGGRAPH ---

def route_planner(state: AgentState) -> str:
    return state["next_step"]
