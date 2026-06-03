import streamlit as st
import pandas as pd
import plotly.express as px
import folium

from pathlib import Path
from streamlit_folium import st_folium

from modules import external_data

from modules.report_model import generate_final_report

from modules.market_model import (
    calculate_market_risk,
    generate_market_text,
    convert_risk_to_tariff_adjustments
)

from modules.cost_model import (
    get_best_route,
    calculate_savings,
    add_cost_difference,
    apply_scenario,
    generate_conclusion
)

from modules.forecast_model import (
    build_linear_forecast,
    build_target_forecast,
    calculate_forecast_summary
)

from modules.terminal_model import (
    calculate_terminal_load,
    calculate_terminal_summary
)

from modules.port_model import (
    calculate_port_load,
    get_selected_port_load
)

from modules.destination_model import (
    get_available_destinations,
    calculate_international_route,
    generate_destination_conclusion
)


# ============================================================
# НАСТРОЙКИ СТРАНИЦЫ
# ============================================================

st.set_page_config(
    page_title="Аналитическая система зерновой логистики",
    layout="wide"
)

st.title("Аналитическая система оценки зерновых маршрутов")

st.write(
    "Прототип системы поддержки принятия решений для выбора "
    "конкурентоспособных речных и мультимодальных маршрутов перевозки зерна."
)


# ============================================================
# ПУТИ К ДАННЫМ
# ============================================================

DATA_PATH = Path("data/routes.csv")
HISTORY_PATH = Path("data/grain_transport_history.csv")
TERMINALS_PATH = Path("data/terminals.csv")
DESTINATIONS_PATH = Path("data/foreign_destinations.csv")
PORT_LOAD_PATH = Path("data/port_load.csv")
TERMINALS_GEO_PATH = Path("data/terminals_geo.csv")
PORTS_GEO_PATH = Path("data/ports_geo.csv")
FOREIGN_GEO_PATH = Path("data/foreign_destinations_geo.csv")


# ============================================================
# БЕЗОПАСНЫЕ ФУНКЦИИ ЗАГРУЗКИ
# ============================================================

@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(ttl=1800)
def load_news_digest_safe(query: str, max_records: int = 3):
    """
    Безопасная загрузка новостей.
    Даже если внешний источник не ответит, приложение не упадет.
    """
    try:
        articles = external_data.get_main_thematic_news(
            query,
            max_records=max_records
        )
    except Exception:
        articles = []

    try:
        risk_result = external_data.calculate_news_risk_from_articles(articles)
    except Exception:
        risk_result = {
            "news_risk": 30,
            "risk_comment": (
                "Новости не удалось автоматически обработать. "
                "Используется нейтральная оценка новостного риска."
            )
        }

    try:
        digest = external_data.generate_news_digest(articles, risk_result)
    except Exception:
        digest = ""

    return articles, risk_result, digest


def get_usd_rate_safe() -> dict:
    """
    Безопасное получение курса доллара.
    """
    try:
        return external_data.get_cbr_usd_rate()
    except Exception:
        return {
            "rate": 90.0,
            "date": "нет данных",
            "source": "Резервное значение"
        }


def get_market_indicators_safe() -> dict:
    """
    Безопасное получение рыночных индикаторов.
    Если функции get_auto_market_indicators нет или источник недоступен,
    используются резервные значения.
    """
    fallback = {
        "wheat_price_usd_t": 230.0,
        "wheat_source": "Резервное значение",
        "wheat_date": "",
        "oil_price_usd_bbl": 80.0,
        "oil_source": "Резервное значение",
        "oil_date": "",
        "fuel_change_percent": 0.0
    }

    market_func = getattr(external_data, "get_auto_market_indicators", None)

    if market_func is None:
        return fallback

    try:
        data = market_func()

        required_keys = [
            "wheat_price_usd_t",
            "wheat_source",
            "oil_price_usd_bbl",
            "oil_source",
            "fuel_change_percent"
        ]

        for key in required_keys:
            if key not in data:
                return fallback

        return data

    except Exception:
        return fallback


# ============================================================
# КАРТА МАРШРУТОВ
# ============================================================

def get_terminal_marker_color(status: str) -> str:
    if status == "Низкая загрузка":
        return "green"
    if status == "Нормальная загрузка":
        return "blue"
    if status == "Высокая загрузка":
        return "orange"
    if status == "Перегрузка":
        return "red"
    return "gray"


def build_terminal_map_safe(
    terminal_load_df: pd.DataFrame,
    terminals_geo_df: pd.DataFrame,
    ports_geo_df: pd.DataFrame,
    selected_port: str,
    foreign_geo_df: pd.DataFrame | None = None,
    selected_destination: str | None = None
):
    """
    Безопасная карта:
    терминалы -> российский порт -> зарубежное направление.
    Ошибка selected_foreign здесь невозможна.
    """

    map_df = terminal_load_df.merge(
        terminals_geo_df,
        on="terminal",
        how="left"
    )

    selected_port_row = ports_geo_df[
        ports_geo_df["port"] == selected_port
    ]

    if not selected_port_row.empty:
        port_row = selected_port_row.iloc[0]
        center_lat = float(port_row["lat"])
        center_lon = float(port_row["lon"])
    else:
        center_lat = 50.5
        center_lon = 47.0

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=5,
        tiles="CartoDB positron"
    )

    # Терминалы
    for _, row in map_df.dropna(subset=["lat", "lon"]).iterrows():
        color = get_terminal_marker_color(row.get("status", ""))

        planned_volume = row.get("planned_volume_thousand_tons", 0)
        load_percent = row.get("load_percent", 0)
        capacity = row.get("capacity_thousand_tons", 0)

        popup_text = (
            f"<b>{row['terminal']}</b><br>"
            f"Регион: {row['region']}<br>"
            f"Мощность: {capacity} тыс. т/год<br>"
            f"Плановый объем: {planned_volume} тыс. т<br>"
            f"Загрузка: {load_percent}%<br>"
            f"Статус: {row.get('status', 'нет данных')}"
        )

        folium.CircleMarker(
            location=[float(row["lat"]), float(row["lon"])],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=row["terminal"]
        ).add_to(m)

    port_lat = None
    port_lon = None

    # Российский порт
    if not selected_port_row.empty:
        port = selected_port_row.iloc[0]
        port_lat = float(port["lat"])
        port_lon = float(port["lon"])

        folium.Marker(
            location=[port_lat, port_lon],
            popup=f"<b>{port['port']}</b><br>{port.get('type', 'Порт')}",
            tooltip=f"Российский порт: {port['port']}",
            icon=folium.Icon(color="purple", icon="anchor", prefix="fa")
        ).add_to(m)

        # Линии терминалы -> порт
        for _, row in map_df.dropna(subset=["lat", "lon"]).iterrows():
            planned_volume = float(row.get("planned_volume_thousand_tons", 0))
            line_weight = max(1, min(6, planned_volume / 250))

            folium.PolyLine(
                locations=[
                    [float(row["lat"]), float(row["lon"])],
                    [port_lat, port_lon]
                ],
                color="blue",
                weight=line_weight,
                opacity=0.35,
                tooltip=(
                    f"Внутрироссийский участок: {row['terminal']} → {selected_port}. "
                    f"Плановый объем: {planned_volume} тыс. т. "
                    f"Загрузка терминала: {row.get('load_percent', 0)}%."
                )
            ).add_to(m)

    # Зарубежный порт
    if (
        foreign_geo_df is not None
        and selected_destination is not None
        and selected_destination != ""
        and port_lat is not None
        and port_lon is not None
    ):
        selected_foreign_row = foreign_geo_df[
            foreign_geo_df["destination"] == selected_destination
        ]

        if not selected_foreign_row.empty:
            foreign = selected_foreign_row.iloc[0]
            foreign_lat = float(foreign["lat"])
            foreign_lon = float(foreign["lon"])

            folium.Marker(
                location=[foreign_lat, foreign_lon],
                popup=(
                    f"<b>{foreign['destination']}</b><br>"
                    f"Страна: {foreign['country']}"
                ),
                tooltip=f"Зарубежный порт: {foreign['destination']}",
                icon=folium.Icon(color="red", icon="flag", prefix="fa")
            ).add_to(m)

            folium.PolyLine(
                locations=[
                    [port_lat, port_lon],
                    [foreign_lat, foreign_lon]
                ],
                color="red",
                weight=5,
                opacity=0.8,
                tooltip=(
                    f"Международный участок: {selected_port} → "
                    f"{foreign['destination']} ({foreign['country']})."
                )
            ).add_to(m)

    return m


# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================

df = load_csv(DATA_PATH)
history_df = load_csv(HISTORY_PATH)
terminals_df = load_csv(TERMINALS_PATH)
destinations_df = load_csv(DESTINATIONS_PATH)
port_load_source_df = load_csv(PORT_LOAD_PATH)
terminals_geo_df = load_csv(TERMINALS_GEO_PATH)
ports_geo_df = load_csv(PORTS_GEO_PATH)
foreign_geo_df = load_csv(FOREIGN_GEO_PATH)

port_load_df = calculate_port_load(port_load_source_df)

usd_data = get_usd_rate_safe()
market_indicators = get_market_indicators_safe()


# ============================================================
# ВЫБОР МАРШРУТА
# ============================================================

st.subheader("Параметры маршрута")

regions = sorted(df["region"].dropna().unique())
ports = sorted(df["port"].dropna().unique())

route_mode = st.radio(
    "Тип маршрута",
    [
        "Внутренний маршрут до российского порта",
        "Экспортный маршрут с зарубежным направлением"
    ],
    horizontal=True
)

col1, col2 = st.columns(2)

with col1:
    selected_region = st.selectbox(
        "Регион отправления",
        regions
    )

with col2:
    selected_port = st.selectbox(
        "Российский порт назначения",
        ports
    )

selected_destination = None

if route_mode == "Экспортный маршрут с зарубежным направлением":
    available_destinations = get_available_destinations(
        destinations_df,
        selected_port
    )

    if available_destinations:
        selected_destination = st.selectbox(
            "Зарубежное направление",
            available_destinations
        )
    else:
        st.warning(
            "Для выбранного российского порта зарубежные направления пока не заданы."
        )
else:
    st.info(
        "Выбран внутренний маршрут: расчет выполняется до российского порта назначения."
    )


# ============================================================
# СЦЕНАРНЫЙ АНАЛИЗ ТАРИФОВ
# ============================================================

st.subheader("Сценарный анализ изменения тарифов")

scenario_col1, scenario_col2, scenario_col3 = st.columns(3)

with scenario_col1:
    rail_change = st.slider(
        "Изменение Ж/Д тарифа, %",
        min_value=-30,
        max_value=50,
        value=0,
        step=1
    )

with scenario_col2:
    auto_change = st.slider(
        "Изменение автотарифа, %",
        min_value=-30,
        max_value=50,
        value=0,
        step=1
    )

with scenario_col3:
    river_change = st.slider(
        "Изменение речной составляющей, %",
        min_value=-30,
        max_value=50,
        value=0,
        step=1
    )


# ============================================================
# ЗАГРУЗКА ПОРТА
# ============================================================

selected_port_load = get_selected_port_load(
    port_load_df=port_load_df,
    selected_port=selected_port
)


# ============================================================
# ВНЕШНИЕ РЫНОЧНЫЕ ФАКТОРЫ
# ============================================================

st.subheader("Оценка внешних рыночных факторов")

st.caption(
    f"Курс USD загружен автоматически: {usd_data['rate']} руб. "
    f"Дата: {usd_data['date']}. Источник: {usd_data['source']}."
)

market_col1, market_col2, market_col3 = st.columns(3)

with market_col1:
    usd_rate = st.slider(
        "Курс доллара, руб.",
        min_value=50,
        max_value=150,
        value=int(round(float(usd_data["rate"]))),
        step=1
    )

with market_col2:
    st.caption(
        f"Индикатор цены зерна: {market_indicators['wheat_price_usd_t']} долл./т. "
        f"Источник: {market_indicators['wheat_source']}."
    )

    grain_price = st.slider(
        "Мировая цена зерна, долл./т",
        min_value=100,
        max_value=400,
        value=int(round(float(market_indicators["wheat_price_usd_t"]))),
        step=5
    )

with market_col3:
    st.caption(
        f"Индикатор нефти: {market_indicators['oil_price_usd_bbl']} долл./барр. "
        f"Расчетное изменение топлива: {market_indicators['fuel_change_percent']}%."
    )

    fuel_change = st.slider(
        "Изменение стоимости топлива, %",
        min_value=-30,
        max_value=80,
        value=int(round(float(market_indicators["fuel_change_percent"]))),
        step=1
    )

market_col4, market_col5 = st.columns(2)

with market_col4:
    use_port_load_as_congestion = st.checkbox(
        "Использовать расчетную загрузку выбранного порта",
        value=True
    )

    if use_port_load_as_congestion:
        port_congestion = int(
            round(float(selected_port_load["adjusted_load_percent"]))
        )
        st.metric(
            "Загруженность морских портов",
            f"{port_congestion}%"
        )
    else:
        port_congestion = st.slider(
            "Загруженность морских портов, %",
            min_value=0,
            max_value=100,
            value=70,
            step=5
        )

with market_col5:
    manual_news_risk = st.slider(
        "Новостной риск вручную, 0–100",
        min_value=0,
        max_value=100,
        value=30,
        step=5
    )


# ============================================================
# НОВОСТНАЯ СВОДКА
# ============================================================

st.subheader("Новостная сводка")
st.caption(
    "Новостная сводка используется для автоматической оценки внешнего риска "
    "и корректировки сценария выбора маршрута."
)

news_topics = {
    "Экспорт зерна и пшеницы": "экспорт зерна Россия OR пшеница экспорт OR зерно порт",
    "Портовая логистика": "порт Кавказ OR порт Астрахань OR зерно порт OR перевалка зерна",
    "Тарифы, фрахт и перевозки": "фрахт зерно OR тариф перевозка зерна OR логистика зерна",
    "Риски и ограничения экспорта": "экспорт зерна ограничения OR пошлины зерно OR санкции зерно"
}

selected_news_topic = st.selectbox(
    "Тема новостного анализа",
    list(news_topics.keys())
)

news_query = news_topics[selected_news_topic]

news_articles, news_risk_result, news_digest = load_news_digest_safe(
    news_query,
    max_records=3
)

top_news = news_articles[:3]

news_col1, news_col2, news_col3 = st.columns(3)

with news_col1:
    st.metric(
        "Новостной риск",
        f"{news_risk_result['news_risk']} / 100"
    )

with news_col2:
    news_source_name = top_news[0].get("provider", "Нет данных") if top_news else "Нет данных"
    st.metric(
        "Источник",
        news_source_name
    )

with news_col3:
    st.metric(
        "Новостей учтено",
        len(top_news)
    )

use_auto_news_risk = st.checkbox(
    "Учитывать новостной риск в общем индексе",
    value=True
)

if use_auto_news_risk:
    news_risk = int(news_risk_result["news_risk"])
    st.success(
        f"В общий индекс рыночного риска подставлен новостной риск {news_risk} из 100."
    )
else:
    news_risk = manual_news_risk
    st.info(
        f"Используется ручная оценка новостного риска: {news_risk} из 100."
    )

st.info(news_risk_result["risk_comment"])

if top_news:
    st.markdown("**Ключевые новости:**")

    for number, article in enumerate(top_news, start=1):
        title = article.get("title", "Без заголовка")
        source = article.get("source", "Источник не указан")
        provider = article.get("provider", "Источник данных не указан")
        url = article.get("url", "")

        if url:
            st.markdown(
                f"{number}. [{title}]({url})  \n"
                f"   Источник: {source}, поставщик данных: {provider}"
            )
        else:
            st.markdown(
                f"{number}. {title}  \n"
                f"   Источник: {source}, поставщик данных: {provider}"
            )
else:
    st.warning(
        "Новости не удалось загрузить. Используется нейтральная оценка новостного риска."
    )


# ============================================================
# РЫНОЧНЫЙ РИСК
# ============================================================

market_risk = calculate_market_risk(
    usd_rate=usd_rate,
    grain_price=grain_price,
    fuel_change=fuel_change,
    port_congestion=port_congestion,
    news_risk=news_risk
)

market_text = generate_market_text(
    usd_rate=usd_rate,
    grain_price=grain_price,
    fuel_change=fuel_change,
    port_congestion=port_congestion,
    news_risk=news_risk,
    risk_result=market_risk
)

risk_col1, risk_col2 = st.columns(2)

with risk_col1:
    st.metric(
        "Индекс рыночного риска",
        f"{market_risk['risk_score']} / 100"
    )

with risk_col2:
    st.metric(
        "Оценка ситуации",
        market_risk["status"]
    )

st.info(market_text)


# ============================================================
# ЗАГРУЗКА МОРСКИХ ПОРТОВ
# ============================================================

st.subheader("Оценка загрузки морских портов назначения")

port_col1, port_col2, port_col3 = st.columns(3)

with port_col1:
    st.metric(
        "Выбранный порт",
        selected_port_load["port"]
    )

with port_col2:
    st.metric(
        "Расчетная загрузка порта",
        f"{selected_port_load['adjusted_load_percent']}%"
    )

with port_col3:
    st.metric(
        "Среднее ожидание",
        f"{selected_port_load['waiting_days']} суток"
    )

st.info(
    f"Статус порта «{selected_port_load['port']}»: "
    f"{selected_port_load['status']}."
)

port_view = port_load_df.rename(
    columns={
        "port": "Порт",
        "capacity_thousand_tons": "Пропускная способность, тыс. т",
        "current_volume_thousand_tons": "Текущий объем, тыс. т",
        "waiting_days": "Ожидание, суток",
        "risk_factor": "Коэффициент риска",
        "base_load_percent": "Базовая загрузка, %",
        "adjusted_load_percent": "Расчетная загрузка, %",
        "status": "Статус"
    }
)

port_fig = px.bar(
    port_view,
    x="Порт",
    y="Расчетная загрузка, %",
    color="Статус",
    text="Расчетная загрузка, %",
    title="Сравнение загрузки морских портов назначения"
)

port_fig.update_traces(textposition="outside")
port_fig.update_layout(
    yaxis_title="Загрузка, %",
    xaxis_title="Морской порт"
)

st.dataframe(port_view, use_container_width=True)
st.plotly_chart(port_fig, use_container_width=True)

with st.expander("Подключение AIS / MarineTraffic"):
    st.write(
        "В промышленной версии системы возможно подключение AIS-данных "
        "через MarineTraffic API. На этапе прототипа используется расчетная "
        "оценка загрузки портов на основе пропускной способности, ожидания "
        "обработки и новостного риска."
    )


# ============================================================
# УЧЕТ РИСКА В ТАРИФАХ
# ============================================================

st.subheader("Учет рыночного риска в тарифном сценарии")

use_market_risk_in_tariffs = st.checkbox(
    "Автоматически учитывать рыночный риск в тарифном сценарии",
    value=False
)

risk_adjustments = {
    "rail_risk_add": 0,
    "auto_risk_add": 0,
    "river_risk_add": 0
}

if use_market_risk_in_tariffs:
    risk_adjustments = convert_risk_to_tariff_adjustments(
        market_risk["risk_score"]
    )

    st.warning(
        "Рыночный риск учтен в сценарии тарифов: "
        f"Ж/Д +{risk_adjustments['rail_risk_add']}%, "
        f"авто +{risk_adjustments['auto_risk_add']}%, "
        f"речная составляющая +{risk_adjustments['river_risk_add']}%."
    )


# ============================================================
# РАСЧЕТ МАРШРУТОВ
# ============================================================

filtered = df[
    (df["region"] == selected_region) &
    (df["port"] == selected_port)
].copy()

if filtered.empty:
    st.error(
        "Для выбранного региона и порта нет данных в файле routes.csv."
    )
    st.stop()

effective_rail_change = rail_change + risk_adjustments["rail_risk_add"]
effective_auto_change = auto_change + risk_adjustments["auto_risk_add"]
effective_river_change = river_change + risk_adjustments["river_risk_add"]

filtered = apply_scenario(
    filtered,
    rail_change=effective_rail_change,
    auto_change=effective_auto_change,
    river_change=effective_river_change
)

best_route = get_best_route(filtered)
savings = calculate_savings(filtered, best_route)
comparison_table = add_cost_difference(filtered, best_route)

comparison_table_view = comparison_table.rename(
    columns={
        "region": "Регион отправления",
        "port": "Порт назначения",
        "route_type": "Вариант маршрута",
        "cost_rub_t": "Стоимость, руб./т",
        "difference_from_best_rub_t": "Разница с лучшим, руб./т",
        "difference_from_best_percent": "Разница с лучшим, %"
    }
)

comparison_table_view = comparison_table_view[
    [
        "Регион отправления",
        "Порт назначения",
        "Вариант маршрута",
        "Стоимость, руб./т",
        "Разница с лучшим, руб./т",
        "Разница с лучшим, %"
    ]
]

st.subheader("Сравнение вариантов доставки")
st.dataframe(comparison_table_view, use_container_width=True)

st.subheader("Рекомендация системы")
st.success(
    f"Оптимальный маршрут: {best_route['route_type']}. "
    f"Стоимость: {best_route['cost_rub_t']} руб./т."
)

conclusion = generate_conclusion(
    selected_region=selected_region,
    selected_port=selected_port,
    best_route=best_route,
    savings=savings,
    rail_change=effective_rail_change,
    auto_change=effective_auto_change,
    river_change=effective_river_change
)

st.subheader("Аналитический вывод")
st.info(conclusion)


# ============================================================
# ЭКСПОРТНОЕ НАПРАВЛЕНИЕ
# ============================================================

destination_conclusion = ""
international_result = None

if route_mode == "Экспортный маршрут с зарубежным направлением" and selected_destination:
    international_result = calculate_international_route(
        best_route=best_route,
        destinations=destinations_df,
        selected_destination=selected_destination
    )

    destination_conclusion = generate_destination_conclusion(
        selected_region=selected_region,
        selected_port=selected_port,
        international_result=international_result
    )

    st.subheader("Экспортное направление доставки")

    dest_col1, dest_col2, dest_col3, dest_col4 = st.columns(4)

    with dest_col1:
        st.metric(
            "Российский порт",
            selected_port
        )

    with dest_col2:
        st.metric(
            "Зарубежный порт",
            international_result["destination"]
        )

    with dest_col3:
        st.metric(
            "Страна назначения",
            international_result["country"]
        )

    with dest_col4:
        st.metric(
            "Итоговая стоимость",
            f"{international_result['total_cost']} руб./т"
        )

    st.info(destination_conclusion)


# ============================================================
# ЭКОНОМИЯ И ГРАФИК МАРШРУТОВ
# ============================================================

metric_col1, metric_col2, metric_col3 = st.columns(3)

with metric_col1:
    st.metric(
        label="Экономия относительно самого дорогого варианта",
        value=f"{savings['max_saving']} руб./т",
        delta=f"{savings['max_saving_percent']}%"
    )

with metric_col2:
    st.metric(
        label="Экономия относительно прямой автодоставки",
        value=f"{savings['auto_saving']} руб./т",
        delta=f"{savings['auto_saving_percent']}%"
    )

with metric_col3:
    st.metric(
        label="Экономия относительно прямой Ж/Д доставки",
        value=f"{savings['rail_saving']} руб./т",
        delta=f"{savings['rail_saving_percent']}%"
    )

st.subheader("Графическое сравнение стоимости маршрутов")

fig = px.bar(
    filtered,
    x="route_type",
    y="cost_rub_t",
    text="cost_rub_t",
    labels={
        "route_type": "Вариант маршрута",
        "cost_rub_t": "Стоимость, руб./т"
    },
    title="Стоимость доставки зерна по вариантам маршрутов"
)

fig.update_traces(textposition="outside")
fig.update_layout(
    xaxis_tickangle=-15,
    yaxis_title="Стоимость, руб./т",
    xaxis_title="Вариант маршрута"
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================
# ПРОГНОЗ ПЕРЕВОЗОК
# ============================================================

st.divider()
st.header("Прогноз перевозок зерна речным транспортом")

forecast_type = st.radio(
    "Выберите тип прогноза",
    [
        "Линейный прогноз на основе динамики 2019–2024 гг.",
        "Целевой прогноз до 14 млн т к 2035 г."
    ]
)

if forecast_type == "Линейный прогноз на основе динамики 2019–2024 гг.":
    forecast_df = build_linear_forecast(history_df)
else:
    forecast_df = build_target_forecast(history_df)

forecast_summary = calculate_forecast_summary(forecast_df)

forecast_col1, forecast_col2, forecast_col3 = st.columns(3)

with forecast_col1:
    st.metric(
        "Объем в начальном году",
        f"{forecast_summary['first_volume']} тыс. т"
    )

with forecast_col2:
    st.metric(
        "Прогнозный объем к 2035 г.",
        f"{forecast_summary['last_volume']} тыс. т"
    )

with forecast_col3:
    st.metric(
        "Рост за период",
        f"{forecast_summary['growth_percent']}%"
    )

forecast_view = forecast_df.rename(
    columns={
        "year": "Год",
        "volume_thousand_tons": "Объем перевозок, тыс. т",
        "type": "Тип данных"
    }
)

st.subheader("Таблица прогноза")
st.dataframe(forecast_view, use_container_width=True)

forecast_fig = px.line(
    forecast_df,
    x="year",
    y="volume_thousand_tons",
    markers=True,
    color="type",
    labels={
        "year": "Год",
        "volume_thousand_tons": "Объем перевозок, тыс. т",
        "type": "Тип данных"
    },
    title="Динамика и прогноз перевозок зерна речным транспортом"
)

st.plotly_chart(forecast_fig, use_container_width=True)

st.info(
    "Прогнозный модуль позволяет оценить возможную динамику перевозок зерна "
    "речным транспортом. Линейный прогноз отражает продолжение выявленной "
    "тенденции, а целевой прогноз показывает траекторию достижения потенциала "
    "14 млн т к 2035 году."
)


# ============================================================
# ЗАГРУЗКА ТЕРМИНАЛОВ И КАРТА
# ============================================================

st.divider()
st.header("Оценка загрузки речных зерновых терминалов")

terminal_regions = ["Все регионы"] + sorted(terminals_df["region"].dropna().unique())

selected_terminal_region = st.selectbox(
    "Выберите регион терминалов для анализа",
    terminal_regions
)

if selected_terminal_region == "Все регионы":
    selected_terminals_df = terminals_df.copy()
else:
    selected_terminals_df = terminals_df[
        terminals_df["region"] == selected_terminal_region
    ].copy()

selected_capacity = int(selected_terminals_df["capacity_thousand_tons"].sum())

default_volume = min(14000, selected_capacity)
max_volume = max(1000, selected_capacity * 2)

terminal_volume = st.slider(
    "Планируемый объем перевозок через выбранную сеть терминалов, тыс. т",
    min_value=0,
    max_value=max_volume,
    value=default_volume,
    step=250
)

terminal_load_df = calculate_terminal_load(
    selected_terminals_df,
    total_volume_thousand_tons=terminal_volume
)

terminal_summary = calculate_terminal_summary(terminal_load_df)

load_col1, load_col2, load_col3, load_col4 = st.columns(4)

with load_col1:
    st.metric(
        "Суммарная мощность сети",
        f"{terminal_summary['total_capacity']} тыс. т"
    )

with load_col2:
    st.metric(
        "Плановый объем",
        f"{terminal_summary['total_volume']} тыс. т"
    )

with load_col3:
    st.metric(
        "Средняя загрузка",
        f"{terminal_summary['average_load']}%"
    )

with load_col4:
    st.metric(
        "Терминалов с перегрузкой",
        terminal_summary["overloaded_count"]
    )

terminal_view = terminal_load_df.rename(
    columns={
        "terminal": "Терминал",
        "region": "Регион",
        "capacity_thousand_tons": "Пропускная способность, тыс. т/год",
        "planned_volume_thousand_tons": "Плановый объем, тыс. т",
        "load_percent": "Загрузка, %",
        "status": "Статус"
    }
)

st.subheader("Таблица загрузки терминалов")
st.dataframe(terminal_view, use_container_width=True)

terminal_fig = px.bar(
    terminal_view,
    x="Терминал",
    y="Загрузка, %",
    text="Загрузка, %",
    color="Статус",
    title="Оценка загрузки речных зерновых терминалов",
    labels={
        "Терминал": "Терминал",
        "Загрузка, %": "Загрузка, %"
    }
)

terminal_fig.update_traces(textposition="outside")
terminal_fig.update_layout(
    xaxis_tickangle=-45,
    yaxis_title="Загрузка, %",
    xaxis_title="Терминал"
)

st.plotly_chart(terminal_fig, use_container_width=True)

st.subheader("Карта маршрута: терминалы — российский порт — зарубежное направление")

st.caption(
    "На карте показаны речные зерновые терминалы, выбранный российский порт, "
    "зарубежное направление и расчетные участки маршрута."
)

show_foreign_on_map = False

if route_mode == "Экспортный маршрут с зарубежным направлением":
    show_foreign_on_map = st.checkbox(
        "Показывать зарубежное направление на карте",
        value=True
    )

if (
    route_mode == "Экспортный маршрут с зарубежным направлением"
    and show_foreign_on_map
    and selected_destination
):
    map_selected_destination = selected_destination
else:
    map_selected_destination = None

terminal_map = build_terminal_map_safe(
    terminal_load_df=terminal_load_df,
    terminals_geo_df=terminals_geo_df,
    ports_geo_df=ports_geo_df,
    selected_port=selected_port,
    foreign_geo_df=foreign_geo_df,
    selected_destination=map_selected_destination
)

map_left, map_center, map_right = st.columns([0.5, 5, 0.5])

with map_center:
    st_folium(
        terminal_map,
        width=1450,
        height=700
    )

st.markdown(
    """
    **Условные обозначения:**  
    🟢 низкая загрузка терминала · 🔵 нормальная загрузка · 🟠 высокая загрузка · 🔴 перегрузка · ⚓ российский порт · 🚩 зарубежный порт
    """
)

st.info(
    "Модуль оценки загрузки терминалов показывает, насколько существующая "
    "или выбранная сеть речных зерновых терминалов способна принять заданный "
    "объем перевозок. При загрузке выше 100% терминал считается перегруженным, "
    "что указывает на необходимость расширения мощности или перераспределения "
    "потока между другими пунктами перевалки."
)


# ============================================================
# ИТОГОВЫЙ ОТЧЕТ
# ============================================================

st.divider()
st.header("Итоговый аналитический отчет")

final_report = generate_final_report(
    selected_region=selected_region,
    selected_port=selected_port,
    best_route=best_route,
    savings=savings,
    market_risk=market_risk,
    forecast_summary=forecast_summary,
    terminal_summary=terminal_summary,
    effective_rail_change=effective_rail_change,
    effective_auto_change=effective_auto_change,
    effective_river_change=effective_river_change
)

if route_mode == "Экспортный маршрут с зарубежным направлением" and destination_conclusion:
    final_report += "\n\n" + destination_conclusion

st.text_area(
    "Сформированный текст отчета",
    value=final_report,
    height=400
)

st.download_button(
    label="Скачать отчет в TXT",
    data=final_report,
    file_name="analytical_report.txt",
    mime="text/plain"
)