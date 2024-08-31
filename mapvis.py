#!/usr/bin/env python3

import sys
from functools import partial
import json
from pathlib import Path
import gradio as gr
import pandas as pd
import plotly.graph_objects as go


BASEDIR = Path(".")  # FIXME for the frozen state


try:
    with open(BASEDIR / "Secrets" / "mapbox_token.txt") as fp:
        MAPBOX_TOKEN = fp.read().strip()
except IOError:
    MAPBOX_TOKEN = None


try:
    with open(BASEDIR / "Secrets" / "stadia_maps_api_key.txt") as fp:
        STADIA_MAPS_API_KEY = fp.read().strip()
except IOError:
    STADIA_MAPS_API_KEY = None


# https://docs.mapbox.com/mapbox-gl-js/guides/styles/
# https://community.plotly.com/t/how-to-change-mapbox-language/42056/2
MAPBOX_STYLES = {
    "navigation-day": "mapbox://styles/mapbox/navigation-day-v1",
    "navigation-night": "mapbox://styles/mapbox/navigation-night-v1",

    "light-rus": "mapbox://styles/shura1oplot/clztlhw0f00fl01qof3dbahjt",
    "dark-rus": "mapbox://styles/shura1oplot/clztmf5yo003z01p90h07cthn",
}


with open(BASEDIR / "Database" / "russian_regions_geojson.json",
          encoding="utf-8") as fp:
    RUSSIAN_REGIONS = json.load(fp)


def create_map(excel_file,
               filter_columns,
               mapbox_style,
               mapbox_style_custom,
               extra_layers,
               *filter_values):
    map_layers = []

    xls = pd.ExcelFile(excel_file)

    for sheet_name in xls.sheet_names:
        if sheet_name.startswith("_"):
            continue

        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        for column, values in zip(filter_columns, filter_values):
            if column not in df.columns:
                continue

            if not values:
                continue

            if "All, except" in values:
                df = df[~df[column].isin(values)]
            else:
                df = df[df[column].isin(values)]

        if "lat1" in df.columns and "lon1" in df.columns \
                and "lat2" in df.columns and "lon2" in df.columns:
            for _, row in df.iterrows():
                map_layers.append(
                    go.Scattermapbox(
                        mode="lines",
                        lon=[row["lon1"], row["lon2"]],
                        lat=[row["lat1"], row["lat2"]],
                        line=dict(width=row.get("line_width", 2),
                                  color=row.get("line_color", "blue")),
                        text=df.get("name", "Unnamed"),
                        hoverinfo="none",
                        name=sheet_name,
                    )
                )
        elif "lat" in df.columns and "lon" in df.columns:
            map_layers.append(
                go.Scattermapbox(
                    mode="markers",
                    lon=df["lon"],
                    lat=df["lat"],
                    marker=dict(size=df.get("marker_size", 10),
                                color=df.get("marker_color", "red"),
                                # https://labs.mapbox.com/maki-icons/
                                symbol=df.get("marker_symbol", "circle"),
                                opacity=df.get("marker_opacity", 1)),
                    text=df.get("name", "Unnamed"),
                    hoverinfo="text",
                    name=sheet_name,
                )
            )
        else:
            raise ValueError(f"'{sheet_name}': wrong format")

    xls.close()

    extra_layer_features = []

    if extra_layers:
        for feature in RUSSIAN_REGIONS["features"]:
            if feature["id"].startswith("node/"):
                continue

            admin_level = feature["properties"]["admin_level"]
            relation_id = int(feature["id"].removeprefix("relation/"))
            is_new_territories = relation_id in \
                (71971, 71973, 71980, 71022)

            if admin_level == "3":
                type_ = "Federal districts"
            elif is_new_territories:
                type_ = "Oblasts (new territories)"
            else:
                type_ = "Oblasts"

            if type_ in extra_layers:
                extra_layer_features.append(feature)

    mapbox_style = mapbox_style or "open-street-map"
    mapbox_style = MAPBOX_STYLES.get(mapbox_style, mapbox_style)

    if mapbox_style == "custom":
        mapbox_style = mapbox_style_custom

    if mapbox_style.startswith("stamen-"):
        mapbox_accesstoken = STADIA_MAPS_API_KEY
    else:
        mapbox_accesstoken = MAPBOX_TOKEN

    fig = go.Figure(map_layers)
    fig.update_layout(
        mapbox=dict(
            style=mapbox_style,
            accesstoken=mapbox_accesstoken,
            center=dict(lat=55.751244, lon=37.618423),  # Moscow
            # zoom=1,
            # https://plotly.com/python/filled-area-on-mapbox/
            # https://plotly.com/python/reference/scattermapbox/
            layers=[dict(source={"type": "FeatureCollection",
                                 "features": extra_layer_features},
                         type="fill",
                         below="traces",
                         color="#d6d6d6")],
        ),
        showlegend=False,
        margin={"r":0,"t":0,"l":0,"b":0}
    )

    return fig


def generate_filter_options(excel_file):
    xls = pd.ExcelFile(excel_file)
    filter_options = {}

    exclude_columns = {"name", "lat", "lon", "lat1", "lon1", "lat2", "lon2",
                       "marker_size", "marker_color", "marker_symbol",
                       "marker_opacity", "line_width", "line_color"}

    for sheet_name in xls.sheet_names:
        if sheet_name.startswith("_"):
            continue

        df = pd.read_excel(xls, sheet_name=sheet_name)

        for column in df.columns:
            if column in exclude_columns:
                continue

            if column.startswith("_"):
                continue

            if column not in filter_options:
                filter_options[column] = set()

            filter_options[column].update(df[column].dropna().unique())

    for column in filter_options:
        filter_options[column] = ["All, except"] + sorted(filter_options[column])

    return filter_options


def main(argv=sys.argv):
    with gr.Blocks() as demo:
        with gr.Row():
            input_file = gr.File(
                label="Select Excel File",
                file_types=[".xlsx", ".xlsm"])

        with gr.Row():
            with gr.Column(scale=1):
                map_style = gr.Dropdown(
                    choices=["open-street-map",
                             "white-bg",
                             "basic",
                             "streets",
                             "outdoors",
                             "light",
                             "light-rus",
                             "dark",
                             "dark-rus",
                             "satellite",
                             "satellite-streets",
                             "navigation-day",
                             "navigation-night",
                             # "stamen-terrain",
                             # "stamen-toner",
                             # "stamen-watercolor",
                             "carto-darkmatter",
                             "carto-positron",
                             "custom",
                            ],
                    label="Map style")

                map_style_custom = gr.Textbox(
                    interactive=True,
                    visible=False,
                    label="Custom map style")

                map_style.select(fn=lambda sel: gr.update(visible=sel == "custom"),
                                 inputs=[map_style],
                                 outputs=[map_style_custom])

                extra_layers = gr.Dropdown(
                        choices=["Federal districts",
                                 "Oblasts",
                                 "Oblasts (new territories)"],
                        multiselect=True,
                        label="Extra layers")

                clear_btn = None
                submit_btn = None
                output = None

                @gr.render(inputs=[input_file])
                def update_layout(excel_file):
                    nonlocal clear_btn
                    nonlocal submit_btn
                    nonlocal output

                    if not excel_file:
                        return

                    inputs = [map_style, map_style_custom, extra_layers]
                    filters = []
                    filter_columns = []

                    filter_options = generate_filter_options(excel_file)

                    for column, options in filter_options.items():
                        filter_columns.append(column)
                        dropdown = gr.Dropdown(choices=options,
                                               multiselect=True,
                                               label=f"Filter by {column}")

                        filters.append(dropdown)
                        inputs.append(dropdown)

                    clear_btn.click(fn=lambda: [[]] * len(filters),
                                    outputs=filters)

                    submit_btn.click(fn=partial(create_map,
                                                excel_file,
                                                filter_columns),
                                     inputs=inputs,
                                     outputs=output)

                with gr.Row():
                    clear_btn = gr.ClearButton()
                    submit_btn = gr.Button("Submit")

            with gr.Column(scale=4):
                output = gr.Plot(label="Map")

    demo.launch()


if __name__ == "__main__":
    sys.exit(main())
