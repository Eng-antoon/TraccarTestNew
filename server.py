from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import math
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Define the global list to store location updates in memory
location_updates = []

def vincenty(lat1, lon1, lat2, lon2):
    a = 6378137.0  # major axis
    f = 1 / 298.257223563  # flattening
    b = (1 - f) * a  # minor axis

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    L = lon2 - lon1

    U1 = math.atan((1 - f) * math.tan(lat1))
    U2 = math.atan((1 - f) * math.tan(lat2))
    sinU1 = math.sin(U1)
    cosU1 = math.cos(U1)
    sinU2 = math.sin(U2)
    cosU2 = math.cos(U2)

    lambda_ = L
    lambdaP = 2 * math.pi
    iterLimit = 100

    while abs(lambda_ - lambdaP) > 1e-12 and iterLimit > 0:
        sinLambda = math.sin(lambda_)
        cosLambda = math.cos(lambda_)
        sinSigma = math.sqrt((cosU2 * sinLambda) ** 2 +
                             (cosU1 * sinU2 - sinU1 * cosU2 * cosLambda) ** 2)
        if sinSigma == 0:
            return 0  # coincident points
        cosSigma = sinU1 * sinU2 + cosU1 * cosU2 * cosLambda
        sigma = math.atan2(sinSigma, cosSigma)
        sinAlpha = cosU1 * cosU2 * sinLambda / sinSigma
        cosSqAlpha = 1 - sinAlpha ** 2
        cos2SigmaM = cosSigma - 2 * sinU1 * sinU2 / cosSqAlpha
        if math.isnan(cos2SigmaM):
            cos2SigmaM = 0  # equatorial line
        C = f / 16 * cosSqAlpha * (4 + f * (4 - 3 * cosSqAlpha))
        lambdaP = lambda_
        lambda_ = L + (1 - C) * f * sinAlpha * (
            sigma + C * sinSigma * (
                cos2SigmaM + C * cosSigma * (
                    -1 + 2 * cos2SigmaM ** 2)))

        iterLimit -= 1

    if iterLimit == 0:
        return None  # formula failed to converge

    uSq = cosSqAlpha * (a ** 2 - b ** 2) / (b ** 2)
    A = 1 + uSq / 16384 * (4096 + uSq * (-768 + uSq * (320 - 175 * uSq)))
    B = uSq / 1024 * (256 + uSq * (-128 + uSq * (74 - 47 * uSq)))
    deltaSigma = B * sinSigma * (
        cos2SigmaM + B / 4 * (
            cosSigma * (-1 + 2 * cos2SigmaM ** 2) -
            B / 6 * cos2SigmaM * (-3 + 4 * sinSigma ** 2) * (-3 + 4 * cos2SigmaM ** 2)))

    s = b * A * (sigma - deltaSigma)

    return s  # distance in meters

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
            distance = vincenty(last_lat, last_lon, lat, lon) / 1000  # Convert to kilometers
            cumulative_distance = last_update.get('cumulative_distance', 0) + distance
            speed = (distance / (time_diff / 3600)) if time_diff > 0 else 0

            # Validation to avoid unrealistic speed
            if speed > 130:
                print(f"Error: Unrealistic speed detected: {speed} km/h")
                return jsonify({'error': 'Unrealistic speed detected'}), 400

            # Validation to avoid duplicate locations within 10 meters and 30 seconds
            if distance < 0.05 and time_diff < 30:
                print(f"Error: Duplicate location detected: distance={distance}, time_diff={time_diff}")
                return jsonify({'error': 'Duplicate location detected'}), 400

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
