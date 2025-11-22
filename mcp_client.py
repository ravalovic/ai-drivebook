from asyncio import sleep
import json
from typing import Dict, List, Tuple

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from config import SERVER_PARAMS


async def get_map_data_from_mcp(start_city: str, candidate_cities: List[str]) -> Dict[str, Tuple[float, int]]:
    """
    Volá MCP tool 'driving_time_between_cities' priamo cez MCP clienta,
    nie cez HTTP. Pre každé mesto v candidate_cities sa vykoná  MCP tool call.

    MCP result.content[0].text je JSON string:
    {
        "city1": "Vrbové",
        "city2": "Bratislava",
        "driving_time_seconds": 3951,
        "driving_time_human": "1 h 6 min",
        "distance_km_road": 92.52,
        "distance_km_air": 69.12
    }
    """
    print("--- MCP: PRIAME VOLANIE driving_time_between_cities (per-city) ---")

    city_map: Dict[str, Tuple[float, int]] = {}

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Available MCP services:", [t.name for t in tools.tools])

            for dest_city in candidate_cities:
                print(f"→ MCP call: {start_city} → {dest_city}")
                sleep(2)  
                result = await session.call_tool(
                    "driving_time_between_cities",
                    {
                        "city1": start_city,
                        "city2": dest_city,
                    }
                )
                # MCP call: Vrbové → Martin
                # Haluz roka Martin: 3077.90 km, 1904 min
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

                city_map[dest_city] = (dist_km, duration_min)
                print(f"{dest_city}: {dist_km:.2f} km, {duration_min} min")

    if not city_map:
        raise RuntimeError("MCP nevrátil žiadne trasy.")

    print(f"Finálny city_map z MCP: {city_map}")
    return city_map
