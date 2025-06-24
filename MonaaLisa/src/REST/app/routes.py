from flask import Blueprint, jsonify

# This builds the base for all further routes
api = Blueprint('api', __name__)

# Define a test route
@api.route('/test', methods=['GET'])
def test_route():
    return jsonify({'message': 'API running'}), 200