from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import requests

app = Flask(__name__, static_folder="static")
CORS(app)

TASKS_FILE = "tasks.json"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify(load_tasks())

@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json()
    tasks = load_tasks()
    task = {
        "id": len(tasks) + 1,
        "title": data.get("title", ""),
        "done": False
    }
    tasks.append(task)
    save_tasks(tasks)
    return jsonify(task), 201

@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = not task["done"]
            save_tasks(tasks)
            return jsonify(task)
    return jsonify({"error": "Task not found"}), 404

@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    tasks = load_tasks()
    tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(tasks)
    return jsonify({"message": "Deleted"})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "")
    tasks = load_tasks()
    task_list = ", ".join([t["title"] for t in tasks]) if tasks else "No tasks yet"

    system_prompt = f"""You are a helpful productivity assistant for a Todo app. 
    The user currently has these tasks: {task_list}.
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
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
