import pandas as pd
from pathlib import Path
import geopandas as gpd
import streamlit as st
import pydeck as pdk
import altair as alt
import matplotlib.pyplot as plt

# Page config
st.set_page_config(page_title="Chicago EJ Typology Explorer", layout="wide")

# Quadrant config
QUAD_CONFIG = {
    0: {"label": "Low Socio – Low Exposure (LL)", "abbr": "LL", "color": [200, 200, 200], "hex": "#C8C8C8"},
    1: {"label": "Low Socio – High Exposure (LH)", "abbr": "LH", "color": [102, 194, 165], "hex": "#66C2A5"},
    2: {"label": "High Socio – Low Exposure (HL)", "abbr": "HL", "color": [252, 141, 98], "hex": "#FC8D62"},
    3: {"label": "High Socio – High Exposure (HH)", "abbr": "HH", "color": [141, 160, 203], "hex": "#8DA0CB"},
}

# Data loader
@st.cache_data
def load_data():
    # repo root: .../final-project_winter-2026/
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data" / "derived-data"
    path = data_dir / "combined.geojson"

# Read
    gdf = gpd.read_file(path)

    # Percentiles (for static maps)
    if "socio_index" in gdf.columns:
        gdf["socio_percentile"] = gdf["socio_index"].rank(pct=True)
    if "env_exposure_index" in gdf.columns:
        gdf["env_percentile"] = gdf["env_exposure_index"].rank(pct=True)

    # CRS
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    # Deduplicate GEOID if present
    if "GEOID" in gdf.columns and gdf["GEOID"].duplicated().any():
        gdf = gdf.sort_values("GEOID").drop_duplicates(subset=["GEOID"], keep="first")

    # Simplified geometry for smoother rendering
    gdf_low_res = gdf.copy()
    gdf_low_res["geometry"] = gdf_low_res["geometry"].simplify(0.0005, preserve_topology=True)

    return gdf, gdf_low_res

# Helpers
def assign_quadrant(df, socio_th=0.0, expo_th=0.0):
    socio_hi = df["socio_index"] > socio_th
    expo_hi = df["env_exposure_index"] > expo_th
    return (socio_hi.astype(int) * 2 + expo_hi.astype(int))
    
# Load data
gdf, gdf_altair = load_data()

# Sidebar
with st.sidebar:
    st.header("Classification Settings")

    mode = st.radio(
        "Threshold Mode",
        ["Mean", "Median", "Manual"],
        help=(
            "Mean: Uses the city-wide average as the cutoff point; "
            "Median: Uses the median (50th percentile ranking) to ensure a more balanced sample distribution; "
            "Manual: Custom cutoff value."
        ),
    )

    if mode == "Mean":
        st.info("Division based on **Average (0.0)** of Chicago")
        socio_th, expo_th = 0.0, 0.0
    elif mode == "Median":
        st.info("Division based on **Median (50th Percentile)** of Chicago")
        socio_th = float(gdf["socio_index"].median())
        expo_th = float(gdf["env_exposure_index"].median())
    else:
        socio_th = st.slider("Socio-Vulnerability Threshold", -3.0, 3.0, 0.0)
        expo_th = st.slider("Env-Exposure Threshold", -3.0, 3.0, 0.0)

    show_quads = st.multiselect(
        "Filter Typologies",
        options=[0, 1, 2, 3],
        default=[0, 1, 2, 3],
        format_func=lambda x: QUAD_CONFIG[x]["label"],
    )

# Assign quadrants + display fields
gdf["quadrant"] = assign_quadrant(gdf, socio_th, expo_th)
gdf["quad_label"] = gdf["quadrant"].map(lambda x: QUAD_CONFIG[int(x)]["label"])
gdf["quad_abbr"] = gdf["quadrant"].map(lambda x: QUAD_CONFIG[int(x)]["abbr"])
gdf["fill_color"] = gdf["quadrant"].map(lambda x: QUAD_CONFIG[int(x)]["color"])

gdf_show = gdf[gdf["quadrant"].isin(show_quads)].copy()
gdf_show["socio_index"] = gdf_show["socio_index"].round(3)
gdf_show["env_exposure_index"] = gdf_show["env_exposure_index"].round(3)

# Main page
st.title("Chicago Environmental Justice (EJ) Typology")

tab_interactive, tab_static = st.tabs(["Interactive Map", "Static Maps"])

# Interactive tab
with tab_interactive:
    view_state = pdk.ViewState(latitude=41.8781, longitude=-87.6298, zoom=10, pitch=0)

    layer = pdk.Layer(
        "GeoJsonLayer",
        gdf_show,  # you can switch to gdf_altair if you want simplified
        pickable=True,
        opacity=0.7,
        get_fill_color="fill_color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=0.5,
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={
                "text": (
                    "Community: {community}\n"
                    "Type: {quad_label}\n"
                    "Socio Index: {socio_index}\n"
                    "Env Index: {env_exposure_index}"
                )
            },
        )
    )

    st.markdown("### Typology Legend")
    leg_cols = st.columns(4)
    for i, (_, v) in enumerate(QUAD_CONFIG.items()):
        leg_cols[i].markdown(
            f"""
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 20px; height: 20px; background-color: rgb{tuple(v['color'])}; border: 1px solid white; margin-right: 10px;"></div>
                <span style="font-size: 0.9rem;">{v['label']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Static tab
with tab_static:
    st.header("Static Visualization")
    st.markdown("### Standardized Index Spatial Distribution")

    col1, col2 = st.columns([1, 1])

    with col1:
        fig, ax = plt.subplots(figsize=(7, 7))
        gdf.plot(
            column="socio_percentile",
            cmap="YlOrRd",
            legend=True,
            legend_kwds={"label": "Socioeconomic Percentile", "orientation": "horizontal", "pad": 0.01, "shrink": 0.6, "aspect": 30},
            ax=ax,
        )
        ax.set_axis_off()
        ax.set_title("Socioeconomic Vulnerability", fontsize=11, fontweight="bold", pad=5)
        plt.subplots_adjust(left=0, right=1, top=0.9, bottom=0.1)
        st.pyplot(fig)

    with col2:
        fig, ax = plt.subplots(figsize=(7, 6.9))
        gdf.plot(
            column="env_percentile",
            cmap="viridis",
            legend=True,
            legend_kwds={"label": "Environmental Percentile", "orientation": "horizontal", "pad": 0.01, "shrink": 0.6, "aspect": 30},
            ax=ax,
        )
        ax.set_axis_off()
        ax.set_title("Environmental Exposure", fontsize=11, fontweight="bold", pad=5)
        plt.subplots_adjust(left=0, right=1, top=0.9, bottom=0.1)
        st.pyplot(fig)

    st.divider()
    st.subheader("Typology Cross-Analysis (Scatter Plot)")

    domain_labels = [v["label"] for v in QUAD_CONFIG.values()]
    range_colors = [v["hex"] for v in QUAD_CONFIG.values()]

    scatter = (
        alt.Chart(gdf)
        .mark_circle(opacity=0.6, size=50)
        .encode(
            x=alt.X("socio_index:Q", title="Socioeconomic Vulnerability (std)"),
            y=alt.Y("env_exposure_index:Q", title="Environmental Exposure (std)"),
            color=alt.Color(
                "quad_label:N",
                scale=alt.Scale(domain=domain_labels, range=range_colors),
                legend=alt.Legend(orient="none", title="Quadrant:", legendX=10, legendY=10, fillColor="white", padding=5, labelLimit=300),
            ),
            tooltip=["community:N", "socio_index:Q", "env_exposure_index:Q"],
        )
        .properties(width=700, height=450)
    )

    vline = alt.Chart(pd.DataFrame({"x": [socio_th]})).mark_rule(strokeDash=[3, 3]).encode(x="x:Q")
    hline = alt.Chart(pd.DataFrame({"y": [expo_th]})).mark_rule(strokeDash=[3, 3]).encode(y="y:Q")

    st.altair_chart(scatter + vline + hline, use_container_width=True)

# Rankings
st.divider()

with st.expander("View Community Rankings (Top 20 High-Environmental-Exposure)"):
    top_20 = gdf.sort_values("env_exposure_index", ascending=False).head(20)
    st.dataframe(
        top_20[["community", "socio_index", "env_exposure_index", "quad_label"]],
        column_config={
            "community": "Community Name",
            "socio_index": "Socio Score",
            "env_exposure_index": "Env Score",
            "quad_label": "Typology Classification",
        },
        use_container_width=True,
        hide_index=True,
    )

st.caption("Data Source: Chicago Census Tracts - EJ Analysis Framework")
