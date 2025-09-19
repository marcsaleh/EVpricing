import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import folium
from folium.plugins import MarkerCluster, LocateControl
from streamlit_folium import st_folium

# Set the page config with a custom title, favicon, and hide the Streamlit menu
st.set_page_config(
    page_title="ChargeCompare",  # Custom tab title
    page_icon="logo_white_background - Copy.jpg",  # Path to your custom favicon
    #initial_sidebar_state="collapsed",  # Collapse the sidebar initially
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)


import uuid
from datetime import datetime
from opencensus.ext.azure.log_exporter import AzureLogHandler
import logging

# Replace with your Azure Application Insights Connection String
CONNECTION_STRING = "InstrumentationKey=4c91cae0-735c-4d2e-bf0c-01782744234f;IngestionEndpoint=https://canadacentral-1.in.applicationinsights.azure.com/;LiveEndpoint=https://canadacentral.livediagnostics.monitor.azure.com/;ApplicationId=6e461640-80ec-46f6-86d3-1456c03c1b35"

## Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(AzureLogHandler(connection_string=CONNECTION_STRING))

# Track unique sessions
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())  # Generate a unique session ID
    session_start_time = datetime.now().isoformat()
    logger.info(f"New user session: {st.session_state['session_id']} at {session_start_time}")


# Main page title
st.title("ChargeCompare: Explore Public EV Charging in Canada")

st.markdown("""
This dashboard explores **public electric vehicle (EV) charging infrastructure across Canada**, with a focus on:
- **Where Level 2 and Level 3 chargers are located**
- **Who operates them** (utilities, automakers, retailers)
- **How pricing models vary**

It helps you make sense of station availability, operator categories, and pricing types (kWh, time, idle fees) by province.
""")


st.sidebar.title("About ChargeCompare")
st.sidebar.markdown("""
This tool helps users explore how **public EV charging pricing** varies across **Canadian provinces**, with a focus on differences by:

- ⚡ **Charging speed** (Level 2 vs. Level 3)
- 🏢 **Operator type** (utility, automaker, retail, site-host)
- 💵 **Pricing model** (kWh, time, flat rate)

---""")


st.sidebar.title("🔁 Centralized vs. Non-Centralized Charging Networks")
st.sidebar.markdown("""**Centralized Charge Point Operators**  
Charging networks that are **centrally managed** with consistent pricing, branding, and customer experience. These include **utility-backed**, **automaker-backed**, or **fuel/retail-integrated** networks. They typically provide uniform billing, support, and maintenance across all locations.

**Non-Centralized Charge Point Operators**  
Charging stations run by **individual site hosts** (e.g., businesses or municipalities) using platforms like **FLO** or **ChargePoint**. They appear on provider apps and share a common interface, but **pricing, access, and maintenance are set locally**, leading to more variation across stations.

---                    
                    
⚠️ **Disclaimer**  
This tool is for **informational and awareness purposes only**.  
It does **not provide real-time prices** or exact fees at individual stations.  
For current pricing, please consult the charging network’s app.

---
""")

#charging_ports = pd.read_csv("alt_fuel_stations_ev_charging_units (May 19 2025).csv")


# Define the function to process the charging ports dataset
def process_charging_ports_data(file_path):
    charging_ports = pd.read_csv(file_path)
    
    # Initialize columns
    charging_ports["ports"] = 1

    # Tesla Level 2
    charging_ports['L2_Tesla'] = charging_ports['EV Network'].apply(lambda x: 1 if 'Tesla Destination' in str(x) else 0)
    charging_ports['L2_Tesla'] = charging_ports.apply(
        lambda row: 0 if row.get('EV J1772 Connector Count', 0) == 1 and row['L2_Tesla'] == 1 else row['L2_Tesla'],
        axis=1
    )

    # Tesla Level 3
    charging_ports['L3_Tesla'] = charging_ports.apply(
        lambda row: 1 if row.get('EV J3400 Connector Count', 0) == 1 and row['L2_Tesla'] == 0 else 0,
        axis=1
    )

    # DCFC and dual connector adjustment
    DCFC_ports = charging_ports[charging_ports["EV DC Fast Count"] > 0]
    filtered_df = DCFC_ports[(DCFC_ports['EV CHAdeMO Connector Count'] == 1) & (DCFC_ports['EV CCS Connector Count'] == 1)]

    # Update dual connector adjustment
    filtered_df.loc[:, 'EV CHAdeMO Connector Count'] = 0
    filtered_df.loc[:, 'EV CCS Connector Count'] = 0
    filtered_df.loc[:, 'ChademoCCSsingleuseport'] = 1

    # Apply updates to original DataFrame
    charging_ports.loc[filtered_df.index, ['EV CHAdeMO Connector Count', 'EV CCS Connector Count']] = filtered_df[['EV CHAdeMO Connector Count', 'EV CCS Connector Count']]
    charging_ports.loc[filtered_df.index, 'ChademoCCSsingleuseport'] = 1

    # Create L2 and L3 port columns
    charging_ports["L2_port"] = charging_ports.apply(
        lambda row: 1 if row.get("EV J1772 Connector Count", 0) > 0 or row.get("L2_Tesla", 0) > 0 else 0,
        axis=1
    )
    charging_ports["L3_port"] = charging_ports.apply(
        lambda row: 1 if (
            row.get("EV CCS Connector Count", 0) > 0 or
            row.get("EV CHAdeMO Connector Count", 0) > 0 or
            row.get("ChademoCCSsingleuseport", 0) > 0 or
            row.get("L3_Tesla", 0) > 0
        ) else 0,
        axis=1
    )
    
    # Define bucket mapping
    network_bucket_map = {
    # Centralized utility-backed
    'BCHYDRO': 'Centralized Utility-Backed',
    'Circuit électrique': 'Centralized Utility-Backed',
    'IVY': 'Centralized Utility-Backed',
    'eCharge Network': 'Centralized Utility-Backed',

    # Centralized automaker-backed
    'Tesla': 'Centralized Automaker-Backed',
    'Tesla Destination': 'Centralized Automaker-Backed',
    'Electrify Canada': 'Centralized Automaker-Backed',
    'FORD_CHARGE': 'Centralized Automaker-Backed',

    # Centralized fuel/retail-integrated
    'PETROCAN': 'Centralized Fuel/Retail Integrated',
    'SHELL_RECHARGE': 'Centralized Fuel/Retail Integrated',
    'COUCHE_TARD': 'Centralized Fuel/Retail Integrated',
    'ON_THE_RUN_EV': 'Centralized Fuel/Retail Integrated',
    '7CHARGE': 'Centralized Fuel/Retail Integrated',
    'CIRCLE_K': 'Centralized Fuel/Retail Integrated',

    # Non-Centralized site-hosts
    'AUTEL': 'Non-Centralized Site-Host',
    'LAKELAND_EV': 'Non-Centralized Site-Host',
    'ChargePoint Network': 'Non-Centralized Site-Host',
    'FLO': 'Non-Centralized Site-Host',
    'SWTCH': 'Non-Centralized Site-Host',
    'CHARGELAB': 'Non-Centralized Site-Host',
    'EV Connect': 'Non-Centralized Site-Host',
    'OpConnect': 'Non-Centralized Site-Host',
    'JULE': 'Non-Centralized Site-Host',
    'NOODOE': 'Non-Centralized Site-Host',
    'AMPUP': 'Non-Centralized Site-Host',
    'TURNONGREEN': 'Non-Centralized Site-Host',
    'EVBOLT': 'Non-Centralized Site-Host',
    'Hwisel': 'Non-Centralized Site-Host',
    'ZEFNET': 'Non-Centralized Site-Host',
    'EVGATEWAY': 'Non-Centralized Site-Host',
    'CHARGEUP': 'Non-Centralized Site-Host',
    'RED_E': 'Non-Centralized Site-Host',
    'HONEY_BADGER': 'Non-Centralized Site-Host',
    'Sun Country Highway': 'Non-Centralized Site-Host',

    # Fallback for unknown or missing
    'Non-Networked': 'Non-Centralized Site-Host'
    }

    # Apply the bucket mapping
    charging_ports['Operator_Bucket'] = charging_ports['EV Network'].map(network_bucket_map).fillna('Non-Networked')

    # Mapping from 'EV Network' to standardized names
    network_name_mapping = {
    'Tesla': 'Tesla',
    'Tesla Destination': 'Tesla',
    'Electrify Canada': 'Electrify Canada',
    'SHELL_RECHARGE': 'Shell Recharge',
    'PETROCAN': 'Petro Canada',
    'COUCHE_TARD': 'Couche Tard/CircleK',
    'CIRCLE_K': 'Couche Tard/CircleK',
    'ON_THE_RUN_EV': 'On The Run EV (Parkland)',
    'BCHYDRO': 'BC Hydro',
    'Circuit électrique': 'Electric Circuit (Hydro Quebec)',
    'IVY': 'Ivy (OPG and Hydro One)',
    'eCharge Network': 'eCharge (NB power)',
    'FORD_CHARGE': 'Ford Blue Oval'
    }

    # Apply mapping to create a new column
    charging_ports['Clean_Network_Name'] = charging_ports['EV Network'].map(network_name_mapping)

    # Drop IVY stations outside Ontario
    charging_ports = charging_ports[~((charging_ports['EV Network'] == 'IVY') & (charging_ports['State'] != 'ON'))]


    return charging_ports

charging_ports = process_charging_ports_data("alt_fuel_stations_ev_charging_units (May 19 2025).csv")

#charging_ports.to_csv('look.csv')

# Province selector
province_full_name = st.selectbox(
    "Select a province to view public EV charging information:",
    [
        "Alberta", "British Columbia", "Manitoba", "New Brunswick", 
        "Newfoundland and Labrador", "Nova Scotia", "Ontario", 
        "Prince Edward Island", "Quebec", "Saskatchewan"
    ]
)

# Add this in your Streamlit app script
st.subheader(f"1. Charging Port Availability in {province_full_name}")

st.markdown("""
A **charging port** refers to an individual plug where one electric vehicle can charge at a time.  
Some stations may have multiple ports to serve more than one EV simultaneously.
""")

province_map = {
    'Alberta': 'AB', 'British Columbia': 'BC', 'Manitoba': 'MB', 'New Brunswick': 'NB',
    'Newfoundland and Labrador': 'NL', 'Nova Scotia': 'NS', 'Ontario': 'ON',
    'Prince Edward Island': 'PE', 'Quebec': 'QC', 'Saskatchewan': 'SK',
    'Yukon': 'YT', 'Northwest Territories': 'NT', 'Nunavut': 'NU'
}

province = province_map.get(province_full_name)

# Optional subheading
st.markdown("Charging stations have varying power levels and charging times:")
st.markdown("Level 2 charging typically provides 7–19 kW of power and takes 4–10 hours to fully charge an EV.\n\n"
        "Level 3 charging (DC Fast Charging) delivers 50–500 kW and can charge most EVs in under 1 hour.")


# Function to generate the plot and description
def plot_ports_by_province(charging_ports: pd.DataFrame, province):
    # Filter data for the selected province
    province_data = charging_ports[charging_ports["State"] == province]

    # Sum Level 2 and Level 3 ports
    port_counts = province_data[['L2_port', 'L3_port']].sum()

    # Create bar plot
    fig, ax = plt.subplots(figsize=(7, 5))
    port_counts.plot(
        kind='bar',
        ax=ax,
        color=['#015A06', '#999999']
    )

    # Add horizontal grid lines
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)

    # Customize the plot
    #ax.set_title(f'EV Charging Ports in {province}', fontsize=14, fontweight='bold')
    ax.set_ylabel('Number of Ports', fontsize=12)
    ax.set_xlabel('Power Level', fontsize=12)
    ax.set_xticklabels(['Level 2', 'Level 3'], rotation=0, fontsize=12)
    ax.tick_params(axis='y', labelsize=12)

    return fig


# --- Section: Province Summary Box ---
def generate_station_summary(charging_ports, province_code):
    df = charging_ports[charging_ports['State'] == province_code]
    total_ports = len(df)
    l2 = df['L2_port'].sum()
    l3 = df['L3_port'].sum()

    st.markdown(f"""
    <div style="background-color:#f0f2f6; padding:10px; border-radius:8px">
    <b>{province_full_name} Charging Ports Summary:</b><br>
    🔌 Total charging ports: {total_ports:,}<br>
    - Level 2 ports: {int(l2):,}<br>
    - Level 3 ports: {int(l3):,}<br>
    - Proportion of Level 2 (%): {l2 / total_ports * 100:.1f}%
    </div>
    """, unsafe_allow_html=True)


#def plot_charging_map_by_province(df, province_code):
#    df = df[df['State'] == province_code].dropna(subset=['Latitude', 'Longitude']).copy()
#
#    # Center map on province average coordinates
#    map_center = [df['Latitude'].mean(), df['Longitude'].mean()]
#    ev_map = folium.Map(location=map_center, zoom_start=6)

#    # Create marker clusters
#    l2_cluster = MarkerCluster(name='Level 2 Charging').add_to(ev_map)
#    l3_cluster = MarkerCluster(name='Level 3 Charging').add_to(ev_map)

#    # Add L2 and L3 markers
#    for _, row in df.iterrows():
#        popup_text = f"{row['Station Name']}<br>{row['Street Address']}<br>{row['City']}"
#        if row.get('L2_port', 0) == 1:
#            folium.Marker(
#                location=[row['Latitude'], row['Longitude']],
#                popup=popup_text,
#                icon=folium.Icon(color='green', icon='flash', prefix='fa')
#            ).add_to(l2_cluster)
#        if row.get('L3_port', 0) == 1:
#            folium.Marker(
#                location=[row['Latitude'], row['Longitude']],
#                popup=popup_text,
#                icon=folium.Icon(color='red', icon='bolt', prefix='fa')
#            ).add_to(l3_cluster)

#    # Add legend controls (expanded)
#    LocateControl(auto_start=True).add_to(ev_map)
#    folium.LayerControl(collapsed=False).add_to(ev_map)

#    return ev_map


import os

def show_province_map(province_code):
    """
    Displays a pre-generated HTML map for a given province.
    Assumes maps are stored in a subfolder called 'maps' as 'QC_map.html', 'AB_map.html', etc.
    """
    map_file = os.path.join("maps", f"{province_code}_map.html")
    if os.path.exists(map_file):
        with open(map_file, "r", encoding="utf-8") as f:
            map_html = f.read()
        st.components.v1.html(map_html, height=600, scrolling=True)
    else:
        st.warning(f"Map for {province_code} not found. It may not have been generated yet.")

# Create tabs
tab1, tab2 = st.tabs(["📊 Number of L2 versus L3 ports", "📍 Locate stations around you"])

# --- Tab 1: Bar Chart and Summary ---
with tab1:
    st.subheader("Public Charging Port Breakdown by Power Level")

    # Plot the bar chart
    fig = plot_ports_by_province(charging_ports, province)
    st.pyplot(fig)

    # Display province summary
    generate_station_summary(charging_ports, province)

# --- Tab 2: Interactive Charging Station Map ---
with tab2:
    st.subheader("Explore the Public Charging Stations in Your Province")
    show_province_map(province)

    #charging_map = plot_charging_map_by_province(charging_ports, province)
    #st_data = st_folium(charging_map, width=700, height=500)

st.subheader(f"2. Who Operates the Charging Stations in {province_full_name}")

# centralized vs non-centralized operators description can go here

st.subheader(f"Key Station Operators in {province_full_name}")



# Descriptions for each operator bucket
bucket_descriptions = {
    "Centralized Utility-Backed": "Operated by or in partnership with utilities, offering slow and/or fast charging.",
    "Centralized Automaker-Backed": "Backed by automakers, focused on slow and/or fast charging along travel corridors.",
    "Centralized Fuel/Retail Integrated": "Installed at major fuel stations or retail sites to serve customers on the go, primarly offerring Level 3 fast charging.",
    "Non-Centralized Site-Host": "Owned by individual businesses (e.g., restaurants, hotels) or municipalities that use hardware and software platforms like FLO or ChargePoint. Pricing and service are typically managed locally."
}

def generate_province_bucket_text(charging_ports: pd.DataFrame, province_code: str) -> str:
    # Filter data to selected province
    df = charging_ports[charging_ports['State'] == province_code]

    # Get available buckets and associated networks in this province
    available_buckets = df.groupby('Operator_Bucket')['EV Network'].unique().to_dict()

    # Compose text
    text_output = []
    for bucket, networks in available_buckets.items():
        if bucket in bucket_descriptions:
            networks_list = sorted(set(networks))
            description = f"**{bucket}**: {bucket_descriptions[bucket]} In {province_full_name}, this includes: {', '.join(networks_list)}."
            text_output.append(description)

    return "\n\n".join(text_output)


# Display the explanatory text for that province's operator buckets
description_text = generate_province_bucket_text(charging_ports, province)
st.markdown(description_text)

import matplotlib.ticker as mtick

def plot_operator_type_distribution_by_province(charging_ports, province_code, level):
    # level = 'L2_port' or 'L3_port'
    df = charging_ports.copy()
 
    # Filter to selected province and charging level
    df = df[(df['State'] == province_code) & (df[level] == 1)]

    bucket_counts = df.groupby('Operator_Bucket').size().reset_index(name='Count')
    bucket_counts['Proportion'] = bucket_counts['Count'] / bucket_counts['Count'].sum()

    ordered_buckets = [
    'Centralized Fuel/Retail Integrated',
    'Centralized Automaker-Backed',
    'Centralized Utility-Backed',
    'Non-Centralized Site-Host']

    bucket_counts['Operator_Bucket'] = pd.Categorical(bucket_counts['Operator_Bucket'], categories=ordered_buckets, ordered=True)
    bucket_counts = bucket_counts.sort_values('Operator_Bucket').dropna(subset=['Operator_Bucket'])

    colors = [
    '#E1B97C',  # Centralized Fuel/Retail Integrated – soft amber
    '#C08D87',  # Centralized Automaker-Backed – clay rose
    '#4A6484',  # Centralized Utility-Backed – steel blue
    '#6C8C78']   # Non-Centralized Site-Host – muted green]


    fig, ax = plt.subplots(figsize=(8, 5))
    #bucket_counts.plot(kind='bar', x='Operator_Bucket', y='Proportion', legend=False, color=colors[:len(bucket_counts)], ax=ax)
    
    # Define color map based on fixed category-color mapping
    color_map = {
        'Centralized Fuel/Retail Integrated': '#E1B97C',
        'Centralized Automaker-Backed': '#C08D87',
        'Centralized Utility-Backed': '#4A6484',
        'Non-Centralized Site-Host': '#6C8C78'
    }

    bucket_counts['Color'] = bucket_counts['Operator_Bucket'].map(color_map)
    bucket_counts.plot(kind='bar', x='Operator_Bucket', y='Proportion', legend=False, color=bucket_counts['Color'], ax=ax)


    # Format y-axis as %
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))

    # Add % labels on bars (placed inside the bar for reliability with ylim=0..1)
    for patch in ax.patches:
        height = patch.get_height()
        if height > 0:  # avoid divide-by-zero/labels on empty bars
            x = patch.get_x() + patch.get_width() / 2
            y = height / 2
            # Pick label color based on bar fill height for readability
            label_color = 'white' if height >= 0.12 else 'black'
            ax.text(
                x, y,
                f"{height * 100:.0f}%",
                ha='center', va='center',
                fontsize=11, fontweight='bold',
                color=label_color
            )

    ax.set_ylabel('Proportion of Charging Ports', fontsize=12)
    ax.set_xlabel('Operator Type', fontsize=12)
    #ax.set_title(f'{level.replace("_", " ")} Operator Types in {province_code}', fontsize=14, fontweight='bold')
    ax.set_ylim(0, 1)
    ax.tick_params(axis='x', labelrotation=30)
    plt.tight_layout()
    return fig


def generate_operator_type_interpretation(charging_ports: pd.DataFrame, province: str, level: str) -> str:
    # level = 'L2_port' or 'L3_port'


    centralized_types = [
        'Centralized Fuel/Retail Integrated',
        'Centralized Automaker-Backed',
        'Centralized Utility-Backed'
    ]
    non_centralized_types = ['Non-Centralized Site-Host', 'Non-Networked']

    df = charging_ports[(charging_ports['State'] == province) & (charging_ports[level] == 1)].copy()
    bucket_summary = df['Operator_Bucket'].value_counts(normalize=True)

    if bucket_summary.empty:
        return f"No {level.replace('_', ' ')} data available for {province}."

    dominant_type = bucket_summary.idxmax()
    dominant_percent = round(bucket_summary.max() * 100)
    centralized_share = round(bucket_summary[bucket_summary.index.isin(centralized_types)].sum() * 100)
    non_centralized_share = round(bucket_summary[bucket_summary.index.isin(non_centralized_types)].sum() * 100)

    # Extract level prefix (e.g., "L2" or "L3")
    level_prefix = level.split('_')[0]

    insights_html = f"""
    <div style="background-color:#f0f2f6; padding:10px; border-radius:8px">
    <b>Operator Insights for {province_full_name} — {level_prefix} Ports:</b><br>
    - Most common operator type: <b>{dominant_type}</b> ({dominant_percent}% of {level_prefix} ports)<br>
    - <b>{centralized_share}%</b> are managed by centralized networks with consistent pricing and maintenance<br>
    - <b>{non_centralized_share}%</b> are non-centralized (owned and priced independently by site hosts)
    </div>
    """

    st.markdown(insights_html, unsafe_allow_html=True)


# Level 2
fig_l2 = plot_operator_type_distribution_by_province(charging_ports, province, "L2_port")
# Level 3
fig_l3 = plot_operator_type_distribution_by_province(charging_ports, province, "L3_port")

tab1, tab2 = st.tabs(["🔌 Level 2 Overview", "⚡ Level 3 Overview"])
with tab1:
    st.pyplot(fig_l2)
    generate_operator_type_interpretation(charging_ports, province, "L2_port")

with tab2:
    st.pyplot(fig_l3)
    generate_operator_type_interpretation(charging_ports, province, "L3_port")



# --- Section: Explanation of Pricing Models ---
st.markdown("### 3. How Public Charging is Priced")

# Shared pricing concepts
st.markdown("""
Understanding how EV charging is priced helps users navigate costs across provinces and networks. Below are **common elements** that apply across most public charging stations:

- **Flat Fees (Per Session):** A fixed cost to start charging, regardless of energy used or time plugged in. Common at hotels, restaurants, or older installations.
- **Subscription Discounts:** Some networks offer members lower rates or waive fees in exchange for a monthly fee.
- **Roaming Access:** Some providers allow users to access multiple networks using a single app or RFID card, though fees may vary.

_Note: Pricing is set by individual networks or site hosts and may vary within provinces due to a number of site considerations._
""")

# Tabs for kWh-based and time-based pricing
tab1, tab2 = st.tabs(["⚡ Energy-Based Pricing (kWh)", "⏱️ Time-Based Pricing"])

with tab1:
    st.markdown("""
    **Energy-Based (kWh) Pricing**
    
    Users are billed based on the exact amount of electricity delivered — similar to how fuel is priced per gallon or litre at gas stations. This model:
    
    - Is common at **Level 3** DC fast chargers 
    - Is **not yet permitted** in all provinces due to regulatory limits
    - Viewed as **fairest and most transparent**
    
    **Common Features:**
    - **Tiered Pricing by Power Level:** Higher per-kWh rates may apply when using faster chargers (e.g., above 50 kW)
    - **Idle Fees:** Extra charges if you stay connected after charging finishes, to keep stations available.
    
    
    """)

with tab2:
    st.markdown("""
    **Time-Based Pricing**

    Users are billed based on the amount of time the vehicle is connected to the charger — regardless of how much electricity is delivered. This model:

    - Is common at **Level 2** AC stations
    - Is used where **per-kWh pricing is not yet permitted**
    - Is seen as a way to encourage users to unplug promptly once charging is complete 

    **Common Features:**
    - **Tiered Pricing by Power Level:** Higher per-minute/hour rates may apply when using faster chargers (e.g., above 50 kW)  
    - **Limited Idle Fee Use:** Typically no idle fees, as time-based billing already discourages lingering

    """)


st.markdown("### Pricing Characteristics of Centralized Charging Networks")
st.markdown("The following table summarizes the **pricing characteristics** of major centralized public charging networks in Canada, categorized by their operator type. This helps users understand how different networks charge for EV charging services." \
"\n\n This table does not include **non-centralized site-hosts** that use EVSE provider hardware/software (e.g., FLO, ChargePoint) but set their own pricing. The EVSE providers provide recommended pricing ranges, but site hosts can set their own rates within those ranges." \
"\n\nFLO and ChargePoint are the most common EVSE providers in Canada. ")

# --- Load and process pricing data ---
charging_network_data = pd.read_csv("Pricing_data_networks.csv", encoding='ISO-8859-1')

# --- Standardization and Styling Maps ---
standardized_bucket_map = {
    'Tesla': 'Centralized Automaker-Backed',
    'Electrify Canada': 'Centralized Automaker-Backed',
    'Ford Blue Oval': 'Centralized Automaker-Backed',
    'Shell Recharge': 'Centralized Fuel/Retail Integrated',
    'Petro Canada': 'Centralized Fuel/Retail Integrated',
    'Couche Tard/CircleK': 'Centralized Fuel/Retail Integrated',
    'On The Run EV (Parkland)': 'Centralized Fuel/Retail Integrated',
    'BC Hydro': 'Centralized Utility-Backed',
    'Electric Circuit (Hydro Quebec)': 'Centralized Utility-Backed',
    'Ivy (OPG and Hydro One)': 'Centralized Utility-Backed',
    'eCharge (NB power)': 'Centralized Utility-Backed',
}
bucket_colors = {
    'Centralized Fuel/Retail Integrated': 'background-color: #E1B97C',
    'Centralized Automaker-Backed': 'background-color: #C08D87',
    'Non-Centralized Site-Host': 'background-color: #6C8C78',
    'Centralized Utility-Backed': 'background-color: #9BBBE6',
    'Non-Networked': 'background-color: #A0A9AB',
}
legend_labels = {
    'Centralized Fuel/Retail Integrated': '🟨 Centralized Fuel/Retail Integrated',
    'Centralized Automaker-Backed': '🟫 Centralized Automaker-Backed',
    'Centralized Utility-Backed': '🟦 Centralized Utility-Backed',
    'Non-Centralized Site-Host': '🟩 Non-Centralized Site-Host',
    'Non-Networked': '⬜️ Non-Networked'
}

def highlight_by_bucket(row):
    bucket = standardized_bucket_map.get(row['Network'], 'Non-Networked')
    return [bucket_colors.get(bucket, '')] * len(row)

# --- Utility functions ---
def get_active_networks_by_province_and_level(province_acronym, charging_ports, level_column):
    df = charging_ports[(charging_ports['State'] == province_acronym) & (charging_ports[level_column] == 1)]
    return df['Clean_Network_Name'].dropna().unique().tolist()

def get_filtered_table_by_level(province_acronym, charging_network_data, level):
    level_column = 'L2_port' if level == 'L2' else 'L3_port'
    active_networks = get_active_networks_by_province_and_level(province_acronym, charging_ports, level_column)
    filtered = charging_network_data[
        (charging_network_data['Network'].isin(active_networks)) &
        (charging_network_data['Charging station level'] == level)
    ].copy()

    # Apply overrides for Tesla
    if 'Tesla' in filtered['Network'].values:
        if province_acronym in ['NB', 'PE']: #NS not sure
            filtered.loc[filtered['Network'] == 'Tesla', 'kWh Based Pricing'] = 'No'
            filtered.loc[filtered['Network'] == 'Tesla', 'Time Based Pricing'] = 'Yes'
            filtered.loc[filtered['Network'] == 'Tesla', 'Tiered Pricing for L3'] = 'Yes'

            filtered.loc[filtered['Network'] == 'Tesla', 'Pricing Approach'] = 'Time-based'
        else:
            filtered.loc[filtered['Network'] == 'Tesla', 'kWh Based Pricing'] = 'Yes'
            filtered.loc[filtered['Network'] == 'Tesla', 'Time Based Pricing'] = 'No'
            filtered.loc[filtered['Network'] == 'Tesla', 'Tiered Pricing for L3'] = 'No'

            filtered.loc[filtered['Network'] == 'Tesla', 'Pricing Approach'] = 'Energy-based'

    # Apply overrides for Shell Recharge
    if 'Shell Recharge' in filtered['Network'].values:
        if province_acronym == 'MB':
            filtered.loc[filtered['Network'] == 'Shell Recharge', 'kWh Based Pricing'] = 'No'
            filtered.loc[filtered['Network'] == 'Shell Recharge', 'Time Based Pricing'] = 'Yes'
        else:
            filtered.loc[filtered['Network'] == 'Shell Recharge', 'kWh Based Pricing'] = 'Yes'
            filtered.loc[filtered['Network'] == 'Shell Recharge', 'Time Based Pricing'] = 'No'

    return filtered

def is_all_non_centralized(df):
    non_centralized_set = {'Non-Centralized Site-Host', 'Non-Networked'}
    buckets = [standardized_bucket_map.get(net, 'Non-Networked') for net in df['Network'].unique()]
    return set(buckets).issubset(non_centralized_set)

def get_used_buckets(df):
    return sorted(set(standardized_bucket_map.get(n, 'Non-Networked') for n in df['Network'].unique()))


# --- Tabs ---
tab1, tab2 = st.tabs(["🔌 Level 2 Networks", "⚡ Level 3 Networks"])

# Base tables
l2_table = get_filtered_table_by_level(province, charging_network_data, "L2")
l3_table = get_filtered_table_by_level(province, charging_network_data, "L3")

# Import pricing range per network/province by power level
level2_pricing = pd.read_csv("L2_pricing.csv")
level3_pricing = pd.read_csv("L3_pricing.csv")

# Pricing lookups
L2_pricing_indexed = level2_pricing.set_index("Network")
l2_table["Pricing Range"] = l2_table["Network"].map(
    lambda n: L2_pricing_indexed.loc[n, province_full_name]
    if n in L2_pricing_indexed.index else "N/A"
)

L3_pricing_indexed = level3_pricing.set_index("Network")
l3_table["Pricing Range"] = l3_table["Network"].map(
    lambda n: L3_pricing_indexed.loc[n, province_full_name]
    if (n in L3_pricing_indexed.index and province_full_name in L3_pricing_indexed.columns)
    else "N/A"
)

# Column order
l2_table = l2_table[[
    "Network", "Station Power Level Range (kW)", "Pricing Approach",
    "Pricing Range", "Network App and roaming partners"
]]
l3_table = l3_table[[
    "Network", "Station Power Level Range (kW)", "Pricing Approach",
    "Pricing Range", "Idle Fees Applied", "Network App and roaming partners"
]]

# Friendly missing text (handle both NaN and explicit "N/A")
l2_table = l2_table.replace("N/A", pd.NA).fillna("Not available")
l3_table = l3_table.replace("N/A", pd.NA).fillna("Not available")

# Shared styling helper: highlight rows + center headers & cells
def style_table(df):
    return (
        df.style
          .apply(highlight_by_bucket, axis=1)
          .hide(axis="index")
          .set_table_styles([
              {"selector": "th", "props": [
                  ("text-align", "center"),
                  ("vertical-align", "middle"),
                  ("white-space", "normal"),
              ]},
              {"selector": "td", "props": [
                  ("text-align", "center"),
                  ("vertical-align", "middle"),
                  ("white-space", "normal"),
                  ("word-break", "break-word"),
              ]},
          ])
          .set_table_attributes('style="width:100%; table-layout:fixed"')
    )

# --- Display Legend (collect once for both tabs if you need it elsewhere) ---
used_buckets = set(get_used_buckets(l2_table) + get_used_buckets(l3_table))

# ----- TAB: Level 2 -----
with tab1:
    l2_buckets = get_used_buckets(l2_table)
    if l2_buckets:
        cols = st.columns(len(l2_buckets))
        for i, bucket in enumerate(l2_buckets):
            label = legend_labels.get(bucket, bucket)
            color = bucket_colors.get(bucket, '')
            with cols[i]:
                st.markdown(
                    f"<div style='{color}; padding: 6px; border-radius: 4px; text-align:center;'>{label}</div>",
                    unsafe_allow_html=True
                )

    if l2_table.empty or is_all_non_centralized(l2_table):
        st.markdown("""
        <div style="background-color:#f0f2f6; padding:10px; border-radius:8px">
        <b>All Level 2 stations in this province are operated by individual site hosts.</b><br>
        These use EVSE provider software (like FLO or ChargePoint) under a non-centralized pricing model.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(style_table(l2_table).to_html(index=False, escape=False), unsafe_allow_html=True)

# ----- TAB: Level 3 -----
with tab2:
    l3_buckets = get_used_buckets(l3_table)
    if l3_buckets:
        cols = st.columns(len(l3_buckets))
        for i, bucket in enumerate(l3_buckets):
            label = legend_labels.get(bucket, bucket)
            color = bucket_colors.get(bucket, '')
            with cols[i]:
                st.markdown(
                    f"<div style='{color}; padding: 6px; border-radius: 4px; text-align:center;'>{label}</div>",
                    unsafe_allow_html=True
                )

    if l3_table.empty or is_all_non_centralized(l3_table):
        st.markdown("""
        <div style="background-color:#f0f2f6; padding:10px; border-radius:8px">
        <b>All Level 3 stations in this province are operated by individual site hosts.</b><br>
        These use EVSE provider software (like FLO or ChargePoint) under a non-centralized pricing model.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(style_table(l3_table).to_html(index=False, escape=False), unsafe_allow_html=True)
