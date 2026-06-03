import pandas as pd
import folium


def get_marker_color(status: str) -> str:
    """
    Цвет маркера по статусу загрузки.
    """
    if status == "Низкая загрузка":
        return "green"
    if status == "Нормальная загрузка":
        return "blue"
    if status == "Высокая загрузка":
        return "orange"
    if status == "Перегрузка":
        return "red"
    return "gray"


def build_terminal_map(
    terminal_load_df: pd.DataFrame,
    terminals_geo_df: pd.DataFrame,
    ports_geo_df: pd.DataFrame,
    selected_port: str,
    foreign_geo_df: pd.DataFrame | None = None,
    selected_destination: str | None = None
):
    """
    Строит карту:
    терминалы → российский порт → зарубежное направление.
    """
    map_df = terminal_load_df.merge(
        terminals_geo_df,
        on="terminal",
        how="left"
    )

    m = folium.Map(
        location=[50.5, 47.0],
        zoom_start=5,
        tiles="CartoDB positron"
    )

    for _, row in map_df.dropna(subset=["lat", "lon"]).iterrows():
        color = get_marker_color(row["status"])

        popup_text = (
            f"<b>{row['terminal']}</b><br>"
            f"Регион: {row['region']}<br>"
            f"Мощность: {row['capacity_thousand_tons']} тыс. т/год<br>"
            f"Плановый объем: {row['planned_volume_thousand_tons']} тыс. т<br>"
            f"Загрузка: {row['load_percent']}%<br>"
            f"Статус: {row['status']}"
        )

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=row["terminal"]
        ).add_to(m)

    selected_port_row = ports_geo_df[ports_geo_df["port"] == selected_port]

    port_lat = None
    port_lon = None

    if not selected_port_row.empty:
        port = selected_port_row.iloc[0]
        port_lat = port["lat"]
        port_lon = port["lon"]

        folium.Marker(
            location=[port_lat, port_lon],
            popup=f"<b>{port['port']}</b><br>{port['type']}",
            tooltip=f"Российский порт: {port['port']}",
            icon=folium.Icon(color="purple", icon="anchor", prefix="fa")
        ).add_to(m)

        for _, row in map_df.dropna(subset=["lat", "lon"]).iterrows():
            line_weight = max(1, min(6, row["planned_volume_thousand_tons"] / 250))

        folium.PolyLine(
            locations=[
            [row["lat"], row["lon"]],
            [port_lat, port_lon]
            ],
            color="blue",
            weight=line_weight,
            opacity=0.35,
            tooltip=(
        f"Внутрироссийский участок: {row['terminal']} → {selected_port}. "
        f"Плановый объем: {row['planned_volume_thousand_tons']} тыс. т. "
        f"Загрузка терминала: {row['load_percent']}%."
    )
).add_to(m)

        if (
        foreign_geo_df is not None
        and selected_destination is not None
        and port_lat is not None
        and port_lon is not None
    ):
            selected_foreign = foreign_geo_df[
            foreign_geo_df["destination"] == selected_destination
        ]

        if not selected_foreign.empty:
            foreign = selected_foreign.iloc[0]

            folium.Marker(
                location=[foreign["lat"], foreign["lon"]],
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
            [foreign["lat"], foreign["lon"]]
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