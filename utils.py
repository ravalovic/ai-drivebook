import datetime
import pandas as pd
from typing import List


def get_workdays(year: int, month: int) -> List[str]:
    """Vráti ISO dátumy pracovných dní v danom mesiaci."""
    num_days = pd.Period(f"{year}-{month}").days_in_month
    dates: List[str] = []
    for day in range(1, num_days + 1):
        d = datetime.date(year, month, day)
        if d.weekday() < 5:  # 0-4 = pondelok-piatok
            dates.append(d.isoformat())
    return dates
