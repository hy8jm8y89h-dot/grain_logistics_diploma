import pandas as pd


def calculate_port_load(ports: pd.DataFrame) -> pd.DataFrame:
    """
    Рассчитывает загрузку морских портов назначения.

    current_volume_thousand_tons — текущий или расчетный объем грузопотока;
    capacity_thousand_tons — расчетная пропускная способность;
    waiting_days — среднее ожидание обработки/перевалки;
    risk_factor — коэффициент внешнего риска.
    """
    result = ports.copy()

    result["base_load_percent"] = (
        result["current_volume_thousand_tons"] /
        result["capacity_thousand_tons"] * 100
    ).round(1)

    result["adjusted_load_percent"] = (
        result["base_load_percent"] * result["risk_factor"] +
        result["waiting_days"] * 2
    ).round(1)

    result["status"] = result["adjusted_load_percent"].apply(get_port_status)

    return result


def get_port_status(load_percent: float) -> str:
    """
    Возвращает статус загрузки морского порта.
    """
    if load_percent < 50:
        return "Низкая загрузка"
    if load_percent < 75:
        return "Нормальная загрузка"
    if load_percent <= 95:
        return "Высокая загрузка"
    return "Риск перегрузки"


def get_selected_port_load(port_load_df: pd.DataFrame, selected_port: str) -> dict:
    """
    Возвращает показатели выбранного порта.
    """
    selected = port_load_df[port_load_df["port"] == selected_port]

    if selected.empty:
        return {
            "port": selected_port,
            "adjusted_load_percent": 0,
            "status": "Нет данных",
            "waiting_days": 0
        }

    row = selected.iloc[0]

    return {
        "port": row["port"],
        "adjusted_load_percent": row["adjusted_load_percent"],
        "status": row["status"],
        "waiting_days": row["waiting_days"]
    }