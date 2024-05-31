import yaml

with open("dashboard.yaml", "r") as file:
    data = yaml.safe_load(file)

print (data)