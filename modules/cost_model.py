import pandas as pd


def get_best_route(routes: pd.DataFrame) -> pd.Series:
    """
    Возвращает маршрут с минимальной стоимостью доставки.
    """
    return routes.loc[routes["cost_rub_t"].idxmin()]


def calculate_savings(routes: pd.DataFrame, best_route: pd.Series) -> dict:
    """
    Считает экономию оптимального маршрута относительно
    самого дорогого варианта, прямой автодоставки и прямой Ж/Д доставки.
    """
    best_cost = best_route["cost_rub_t"]

    max_cost = routes["cost_rub_t"].max()
    max_saving = max_cost - best_cost
    max_saving_percent = max_saving / max_cost * 100

    auto_direct = routes[
        routes["route_type"].str.contains("Авто напрямую", case=False, na=False)
    ]

    rail_direct = routes[
        routes["route_type"].str.contains("Ж/Д напрямую", case=False, na=False)
    ]

    auto_saving = None
    auto_saving_percent = None
    rail_saving = None
    rail_saving_percent = None

    if not auto_direct.empty:
        auto_cost = auto_direct.iloc[0]["cost_rub_t"]
        auto_saving = auto_cost - best_cost
        auto_saving_percent = auto_saving / auto_cost * 100

    if not rail_direct.empty:
        rail_cost = rail_direct.iloc[0]["cost_rub_t"]
        rail_saving = rail_cost - best_cost
        rail_saving_percent = rail_saving / rail_cost * 100

    return {
        "max_saving": round(max_saving, 2),
        "max_saving_percent": round(max_saving_percent, 2),
        "auto_saving": round(auto_saving, 2) if auto_saving is not None else None,
        "auto_saving_percent": round(auto_saving_percent, 2) if auto_saving_percent is not None else None,
        "rail_saving": round(rail_saving, 2) if rail_saving is not None else None,
        "rail_saving_percent": round(rail_saving_percent, 2) if rail_saving_percent is not None else None,
    }


def add_cost_difference(routes: pd.DataFrame, best_route: pd.Series) -> pd.DataFrame:
    """
    Добавляет к таблице разницу относительно лучшего маршрута.
    """
    result = routes.copy()

    result["cost_rub_t"] = result["cost_rub_t"].astype(float)
    best_cost = float(best_route["cost_rub_t"])

    result["difference_from_best_rub_t"] = (
        result["cost_rub_t"] - best_cost
    ).round(2)

    result["difference_from_best_percent"] = (
        result["difference_from_best_rub_t"] / result["cost_rub_t"] * 100
    ).round(2)

    return result
def apply_scenario(routes: pd.DataFrame, rail_change: float, auto_change: float, river_change: float) -> pd.DataFrame:
    """
    Применяет сценарные коэффициенты к стоимости маршрутов.

    rail_change — изменение стоимости Ж/Д составляющей, %
    auto_change — изменение стоимости автомобильной составляющей, %
    river_change — изменение стоимости речной составляющей, %
    """
    result = routes.copy()

    # ВАЖНО: переводим числовые колонки в float,
    # чтобы можно было записывать значения типа 2514.6
    result["cost_rub_t"] = result["cost_rub_t"].astype(float)

    if "base_cost_rub_t" not in result.columns:
        result["base_cost_rub_t"] = result["cost_rub_t"].astype(float)
    else:
        result["base_cost_rub_t"] = result["base_cost_rub_t"].astype(float)

    for index, row in result.iterrows():
        route_type = str(row["route_type"])
        cost = float(row["base_cost_rub_t"])

        if "Ж/Д" in route_type:
            cost = cost * (1 + rail_change / 100)

        if "Авто" in route_type:
            cost = cost * (1 + auto_change / 100)

        if "речной терминал" in route_type or "речное судно" in route_type:
            cost = cost * (1 + river_change / 100)

        result.loc[index, "cost_rub_t"] = float(round(cost, 2))

    return result
def generate_conclusion(
    selected_region: str,
    selected_port: str,
    best_route: pd.Series,
    savings: dict,
    rail_change: float,
    auto_change: float,
    river_change: float
) -> str:
    """
    Формирует текстовый аналитический вывод по выбранному сценарию.
    """
    route_type = best_route["route_type"]
    cost = best_route["cost_rub_t"]

    conclusion = (
        f"Для направления «{selected_region} — {selected_port}» "
        f"при заданных параметрах сценария оптимальным является маршрут "
        f"«{route_type}» со стоимостью {cost} руб./т. "
    )

    conclusion += (
        f"В рассматриваемом сценарии изменение Ж/Д тарифа составляет {rail_change}%, "
        f"изменение автотарифа — {auto_change}%, "
        f"изменение речной составляющей — {river_change}%. "
    )

    if savings["max_saving"] > 0:
        conclusion += (
            f"Экономия относительно наиболее дорогого варианта составляет "
            f"{savings['max_saving']} руб./т, или {savings['max_saving_percent']}%. "
        )

    if savings["auto_saving"] is not None:
        if savings["auto_saving"] > 0:
            conclusion += (
                f"По сравнению с прямой автомобильной доставкой выбранный вариант "
                f"дешевле на {savings['auto_saving']} руб./т "
                f"({savings['auto_saving_percent']}%). "
            )
        elif savings["auto_saving"] == 0:
            conclusion += (
                "Выбранный вариант совпадает с прямой автомобильной доставкой, "
                "поэтому экономия относительно нее отсутствует. "
            )
        else:
            conclusion += (
                f"По сравнению с прямой автомобильной доставкой выбранный вариант "
                f"дороже на {abs(savings['auto_saving'])} руб./т. "
            )

    if savings["rail_saving"] is not None:
        if savings["rail_saving"] > 0:
            conclusion += (
                f"По сравнению с прямой железнодорожной доставкой выбранный вариант "
                f"дешевле на {savings['rail_saving']} руб./т "
                f"({savings['rail_saving_percent']}%). "
            )
        elif savings["rail_saving"] == 0:
            conclusion += (
                "Выбранный вариант совпадает с прямой железнодорожной доставкой, "
                "поэтому экономия относительно нее отсутствует. "
            )
        else:
            conclusion += (
                f"По сравнению с прямой железнодорожной доставкой выбранный вариант "
                f"дороже на {abs(savings['rail_saving'])} руб./т. "
            )

    return conclusion