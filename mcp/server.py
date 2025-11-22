#!/usr/bin/env python3
"""
MCP server: výpočet času jazdy autom a vzdialenosti medzi dvomi mestami.

Režim:
  - spúšťa sa cez mcp.run()  -> STDIO/SSE transport (žiadny HTTP port)
  - vhodné na použitie z LangChain / ChatGPT MCP
  - logovanie  na stdout
"""

import json
import traceback
import sys
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests

# --------------------------------------------------------------------
# ZÁKLADNÁ CONFIG
# --------------------------------------------------------------------
DEBUG = False
SERVER_NAME = "distance-driving-server"
OSRM_URL_TEMPLATE = (
    "http://router.project-osrm.org/route/v1/driving/"
    "{lon1},{lat1};{lon2},{lat2}?overview=false"
)

# --------------------------------------------------------------------
# Pomocná funkcia na logovanie
# --------------------------------------------------------------------


def log(msg: str) -> None:
    if DEBUG:
        """Logovanie na STDERR, aby sme nerozbili MCP JSON-RPC na STDOUT."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {msg}", file=sys.stderr, flush=True)


log("====================================================")
log(f"Inicializujem MCP server: {SERVER_NAME}")
log("====================================================")

# --------------------------------------------------------------------
# Inicializácia MCP a geokodéra
# --------------------------------------------------------------------

mcp = FastMCP(SERVER_NAME)

log("Inicializujem Nominatim geocoder…")
geolocator = Nominatim(user_agent=f"{SERVER_NAME}-geocoder")
log("Nominatim geocoder inicializovaný.")


# --------------------------------------------------------------------
# Helper 
# --------------------------------------------------------------------
def geocode_city(city: str):
    #Prevedie názov mesta na (lat, lon)
    log(f"[GEOCODE] Geocoding mesta: {city!r}")
    loc = geolocator.geocode(city)
    if not loc:
        raise ValueError(f"Nepodarilo sa geokódovať mesto: {city}")
    log(f"[GEOCODE] {city!r} → ({loc.latitude}, {loc.longitude})")
    return (loc.latitude, loc.longitude)


def get_driving_stats(coord1, coord2):
    """
    Vráti (duration_seconds, distance_km_road) z OSRM
    - duration_seconds: čas jazdy autom v sekundách
    - distance_km_road: dĺžka trasy po ceste v km
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    url = OSRM_URL_TEMPLATE.format(
        lon1=lon1, lat1=lat1,
        lon2=lon2, lat2=lat2,
    )

    log(f"[OSRM] Volám OSRM: {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if "routes" not in data or not data["routes"]:
        raise ValueError("OSRM nenašiel žiadnu trasu.")

    route = data["routes"][0]
    duration = route["duration"]  # sekundy
    distance_m = route["distance"]  # metre
    distance_km = round(distance_m / 1000.0,1)

    log(
        f"[OSRM] OK – duration={duration:.1f} s, "
        f"distance={distance_km:.1f} km"
    )

    return duration, distance_km


def format_duration(seconds: float) -> str:
    # Textový formát trvania (napr. '4 h 12 min')
    total_minutes = int(round(seconds / 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


# --------------------------------------------------------------------
# MCP TOOL
# --------------------------------------------------------------------


@mcp.tool()
def driving_time_between_cities(city1: str, city2: str) -> dict:
    """
    Vypočíta čas jazdy autom a vzdialenosť medzi dvomi mestami.

    Args:
        city1: Názov prvého mesta (napr. 'Bratislava')
        city2: Názov druhého mesta (napr. 'Praha')

    Returns:
        dict:
            {
              "city1": ...,
              "city2": ...,
              "driving_time_seconds": int,
              "driving_time_human": str,
              "distance_km_road": float,
              "distance_km_air": float
            }
        alebo:
            {"error": "popis chyby"}
    """
    log("----------------------------------------------------")
    log(
        f"[TOOL CALL] driving_time_between_cities("
        f"{city1!r}, {city2!r})"
    )
    log("----------------------------------------------------")

    try:
        # Geokódovanie miest
        coord1 = geocode_city(city1)
        coord2 = geocode_city(city2)

        # Vzdušná vzdialenosť
        km_air = geodesic(coord1, coord2).km
        log(f"[DIST] Vzdušná vzdialenosť: {km_air:.2f} km")

        # Trasa po ceste + čas jazdy
        seconds, km_road = get_driving_stats(coord1, coord2)
        human = format_duration(seconds)

        result = {
            "city1": city1,
            "city2": city2,
            "driving_time_seconds": int(round(seconds)),
            "driving_time_human": human,
            "distance_km_road": round(km_road, 2),
            "distance_km_air": round(km_air, 2),
        }
        log(result)
        log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")
        return result

    except Exception as e:
        log("[ERROR] Výnimka pri spracovaní požiadavky:")
        traceback.print_exc()
        return {"error": str(e)}


# --------------------------------------------------------------------
# ŠTART SERVERA – STDIO / SSE (MCP režim)
# --------------------------------------------------------------------


if __name__ == "__main__":
    log("====================================================")
    log("Štartujem MCP Distance Server v režime mcp.run()")
    log("Tento režim NEOTVÁRA HTTP port.")
    log("Server komunikuje cez STDIO/SSE (MCP protokol).")
    log("Testuje sa cez MCP klienta.")
    log("====================================================")


    mcp.run()

