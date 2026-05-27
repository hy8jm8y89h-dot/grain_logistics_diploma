import pandas as pd
from sklearn.linear_model import LinearRegression


def build_linear_forecast(
    history: pd.DataFrame,
    start_year: int = 2025,
    end_year: int = 2035
) -> pd.DataFrame:
    """
    Строит линейный прогноз объемов перевозок зерна речным транспортом.

    history должен содержать колонки:
    year — год
    volume_thousand_tons — объем перевозок, тыс. т
    """
    model = LinearRegression()

    x = history[["year"]]
    y = history["volume_thousand_tons"]

    model.fit(x, y)

    future_years = pd.DataFrame(
        {"year": list(range(start_year, end_year + 1))}
    )

    future_years["volume_thousand_tons"] = model.predict(future_years[["year"]])
    future_years["volume_thousand_tons"] = future_years["volume_thousand_tons"].round(0)

    future_years["type"] = "Прогноз"

    history_result = history.copy()
    history_result["type"] = "Факт"

    result = pd.concat([history_result, future_years], ignore_index=True)

    return result


def build_target_forecast(
    history: pd.DataFrame,
    target_year: int = 2035,
    target_volume: int = 14000
) -> pd.DataFrame:
    """
    Строит целевой прогноз до заданного объема.

    По умолчанию целевой ориентир — 14 млн т к 2035 году.
    Значение указывается в тыс. т, поэтому 14 млн т = 14000 тыс. т.
    """
    last_year = int(history["year"].max())
    last_volume = float(history.loc[history["year"] == last_year, "volume_thousand_tons"].iloc[0])

    years = list(range(last_year + 1, target_year + 1))
    steps = target_year - last_year

    annual_growth = (target_volume - last_volume) / steps

    forecast_rows = []

    for index, year in enumerate(years, start=1):
        forecast_rows.append(
            {
                "year": year,
                "volume_thousand_tons": round(last_volume + annual_growth * index, 0),
                "type": "Целевой прогноз"
            }
        )

    history_result = history.copy()
    history_result["type"] = "Факт"

    forecast = pd.DataFrame(forecast_rows)

    result = pd.concat([history_result, forecast], ignore_index=True)

    return result


def calculate_forecast_summary(forecast: pd.DataFrame) -> dict:
    """
    Считает ключевые показатели прогноза.
    """
    first_year = int(forecast["year"].min())
    last_year = int(forecast["year"].max())

    first_volume = float(
        forecast.loc[forecast["year"] == first_year, "volume_thousand_tons"].iloc[0]
    )

    last_volume = float(
        forecast.loc[forecast["year"] == last_year, "volume_thousand_tons"].iloc[0]
    )

    growth_abs = last_volume - first_volume
    growth_percent = growth_abs / first_volume * 100

    return {
        "first_year": first_year,
        "last_year": last_year,
        "first_volume": round(first_volume, 0),
        "last_volume": round(last_volume, 0),
        "growth_abs": round(growth_abs, 0),
        "growth_percent": round(growth_percent, 2),
    }