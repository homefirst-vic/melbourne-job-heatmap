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

@st.cache_data
def load_data():
    # Load reports
    rev_df = pd.read_excel("Rev Report Chat GPT.xlsx", engine="openpyxl")
    conv_df = pd.read_excel("Conversion Report Chat GPT.xlsx", engine="openpyxl")

    # Clean columns
    rev_df.columns = rev_df.columns.str.strip()
    conv_df.columns = conv_df.columns.str.strip()

    # Normalize postcodes
    rev_df["Location Zip"] = rev_df["Location Zip"].astype(str).str.strip()
    conv_df["Location Zip"] = conv_df["Location Zip"].astype(str).str.strip()

    # Clean numeric fields
    rev_df["Jobs Subtotal"] = pd.to_numeric(rev_df["Jobs Subtotal"], errors='coerce')
    rev_df["Jobs Gross Margin %"] = pd.to_numeric(rev_df["Jobs Gross Margin %"], errors='coerce')
    conv_df["Jobs Estimate Sales Subtotal"] = pd.to_numeric(conv_df["Jobs Estimate Sales Subtotal"], errors='coerce')

    # Calculate conversion
    conv_df = conv_df.dropna(subset=["Location Zip", "Jobs Estimate Sales Subtotal"])
    conv_df["Converted"] = conv_df["Jobs Estimate Sales Subtotal"] < 101

    # Aggregate
    rev_agg = rev_df.groupby("Location Zip").agg({
        "Jobs Subtotal": "sum",
        "Jobs Gross Margin %": "mean",
        "Business Unit": "first",
        "Campaign Category": "first"
    }).reset_index()
    rev_agg.rename(columns={"Jobs Subtotal": "Revenue"}, inplace=True)

    conv_agg = conv_df.groupby("Location Zip").agg(
        Total_Jobs=("Converted", "count"),
        Converted_Jobs=("Converted", "sum")
    ).reset_index()
    conv_agg["Conversion Rate"] = (conv_agg["Converted_Jobs"] / conv_agg["Total_Jobs"]) * 100

    # Merge datasets
    final = pd.merge(rev_agg, conv_agg[["Location Zip", "Conversion Rate"]], on="Location Zip", how="left")
    return final, rev_df  # rev_df retained for filtering

# ----------------------
# Load all
# ----------------------
gdf = load_geojson()
data, full_rev = load_data()

# ----------------------
# Sidebar Filters
# ----------------------

st.sidebar.title("Filters")

available_bu = sorted(full_rev["Business Unit"].dropna().unique())
bu_selection = st.sidebar.multiselect("Select Business Units", available_bu, default=available_bu)

available_categories = sorted(full_rev["Campaign Category"].dropna().unique())
category_selection = st.sidebar.multiselect("Select Campaign Categories", available_categories, default=available_categories)

filtered = data[
    (full_rev["Business Unit"].isin(bu_selection)) &
    (full_rev["Campaign Category"].isin(category_selection))
]

# ----------------------
# Merge with Geo Data
# ----------------------
gdf["POA_CODE21"] = gdf["POA_CODE21"].astype(str).str.strip()
filtered["Location Zip"] = filtered["Location Zip"].astype(str).str.strip()
merged = gdf.merge(filtered, left_on="POA_CODE21", right_on="Location Zip", how="left")

# ----------------------
# Select Metric
# ----------------------

st.title("Melbourne Job Heatmap Dashboard")

metric = st.radio("Select Metric to Display", ["Revenue", "Conversion Rate", "Jobs Gross Margin %"], horizontal=True)

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
