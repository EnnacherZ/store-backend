import json
import os

PARAMS_PATH = os.path.join(os.path.dirname(__file__), 'parameters.json')

def load_parameters():
    with open(PARAMS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_param_values(product_type, label):
    try:
        params = load_parameters()
        return params.get(product_type, {}).get(label, [])
    except Exception:
        return []