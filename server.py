from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

location_updates = []

@app.route('/log_location', methods=['POST'])
def log_location():
    loc_id = request.args.get('id') or request.form.get('id')
    lat = request.args.get('lat') or request.form.get('lat')
    lon = request.args.get('lon') or request.form.get('lon')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"Received data - id: {loc_id}, lat: {lat}, lon: {lon}, timestamp: {timestamp}")

    update = {
        'id': loc_id,
        'lat': lat,
        'lon': lon,
        'timestamp': timestamp
    }
    location_updates.append(update)
    return jsonify(update), 200

@app.route('/locations', methods=['GET'])
def get_locations():
    return jsonify(location_updates), 200

@app.route('/locations', methods=['DELETE'])
def delete_all_locations():
    global location_updates
    location_updates = []
    return jsonify({'status': 'all records deleted'}), 200

@app.route('/locations/<int:index>', methods=['DELETE'])
def delete_location(index):
    global location_updates
    if 0 <= index < len(location_updates):
        del location_updates[index]
        return jsonify({'status': 'record deleted'}), 200
    else:
        return jsonify({'status': 'record not found'}), 404

@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
