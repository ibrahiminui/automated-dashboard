import yaml
from google.cloud import monitoring_dashboard_v1, storage
import json
import copy
from google.protobuf import field_mask_pb2

def load_config(file_path):
    """Load and return configuration from a YAML file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def load_dashboard_json(file_path):
    """Load and return the dashboard JSON from a file."""
    with open(file_path, 'r') as file:
        return json.load(file)

def upload_dashboard_state(bucket_name, file_name, data):
    """Upload the dashboard state to Google Cloud Storage."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(json.dumps(data))
    print(f"Dashboard state uploaded to {file_name} in bucket {bucket_name}")

def download_dashboard_state(bucket_name, file_name):
    """Download the dashboard state from Google Cloud Storage."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    if blob.exists():
        dashboard_state = json.loads(blob.download_as_string())
        print(f"Dashboard state downloaded from {file_name} in bucket {bucket_name}")
        return dashboard_state
    else:
        return None

def get_existing_dashboard(client, dashboard_name):
    """Retrieve the existing dashboard details, including etag."""
    try:
        dashboard = client.get_dashboard(name=dashboard_name)
        return dashboard
    except Exception as e:
        print(f"Failed to retrieve existing dashboard: {e}")
        return None

def create_or_update_dashboard(project_id, config_file, json_file_line, json_file_group, bucket_name, state_file):
    # Load the configuration file
    config = load_config(config_file)
    display_name = config['dashboard']['name']
    
    # Collect all chart titles, metrics, resource types, and chart types dynamically from the config file
    charts = [(metric['chart_name'], metric.get('metric'), metric.get('resource_type'), metric['chart_type']) for metric in config['Metrics']]
    print("Charts: ", charts)  # Debug: Print charts

    client = monitoring_dashboard_v1.DashboardsServiceClient()
    project_name = f"projects/{project_id}"
    
    # Load the base JSON structures from the JSON files
    dashboard_json_line = load_dashboard_json(json_file_line)
    dashboard_json_group = load_dashboard_json(json_file_group)

    # Define the display name and mosaic layout directly in the Python code
    dashboard_structure = {
        "display_name": display_name,
        "mosaic_layout": {
            "columns": 48,
            "tiles": []
        }
    }

    # Initialize a variable to keep track of the current y position
    current_y_pos = 0

    # Update the JSON with dynamic values
    for index, (title, metric, resource_type, chart_type) in enumerate(charts):
        print(f"Processing chart {index + 1}: {title} ({chart_type})")  # Debug: Verify each title and type
        if chart_type == 'line':
            new_tile = copy.deepcopy(dashboard_json_line["tiles_template"])
            new_tile['width'] = 24
            new_tile['height'] = 16
            if metric and resource_type:
                new_tile["widget"]["xy_chart"]["data_sets"][0]["time_series_query"]["time_series_filter"]["filter"] = f'metric.type="{metric}" resource.type="{resource_type}"'
        elif chart_type == 'group':
            new_tile = copy.deepcopy(dashboard_json_group["tiles_template"])
            new_tile['width'] = 48  # Ensure the collapsible group spans the full width
            new_tile['height'] = 2
        else:
            print(f"Unknown chart type {chart_type} for chart {title}, skipping.")
            continue
        
        new_tile["widget"]["title"] = title
        
        # Adjust position based on index
        new_tile['x_pos'] = 0  # All tiles start from the first column
        new_tile['y_pos'] = current_y_pos  # Set the current y position
        current_y_pos += new_tile['height']  # Increase y position for the next row

        dashboard_structure["mosaic_layout"]["tiles"].append(new_tile)
        print(f"Added tile: {new_tile}")  # Debug: Print each added tile

    # Check if the dashboard state exists in GCS
    dashboard_state = download_dashboard_state(bucket_name, state_file)

    if dashboard_state:
        # Retrieve existing dashboard details including etag
        dashboard_id = dashboard_state['dashboard_id']
        dashboard_name = f"{project_name}/dashboards/{dashboard_id}"
        existing_dashboard = get_existing_dashboard(client, dashboard_name)

        if existing_dashboard:
            # Update existing dashboard with the new structure and etag
            dashboard = monitoring_dashboard_v1.types.Dashboard(
                name=existing_dashboard.name,
                display_name=dashboard_structure["display_name"],
                mosaic_layout=dashboard_structure["mosaic_layout"],
                etag=existing_dashboard.etag
            )
            update_request = monitoring_dashboard_v1.UpdateDashboardRequest(
                dashboard=dashboard
            )
            response = client.update_dashboard(request=update_request)
            print("Dashboard updated: ", response.name)
        else:
            print("Failed to retrieve existing dashboard. Creating a new one instead.")
            dashboard = monitoring_dashboard_v1.types.Dashboard(
                display_name=dashboard_structure["display_name"],
                mosaic_layout=dashboard_structure["mosaic_layout"]
            )
            response = client.create_dashboard(parent=project_name, dashboard=dashboard)
            print("Dashboard created: ", response.name)
            
            # Save the new dashboard state to GCS
            dashboard_state = {'dashboard_id': response.name.split('/')[-1]}
            upload_dashboard_state(bucket_name, state_file, dashboard_state)
    else:
        # Create new dashboard
        dashboard = monitoring_dashboard_v1.types.Dashboard(
            display_name=dashboard_structure["display_name"],
            mosaic_layout=dashboard_structure["mosaic_layout"]
        )
        response = client.create_dashboard(parent=project_name, dashboard=dashboard)
        print("Dashboard created: ", response.name)
        
        # Save the new dashboard state to GCS
        dashboard_state = {'dashboard_id': response.name.split('/')[-1]}
        upload_dashboard_state(bucket_name, state_file, dashboard_state)

    return response

# Example usage
project_id = 'staticwebsitegcs'  # replace with your GCP project ID
bucket_name = 'dashboard_state'  # replace with your GCS bucket name (do not include 'gs://')
state_file = 'dashboard_state.json'  # the file to store dashboard state
create_or_update_dashboard(project_id, 'dashboard.yaml', 'dashboard_line.json', 'dashboard_group.json', bucket_name, state_file)
