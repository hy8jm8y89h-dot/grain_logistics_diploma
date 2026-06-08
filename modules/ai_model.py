import streamlit as st
from groq import Groq


def get_groq_api_key() -> str | None:
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return None


def build_ai_prompt(
    selected_region,
    selected_port,
    route_mode,
    selected_destination,
    best_route,
    savings,
    market_risk,
    news_risk,
    selected_port_load,
    forecast_summary,
    terminal_summary,
    effective_rail_change,
    effective_auto_change,
    effective_river_change,
    comparison_table_view,
):
    destination_text = (
        selected_destination
        if selected_destination
        else "не выбрано, рассматривается внутренний маршрут"
    )

    comparison_text = comparison_table_view.to_string(index=False)

    return f"""
Ты являешься интеллектуальным аналитическим модулем системы поддержки принятия решений
для выбора конкурентоспособных маршрутов перевозки зерна.

Тебе переданы расчетные данные приложения. Не выдумывай новые числовые значения.
Используй только показатели ниже. Сформируй прогнозно-аналитическое заключение.

Данные сценария:
- Тип маршрута: {route_mode}
- Регион отправления: {selected_region}
- Российский порт назначения: {selected_port}
- Зарубежное направление: {destination_text}

Оптимальный маршрут:
- Вариант маршрута: {best_route["route_type"]}
- Стоимость оптимального маршрута: {best_route["cost_rub_t"]} руб./т

Экономия:
- Максимальная экономия: {savings["max_saving"]} руб./т
- Максимальная экономия, %: {savings["max_saving_percent"]}%
- Экономия относительно автодоставки: {savings["auto_saving"]} руб./т
- Экономия относительно Ж/Д доставки: {savings["rail_saving"]} руб./т

Рыночный риск:
- Индекс рыночного риска: {market_risk["risk_score"]} из 100
- Статус рыночной ситуации: {market_risk["status"]}
- Новостной риск: {news_risk} из 100

Загрузка порта:
- Порт: {selected_port_load["port"]}
- Расчетная загрузка: {selected_port_load["adjusted_load_percent"]}%
- Среднее ожидание: {selected_port_load["waiting_days"]} суток
- Статус порта: {selected_port_load["status"]}

Прогноз перевозок:
- Начальный объем: {forecast_summary["first_volume"]} тыс. т
- Прогнозный объем к 2035 г.: {forecast_summary["last_volume"]} тыс. т
- Рост за период: {forecast_summary["growth_percent"]}%

Загрузка терминалов:
- Суммарная мощность сети: {terminal_summary["total_capacity"]} тыс. т
- Плановый объем: {terminal_summary["total_volume"]} тыс. т
- Средняя загрузка терминалов: {terminal_summary["average_load"]}%
- Количество перегруженных терминалов: {terminal_summary["overloaded_count"]}

Изменение тарифов:
- Ж/Д тариф: {effective_rail_change}%
- Автотариф: {effective_auto_change}%
- Речная составляющая: {effective_river_change}%

Сравнительная таблица маршрутов:
{comparison_text}

Сформируй ответ на русском языке по структуре:

1. Общая оценка выбранного маршрута.
2. Анализ рыночных и новостных факторов.
3. Оценка портовой и терминальной инфраструктуры.
4. Прогноз устойчивости маршрута.
5. Рекомендация по управлению логистикой.
6. Краткий итоговый вывод.

Стиль: научно-аналитический, понятный.
Объем: 250–400 слов.
"""


def generate_ai_analysis(
    selected_region,
    selected_port,
    route_mode,
    selected_destination,
    best_route,
    savings,
    market_risk,
    news_risk,
    selected_port_load,
    forecast_summary,
    terminal_summary,
    effective_rail_change,
    effective_auto_change,
    effective_river_change,
    comparison_table_view,
):
    api_key = get_groq_api_key()

    if not api_key:
        return (
            "ИИ-анализ пока не выполнен: не настроен GROQ_API_KEY. "
            "Добавьте ключ Groq API в Secrets приложения Streamlit Cloud."
        )

    prompt = build_ai_prompt(
        selected_region=selected_region,
        selected_port=selected_port,
        route_mode=route_mode,
        selected_destination=selected_destination,
        best_route=best_route,
        savings=savings,
        market_risk=market_risk,
        news_risk=news_risk,
        selected_port_load=selected_port_load,
        forecast_summary=forecast_summary,
        terminal_summary=terminal_summary,
        effective_rail_change=effective_rail_change,
        effective_auto_change=effective_auto_change,
        effective_river_change=effective_river_change,
        comparison_table_view=comparison_table_view,
    )

    try:
        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты аналитический модуль дипломного прототипа. "
                        "Пиши строго на русском языке, не выдумывай числовые данные."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=1200
        )

        return response.choices[0].message.content

    except Exception as error:
        return f"Ошибка при обращении к Groq API: {error}"