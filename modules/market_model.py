def calculate_market_risk(
    usd_rate: float,
    grain_price: float,
    fuel_change: float,
    port_congestion: float,
    news_risk: float
) -> dict:
    """
    Рассчитывает интегральный индекс рыночного риска для экспортной логистики зерна.

    usd_rate — курс доллара, руб.
    grain_price — мировая цена зерна, долл./т
    fuel_change — изменение стоимости топлива, %
    port_congestion — загруженность морских портов, %
    news_risk — экспертная оценка новостного риска, 0-100
    """

    risk_score = 0

    # Курс валюты
    if usd_rate < 80:
        risk_score += 5
    elif usd_rate < 95:
        risk_score += 10
    elif usd_rate < 110:
        risk_score += 18
    else:
        risk_score += 25

    # Мировая цена зерна
    # Высокая цена повышает привлекательность экспорта,
    # но может усиливать нагрузку на транспортную систему.
    if grain_price < 180:
        risk_score += 20
    elif grain_price < 230:
        risk_score += 12
    elif grain_price < 280:
        risk_score += 8
    else:
        risk_score += 14

    # Топливо
    if fuel_change < 0:
        risk_score += 3
    elif fuel_change < 10:
        risk_score += 8
    elif fuel_change < 25:
        risk_score += 15
    else:
        risk_score += 22

    # Загруженность портов
    if port_congestion < 50:
        risk_score += 5
    elif port_congestion < 75:
        risk_score += 12
    elif port_congestion < 90:
        risk_score += 20
    else:
        risk_score += 28

    # Новостной риск
    risk_score += news_risk * 0.25

    risk_score = round(min(risk_score, 100), 1)

    if risk_score < 35:
        status = "Низкий риск"
        recommendation = (
            "Рыночная ситуация относительно стабильна. "
            "Можно использовать базовый оптимальный маршрут, выбранный системой."
        )
    elif risk_score < 65:
        status = "Умеренный риск"
        recommendation = (
            "Ситуация требует контроля. Рекомендуется сравнить базовый маршрут "
            "с альтернативными схемами и учитывать возможность роста тарифов."
        )
    else:
        status = "Высокий риск"
        recommendation = (
            "Рыночная и инфраструктурная ситуация нестабильна. "
            "Рекомендуется использовать сценарный анализ, резервные маршруты "
            "и проверять загрузку портов и терминалов перед принятием решения."
        )

    return {
        "risk_score": risk_score,
        "status": status,
        "recommendation": recommendation
    }


def generate_market_text(
    usd_rate: float,
    grain_price: float,
    fuel_change: float,
    port_congestion: float,
    news_risk: float,
    risk_result: dict
) -> str:
    """
    Формирует текстовый вывод по внешним факторам.
    """

    return (
        f"При курсе доллара {usd_rate} руб., мировой цене зерна {grain_price} долл./т, "
        f"изменении стоимости топлива на {fuel_change}%, загруженности морских портов "
        f"{port_congestion}% и новостном риске {news_risk} баллов система оценивает "
        f"интегральный уровень риска как «{risk_result['status']}». "
        f"Индекс риска составляет {risk_result['risk_score']} из 100. "
        f"{risk_result['recommendation']}"
    )
def convert_risk_to_tariff_adjustments(risk_score: float) -> dict:
    """
    Преобразует индекс рыночного риска в дополнительные тарифные поправки.

    Логика:
    - при низком риске влияние на тарифы минимальное;
    - при умеренном риске растут авто- и Ж/Д тарифы;
    - при высоком риске сильнее растут автотарифы и стоимость речной составляющей
      из-за возможной перегрузки портов, ожидания судов и роста фрахта.
    """

    if risk_score < 35:
        return {
            "rail_risk_add": 2,
            "auto_risk_add": 3,
            "river_risk_add": 2
        }

    if risk_score < 65:
        return {
            "rail_risk_add": 6,
            "auto_risk_add": 10,
            "river_risk_add": 7
        }

    return {
        "rail_risk_add": 12,
        "auto_risk_add": 18,
        "river_risk_add": 15
    }