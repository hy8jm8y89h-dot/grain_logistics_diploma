import pandas as pd


def get_available_destinations(
    destinations: pd.DataFrame,
    selected_port: str
) -> list:
    """
    Возвращает зарубежные направления, доступные из выбранного российского порта.
    """
    filtered = destinations[destinations["base_port"] == selected_port]

    return sorted(filtered["destination"].unique())


def calculate_international_route(
    best_route: pd.Series,
    destinations: pd.DataFrame,
    selected_destination: str
) -> dict:
    """
    Рассчитывает итоговую стоимость маршрута с учетом зарубежного направления.
    """
    selected = destinations[
        destinations["destination"] == selected_destination
    ]

    if selected.empty:
        return {
            "destination": selected_destination,
            "country": "Нет данных",
            "base_port": "",
            "domestic_cost": float(best_route["cost_rub_t"]),
            "extra_cost": 0,
            "total_cost": float(best_route["cost_rub_t"]),
            "distance_km": 0,
            "risk_factor": 1
        }

    row = selected.iloc[0]

    domestic_cost = float(best_route["cost_rub_t"])
    extra_cost = float(row["extra_cost_rub_t"])
    risk_factor = float(row["risk_factor"])

    adjusted_extra_cost = extra_cost * risk_factor
    total_cost = domestic_cost + adjusted_extra_cost

    return {
        "destination": row["destination"],
        "country": row["country"],
        "base_port": row["base_port"],
        "domestic_cost": round(domestic_cost, 2),
        "extra_cost": round(adjusted_extra_cost, 2),
        "total_cost": round(total_cost, 2),
        "distance_km": row["distance_km"],
        "risk_factor": risk_factor
    }


def generate_destination_conclusion(
    selected_region: str,
    selected_port: str,
    international_result: dict
) -> str:
    """
    Формирует текстовый вывод по международному направлению.
    """
    return (
        f"Для экспортного направления «{selected_region} — {selected_port} — "
        f"{international_result['destination']} ({international_result['country']})» "
        f"ориентировочная стоимость доставки составляет "
        f"{international_result['total_cost']} руб./т. "
        f"Из них внутрироссийская часть маршрута составляет "
        f"{international_result['domestic_cost']} руб./т, "
        f"международная составляющая с учетом коэффициента риска — "
        f"{international_result['extra_cost']} руб./т. "
        f"Расчетная дальность международного участка составляет "
        f"{international_result['distance_km']} км."
    )