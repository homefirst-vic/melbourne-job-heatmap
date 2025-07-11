import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import json

# Page config
st.set_page_config(layout="wide", page_title="Melbourne Job Heatmap")
st.title("Melbourne Job Heatmap Dashboard")

# Load data files
@st.cache_data
def load_data():
    rev_df = pd.read_excel("Rev Report Chat GPT.xlsx", engine="openpyxl")
    conv_df = pd.read_excel("Conversion Report Chat GPT.xlsx", engine="openpyxl")
    with open("vic_postcodes_simplified.geojson") as f:
        geojson = json.load(f)
    return rev_df, conv_df, geojson

rev_df, conv_df, geojson = load_data()

# Prepare Revenue Data
rev_df = rev_df.rename(columns={
    "Location Zip": "Postal Code",
    "Jobs Subtotal": "Revenue",
    "Jobs Gross Margin %": "Gross Margin",
    "Business Unit": "Business Unit",
    "Campaign Category": "Campaign"
})
rev_df = rev_df[rev_df["Postal Code"].notnull()]  # Clean null Zips
rev_df["Postal Code"] = rev_df["Postal Code"].astype(int)

# Prepare Conversion Data
conv_df = conv_df.rename(columns={
    "Location Zip": "Postal Code",
    "Jobs Estimate Sales Subtotal": "Estimate Subtotal",
    "Business Unit": "Business Unit"
})
conv_df = conv_df[conv_df["Postal Code"].notnull()]
conv_df["Postal Code"] = conv_df["Postal Code"].astype(int)

# Mark as converted or not
conv_df["Converted"] = conv_df["Estimate Subtotal"] < 101
conversion_summary = conv_df.groupby("Postal Code")["Converted"].agg(["sum", "count"])
conversion_summary["Conversion Rate"] = (conversion_summary["sum"] / conversion_summary["count"]) * 100
conversion_summary = conversion_summary.reset_index()

# Sidebar filters
st.sidebar.header("Filters")
bu_options = rev_df["Business Unit"].dropna().unique().tolist()
selected_bu = st.sidebar.multiselect("Business Unit", bu_options, default=bu_options)
campaign_options = rev_df["Campaign"].dropna().unique().tolist()
selected_campaigns = st.sidebar.multiselect("Campaign Category", campaign_options, default=campaign_options)

# Merge filtered data for map
filtered_df = rev_df[(rev_df["Business Unit"].isin(selected_bu)) & (rev_df["Campaign"].isin(selected_campaigns))].copy()
revenue_summary = filtered_df.groupby("Postal Code")["Revenue"].sum().reset_index()

# Join with conversion rates
merged_df = pd.merge(revenue_summary, conversion_summary, on="Postal Code", how="left")

# Ensure valid data types
merged_df = merged_df[merged_df["Postal Code"].notnull() & merged_df["Revenue"].notnull()]
merged_df["Postal Code"] = merged_df["Postal Code"].astype(int)

# Toggle map type
map_type = st.radio("Select overlay:", ["Revenue", "Conversion Rate"])

# Create Folium map
m = folium.Map(location=[-37.8136, 144.9631], zoom_start=10)

# Choropleth rendering
if map_type == "Revenue":
    folium.Choropleth(
        geo_data=geojson,
        data=merged_df,
        columns=["Postal Code", "Revenue"],
        key_on="feature.properties.POA_CODE21",
        fill_color="YlGnBu",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Revenue ($)"
    ).add_to(m)
else:
    folium.Choropleth(
        geo_data=geojson,
        data=merged_df,
        columns=["Postal Code", "Conversion Rate"],
        key_on="feature.properties.POA_CODE21",
        fill_color="OrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Conversion Rate (%)"
    ).add_to(m)

# Show map
st_data = st_folium(m, width=1100, height=650)
