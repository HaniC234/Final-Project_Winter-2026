import pandas as pd
from pathlib import Path
import os
import geopandas as gpd
from shapely.geometry import Point
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask
from rasterstats import zonal_stats
import numpy as np

import matplotlib.pyplot as plt
import seaborn as sns

import streamlit as st
import pydeck as pdk
import altair as alt



st.set_page_config(page_title="Chicago Justice Typology", layout="wide")

@st.cache_data
def load_data(path="data/derived-data/combined.geojson"):
    gdf = gpd.read_file(path)
    
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    if gdf["GEOID"].duplicated().any():
        
        numeric_cols = ["socio_index", "env_exposure_index", "lst_summer_mean", "road_density"]
        valid_numeric = [c for c in numeric_cols if c in gdf.columns]
        gdf = gdf.sort_values("GEOID").drop_duplicates(subset=["GEOID"], keep="first")

    return gdf

def assign_quadrant(df, socio_th=0.0, expo_th=0.0):
    socio_hi = df["socio_index"] > socio_th
    expo_hi = df["env_exposure_index"] > expo_th

    # 0 LL, 1 LH, 2 HL, 3 HH
    quad = (socio_hi.astype(int) * 2) + (expo_hi.astype(int) * 1)
    return quad

# Load
gdf = load_data()
st.write("Rows:", len(gdf))
st.write("CRS:", gdf.crs)
st.title("Environmental Justice Typology (Chicago Census Tracts)")

# Sidebar controls
st.sidebar.header("Typology Controls")

mode = st.sidebar.radio("Threshold mode", ["Standardized Threshold (Mean=0)", "Percentile Threshold"], index=0)

if mode == "Standardized Threshold (Mean=0)":
    socio_th = st.sidebar.slider("Socio Vulnerability threshold", -2.0, 2.0, 0.0, 0.1)
    expo_th  = st.sidebar.slider("Environmental Exposure threshold", -2.0, 2.0, 0.0, 0.1)
else:
    socio_p = st.sidebar.slider("Socio Vulnerability percentile (e.g., 75 = top 25%)", 50, 95, 75, 1)
    expo_p  = st.sidebar.slider("Environmental Exposure percentile", 50, 95, 75, 1)
    socio_th = float(np.nanpercentile(gdf["socio_index"], socio_p))
    expo_th  = float(np.nanpercentile(gdf["env_exposure_index"], expo_p))
    st.sidebar.caption(f"Socio threshold value: {socio_th:.3f}")
    st.sidebar.caption(f"Exposure threshold value: {expo_th:.3f}")

show_quads = st.sidebar.multiselect(
    "Show quadrants",
    options=[0,1,2,3],
    default=[0,1,2,3],
    format_func=lambda q: {0:"LL (Baseline)",1:"LH (High exposure, low vuln)",2:"HL (High vuln, low exposure)",3:"HH (EJ Priority)"}[q]
)

opacity = st.sidebar.slider("Map opacity", 0.1, 1.0, 0.65, 0.05)

# Compute quadrant + colors
gdf = gdf.copy()

gdf['socio_index'] = gdf['socio_index'].round(3)
gdf['env_exposure_index'] = gdf['env_exposure_index'].round(3)

gdf["quadrant"] = assign_quadrant(gdf, socio_th=socio_th, expo_th=expo_th)

# Filter
gdf_show = gdf[gdf["quadrant"].isin(show_quads)].copy()

# Color mapping (RGBA)
color_map = {
    0: [200, 200, 200],  # LL
    1: [102, 194, 165],  # LH
    2: [252, 141, 98],   # HL
    3: [141, 160, 203],  # HH
}
gdf_show["fill_color"] = gdf_show["quadrant"].map(color_map)

# Center map on Chicago
center_lat = float(gdf.geometry.centroid.y.mean())
center_lon = float(gdf.geometry.centroid.x.mean())

# Convert to GeoJSON dict for pydeck
geojson = gdf_show.__geo_interface__

layer = pdk.Layer(
    "GeoJsonLayer",
    data=geojson,
    opacity=opacity,
    stroked=True,
    filled=True,
    get_fill_color="properties.fill_color",
    get_line_color=[80, 80, 80],
    line_width_min_pixels=0.5,
    pickable=True,
)

view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=9.5)

tooltip = {
    "html": """
        <div style="font-family: sans-serif; padding: 5px;">
            <b>Community:</b> {community} <br/>
            <hr style="margin: 5px 0;"/>
            <b>Socio Vulnerability:</b> {socio_index} <br/>
            <b>Env Exposure:</b> {env_exposure_index} <br/>
            <b>EJ Quadrant:</b> {quadrant}
        </div>
    """,
    "style": {
        "backgroundColor": "rgba(255, 255, 255, 0.9)",
        "color": "black",
        "border": "1px solid #777",
        "zIndex": "10000"
    }
}

# KPIs
col1, col2, col3, col4 = st.columns(4)

total = len(gdf)
hh = int((gdf["quadrant"] == 3).sum())
hh_share = hh / total if total else 0
corr = float(gdf[["socio_index","env_exposure_index"]].corr().iloc[0,1])

col1.metric("Total tracts", f"{total}")
col2.metric("HH (EJ Priority)", f"{hh}")
col3.metric("HH share", f"{hh_share:.1%}")
col4.metric("Corr(socio, exposure)", f"{corr:.3f}")

# Map
st.subheader("Interactive Map")
st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))

# Scatter with highlighted quadrant
st.subheader("Exposure vs Vulnerability (Scatter)")
plot_df = gdf.copy()
plot_df["quad_label"] = plot_df["quadrant"].map({
    0:"LL", 1:"LH", 2:"HL", 3:"HH"
})

color_map_hex = {
    0: "#C8C8C8",
    1: "#66C2A5",
    2: "#FC8D62",
    3: "#8DA0CB"
}
domain = ["LL", "LH", "HL", "HH"]
range_ = ["#C8C8C8", "#66C2A5", "#FC8D62", "#8DA0CB"]

scatter = alt.Chart(plot_df).mark_circle(opacity=0.55, size=45).encode(
    x=alt.X("socio_index:Q", title="Socioeconomic Vulnerability (std)"),
    y=alt.Y("env_exposure_index:Q", title="Environmental Exposure (std)"),
    color=alt.Color("quad_label:N", 
                    title="Quadrant",
                    scale=alt.Scale(domain=domain, range=range_)),
    tooltip=["GEOID:N","socio_index:Q","env_exposure_index:Q","quad_label:N"]
).properties(height=350)

vline = alt.Chart(pd.DataFrame({'x': [0]})).mark_rule(color='lightblue', strokeDash=[3,3]).encode(x='x:Q')
hline = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='lightblue', strokeDash=[3,3]).encode(y='y:Q')

final_chart = (scatter + vline + hline).properties(
    width=400,
    height=350,
    title="Environmental Justice Quadrant Analysis"
)

st.altair_chart(final_chart, use_container_width=True)

# Table
st.subheader("Tracts in Selected Quadrants (Top 20 by Environmental Exposure)")
table = gdf_show[["GEOID","NAME","socio_index","env_exposure_index","quadrant"]].copy()
table = table.sort_values("env_exposure_index", ascending=False).head(20)
st.dataframe(table, use_container_width=True)


gdf_show.columns
