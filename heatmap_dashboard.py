import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium import Choropleth, GeoJson
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

    # Ensure matching dtype
    gdf["POA_CODE21"] = gdf["POA_CODE21"].astype(int)
    gdf["Postcode"] = gdf["POA_CODE21"].astype(str)

    # Extract postcode from location string if needed
    jobs_df["Postcode"] = jobs_df["Location City"].str.extract(r"(\d{4})")
    jobs_df["Postcode"] = jobs_df["Postcode"].astype(str)

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

# --- Aggregate Revenue by Postcode ---
agg = filtered_jobs.groupby("Postcode").agg({
    "Jobs Subtotal": "sum"
}).reset_index().rename(columns={"Jobs Subtotal": "Revenue"})

# Merge with geodata
merged = gdf.merge(agg, on="Postcode", how="left")
merged["Revenue"] = merged["Revenue"].fillna(0)

# --- Create Map ---
m = folium.Map(location=[-37.8136, 144.9631], zoom_start=9, tiles="cartodbpositron")

# Colormap
min_rev = merged["Revenue"].min()
max_rev = merged["Revenue"].max()
colormap = linear.YlOrRd_09.scale(min_rev, max_rev)
colormap.caption = "Revenue ($)"
colormap.add_to(m)

# Add Choropleth manually with hover tooltip
def style_function(feature):
    rev = feature["properties"].get("Revenue", 0)
    return {
        "fillOpacity": 0.7,
        "weight": 0.5,
        "color": "black",
        "fillColor": colormap(rev),
    }

tooltip = folium.GeoJsonTooltip(
    fields=["Postcode", "Revenue"],
    aliases=["Postcode:", "Revenue ($):"],
    localize=True
)

GeoJson(
    merged,
    name="Revenue",
    style_function=style_function,
    tooltip=tooltip
).add_to(m)

st_folium(m, width=1100, height=650)
