from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import sqlite3
import os
import math

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

DATABASE = 'locations.db'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                lat REAL,
                lon REAL,
                timestamp TEXT,
                distance REAL,
                cumulative_distance REAL,
                speed REAL
            )
        ''')
        conn.commit()

def query_db(query, args=(), one=False):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        rv = cursor.fetchall()
        conn.commit()
        return (rv[0] if rv else None) if one else rv

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
    user_id = request.args.get('id') or request.form.get('id')
    lat = float(request.args.get('lat') or request.form.get('lat'))
    lon = float(request.args.get('lon') or request.form.get('lon'))
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    distance = 0
    speed = 0
    cumulative_distance = 0

    last_update = query_db('SELECT * FROM locations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1', [user_id], one=True)
    
    if last_update:
        last_lat = last_update[2]
        last_lon = last_update[3]
        last_timestamp = datetime.strptime(last_update[4], '%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

        # Check if it's a new trip (more than 15 minutes since the last update)
        time_diff = (current_timestamp - last_timestamp).total_seconds()
        if time_diff > 15 * 60:
            cumulative_distance = 0
        else:
            distance = haversine(last_lat, last_lon, lat, lon)
            cumulative_distance = last_update[6] + distance
            speed = (distance / (time_diff / 3600)) if time_diff > 0 else 0

    # Ignore records with speed less than 0.3 km/h
    if speed < 0.3:
        return jsonify({'status': 'ignored', 'reason': 'speed less than 0.3 km/h'}), 200

    query_db('''
        INSERT INTO locations (user_id, lat, lon, timestamp, distance, cumulative_distance, speed)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [user_id, lat, lon, timestamp, distance, cumulative_distance, speed])

    update = {
        'user_id': user_id,
        'lat': lat,
        'lon': lon,
        'timestamp': timestamp,
        'distance': distance,
        'cumulative_distance': cumulative_distance,
        'speed': speed
    }
    return jsonify(update), 200

@app.route('/locations', methods=['GET'])
def get_locations():
    locations = query_db('SELECT * FROM locations')
    return jsonify(locations), 200

@app.route('/locations', methods=['DELETE'])
def delete_all_locations():
    query_db('DELETE FROM locations')
    return jsonify({'status': 'all records deleted'}), 200

@app.route('/locations/<int:index>', methods=['DELETE'])
def delete_location(index):
    query_db('DELETE FROM locations WHERE id = ?', [index])
    return jsonify({'status': 'record deleted'}), 200

@app.route('/locations/user/<user_id>', methods=['DELETE'])
def delete_user_locations(user_id):
    query_db('DELETE FROM locations WHERE user_id = ?', [user_id])
    return jsonify({'status': f'all records for user {user_id} deleted'}), 200

@app.route('/locations/trip/<user_id>/<trip_index>', methods=['DELETE'])
def delete_trip(user_id, trip_index):
    user_updates = query_db('SELECT * FROM locations WHERE user_id = ? ORDER BY timestamp', [user_id])
    trips = []
    current_trip = []
    last_timestamp = None

    for update in user_updates:
        current_timestamp = datetime.strptime(update[4], '%Y-%m-%d %H:%M:%S')
        if last_timestamp and (current_timestamp - last_timestamp).total_seconds() > 15 * 60:
            trips.append(current_trip)
            current_trip = []
        current_trip.append(update)
        last_timestamp = current_timestamp

    if current_trip:
        trips.append(current_trip)

    if 0 <= int(trip_index) < len(trips):
        trip_to_delete = trips[int(trip_index)]
        for record in trip_to_delete:
            query_db('DELETE FROM locations WHERE id = ?', [record[0]])
        return jsonify({'status': f'trip {trip_index} for user {user_id} deleted'}), 200
    else:
        return jsonify({'status': 'trip not found'}), 404

@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
