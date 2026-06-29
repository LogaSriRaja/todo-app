from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import requests
import os

app = Flask(__name__, static_folder="static")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

DB_CONFIG = {
    "host": "localhost",
    "database": "tododb",
    "user": "todouser",
    "password": "todo123"
}

def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/tasks", methods=["GET"])
def get_tasks():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    tasks = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([dict(t) for t in tasks])

@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json()
    title = data.get("title", "")
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING *",
        (title, False)
    )
    task = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(dict(task)), 201

@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "UPDATE tasks SET done = NOT done WHERE id = %s RETURNING *",
        (task_id,)
    )
    task = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if task:
        return jsonify(dict(task))
    return jsonify({"error": "Task not found"}), 404

@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Deleted"})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT title FROM tasks WHERE done = FALSE")
    tasks = cur.fetchall()
    task_list = ", ".join([t["title"] for t in tasks]) if tasks else "No pending tasks"

    system_prompt = f"""You are a helpful productivity assistant for a Todo app.
    The user currently has these pending tasks: {task_list}.
    Help them manage their tasks, suggest priorities, and answer questions.
    Keep responses short and friendly."""

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "max_tokens": 200
            },
            timeout=30
        )
        result = response.json()
        reply = result["choices"][0]["message"]["content"]

        cur.execute(
            "INSERT INTO chats (user_message, ai_reply) VALUES (%s, %s)",
            (message, reply)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"reply": reply})
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/chats", methods=["GET"])
def get_chats():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM chats ORDER BY created_at DESC LIMIT 50")
    chats = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([dict(c) for c in chats])

if __name__ == "__main__":
    app.run(debug=True, port=5000)
