from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import math

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

location_updates = []

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of the Earth in kilometers
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance

@app.route('/log_location', methods=['POST'])
def log_location():
    loc_id = request.args.get('id') or request.form.get('id')
    lat = request.args.get('lat') or request.form.get('lat')
    lon = request.args.get('lon') or request.form.get('lon')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    distance = 0
    speed = 0
    cumulative_distance = 0

    if location_updates:
        last_update = location_updates[-1]
        last_lat = float(last_update['lat'])
        last_lon = float(last_update['lon'])
        last_timestamp = datetime.strptime(last_update['timestamp'], '%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

        distance = haversine(last_lat, last_lon, float(lat), float(lon))
        cumulative_distance = last_update.get('cumulative_distance', 0) + distance
        time_diff = (current_timestamp - last_timestamp).total_seconds() / 3600  # Time difference in hours
        if time_diff > 0:
            speed = distance / time_diff
    else:
        cumulative_distance = distance

    print(f"Received data - id: {loc_id}, lat: {lat}, lon: {lon}, timestamp: {timestamp}, distance: {distance:.2f} km, cumulative_distance: {cumulative_distance:.2f} km, speed: {speed:.2f} km/h")

    update = {
        'id': loc_id,
        'lat': lat,
        'lon': lon,
        'timestamp': timestamp,
        'distance': distance,
        'cumulative_distance': cumulative_distance,
        'speed': speed
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
