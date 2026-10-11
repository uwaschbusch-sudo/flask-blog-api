from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Aktiviert CORS fuer alle Routen

POSTS = [
    {"id": 1, "title": "First post", "content": "This is the first post."},
    {"id": 2, "title": "Second post", "content": "This is the second post."},
]

REQUIRED_FIELDS = ("title", "content")


def generate_new_id():
    """Erzeugt eine neue, eindeutige Integer-ID (hoechste vorhandene ID + 1)."""
    if not POSTS:
        return 1
    return max(post["id"] for post in POSTS) + 1


def find_post_by_id(post_id):
    """Sucht einen Beitrag anhand seiner ID.

    Args:
        post_id: Die ID des gesuchten Beitrags (int).

    Returns:
        Das Beitrags-Dict oder None, wenn keine ID passt.
    """
    for post in POSTS:
        if post["id"] == post_id:
            return post
    return None


def find_missing_fields(data):
    """Gibt die Namen der Pflichtfelder zurueck, die fehlen oder leer sind.

    Args:
        data: Der geparste JSON-Body (dict) oder None.

    Returns:
        Liste der fehlenden Feldnamen (leer, wenn alles vorhanden ist).
    """
    if not isinstance(data, dict):
        return list(REQUIRED_FIELDS)

    missing = []
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    return missing


def find_invalid_fields(data):
    """Gibt die Namen der mitgesendeten Felder zurueck, deren Wert ungueltig ist.

    Fehlende Felder sind erlaubt (optional). Ein mitgesendetes Feld muss
    aber ein nicht leerer String sein.

    Args:
        data: Der geparste JSON-Body (dict).

    Returns:
        Liste der ungueltigen Feldnamen (leer, wenn alles gueltig ist).
    """
    invalid = []
    for field in REQUIRED_FIELDS:
        if field in data:
            value = data[field]
            if not isinstance(value, str) or not value.strip():
                invalid.append(field)
    return invalid


@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Gibt alle Blogbeitraege als JSON zurueck."""
    return jsonify(POSTS)


@app.route('/api/posts', methods=['POST'])
def add_post():
    """Legt einen neuen Blogbeitrag an.

    Erwartet einen JSON-Body mit "title" und "content". Die ID wird
    automatisch erzeugt. Bei fehlenden Feldern wird 400 zurueckgegeben,
    bei Erfolg 201 mit dem neuen Beitrag.
    """
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
    """Loescht den Beitrag mit der angegebenen ID.

    Gibt bei Erfolg 200 mit einer Meldung zurueck, wenn die ID nicht
    existiert 404 mit einer Fehlermeldung.
    """
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
    """Aktualisiert den Beitrag mit der angegebenen ID.

    "title" und "content" sind optional. Fehlende Felder behalten ihren
    bisherigen Wert. Gibt bei Erfolg 200 mit dem aktualisierten Beitrag
    zurueck, 404 wenn die ID nicht existiert und 400, wenn ein
    mitgesendetes Feld kein nicht leerer String ist.
    """
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
