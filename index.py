from flask import Flask, request, jsonify
import json
import os
import time
import random
import string

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'keys.json')

users = {}

def load_keys():
    global users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
                for key, data in users.items():
                    if 'expiresAt' in data and data['expiresAt'] is not None:
                        data['expiresAt'] = int(data['expiresAt'])
        except Exception as e:
            print('Failed to parse keys.json, starting fresh.', e)
            users = {}

def save_keys():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2)

def parse_duration(time_str):
    units = {
        'min': 60,
        'h': 3600,
        'd': 86400,
        'm': 2592000,
        'y': 31536000
    }

    import re
    match = re.match(r'^(\d+)(min|[dhmy])$', time_str, re.IGNORECASE)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2).lower()

    return value * units[unit]

def generate_api_key():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

load_keys()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    time_input = data.get('time')

    if not username or not time_input:
        return jsonify({'error': 'Username and time are required'}), 400

    expires_at = None
    if time_input.lower() != 'lifetime':
        seconds = parse_duration(time_input)
        if not seconds:
            return jsonify({'error': 'Invalid time format (e.g., 1d, 1m, 1y, 1min)'}), 400
        expires_at = int(time.time() * 1000) + seconds * 1000

    api_key = generate_api_key()
    users[api_key] = {
        'username': username,
        'hwid': None,
        'expiresAt': expires_at
    }

    save_keys()

    return jsonify({'apiKey': api_key, 'expiresAt': expires_at})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    api_key = data.get('apiKey')
    hwid = data.get('hwid')

    user = users.get(api_key)
    if not user:
        return jsonify({'error': 'Invalid key'}), 401

    if user.get('expiresAt') and int(time.time() * 1000) > user['expiresAt']:
        return jsonify({'error': 'Key expired'}), 401

    if user.get('hwid') and user['hwid'] != hwid:
        return jsonify({'error': 'HWID mismatch'}), 401

    if not user.get('hwid'):
        user['hwid'] = hwid
        save_keys()

    return jsonify({'success': True, 'expiresAt': user.get('expiresAt', 0)})

@app.route('/list', methods=['GET'])
def list_keys():
    result = []
    for key, data in users.items():
        result.append({
            'key': key,
            'username': data['username'],
            'hwid': data['hwid'],
            'expiresAt': data.get('expiresAt', None)
        })
    return jsonify(result)

@app.route('/hwid-reset', methods=['POST'])
def hwid_reset():
    data = request.get_json()
    api_key = data.get('apiKey')
    user = users.get(api_key)
    if not user:
        return jsonify({'error': 'Key not found'}), 404

    user['hwid'] = None
    save_keys()

    return jsonify({'success': True})

@app.route('/key', methods=['DELETE'])
def delete_key():
    data = request.get_json()
    api_key = data.get('apiKey')
    if api_key not in users:
        return jsonify({'error': 'Key not found'}), 404

    del users[api_key]
    save_keys()

    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f'✅ API running on port {port}')
    app.run(host='0.0.0.0', port=port)
