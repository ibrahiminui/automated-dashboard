import yaml
from google.cloud import monitoring_dashboard_v1
import json
import copy

def load_config(file_path):
    """Load and return configuration from a YAML file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def load_dashboard_json(file_path):
    """Load and return the dashboard JSON from a file."""
    with open(file_path, 'r') as file:
        return json.load(file)

def create_dashboard(project_id, config_file, json_file):
    # Load the configuration file
    config = load_config(config_file)
    display_name = config['dashboard']['name']
    
    # Collect all chart titles dynamically from the config file
    chart_titles = [metric['chart_name'] for metric in config['Metrics']]
    print("Chart Titles: ", chart_titles)  # Debug: Print chart titles

    client = monitoring_dashboard_v1.DashboardsServiceClient()
    project_name = f"projects/{project_id}"
    
    # Load the base JSON structure from the JSON file
    dashboard_json = load_dashboard_json(json_file)

    # Define the display name and mosaic layout directly in the Python code
    dashboard_structure = {
        "display_name": display_name,
        "mosaic_layout": {
            "columns": 48,
            "tiles": []
        }
    }

    # Update the JSON with dynamic values
    for index, title in enumerate(chart_titles):
        print(f"Processing chart {index + 1}: {title}")  # Debug: Verify each title is processed
        new_tile = copy.deepcopy(dashboard_json["tiles_template"])
        new_tile["widget"]["title"] = title
        
        # Adjust position based on index
        if index % 2 == 0:  # Start new row after every 2 tiles
            new_tile['x_pos'] = 0  # Start from the first column
        else:
            new_tile['x_pos'] = 24  # Start from the middle column
        
        new_tile['y_pos'] = (index // 2) * 16  # Increase y position to move down for new rows
        dashboard_structure["mosaic_layout"]["tiles"].append(new_tile)
     

    # Optional: Remove the template from the JSON structure if not needed
    # del dashboard_json["tiles_template"]

    dashboard = monitoring_dashboard_v1.types.Dashboard(
        display_name=dashboard_structure["display_name"],
        mosaic_layout=dashboard_structure["mosaic_layout"]
    )

    response = client.create_dashboard(parent=project_name, dashboard=dashboard)
    print("Dashboard created: ", response.name)
    return response

# Example usage
project_id = 'staticwebsitegcs'  # replace with your GCP project ID
create_dashboard(project_id, 'dashboard.yaml', 'dashboard_line.json')
