# Import necessary libraries
import folium
import panel as pn
import requests
import pandas as pd
import requests_cache
from folium.plugins import Fullscreen, MarkerCluster

# Initialize Panel with custom CSS
css = """
.bk input[type="text"] {
    border: 2px solid #4CAF50; /* Green border */
    border-radius: 4px;
}
.bk .bk-btn-primary {
    background-color: #4CAF50; /* Green background */
    color: white;
}
"""
pn.extension(raw_css=[css])

# Cache API Requests
requests_cache.install_cache('traffic_cache', backend='sqlite', expire_after=180)

# API Keys and Configuration (Replace with your keys)
mapbox_api_key = 'YOUR_MAPBOX_API_KEY'
tomtom_api_key = 'YOUR_TOMTOM_API_KEY'

# Function to create a Folium map with various traffic layers
def create_map(location=(53.4084, -2.9916), filters=['All']):
    mapbox_tile_url = f"https://api.mapbox.com/styles/v1/ashicklaszo/clvo7vi0700ev01pc35ar4bi2/tiles/256/{{z}}/{{x}}/{{y}}.png?access_token={mapbox_api_key}"
    m = folium.Map(location=location, zoom_start=13, tiles=mapbox_tile_url, attr='Map data © Mapbox | Traffic data © TomTom')
    Fullscreen(position='topright').add_to(m)

    # Traffic Flow Layer
    if 'All' in filters or 'Traffic' in filters:
        traffic_flow_url = f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{{z}}/{{x}}/{{y}}.png?key={tomtom_api_key}"
        folium.TileLayer(tiles=traffic_flow_url, name='Traffic Flow', attr='TomTom Traffic Flow', overlay=True).add_to(m)

    # Traffic Incidents Layer
    if 'All' in filters or 'Accidents' in filters:
        traffic_incidents_url = f"https://api.tomtom.com/traffic/map/4/tile/incidents/s1/{{z}}/{{x}}/{{y}}.png?key={tomtom_api_key}"
        folium.TileLayer(tiles=traffic_incidents_url, name='Traffic Incidents', attr='TomTom Traffic Incidents', overlay=True).add_to(m)

    # Road Closures Layer
    if 'All' in filters or 'Road Closures' in filters:
        road_closures_url = f"https://api.tomtom.com/traffic/map/4/tile/incidents/s2/{{z}}/{{x}}/{{y}}.png?key={tomtom_api_key}"
        folium.TileLayer(tiles=road_closures_url, name='Road Closures', attr='TomTom Road Closures', overlay=True).add_to(m)

    folium.LayerControl().add_to(m)
    return m

# Function to search for a location using TomTom's Search API
def search_location(address):
    search_url = f"https://api.tomtom.com/search/2/search/{address}.json?key={tomtom_api_key}&limit=1"
    try:
        response = requests.get(search_url)
        if response.status_code == 200:
            results = response.json()
            if results['results']:
                position = results['results'][0]['position']
                return (position['lat'], position['lon'])
    except requests.RequestException as e:
        print(f"Request failed: {e}")
    return None

# Panel widgets for interactivity
search_input = pn.widgets.TextInput(name='Search Location', placeholder='Enter a location...')
search_button = pn.widgets.Button(name='Search', button_type='success')

# Use RadioButtonGroup and set default to 'All'
incident_filter = pn.widgets.RadioButtonGroup(name='Select Data to Display', value='All', options=['All', 'Traffic', 'Accidents', 'Road Closures'])

# HTML pane for displaying the map
map_pane1 = pn.pane.HTML(width=1100, height=900)

# Update map on search and filter change
def update_view(event=None):
    location = search_location(search_input.value) if search_input.value else (53.4084, -2.9916)
    # Filters now expects a list, so we wrap the value in a list
    updated_map = create_map(location=location, filters=[incident_filter.value])
    map_pane1.object = updated_map._repr_html_()

# Call update_view to initialize map at start
update_view()

search_button.on_click(update_view)
incident_filter.param.watch(update_view, 'value')

# Layout the dashboard
dashboard1 = pn.Column(
    "# Traffic Management Dashboard",
    "Search and filter traffic data to display on the map.",
    pn.Row(search_input, search_button),
    incident_filter,
    map_pane1
)

# Function to plot a route between two locations
def plot_tomtom_route(map_obj, start_coord, end_coord, api_key):
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{start_coord[0]},{start_coord[1]}:{end_coord[0]},{end_coord[1]}/json?avoid=unpavedRoads&key={api_key}"
    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to retrieve data:", response.status_code, response.text)
        return

    data = response.json()
    if 'routes' not in data:
        if 'error' in data:
            print("API Error:", data['error'].get('description', "No error description provided."))
        else:
            print("No routes found in response and no error information provided.")
        return

    routes = data['routes'][0]['legs'][0]['points']
    route_coords = [(point['latitude'], point['longitude']) for point in routes]

    folium.PolyLine(locations=route_coords, tooltip='Route', color='blue', weight=5).add_to(map_obj)

# Panel widgets for route planning
start_input = pn.widgets.TextInput(name='Start Location', placeholder='Enter start location...')
end_input = pn.widgets.TextInput(name='End Location', placeholder='Enter end location...')
route_button = pn.widgets.Button(name='Show Route', button_type='primary')
map_pane2 = pn.pane.HTML(width=1100, height=900)

# Update map with route planning
def on_route_button_click(event):
    start_location = search_location(start_input.value)
    end_location = search_location(end_input.value)
    if start_location and end_location:
        current_map = create_map()
        plot_tomtom_route(current_map, start_location, end_location, tomtom_api_key)
        map_pane2.object = current_map._repr_html_()

route_button.on_click(on_route_button_click)

# Layout including the route planning widgets
dashboard2 = pn.Column(
    "# Route Planner",
    pn.Row(start_input, end_input, route_button),
    map_pane2
)

# Load collision data and create a map centered on the UK
df = pd.read_csv('collision-2022.csv', low_memory=False)
df = df.dropna(subset=['latitude', 'longitude'])  # Ensure correct column names

def create_foliumMap(data):
    center_lat, center_lon = 54.5, -3.0  # UK coordinates for map centering
    folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=6)
    Fullscreen(position='topright').add_to(folium_map)

    # Traffic layer
    traffic_flow_url = f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{{z}}/{{x}}/{{y}}.png?key={tomtom_api_key}"
    folium.TileLayer(tiles=traffic_flow_url, name='Live Traffic', attr='TomTom Traffic Flow', overlay=True).add_to(folium_map)

    # Marker cluster for collisions
    marker_cluster = MarkerCluster().add_to(folium_map)
    for idx, row in data.iterrows():
        popup_text = f"Date: {row['date']}<br>Number of Vehicles: {row.get('number_of_vehicles', 'N/A')}<br>Number of Casualties: {row.get('number_of_casualties', 'N/A')}"
        folium.Marker(location=[row['latitude'], row['longitude']], popup=popup_text).add_to(marker_cluster)

    folium.LayerControl().add_to(folium_map)
    return folium_map

# Create the map and wrap it in HTML for the Panel display
width, height = 1100, 900
folium_map = create_foliumMap(df)
map_pane3 = pn.pane.HTML(folium_map._repr_html_(), width=width, height=height)

# Layout the traffic and collision dashboard
dashboard3 = pn.Column(
    "# Traffic and Collision Data Visualization",
    map_pane3
)

# Create a new Panel Column to hold all three dashboards
combined_dashboard = pn.Column(dashboard1, dashboard2, dashboard3)

# Serve the interactive dashboard
combined_dashboard.servable()

