import copy
import json
import os
import tempfile
import threading
from datetime import date, datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)
CORS(app)  # Aktiviert CORS fuer alle Routen

FILE_NAME = "posts.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTS_FILE = os.path.join(BASE_DIR, FILE_NAME)
FILE_LOCK = threading.Lock()  # Verhindert gleichzeitige Dateizugriffe

DEFAULT_POSTS = [
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


class StorageError(Exception):
    """Wird ausgeloest, wenn die Beitragsdatei nicht nutzbar ist."""


@app.errorhandler(StorageError)
def handle_storage_error(error):
    """Antwortet bei Dateifehlern mit 500 und einer JSON-Meldung."""
    app.logger.error("Storage error: %s", error)
    return jsonify({
        "error": "Posts storage is not available",
        "details": str(error),
    }), 500


def is_valid_date(value):
    """Prueft, ob der Wert ein gueltiges Datum im Format YYYY-MM-DD ist."""
    try:
        if len(value) != 10:
            return False
        datetime.strptime(value, DATE_FORMAT)
    except (TypeError, ValueError):
        return False
    return True


def is_valid_stored_post(post):
    """Prueft, ob ein Eintrag aus der Datei ein vollstaendiger Beitrag ist."""
    return (
        isinstance(post, dict)
        and isinstance(post.get("id"), int)
        and all(isinstance(post.get(field), str) for field in POST_FIELDS)
        and is_valid_date(post["date"])
    )


def save_posts(posts):
    """Schreibt alle Beitraege sicher in die JSON-Datei."""
    tmp_path = None
    try:
        folder = os.path.dirname(POSTS_FILE)
        handle, tmp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(posts, file, indent=2, ensure_ascii=False)
        os.replace(tmp_path, POSTS_FILE)
    except OSError as error:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise StorageError(f"{FILE_NAME} could not be written") from error


def load_posts():
    """Liest alle Beitraege aus der JSON-Datei, legt sie bei Bedarf an."""
    if not os.path.exists(POSTS_FILE):
        posts = copy.deepcopy(DEFAULT_POSTS)
        save_posts(posts)
        return posts

    try:
        with open(POSTS_FILE, "r", encoding="utf-8-sig") as file:
            posts = json.load(file)
    except json.JSONDecodeError as error:
        raise StorageError(
            f"{FILE_NAME} contains invalid JSON "
            f"(line {error.lineno}, column {error.colno})"
        ) from error
    except (OSError, UnicodeDecodeError) as error:
        raise StorageError(f"{FILE_NAME} could not be read") from error

    if not isinstance(posts, list):
        raise StorageError(f"{FILE_NAME} must contain a list of posts")
    if not all(is_valid_stored_post(post) for post in posts):
        raise StorageError(f"{FILE_NAME} contains an invalid post")
    return posts


def generate_new_id(posts):
    """Erzeugt eine neue ID (hoechste vorhandene ID + 1)."""
    if not posts:
        return 1
    return max(post["id"] for post in posts) + 1


def find_post_by_id(posts, post_id):
    """Gibt den Beitrag mit dieser ID zurueck, sonst None."""
    for post in posts:
        if post["id"] == post_id:
            return post
    return None


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

    with FILE_LOCK:
        posts = load_posts()

    if not sort_field:
        return jsonify(posts)

    sorted_posts = sorted(
        posts,
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

    with FILE_LOCK:
        posts = load_posts()

    results = [
        post for post in posts
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

    with FILE_LOCK:
        posts = load_posts()
        new_post = {
            "id": generate_new_id(posts),
            "title": data["title"],
            "content": data["content"],
            "author": data.get("author", DEFAULT_AUTHOR),
            "date": data.get("date", date.today().isoformat()),
        }
        posts.append(new_post)
        save_posts(posts)
    return jsonify(new_post), 201


@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """Loescht einen Beitrag (200) oder meldet, dass er fehlt (404)."""
    with FILE_LOCK:
        posts = load_posts()
        post = find_post_by_id(posts, post_id)
        if post is None:
            return jsonify({
                "error": f"Post with id {post_id} was not found."
            }), 404

        posts.remove(post)
        save_posts(posts)
    return jsonify({
        "message": f"Post with id {post_id} has been deleted successfully."
    }), 200


@app.route('/api/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    """Aktualisiert einen Beitrag (200), meldet 404 oder 400 bei Fehlern."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    with FILE_LOCK:
        posts = load_posts()
        post = find_post_by_id(posts, post_id)
        if post is None:
            return jsonify({
                "error": f"Post with id {post_id} was not found."
            }), 404

        invalid = find_invalid_fields(data)
        if invalid:
            return jsonify({
                "error": "Invalid value for field(s)",
                "invalid_fields": invalid,
            }), 400

        for field in POST_FIELDS:
            if field in data:
                post[field] = data[field]
        save_posts(posts)
    return jsonify(post), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002, debug=True)
