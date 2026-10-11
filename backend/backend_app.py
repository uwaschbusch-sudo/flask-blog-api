from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)
CORS(app)  # Aktiviert CORS fuer alle Routen

POSTS = [
    {"id": 1, "title": "First post", "content": "This is the first post."},
    {"id": 2, "title": "Second post", "content": "This is the second post."},
]

REQUIRED_FIELDS = ("title", "content")
SORT_FIELDS = ("title", "content")
SORT_DIRECTIONS = ("asc", "desc")

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
    """Gibt mitgesendete Felder zurueck, die kein nicht leerer String sind."""
    invalid = []
    for field in REQUIRED_FIELDS:
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not value.strip():
                invalid.append(field)
    return invalid


def matches_search(post, title_query, content_query):
    """Prueft, ob der Beitrag zu einem der Suchbegriffe passt."""
    if title_query and title_query in post["title"].lower():
        return True
    if content_query and content_query in post["content"].lower():
        return True
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
        key=lambda post: post[sort_field].lower(),
        reverse=(direction == "desc"),
    )
    return jsonify(sorted_posts)


@app.route('/api/posts/search', methods=['GET'])
def search_posts():
    """Sucht Beitraege per Query-Parameter title und content."""
    title_query = request.args.get("title", "").strip().lower()
    content_query = request.args.get("content", "").strip().lower()

    results = [
        post for post in POSTS
        if matches_search(post, title_query, content_query)
    ]
    return jsonify(results), 200


@app.route('/api/posts', methods=['POST'])
def add_post():
    """Legt einen neuen Beitrag an (201) oder meldet fehlende Felder (400)."""
    data = request.get_json(silent=True)

    missing = find_missing_fields(data)
    if missing:
        return jsonify({
            "error": "Missing required field(s)",
            "missing_fields": missing,
        }), 400

    new_post = {
        "id": generate_new_id(),
        "title": data["title"],
        "content": data["content"],
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

    post["title"] = data.get("title", post["title"])
    post["content"] = data.get("content", post["content"])
    return jsonify(post), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002, debug=True)
