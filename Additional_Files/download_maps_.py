import pandas as pd
import folium
from folium.plugins import MarkerCluster, LocateControl
import os

# --- Load & Process Data ---
def process_charging_ports_data(file_path):
    charging_ports = pd.read_csv(file_path)
    charging_ports["ports"] = 1

    # Tesla L2
    charging_ports['L2_Tesla'] = charging_ports['EV Network'].apply(lambda x: 1 if 'Tesla Destination' in str(x) else 0)
    charging_ports['L2_Tesla'] = charging_ports.apply(
        lambda row: 0 if row.get('EV J1772 Connector Count', 0) == 1 and row['L2_Tesla'] == 1 else row['L2_Tesla'],
        axis=1
    )

    # Tesla L3
    charging_ports['L3_Tesla'] = charging_ports.apply(
        lambda row: 1 if row.get('EV J3400 Connector Count', 0) == 1 and row['L2_Tesla'] == 0 else 0,
        axis=1
    )

    # Adjust dual DCFC
    DCFC_ports = charging_ports[charging_ports["EV DC Fast Count"] > 0]
    filtered_df = DCFC_ports[(DCFC_ports['EV CHAdeMO Connector Count'] == 1) & (DCFC_ports['EV CCS Connector Count'] == 1)]
    filtered_df.loc[:, 'EV CHAdeMO Connector Count'] = 0
    filtered_df.loc[:, 'EV CCS Connector Count'] = 0
    filtered_df.loc[:, 'ChademoCCSsingleuseport'] = 1

    charging_ports.loc[filtered_df.index, ['EV CHAdeMO Connector Count', 'EV CCS Connector Count']] = \
        filtered_df[['EV CHAdeMO Connector Count', 'EV CCS Connector Count']]
    charging_ports.loc[filtered_df.index, 'ChademoCCSsingleuseport'] = 1

    # L2 and L3 port flags
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

    # Clean network names
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
    charging_ports['Clean_Network_Name'] = charging_ports['EV Network'].map(network_name_mapping)

    # Drop IVY stations outside Ontario
    charging_ports = charging_ports[~((charging_ports['EV Network'] == 'IVY') & (charging_ports['State'] != 'ON'))]

    return charging_ports


# --- Map Generator ---
def plot_charging_map_by_province(df, province_code):
    df = df[df['State'] == province_code].dropna(subset=['Latitude', 'Longitude']).copy()
    if df.empty:
        return None

    map_center = [df['Latitude'].mean(), df['Longitude'].mean()]
    ev_map = folium.Map(location=map_center, zoom_start=6)

    l2_cluster = MarkerCluster(name='Level 2 Charging').add_to(ev_map)
    l3_cluster = MarkerCluster(name='Level 3 Charging').add_to(ev_map)

    for _, row in df.iterrows():
        popup_text = f"{row['Station Name']}<br>{row['Street Address']}<br>{row['City']}"
        if row.get('L2_port', 0) == 1:
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=popup_text,
                icon=folium.Icon(color='green', icon='flash', prefix='fa')
            ).add_to(l2_cluster)
        if row.get('L3_port', 0) == 1:
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=popup_text,
                icon=folium.Icon(color='red', icon='bolt', prefix='fa')
            ).add_to(l3_cluster)

    LocateControl(auto_start=False).add_to(ev_map)
    folium.LayerControl(collapsed=False).add_to(ev_map)

    return ev_map


# --- Save All Maps ---
def export_all_province_maps(charging_ports_df, output_dir="maps"):
    os.makedirs(output_dir, exist_ok=True)

    provinces = sorted(charging_ports_df['State'].dropna().unique())
    for prov in provinces:
        print(f"Generating map for {prov}...")
        map_obj = plot_charging_map_by_province(charging_ports_df, prov)
        if map_obj:
            map_obj.save(os.path.join(output_dir, f"{prov}_map.html"))
        else:
            print(f"  Skipped {prov} (no data).")


# --- Run It ---
if __name__ == "__main__":
    input_file = "alt_fuel_stations_ev_charging_units (May 19 2025).csv"  # Or whatever the monthly name is
    charging_ports = process_charging_ports_data(input_file)
    export_all_province_maps(charging_ports)
    print("✅ All province maps generated.")
