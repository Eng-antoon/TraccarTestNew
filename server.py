from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import firebase_admin
from firebase_admin import credentials, firestore
from geopy.distance import geodesic

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Define the global list to store location updates in memory
location_updates = []

@app.route('/log_location', methods=['POST'])
def log_location():
    global location_updates  # Ensure we're modifying the global list
    loc_id = request.args.get('id') or request.form.get('id')
    lat = request.args.get('lat') or request.form.get('lat')
    lon = request.args.get('lon') or request.form.get('lon')
    
    if not loc_id or not lat or not lon:
        print('Error: id, lat, and lon are required')
        return jsonify({'error': 'id, lat, and lon are required'}), 400

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        print('Error: lat and lon must be valid numbers')
        return jsonify({'error': 'lat and lon must be valid numbers'}), 400

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    distance = 0
    speed = 0
    cumulative_distance = 0

    user_updates = [update for update in location_updates if update['id'] == loc_id]
    
    if user_updates:
        last_update = user_updates[-1]
        last_lat = float(last_update['lat'])
        last_lon = float(last_update['lon'])
        last_timestamp = datetime.strptime(last_update['timestamp'], '%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

        time_diff = (current_timestamp - last_timestamp).total_seconds()
        if time_diff > 15 * 60:
            cumulative_distance = 0
        else:
            distance = geodesic((last_lat, last_lon), (lat, lon)).kilometers
            cumulative_distance = last_update.get('cumulative_distance', 0) + distance
            speed = (distance / (time_diff / 3600)) if time_diff > 0 else 0

            # Validation to avoid unrealistic speed
            if speed > 140:
                print(f"Error: Unrealistic speed detected: {speed} km/h")
                return jsonify({'error': 'Unrealistic speed detected'}), 400

            # Validation to avoid points within 0.2 kilometers
            if distance < 0.05:
                print(f"Error: Point too close to the previous point")
                return jsonify({'error': 'Point too close to the previous point'}), 400

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
    try:
        db.collection('location_updates').add(update)
        print('Successfully added to Firestore:', update)
    except Exception as e:
        print('Error adding to Firestore:', e)

    return jsonify(update), 200

@app.route('/locations', methods=['GET'])
def get_locations():
    try:
        location_data = []
        docs = db.collection('location_updates').stream()
        for doc in docs:
            location_data.append(doc.to_dict())
        return jsonify(location_data), 200
    except Exception as e:
        print('Error fetching locations from Firestore:', e)
        return jsonify({'error': 'Error fetching locations from Firestore'}), 500

@app.route('/locations', methods=['DELETE'])
def delete_all_locations():
    global location_updates
    location_updates = []
    try:
        docs = db.collection('location_updates').stream()
        for doc in docs:
            db.collection('location_updates').document(doc.id).delete()
        return jsonify({'status': 'all records deleted'}), 200
    except Exception as e:
        print('Error deleting locations from Firestore:', e)
        return jsonify({'error': 'Error deleting locations from Firestore'}), 500

@app.route('/locations/<int:index>', methods=['DELETE'])
def delete_location(index):
    global location_updates
    if 0 <= index < len(location_updates):
        update_to_delete = location_updates.pop(index)
        try:
            docs = db.collection('location_updates').where('timestamp', '==', update_to_delete['timestamp']).stream()
            for doc in docs:
                db.collection('location_updates').document(doc.id).delete()
            return jsonify({'status': 'record deleted'}), 200
        except Exception as e:
            print('Error deleting location from Firestore:', e)
            return jsonify({'error': 'Error deleting location from Firestore'}), 500
    else:
        return jsonify({'status': 'record not found'}), 404

@app.route('/locations/user/<user_id>', methods=['DELETE'])
def delete_user_locations(user_id):
    global location_updates
    location_updates = [update for update in location_updates if update['id'] != user_id]
    try:
        docs = db.collection('location_updates').where('id', '==', user_id).stream()
        for doc in docs:
            db.collection('location_updates').document(doc.id).delete()
        return jsonify({'status': f'all records for user {user_id} deleted'}), 200
    except Exception as e:
        print('Error deleting user locations from Firestore:', e)
        return jsonify({'error': 'Error deleting user locations from Firestore'}), 500

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
        try:
            for update in trip_to_delete:
                docs = db.collection('location_updates').where('timestamp', '==', update['timestamp']).stream()
                for doc in docs:
                    db.collection('location_updates').document(doc.id).delete()
            return jsonify({'status': f'trip {trip_index} for user {user_id} deleted'}), 200
        except Exception as e:
            print('Error deleting trip from Firestore:', e)
            return jsonify({'error': 'Error deleting trip from Firestore'}), 500
    else:
        return jsonify({'status': 'trip not found'}), 404

@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
