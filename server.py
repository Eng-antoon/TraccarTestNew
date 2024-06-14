from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import os
import math

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Firebase credentials JSON embedded directly
firebase_credentials = {
    "type": "service_account",
    "project_id": "illa-traccartest",
    "private_key_id": "414086cf6fcf638a955e625d743c6cbc0dd0f2da",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDJon54z//05IdQ\nBveYQxo5YPRAcWAqTANKksh3Ffrj4QcRWKhwK0VpYHp/qCwUbceW1KCryE1iNz9l\nRqLHw4De08Os/1bdskVlQOfI88GNuT73dXM/7OubwCpGdd3Mkd/lTl6S2tGRJLGu\nQ2YGma0VF8lGZtaq54/hw22BgE6Y7ziADsTccxWPjeK5Mk4VPk0n3m1CALGGMfc+\nnxEweoLgMIpgRZvbwYww9fY8iarh80sxeDOAPtpYRAYbbwGNkwCjx0vM1Jn6WdnE\nIXV3mQZznpbUZfWHfBAUcbaLRol8mkS8PfKgTHrUfHXy2Mhb++y2I/ZVIekMrBAB\nKLu03S/BAgMBAAECggEAAIWAkTxse4wpw225LzYhN7vF9fK1Hnbi3UsC5Lf0VamL\n1KInkV6zR8H9nx3mu0jLZtr27WrPtGzTJ6ZmnmClkS34CBcC+QDQiCICV3U173Fm\ntcoieaxZsaXuFg+Q+sn3y8aHnRaeyyLOqNY4ydSU64SLuzhh3sBJkXppapfT3DZk\n//i5bCrsq+f3UtKs8fU3nhs19S6cKYHc4Ar0EyVdpdcxyd/yo5RJNBUCZmww9l0M\nbp/LmZJIOrk5xfjRVA2WyZEuwz0sgx+YKddZ4mCIzdF4EuJx0n8t2y+Zj/YHC6Hx\nhGSLhLmf9l6JkIJLlS/YUWWihpNLmieY/5ggPyF5ZwKBgQDzDNbOSNjkqTDqjAlP\nVUHsJFEJ1vHXK/bNjNUVqRG0Ig1pSo3gvTk/dPYgo0Vce53LmMjogFim3RYk5az7\nCRB3pCAJB6Rjnwr5v7Hi+B7pHmPdCdHI4hogFAH6NiRIiVFbuVB44LO/OCkmDLj8\nXNyXVxVKkOP7sKy+jHuvKIVDLwKBgQDUYMGQCaN+7/jw8YDxtexoE6t/hWLpR1B8\nJlfGhHp835o/8Rzm4Lj1VbskPP/CnLBtNiuOaQuBQRl+vYy16RJBxw+69Z1U3ouc\nJmVqITRdvoouTrRVg2Xvc0maQh531dms2ItwR08y72TH5lYHrm3c711TGFXTARN5\n8dhVaUXADwKBgQC+X48dMvgYWuHCxX9BUZF6KpQDNgZluLzvEeGRvsTsKEQC9e+d\nWfmuV6m1tM1OfFEDuR+c5XMK+F8w9WmBk/7/B2JEUGUV1uxc5Sarlhd4F2K3LsrQ\nIzG9cI5/8sqGunAsfUGn/LEuFQo+EHcQzJfIPuChcE3yxdb4xcbXUtDW5wKBgA+1\nBDvR6qyltOSlB+NYkB52bfWleNZF9vbnoxBElgaMRw05mOiecC984rVgaY4MJqQ9\nIGWM8VPi667K+BAwJ7CDt28dYUB4oRywXknGIOhaAkBAg+fbKvvVq/jjsPst7sZw\n0YdBTuM2f16lc3Fn/iob7ewKXbaYWsdnEpfmjEkTAoGAOpRClUbVnbHQIXY4E8Xt\n5BDMmomMyvhtSm0xBstkcOfI/vUdCpLocE48gGLh8v9c4PL6jcA4qA6mM/t/I0c3\npyoC1yFQqlAnecZcM62K1XSjia6+hzWe5Sg3rpmFz4Mk85kxv+d/R7+xxuPzz5ya\nqg0lELkb6a9G7WOlX4vcKUg=\n-----END PRIVATE KEY-----\n".replace("\\n", "\n"),
    "client_email": "firebase-adminsdk-7yngb@illa-traccartest.iam.gserviceaccount.com",
    "client_id": "114884629195270028026",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-7yngb%40illa-traccartest.iam.gserviceaccount.com"
}

cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred)
db = firestore.client()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of the Earth in kilometers
    lat1 = math.radians(lat1)
    lon1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lat2)
    
    dlat = lat2 - lat1
    dlon = lon2 - lat1
    
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

    # Fetch last update from Firestore
    last_update = db.collection('locations').where('user_id', '==', user_id).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()
    last_update = next(last_update, None)
    
    if last_update:
        last_update = last_update.to_dict()
        last_lat = last_update['lat']
        last_lon = last_update['lon']
        last_timestamp = datetime.strptime(last_update['timestamp'], '%Y-%m-%d %H:%M:%S')
        current_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

        # Check if it's a new trip (more than 15 minutes since the last update)
        time_diff = (current_timestamp - last_timestamp).total_seconds()
        if time_diff > 15 * 60:
            cumulative_distance = 0
        else:
            distance = haversine(last_lat, last_lon, lat, lon)
            cumulative_distance = last_update['cumulative_distance'] + distance
            speed = (distance / (time_diff / 3600)) if time_diff > 0 else 0

    # Ignore records with speed less than 0.3 km/h
    if speed < 0.3:
        return jsonify({'status': 'ignored', 'reason': 'speed less than 0.3 km/h'}), 200

    update = {
        'user_id': user_id,
        'lat': lat,
        'lon': lon,
        'timestamp': timestamp,
        'distance': distance,
        'cumulative_distance': cumulative_distance,
        'speed': speed
    }
    db.collection('locations').add(update)
    return jsonify(update), 200

@app.route('/locations', methods=['GET'])
def get_locations():
    locations_ref = db.collection('locations')
    docs = locations_ref.stream()
    locations = [doc.to_dict() for doc in docs]
    return jsonify(locations), 200

@app.route('/locations', methods=['DELETE'])
def delete_all_locations():
    locations_ref = db.collection('locations')
    docs = locations_ref.stream()
    for doc in docs:
        doc.reference.delete()
    return jsonify({'status': 'all records deleted'}), 200

@app.route('/locations/<doc_id>', methods=['DELETE'])
def delete_location(doc_id):
    db.collection('locations').document(doc_id).delete()
    return jsonify({'status': 'record deleted'}), 200

@app.route('/locations/user/<user_id>', methods=['DELETE'])
def delete_user_locations(user_id):
    locations_ref = db.collection('locations')
    docs = locations_ref.where('user_id', '==', user_id).stream()
    for doc in docs:
        doc.reference.delete()
    return jsonify({'status': f'all records for user {user_id} deleted'}), 200

@app.route('/locations/trip/<user_id>/<trip_index>', methods=['DELETE'])
def delete_trip(user_id, trip_index):
    locations_ref = db.collection('locations')
    user_updates = list(locations_ref.where('user_id', '==', user_id).order_by('timestamp').stream())
    trips = []
    current_trip = []
    last_timestamp = None

    for doc in user_updates:
        update = doc.to_dict()
        current_timestamp = datetime.strptime(update['timestamp'], '%Y-%m-%d %H:%M:%S')
        if last_timestamp and (current_timestamp - last_timestamp).total_seconds() > 15 * 60:
            trips.append(current_trip)
            current_trip = []
        current_trip.append(doc)
        last_timestamp = current_timestamp

    if current_trip:
        trips.append(current_trip)

    if 0 <= int(trip_index) < len(trips):
        trip_to_delete = trips[int(trip_index)]
        for doc in trip_to_delete:
            doc.reference.delete()
        return jsonify({'status': f'trip {trip_index} for user {user_id} deleted'}), 200
    else:
        return jsonify({'status': 'trip not found'}), 404

@app.route('/')
def serve_index():
    return send_from_directory(os.getcwd(), 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
