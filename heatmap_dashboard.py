import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import json

st.set_page_config(layout="wide", page_title="Melbourne Job Heatmap")
st.title("Melbourne Job Heatmap Dashboard")

@st.cache_data
def load_data():
    rev_df = pd.read_excel("Rev Report Chat GPT.xlsx", engine="openpyxl")
    conv_df = pd.read_excel("Conversion Report Chat GPT.xlsx", engine="openpyxl")
    with open("vic_postcodes_simplified.geojson") as f:
        geojson = json.load(f)
    return rev_df, conv_df, geojson

rev_df, conv_df, geojson = load_data()

# --- Rename and clean Revenue Data
rev_df = rev_df.rename(columns={
    "Location Zip": "Postal Code",
    "Jobs Subtotal": "Revenue",
    "Jobs Gross Margin %": "Gross Margin",
    "Business Unit": "Business Unit",
    "Campaign Category": "Campaign"
})
rev_df = rev_df[rev_df["Postal Code"].notnull()]
rev_df["Postal Code"] = rev_df["Postal Code"].astype(int)

# --- Rename and clean Conversion Data
conv_df = conv_df.rename(columns={
    "Location Zip": "Postal Code",
    "Jobs Estimate Sales Subtotal": "Estimate Subtotal",
    "Business Unit": "Business Unit"
})
conv_df = conv_df[conv_df["Postal Code"].notnull()]
conv_df["Postal Code"] = conv_df["Postal Code"].astype(int)
conv_df["Converted"] = conv_df["Estimate Subtotal"] < 101

# --- Aggregate Conversion
conversion_summary = conv_df.groupby("Postal Code")["Converted"].agg(["sum", "count"]).reset_index()
conversion_summary["Conversion Rate"] = (conversion_summary["sum"] / conversion_summary["count"]) * 100

# --- Sidebar filters
st.sidebar.header("Filters")
bu_options = rev_df["Business Unit"].dropna().unique().tolist()
selected_bu = st.sidebar.multiselect("Business Unit", bu_options, default=bu_options)
campaign_options = rev_df["Campaign"].dropna().unique().tolist()
selected_campaigns = st.sidebar.multiselect("Campaign Category", campaign_options, default=campaign_options)

# --- Filter and summarize Revenue
filtered_df = rev_df[(rev_df["Business Unit"].isin(selected_bu)) & (rev_df["Campaign"].isin(selected_campaigns))].copy()
revenue_summary = filtered_df.groupby("Postal Code").agg({
    "Revenue": "sum",
    "Gross Margin": "mean"
}).reset_index()

# --- Merge revenue and conversion
merged_df = pd.merge(revenue_summary, conversion_summary[["Postal Code", "Conversion Rate"]], on="Postal Code", how="left")
merged_df = merged_df.dropna(subset=["Postal Code", "Revenue"])
merged_df["Postal Code"] = merged_df["Postal Code"].astype(int)

# --- Map layer selection
map_type = st.radio("Select overlay:", ["Revenue", "Conversion Rate", "Gross Margin %"])

# --- Create map
m = folium.Map(location=[-37.8136, 144.9631], zoom_start=10)

# --- Tooltip Setup
tooltip_fields = ["Postal Code", "Revenue", "Conversion Rate", "Gross Margin"]
tooltip_aliases = ["Postal Code:", "Revenue ($):", "Conversion Rate (%):", "Gross Margin (%):"]

# --- Merge map data with GeoJSON features
for feature in geojson["features"]:
    pc = int(feature["properties"]["POA_CODE21"])
    match = merged_df[merged_df["Postal Code"] == pc]
    if not match.empty:
        row = match.iloc[0]
        feature["properties"]["Revenue"] = round(row["Revenue"], 2)
        feature["properties"]["Conversion Rate"] = round(row.get("Conversion Rate", 0.0), 2)
        feature["properties"]["Gross Margin"] = round(row["Gross Margin"], 2)
    else:
        feature["properties"]["Revenue"] = 0
        feature["properties"]["Conversion Rate"] = 0
        feature["properties"]["Gross Margin"] = 0

# --- Choose data layer for choropleth
if map_type == "Revenue":
    data_col = "Revenue"
    color = "YlGnBu"
    legend = "Revenue ($)"
elif map_type == "Conversion Rate":
    data_col = "Conversion Rate"
    color = "OrRd"
    legend = "Conversion Rate (%)"
else:
    data_col = "Gross Margin"
    color = "BuPu"
    legend = "Gross Margin (%)"

folium.Choropleth(
    geo_data=geojson,
    data=merged_df,
    columns=["Postal Code", data_col],
    key_on="feature.properties.POA_CODE21",
    fill_color=color,
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name=legend,
).add_to(m)

# --- Add hover tooltip
folium.GeoJson(
    geojson,
    name="Postal Areas",
    tooltip=folium.GeoJsonTooltip(
        fields=tooltip_fields,
        aliases=tooltip_aliases,
        localize=True,
        sticky=True
    )
).add_to(m)

# --- Render map
st_folium(m, width=1100, height=650)
