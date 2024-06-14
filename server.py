from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import math
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

location_updates = []

# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of the Earth in kilometers
    lat1 = math.radians(lat1)
    lon1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lat2)
    
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
    
    if not loc_id or not lat or not lon:
        return jsonify({'error': 'id, lat, and lon are required'}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({'error': 'lat and lon must be valid numbers'}), 400

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    distance = 0
    speed = 0
    cumulative_distance = 0

    if location_updates:
        user_updates = [update for update in location_updates if update['id'] == loc_id]
        if user_updates:
            last_update = user_updates[-1]
            last_lat = float(last_update['lat'])
            last_lon = float(last_update['lon'])
            last_timestamp = datetime.strptime(last_update['timestamp'], '%Y-%m-%d %H:%M:%S')
            current_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

            # Check if it's a new trip (more than 15 minutes since the last update)
            time_diff = (current_timestamp - last_timestamp).total_seconds()
            if time_diff > 15 * 60:
                cumulative_distance = 0
            else:
                distance = haversine(last_lat, last_lon, lat, lon)
                cumulative_distance = last_update.get('cumulative_distance', 0) + distance
                speed = (distance / (time_diff / 3600)) if time_diff > 0 else 0

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

    # Store the update in Firebase Firestore
    db.collection('location_updates').add(update)

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

@app.route('/locations/user/<user_id>', methods=['DELETE'])
def delete_user_locations(user_id):
    global location_updates
    location_updates = [update for update in location_updates if update['id'] != user_id]
    return jsonify({'status': f'all records for user {user_id} deleted'}), 200

@app.route('/locations/trip/<user_id>/<int:trip_index>', methods=['DELETE'])
def delete_trip(user_id, trip_index):
    global location_updates
    user_updates = [update for update in location_updates if update['id'] == user_id]
    trips = []
    current_trip = []
    last_timestamp = None

    for update in user_updates:
        current_timestamp = datetime.strptime(update['timestamp'], '%Y-%m-%d %H:%M:%S')
        if last_timestamp and (current_timestamp - last_timestamp).total_seconds() > 15 * 60:
            trips.append(current_trip)
            current_trip = []
        current_trip.append(update)
        last_timestamp = current_timestamp

    if current_trip:
        trips.append(current_trip)

    if 0 <= trip_index < len(trips):
        trip_to_delete = trips[trip_index]
        location_updates = [update for update in location_updates if update not in trip_to_delete]
        return jsonify({'status': f'trip {trip_index} for user {user_id} deleted'}), 200
    else:
        return jsonify({'status': 'trip not found'}), 404

@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
