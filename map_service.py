from typing import Dict, List, Tuple


class MapService:
    def __init__(self, city_map: Dict[str, Tuple[float, int]] | None = None):
        """
        city_map: dict { 'Mesto': (distance_km, duration_min) }
        Ak nie je dodané (alebo MCP zlyhá), použije sa statický fallback.
        """
        if city_map:
            self.mock_db = city_map
        else:
            print("Používam statické fallback mapové dáta.")
            self.mock_db = {
                "Trnava": (52.4, 45),
                "Nitra": (93.2, 65),
                "Trenčín": (128.5, 85),
                "Žilina": (201.3, 120),
                "Brno (CZ)": (135.0, 95),
                "Malacky": (38.1, 40),
                "Senec": (26.5, 30),
                "Piešťany": (85.0, 60),
                "Šamorín": (26.0, 30),
            }

    def get_destinations(self, origin: str) -> List[Dict]:
        #Vráti mestá s ich vzdialenosťami a trvaním
        return [
            {"name": k, "dist": v[0], "dur": v[1]}
            for k, v in self.mock_db.items()
        ]

    def get_precise_route(self, origin: str, destination: str) -> Tuple[float, int]:
        #Vráti vzdialenosť a trvanie pre mesto z db vytvorenej llm.
        dist, dur = self.mock_db.get(destination, (50.0, 50))
        return dist, dur
