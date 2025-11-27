# mcp_client.py
import os
import json
from typing import List, Dict, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dbcache import init_db, get_distance_from_db, save_mcp_record


# Inicializácia DB pri importe
init_db()

# MCP server parametre
server_script_path = os.path.join(os.path.dirname(__file__), "mcp", "server.py")
print("Spúšťam MCP server cez STDIO:", server_script_path)

server_params = StdioServerParameters(
    command="python",
    args=[server_script_path],
    env=None,
)


async def get_map_data_from_mcp(start_city: str, candidate_cities: List[str]) -> Dict[str, Tuple[float, int]]:
    """
    1. Skúsi nájsť trasy v lokálnej SQLite DB (city_distances).
    2. Pre chýbajúce mestá zavolá MCP tool `driving_time_between_cities`.
    3. Nové výsledky z MCP uloží celé do DB (save_mcp_record).
    4. Vráti city_map: { city_name: (distance_km_road, duration_min) }.
    """
    print("--- MAP DATA: DB cache + MCP fallback ---")

    city_map: Dict[str, Tuple[float, int]] = {}
    missing: List[str] = []

    # 1) Najprv čítanie z DB cache
    for dest_city in candidate_cities:
        cached = get_distance_from_db(start_city, dest_city)
        if cached:
            dist_km, duration_min = cached
            city_map[dest_city] = (dist_km, duration_min)
            print(f"[DB] {start_city} -> {dest_city}: {dist_km:.2f} km, {duration_min} min")
        else:
            missing.append(dest_city)

    if not missing:
        print("[MAP DATA] Všetky trasy nájdené v DB, MCP sa nevolá.")
        return city_map

    print(f"[MAP DATA] Pre {len(missing)} miest nie sú dáta v DB – volám MCP.")

    # 2) MCP iba pre chýbajúce
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Available MCP services:", [t.name for t in tools.tools])

            for dest_city in missing:
                print(f"→ MCP call: {start_city} → {dest_city}")

                result = await session.call_tool(
                    "driving_time_between_cities",
                    {
                        "city1": start_city,
                        "city2": dest_city,
                    }
                )

                try:
                    raw_json = result.content[0].text
                    data = json.loads(raw_json)
                except Exception as e:
                    print(f"Chyba parsovania výsledku z MCP pre {dest_city}: {e}")
                    continue

                try:
                    dist_km = float(data["distance_km_road"])
                    duration_min = int(data["driving_time_seconds"] // 60)
                except Exception as e:
                    print(f"MCP dáta neúplné pre {dest_city}: {data}  ({e})")
                    continue

                # pridáme do mapy pre ďalšie spracovanie
                city_map[dest_city] = (dist_km, duration_min)
                print(f"[MCP] {dest_city}: {dist_km:.2f} km, {duration_min} min")

                # uložíme CELÝ MCP záznam do DB
                save_mcp_record(data)
                print(f"[DB] Uložené: {data['city1']} ↔ {data['city2']}")

    if not city_map:
        raise RuntimeError("MCP nevrátil žiadne použiteľné trasy ani po cache pokuse.")

    print(f"Finálny city_map (DB + MCP): {city_map}")
    return city_map
