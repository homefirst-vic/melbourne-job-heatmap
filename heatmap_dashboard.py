import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import json

# --- Load data ---
rev_df = pd.read_excel("Rev Report Chat GPT.xlsx", engine="openpyxl")
conv_df = pd.read_excel("Conversion Report Chat GPT.xlsx", engine="openpyxl")

# --- Preprocess revenue report ---
rev_df = rev_df.dropna(subset=["Location Zip"])
rev_df["Location Zip"] = rev_df["Location Zip"].astype(str).str.zfill(4)
rev_df["Revenue"] = pd.to_numeric(rev_df["Jobs Subtotal"], errors="coerce")
rev_df["Gross Margin"] = pd.to_numeric(rev_df["Jobs Gross Margin %"], errors="coerce")

# --- Preprocess conversion report ---
conv_df = conv_df.dropna(subset=["Location Zip"])
conv_df["Location Zip"] = conv_df["Location Zip"].astype(str).str.zfill(4)
conv_df["Converted"] = conv_df["Jobs Estimate Sales Subtotal"] < 101
conv_summary = conv_df.groupby("Location Zip")["Converted"].agg(["sum", "count"])
conv_summary["Conversion Rate"] = (conv_summary["sum"] / conv_summary["count"]) * 100
conv_summary = conv_summary.reset_index().rename(columns={"Location Zip": "Postal Code"})

# --- Aggregate revenue and gross margin ---
rev_summary = rev_df.groupby("Location Zip").agg({
    "Revenue": "sum",
    "Gross Margin": "mean"
}).reset_index().rename(columns={"Location Zip": "Postal Code"})

# --- Merge both summaries ---
merged_df = pd.merge(rev_summary, conv_summary, on="Postal Code", how="outer")
merged_df = merged_df.fillna(0)

# --- Sidebar filters ---
st.sidebar.header("Filters")
business_units = sorted(rev_df["Business Unit"].dropna().unique())
campaigns = sorted(rev_df["Campaign Category"].dropna().unique())

selected_bu = st.sidebar.multiselect("Select Business Units", business_units, default=business_units)
selected_cc = st.sidebar.multiselect("Select Campaign Categories", campaigns, default=campaigns)

filtered_rev = rev_df[rev_df["Business Unit"].isin(selected_bu) & rev_df["Campaign Category"].isin(selected_cc)]

# --- Recalculate revenue summary after filters ---
rev_filtered_summary = filtered_rev.groupby("Location Zip").agg({
    "Jobs Subtotal": "sum",
    "Jobs Gross Margin %": "mean"
}).reset_index().rename(columns={
    "Location Zip": "Postal Code",
    "Jobs Subtotal": "Revenue",
    "Jobs Gross Margin %": "Gross Margin"
})

merged_df = pd.merge(rev_filtered_summary, conv_summary, on="Postal Code", how="outer").fillna(0)

# --- Load GeoJSON ---
with open("vic_postcodes_simplified.geojson", "r") as f:
    geojson = json.load(f)

# --- Inject data safely into geojson ---
for feature in geojson["features"]:
    props = feature.get("properties", {})
    try:
        pc = int(props.get("POA_CODE21", 0))
    except:
        pc = None

    row = merged_df[merged_df["Postal Code"] == str(pc).zfill(4)]

    revenue = round(float(row["Revenue"].values[0]), 2) if not row.empty and "Revenue" in row else 0.0
    conversion = round(float(row["Conversion Rate"].values[0]), 2) if not row.empty and "Conversion Rate" in row else 0.0
    margin = round(float(row["Gross Margin"].values[0]), 2) if not row.empty and "Gross Margin" in row else 0.0

    props["Revenue"] = revenue
    props["Conversion Rate"] = conversion
    props["Gross Margin"] = margin
    feature["properties"] = props

# --- Streamlit UI ---
st.title("Melbourne Job Heatmap Dashboard")

layer_option = st.radio("Select Metric to Display", ["Revenue", "Conversion Rate", "Gross Margin"], horizontal=True)

# --- Create Folium map ---
m = folium.Map(location=[-37.8136, 144.9631], zoom_start=10, control_scale=True)

# --- Color scale settings ---
if layer_option == "Revenue":
    key = "Revenue"
    colormap = folium.LinearColormap(colors=["#ffffcc", "#41b6c4", "#253494"], vmin=merged_df["Revenue"].min(), vmax=merged_df["Revenue"].max(), caption="Revenue ($)")
elif layer_option == "Conversion Rate":
    key = "Conversion Rate"
    colormap = folium.LinearColormap(colors=["#fee5d9", "#fcae91", "#cb181d"], vmin=0, vmax=100, caption="Conversion Rate (%)")
else:
    key = "Gross Margin"
    colormap = folium.LinearColormap(colors=["#f7fcf5", "#74c476", "#00441b"], vmin=0, vmax=100, caption="Gross Margin (%)")

style_function = lambda feature: {
    'fillColor': colormap(feature['properties'][key]),
    'color': 'black',
    'weight': 0.5,
    'fillOpacity': 0.7,
}

tooltip = folium.GeoJsonTooltip(
    fields=["POA_CODE21", "Revenue", "Conversion Rate", "Gross Margin"],
    aliases=["Postcode", "Revenue ($)", "Conversion Rate (%)", "Gross Margin (%)"],
    localize=True
)

folium.GeoJson(
    geojson,
    name="Postcodes",
    style_function=style_function,
    tooltip=tooltip
).add_to(m)

colormap.add_to(m)

st_data = st_folium(m, width=1100, height=650)
