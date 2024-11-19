import json


def load_json_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


def save_json_file(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file)
