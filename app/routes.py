from os import name

from flask import Blueprint, jsonify, request
from app.es_client import get_es_client
from app.search_service import search_studies
from elasticsearch import (ConnectionError as ESConnectionError,
                           ConnectionTimeout)
from elasticsearch import ApiError

import logging


studies_bp = Blueprint('studies', __name__)


def parse_integer_param(param_value, default=None, minimum=None, maximum=None):
    raw_value = request.args.get(param_value)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        raise ValueError(f"{param_value} must be an integer.")

    if minimum is not None and value < minimum:
        raise ValueError(f"{param_value} must be >= {minimum}.")

    if maximum is not None and value > maximum:
        raise ValueError(f"{param_value} must be <= {maximum}.")

    return value


@studies_bp.route('/api/health/elasticsearch')
def elasticsearch_health():
    try:
        client = get_es_client()
        if client.ping():
            return jsonify({
                "status": "healthy",
                "elasticsearch": "connected"
            }), 200

        return jsonify({
            "status": "unhealthy",
            "elasticsearch": "disconnected"
        }), 503

    except (ESConnectionError, ConnectionTimeout) as e:
        return jsonify({
            "status": "unhealthy",
            "elasticsearch": "disconnected",
        }), 503


@studies_bp.route('/api/studies/search')
def search_studies_endpoint():
    search_text = request.args.get('q')
    status = request.args.get('status')
    sort_by = request.args.get('sort_by')
    order = request.args.get('order', 'desc').lower()
    try:
        min_participants = parse_integer_param('min_participants', minimum=0)
        page = parse_integer_param('page', default=1, minimum=1)
        page_size = parse_integer_param('page_size', default=10, minimum=1, maximum=100)
        if page*page_size > 10000:
            return jsonify({
                "error": "Requested page exceeds the 10000-result window"
            }), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if order not in ('asc', 'desc'):
        return jsonify({"error": "Order must be asc or desc"}), 400

    if sort_by and sort_by not in ('participant_count', 'study_id'):
        return jsonify({"error": "Unsupported sort_by field"}), 400

    if page < 1 or not 1<=page_size<=100:
        return jsonify({"error": "page must be >= 1 and page_size must be between 1 and 100"}), 400

    try:
        client = get_es_client()
        result = search_studies(client, search_text, status, min_participants, sort_by, order, page, page_size)
        return jsonify(result), 200
    except (ESConnectionError, ConnectionTimeout):
        logging.exception("Elasticsearch connection failure")
        return jsonify({"error": "Search service temporarily unavailable"}), 503
    except ApiError:
        logging.exception("Elasticsearch API failure")
        return jsonify({"error": "Search backend error"}), 502