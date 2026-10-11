from datetime import date, datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)
CORS(app)  # Aktiviert CORS fuer alle Routen

POSTS = [
    {
        "id": 1,
        "title": "First post",
        "content": "This is the first post.",
        "author": "Anonymous",
        "date": "2023-06-07",
    },
    {
        "id": 2,
        "title": "Second post",
        "content": "This is the second post.",
        "author": "Anonymous",
        "date": "2023-06-08",
    },
]

REQUIRED_FIELDS = ("title", "content")
POST_FIELDS = ("title", "content", "author", "date")
SORT_FIELDS = POST_FIELDS
SORT_DIRECTIONS = ("asc", "desc")
DEFAULT_AUTHOR = "Anonymous"
DATE_FORMAT = "%Y-%m-%d"

SWAGGER_URL = "/api/docs"  # Adresse der Swagger-Oberflaeche
API_URL = "/static/masterblog.json"  # Pfad zur Definitionsdatei

swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Masterblog API"},
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)


def generate_new_id():
    """Erzeugt eine neue ID (hoechste vorhandene ID + 1)."""
    if not POSTS:
        return 1
    return max(post["id"] for post in POSTS) + 1


def find_post_by_id(post_id):
    """Gibt den Beitrag mit dieser ID zurueck, sonst None."""
    for post in POSTS:
        if post["id"] == post_id:
            return post
    return None


def is_valid_date(value):
    """Prueft, ob der Wert ein gueltiges Datum im Format YYYY-MM-DD ist."""
    try:
        if len(value) != 10:
            return False
        datetime.strptime(value, DATE_FORMAT)
    except (TypeError, ValueError):
        return False
    return True


def find_missing_fields(data):
    """Gibt die fehlenden oder leeren Pflichtfelder zurueck."""
    if not isinstance(data, dict):
        return list(REQUIRED_FIELDS)

    missing = []
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    return missing


def find_invalid_fields(data):
    """Gibt mitgesendete Felder zurueck, deren Wert ungueltig ist."""
    invalid = []
    for field in POST_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, str) or not value.strip():
            invalid.append(field)
        elif field == "date" and not is_valid_date(value):
            invalid.append(field)
    return invalid


def sort_key(post, field):
    """Gibt den Sortierwert zurueck (Datum als echtes Datum, sonst Text)."""
    if field == "date":
        return datetime.strptime(post["date"], DATE_FORMAT).date()
    return post[field].lower()


def matches_search(post, field_queries, general_query):
    """Prueft, ob der Beitrag zu einem der Suchbegriffe passt."""
    for field, term in field_queries.items():
        if term and term in post[field].lower():
            return True
    if general_query:
        return any(general_query in post[f].lower() for f in POST_FIELDS)
    return False


@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Gibt alle Beitraege zurueck, optional sortiert (sort, direction)."""
    sort_field = request.args.get("sort", "").strip().lower()
    direction = request.args.get("direction", "").strip().lower()

    if sort_field and sort_field not in SORT_FIELDS:
        return jsonify({
            "error": "Invalid sort field",
            "allowed_values": list(SORT_FIELDS),
        }), 400

    if direction and direction not in SORT_DIRECTIONS:
        return jsonify({
            "error": "Invalid direction",
            "allowed_values": list(SORT_DIRECTIONS),
        }), 400

    if not sort_field:
        return jsonify(POSTS)

    sorted_posts = sorted(
        POSTS,
        key=lambda post: sort_key(post, sort_field),
        reverse=(direction == "desc"),
    )
    return jsonify(sorted_posts)


@app.route('/api/posts/search', methods=['GET'])
def search_posts():
    """Sucht Beitraege per Parameter search, title, content, author, date."""
    general_query = request.args.get("search", "").strip().lower()
    field_queries = {
        field: request.args.get(field, "").strip().lower()
        for field in POST_FIELDS
    }

    results = [
        post for post in POSTS
        if matches_search(post, field_queries, general_query)
    ]
    return jsonify(results), 200


@app.route('/api/posts', methods=['POST'])
def add_post():
    """Legt einen neuen Beitrag an (201) oder meldet Fehler (400)."""
    data = request.get_json(silent=True)

    missing = find_missing_fields(data)
    if missing:
        return jsonify({
            "error": "Missing required field(s)",
            "missing_fields": missing,
        }), 400

    invalid = find_invalid_fields(data)
    if invalid:
        return jsonify({
            "error": "Invalid value for field(s)",
            "invalid_fields": invalid,
        }), 400

    new_post = {
        "id": generate_new_id(),
        "title": data["title"],
        "content": data["content"],
        "author": data.get("author", DEFAULT_AUTHOR),
        "date": data.get("date", date.today().isoformat()),
    }
    POSTS.append(new_post)
    return jsonify(new_post), 201


@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """Loescht einen Beitrag (200) oder meldet, dass er fehlt (404)."""
    post = find_post_by_id(post_id)
    if post is None:
        return jsonify({
            "error": f"Post with id {post_id} was not found."
        }), 404

    POSTS.remove(post)
    return jsonify({
        "message": f"Post with id {post_id} has been deleted successfully."
    }), 200


@app.route('/api/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    """Aktualisiert einen Beitrag (200), meldet 404 oder 400 bei Fehlern."""
    post = find_post_by_id(post_id)
    if post is None:
        return jsonify({
            "error": f"Post with id {post_id} was not found."
        }), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    invalid = find_invalid_fields(data)
    if invalid:
        return jsonify({
            "error": "Invalid value for field(s)",
            "invalid_fields": invalid,
        }), 400

    for field in POST_FIELDS:
        if field in data:
            post[field] = data[field]
    return jsonify(post), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002, debug=True)
