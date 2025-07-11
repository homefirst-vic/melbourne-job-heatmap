# heatmap_dashboard.py

import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import streamlit as st

# === SETUP ===
st.set_page_config(layout="wide")
st.title("Melbourne Job Heatmap Dashboard")

# === FILE PATHS ===
SHP_PATH = "POA_2021_AUST_GDA2020.shp"
REV_FILE = "Rev Report Chat GPT.xlsx"
CONV_FILE = "Conversion Report Chat GPT.xlsx"

# === LOAD DATA ===
rev_df = pd.read_excel(REV_FILE)
conv_df = pd.read_excel(CONV_FILE)
shp_gdf = gpd.read_file("vic_postcodes_simplified.geojson")

# === CLEAN AND STANDARDIZE ===
rev_df = rev_df[['Location Zip', 'Jobs Subtotal', 'Jobs Gross Margin %', 'Business Unit', 'Campaign Category']].dropna(subset=['Location Zip'])
rev_df['Location Zip'] = rev_df['Location Zip'].astype(str).str[:4]

conv_df = conv_df[['Location Zip', 'Jobs Estimate Sales Subtotal', 'Business Unit', 'Campaign Category']].dropna(subset=['Location Zip'])
conv_df['Location Zip'] = conv_df['Location Zip'].astype(str).str[:4]
conv_df['Converted'] = conv_df['Jobs Estimate Sales Subtotal'] < 101

# === AGGREGATE REVENUE DATA ===
rev_agg = (
    rev_df.groupby(['Location Zip', 'Business Unit', 'Campaign Category'])
    .agg({'Jobs Subtotal': 'sum', 'Jobs Gross Margin %': 'mean'})
    .reset_index()
    .rename(columns={
        'Location Zip': 'POA_CODE21',
        'Jobs Subtotal': 'Revenue',
        'Jobs Gross Margin %': 'Gross Margin'
    })
)

# === AGGREGATE CONVERSION DATA ===
conv_agg = (
    conv_df.groupby(['Location Zip', 'Business Unit', 'Campaign Category'])
    .agg({'Converted': 'mean'})
    .reset_index()
    .rename(columns={
        'Location Zip': 'POA_CODE21',
        'Converted': 'Conversion Rate'
    })
)
conv_agg['Conversion Rate'] = (conv_agg['Conversion Rate'] * 100).round(2)

# === COMBINE BOTH ===
data = pd.merge(rev_agg, conv_agg, on=['POA_CODE21', 'Business Unit', 'Campaign Category'], how='outer')

# === FILTERS ===
business_units = sorted(data['Business Unit'].dropna().unique())
campaigns = sorted(data['Campaign Category'].dropna().unique())

col1, col2 = st.columns(2)
selected_bu = col1.multiselect("Business Units", business_units, default=business_units)
selected_campaign = col2.multiselect("Campaign Categories", campaigns, default=campaigns)

filtered_data = data[
    data['Business Unit'].isin(selected_bu) &
    data['Campaign Category'].isin(selected_campaign)
]

# === AGGREGATE TO POSTCODE LEVEL ===
map_data = (
    filtered_data
    .groupby('POA_CODE21')
    .agg({
        'Revenue': 'sum',
        'Gross Margin': 'mean',
        'Conversion Rate': 'mean'
    })
    .reset_index()
)

# === MERGE WITH SHAPEFILE ===
shp_gdf['POA_CODE21'] = shp_gdf['POA_CODE21'].astype(str)
merged_gdf = shp_gdf.merge(map_data, on='POA_CODE21')

# === BASE MAP ===
m = folium.Map(location=[-37.8136, 144.9631], zoom_start=9, tiles="CartoDB positron")

# === LAYERS ===
def add_choropleth(data_column, name, color):
    folium.Choropleth(
        geo_data=merged_gdf,
        data=merged_gdf,
        columns=['POA_CODE21', data_column],
        key_on='feature.properties.POA_CODE21',
        fill_color=color,
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=name,
        name=name
    ).add_to(m)

add_choropleth("Revenue", "Revenue ($)", "YlGn")
add_choropleth("Gross Margin", "Gross Margin (%)", "OrRd")
add_choropleth("Conversion Rate", "Conversion Rate (%)", "PuBu")

# === TOOLTIPS ===
folium.GeoJson(
    merged_gdf,
    name="Details",
    tooltip=folium.GeoJsonTooltip(
        fields=['POA_CODE21', 'Revenue', 'Gross Margin', 'Conversion Rate'],
        aliases=["Postcode", "Revenue ($)", "Gross Margin (%)", "Conversion Rate (%)"],
        localize=True
    )
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# === DISPLAY IN STREAMLIT ===
st_folium(m, width=1100, height=650)
