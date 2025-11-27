# dbcache.py
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import json

DB_PATH = Path(__file__).resolve().parent / "distances.db"


def init_db() -> None:
    """
    Vytvorí tabuľku, ak ešte neexistuje.
    Ukladá celú štruktúru z MCP (driving_time_* + distance_* + raw_json).
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS city_distances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city1 TEXT NOT NULL,
                city2 TEXT NOT NULL,
                driving_time_seconds INTEGER NOT NULL,
                driving_time_human TEXT NOT NULL,
                distance_km_road REAL NOT NULL,
                distance_km_air REAL NOT NULL,
                raw_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(city1, city2)
            );
            """
        )
        conn.commit()


def _norm(name: str) -> str:
    return name.strip()


def get_mcp_record(city1: str, city2: str) -> Optional[Dict[str, Any]]:
    """
    Vráti celú štruktúru podobnú MCP JSON:

    {
        "city1": ...,
        "city2": ...,
        "driving_time_seconds": ...,
        "driving_time_human": ...,
        "distance_km_road": ...,
        "distance_km_air": ...,
        "raw_json": "pôvodný JSON string"
    }
    """
    c1 = _norm(city1)
    c2 = _norm(city2)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT city1,
                   city2,
                   driving_time_seconds,
                   driving_time_human,
                   distance_km_road,
                   distance_km_air,
                   raw_json
            FROM city_distances
            WHERE (city1 = ? AND city2 = ?)
               OR (city1 = ? AND city2 = ?)
            """,
            (c1, c2, c2, c1),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "city1": row[0],
        "city2": row[1],
        "driving_time_seconds": int(row[2]),
        "driving_time_human": row[3],
        "distance_km_road": float(row[4]),
        "distance_km_air": float(row[5]),
        "raw_json": row[6],
    }


def get_distance_from_db(city1: str, city2: str) -> Optional[Tuple[float, int]]:
    """
    BACKWARD-COMPAT: pôvodné rozhranie, ktoré očakáva mcp_client.
    Vráti (distance_km_road, duration_min) alebo None.
    """
    rec = get_mcp_record(city1, city2)
    if not rec:
        return None
    dist = float(rec["distance_km_road"])
    duration_min = int(rec["driving_time_seconds"] // 60)
    return dist, duration_min


def save_mcp_record(data: Dict[str, Any]) -> None:
    """
    Uloží MCP výsledok do DB (INSERT OR IGNORE).

    Očakáva dict s kľúčmi:
      city1, city2, driving_time_seconds, driving_time_human,
      distance_km_road, distance_km_air
    """
    c1 = _norm(str(data["city1"]))
    c2 = _norm(str(data["city2"]))

    driving_time_seconds = int(data["driving_time_seconds"])
    driving_time_human = str(data.get("driving_time_human", ""))
    distance_km_road = float(data["distance_km_road"])
    distance_km_air = float(data.get("distance_km_air", 0.0))

    raw_json = json.dumps(data, ensure_ascii=False)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO city_distances (
                city1,
                city2,
                driving_time_seconds,
                driving_time_human,
                distance_km_road,
                distance_km_air,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c1,
                c2,
                driving_time_seconds,
                driving_time_human,
                distance_km_road,
                distance_km_air,
                raw_json,
            ),
        )
        conn.commit()
