import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from modules.port_model import calculate_port_load, get_selected_port_load
from streamlit_folium import st_folium
from modules.map_model import build_terminal_map

from modules.report_model import generate_final_report

from modules.external_data import (
    get_cbr_usd_rate,
    get_main_thematic_news,
    calculate_news_risk_from_articles,
    generate_news_digest
)

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

from modules.destination_model import (
    get_available_destinations,
    calculate_international_route,
    generate_destination_conclusion
)


st.set_page_config(
    page_title="Аналитическая система зерновой логистики",
    layout="wide"
)

st.title("Аналитическая система оценки зерновых маршрутов")

st.write(
    "Прототип системы поддержки принятия решений для выбора "
    "конкурентоспособных речных и мультимодальных маршрутов перевозки зерна."
)


DATA_PATH = Path("data/routes.csv")
HISTORY_PATH = Path("data/grain_transport_history.csv")
TERMINALS_PATH = Path("data/terminals.csv")
DESTINATIONS_PATH = Path("data/foreign_destinations.csv")
PORT_LOAD_PATH = Path("data/port_load.csv")
TERMINALS_GEO_PATH = Path("data/terminals_geo.csv")
PORTS_GEO_PATH = Path("data/ports_geo.csv")
FOREIGN_GEO_PATH = Path("data/foreign_destinations_geo.csv")


@st.cache_data
def load_routes(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data
def load_destinations(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data
def load_history(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data
def load_terminals(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data
def load_port_load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data
def load_terminals_geo(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data
def load_ports_geo(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data
def load_foreign_geo(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

@st.cache_data(ttl=1800)
def load_news_digest(query: str, max_records: int = 3):
    articles = get_main_thematic_news(query, max_records=max_records)
    risk_result = calculate_news_risk_from_articles(articles)
    digest = generate_news_digest(articles, risk_result)
    return articles, risk_result, digest


df = load_routes(DATA_PATH)
history_df = load_history(HISTORY_PATH)
terminals_df = load_terminals(TERMINALS_PATH)
destinations_df = load_destinations(DESTINATIONS_PATH)
port_load_source_df = load_port_load(PORT_LOAD_PATH)
port_load_df = calculate_port_load(port_load_source_df)
terminals_geo_df = load_terminals_geo(TERMINALS_GEO_PATH)
ports_geo_df = load_ports_geo(PORTS_GEO_PATH)
foreign_geo_df = load_foreign_geo(FOREIGN_GEO_PATH)
usd_data = get_cbr_usd_rate()


# =========================
# Выбор направления
# =========================

regions = sorted(df["region"].unique())
ports = sorted(df["port"].unique())

st.subheader("Параметры маршрута")

route_mode = st.radio(
    "Выберите тип маршрута",
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


# =========================
# Сценарный анализ тарифов
# =========================

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


# =========================
# Внешние рыночные факторы
# =========================

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
        value=int(round(usd_data["rate"])),
        step=1
    )

with market_col2:
    grain_price = st.slider(
        "Мировая цена зерна, долл./т",
        min_value=100,
        max_value=400,
        value=230,
        step=5
    )

with market_col3:
    fuel_change = st.slider(
        "Изменение стоимости топлива, %",
        min_value=-30,
        max_value=80,
        value=0,
        step=1
    )

market_col4, market_col5 = st.columns(2)

with market_col4:
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


# =========================
# Новостная сводка
# =========================

st.subheader("Новостная сводка по рынку зерна и портовой логистике")
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

news_articles, news_risk_result, news_digest = load_news_digest(
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
    news_source_name = top_news[0]["provider"] if top_news else "Нет данных"
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
    news_risk = news_risk_result["news_risk"]
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

# =========================
# Загрузка морских портов
# =========================

st.subheader("Оценка загрузки морских портов назначения")

selected_port_load = get_selected_port_load(
    port_load_df=port_load_df,
    selected_port=selected_port
)

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

st.dataframe(port_view, width="stretch")

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

st.plotly_chart(port_fig, width="stretch")

# =========================
# Расчет общего рыночного риска
# =========================

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


# =========================
# Учет риска в тарифном сценарии
# =========================

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


# =========================
# Расчет маршрутов
# =========================

filtered = df[
    (df["region"] == selected_region) &
    (df["port"] == selected_port)
].copy()

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


# =========================
# Отображение результатов маршрута
# =========================

st.subheader("Сравнение вариантов доставки")
st.dataframe(comparison_table_view, width="stretch")

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

destination_conclusion = ""

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
else:
    international_result = None

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

st.plotly_chart(fig, width="stretch")


# =========================
# Прогноз перевозок
# =========================

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
st.dataframe(forecast_view, width="stretch")

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

st.plotly_chart(forecast_fig, width="stretch")

st.info(
    "Прогнозный модуль позволяет оценить возможную динамику перевозок зерна "
    "речным транспортом. Линейный прогноз отражает продолжение выявленной "
    "тенденции, а целевой прогноз показывает траекторию достижения потенциала "
    "14 млн т к 2035 году."
)


# =========================
# Загрузка терминалов
# =========================

st.divider()

st.header("Оценка загрузки речных зерновых терминалов")

terminal_regions = ["Все регионы"] + sorted(terminals_df["region"].unique())

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
st.dataframe(terminal_view, width="stretch")

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

st.plotly_chart(terminal_fig, width="stretch")

st.subheader("Карта маршрута: терминалы — российский порт — зарубежное направление")

st.caption(
    "На карте показаны речные зерновые терминалы, выбранный российский порт, "
    "зарубежное направление и расчетные участки маршрута."
)

map_selected_destination = selected_destination if route_mode == "Экспортный маршрут с зарубежным направлением" else None

terminal_map = build_terminal_map(
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


# =========================
# Итоговый отчет
# =========================

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

if route_mode == "Экспортный маршрут с зарубежным направлением" and selected_destination:
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