from flask import Blueprint, jsonify

# Routen für API
api = Blueprint('api', __name__)

# Definiere eine Test Route
@api.route('/test', methods=['GET'])
def test_route():
    return jsonify({'message': 'API running'}), 200
