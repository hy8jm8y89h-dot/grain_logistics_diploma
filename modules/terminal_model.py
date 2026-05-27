import pandas as pd


def get_terminal_demand_weight(terminal: str, region: str) -> float:
    """
    Возвращает условный коэффициент спроса для терминала.

    Чем выше коэффициент, тем больше грузопотока притягивает терминал.
    В дипломе это можно описать как экспертную оценку с учетом:
    - развитости инфраструктуры;
    - близости к грузовой базе;
    - наличия ж/д и автоподходов;
    - фактической активности терминала.
    """
    terminal_lower = terminal.lower()
    region_lower = region.lower()

    weight = 1.0

    # Крупные активные терминалы
    if any(word in terminal_lower for word in ["тольятти жито", "свияжск", "камышин", "балаково", "азов"]):
        weight += 0.9

    # Крупные речные и портовые узлы
    if any(word in terminal_lower for word in ["волгоград", "саратов", "ульяновск", "нижний новгород", "набережные"]):
        weight += 0.6

    # Терминалы в сильных зерновых регионах
    if any(word in region_lower for word in ["самар", "саратов", "волгоград", "ростов", "татарстан"]):
        weight += 0.4

    # Менее крупные или вспомогательные пункты
    if any(word in terminal_lower for word in ["речной порт", "хлебная база", "кхп"]):
        weight -= 0.1

    return max(weight, 0.5)


def calculate_terminal_load(
    terminals: pd.DataFrame,
    total_volume_thousand_tons: float
) -> pd.DataFrame:
    """
    Распределяет заданный объем перевозок между терминалами неравномерно.

    Используется смешанный индекс:
    - 60% зависит от пропускной способности терминала;
    - 40% зависит от экспертного коэффициента спроса.
    """
    result = terminals.copy()

    result["demand_weight"] = result.apply(
        lambda row: get_terminal_demand_weight(
            terminal=row["terminal"],
            region=row["region"]
        ),
        axis=1
    )

    total_capacity = result["capacity_thousand_tons"].sum()

    result["capacity_share"] = (
        result["capacity_thousand_tons"] / total_capacity
    )

    result["demand_share"] = (
        result["demand_weight"] / result["demand_weight"].sum()
    )

    result["combined_share"] = (
        result["capacity_share"] * 0.6 +
        result["demand_share"] * 0.4
    )

    result["planned_volume_thousand_tons"] = (
        result["combined_share"] * total_volume_thousand_tons
    ).round(1)

    result["load_percent"] = (
        result["planned_volume_thousand_tons"] /
        result["capacity_thousand_tons"] * 100
    ).round(1)

    result["status"] = result["load_percent"].apply(get_load_status)

    return result


def get_load_status(load_percent: float) -> str:
    """
    Возвращает статус загрузки терминала.
    """
    if load_percent < 40:
        return "Низкая загрузка"
    if load_percent < 75:
        return "Нормальная загрузка"
    if load_percent <= 100:
        return "Высокая загрузка"
    return "Перегрузка"


def calculate_terminal_summary(load_table: pd.DataFrame) -> dict:
    """
    Считает сводные показатели по терминалам.
    """
    total_capacity = load_table["capacity_thousand_tons"].sum()
    total_volume = load_table["planned_volume_thousand_tons"].sum()
    average_load = load_table["load_percent"].mean()

    overloaded_count = len(load_table[load_table["load_percent"] > 100])
    high_load_count = len(
        load_table[
            (load_table["load_percent"] >= 75) &
            (load_table["load_percent"] <= 100)
        ]
    )

    return {
        "total_capacity": round(total_capacity, 1),
        "total_volume": round(total_volume, 1),
        "average_load": round(average_load, 1),
        "overloaded_count": overloaded_count,
        "high_load_count": high_load_count,
    }