import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.features import GeoJsonTooltip
import branca.colormap as cm

# ----------------------
# Load Data
# ----------------------

@st.cache_data

def load_geojson():
    return gpd.read_file("vic_postcodes_simplified.geojson")

def load_report():
    df = pd.read_excel("Conversion Report Chat GPT.xlsx", engine="openpyxl")
    df["POA_CODE21"] = df["POA_CODE21"].astype(str).str.strip()  # Ensure match format
    return df

gdf = load_geojson()
report_df = load_report()

# ----------------------
# Sidebar Filters
# ----------------------

st.sidebar.title("Filters")

available_bu = sorted(report_df["Business Unit"].dropna().unique())
bu_selection = st.sidebar.multiselect("Select Business Units", available_bu, default=available_bu)

available_categories = sorted(report_df["Campaign Category"].dropna().unique())
category_selection = st.sidebar.multiselect("Select Campaign Categories", available_categories, default=available_categories)

# ----------------------
# Filter & Aggregate
# ----------------------

filtered_df = report_df[
    (report_df["Business Unit"].isin(bu_selection)) &
    (report_df["Campaign Category"].isin(category_selection))
]

agg_df = filtered_df.groupby("POA_CODE21").agg({
    "Revenue": "sum",
    "Conversion Rate": "mean",
    "Jobs Gross Margin %": "mean"
}).reset_index()

# ----------------------
# Merge with Geo Data
# ----------------------

gdf["POA_CODE21"] = gdf["POA_CODE21"].astype(str).str.strip()
merged = gdf.merge(agg_df, on="POA_CODE21", how="left")

# ----------------------
# Select Metric
# ----------------------

st.title("Melbourne Job Heatmap Dashboard")

metric = st.radio("Select Metric to Display", ["Revenue", "Conversion Rate", "Gross Margin"], horizontal=True)

if metric == "Revenue":
    display_col = "Revenue"
    legend_label = "Revenue ($)"
    color_scale = cm.linear.OrRd_09.scale(merged[display_col].min(), merged[display_col].max())
elif metric == "Conversion Rate":
    display_col = "Conversion Rate"
    legend_label = "Conversion Rate (%)"
    color_scale = cm.linear.Blues_09.scale(merged[display_col].min(), merged[display_col].max())
else:
    display_col = "Jobs Gross Margin %"
    legend_label = "Gross Margin (%)"
    color_scale = cm.linear.Greens_09.scale(merged[display_col].min(), merged[display_col].max())

# ----------------------
# Create Map
# ----------------------

m = folium.Map(location=[-37.8136, 144.9631], zoom_start=10, control_scale=True)

# Add choropleth
folium.GeoJson(
    merged,
    name="Postcodes",
    style_function=lambda feature: {
        "fillColor": color_scale(feature["properties"].get(display_col, 0)) if feature["properties"].get(display_col) is not None else "#ccc",
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.7,
    },
    tooltip=GeoJsonTooltip(
        fields=["POA_CODE21", "Revenue", "Conversion Rate", "Jobs Gross Margin %"],
        aliases=["Postcode:", "Revenue:", "Conversion Rate:", "Gross Margin %:"],
        localize=True
    )
).add_to(m)

color_scale.caption = legend_label
color_scale.add_to(m)

st_folium(m, width=1100, height=650)
