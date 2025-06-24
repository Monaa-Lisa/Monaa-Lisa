from flask import Blueprint, jsonify, request
from Util.logger import global_logger

# This builds the base for all further routes
api = Blueprint('api', __name__)

# setup logging
logger = global_logger.setup_logger("REST", "api-routes")

# Define a test route
@api.route('/test', methods=['GET'])
def test_route():
    return jsonify({'message': 'API running'}), 200

# Define a route to fetch publication
@api.route('/fetch-paper', methods=['GET'])
def fetch_publication_route():
    params = request.args
    logger.info(params)
    if "paper_id" in params:
        # id for the requested paper
        paper_id = params["paper_id"]
        return "test"
    else:
        return "no id provided"