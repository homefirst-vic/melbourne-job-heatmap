import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium import Choropleth
from branca.colormap import linear

# Page config
st.set_page_config(layout="wide")
st.title("Melbourne Job Heatmap Dashboard")

# --- Load data ---
@st.cache_data
def load_data():
    geojson_path = "vic_postcodes_simplified.geojson"
    jobs_df = pd.read_excel("Jobs Report Chat GPT.xlsx", engine="openpyxl")
    gdf = gpd.read_file(geojson_path)

    # Ensure postcode field is int for merge
    gdf["POA_CODE21"] = gdf["POA_CODE21"].astype(int)
    jobs_df["Job #"] = pd.to_numeric(jobs_df["Job #"], errors="coerce")

    # Extract postcode from job report (assumes postcode is last 4 digits in Location)
    jobs_df["Postcode"] = jobs_df["Location City"].str.extract(r"(\d{4})").astype(float)

    return gdf, jobs_df

gdf, jobs_df = load_data()

# --- Sidebar filters ---
st.sidebar.header("Filters")

bu_options = sorted(jobs_df["Business Unit"].dropna().unique())
selected_bu = st.sidebar.multiselect("Select Business Units", bu_options, default=bu_options)

campaign_options = sorted(jobs_df["Campaign Category"].dropna().unique())
selected_campaigns = st.sidebar.multiselect("Select Campaign Categories", campaign_options, default=campaign_options)

# --- Filtered job data ---
filtered_jobs = jobs_df[
    (jobs_df["Business Unit"].isin(selected_bu)) &
    (jobs_df["Campaign Category"].isin(selected_campaigns))
]

# --- Aggregate Revenue by postcode ---
agg = filtered_jobs.groupby("Postcode").agg({
    "Jobs Subtotal": "sum"
}).reset_index().rename(columns={"Jobs Subtotal": "Revenue"})

# Merge with GeoDataFrame
gdf["Postcode"] = gdf["POA_CODE21"]
merged = gdf.merge(agg, on="Postcode", how="left")
merged["Revenue"] = merged["Revenue"].fillna(0)

# --- Map rendering ---
m = folium.Map(location=[-37.8136, 144.9631], zoom_start=9, tiles="cartodbpositron")

# Create color scale
colormap = linear.YlGnBu_09.scale(merged["Revenue"].min(), merged["Revenue"].max())
colormap.caption = "Revenue ($)"

# Add Choropleth layer
Choropleth(
    geo_data=merged,
    name="choropleth",
    data=merged,
    columns=["Postcode", "Revenue"],
    key_on="feature.properties.Postcode",
    fill_color="YlGnBu",
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name="Revenue ($)",
    highlight=True
).add_to(m)

colormap.add_to(m)

st_folium(m, width=1100, height=650)

