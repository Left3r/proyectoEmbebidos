from flask import Flask, request, jsonify, render_template, redirect, url_for
from collections import deque

app = Flask(__name__)

# =========================================================
# QUEUES
# =========================================================

pending_commands = deque()

in_progress_commands = {}

completed_commands = {}

next_id = 0

# =========================================================
# MAIN PAGE
# =========================================================

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():

    return render_template(
        'index.html',
        title='Dashboard'
    )

# =========================================================
# ADD COMMAND
# =========================================================

@app.route('/api/queue/add', methods=['POST'])
def add_command():

    global next_id

    data = request.json

    command = {
        "id": next_id,
        "pin": data.get("pin"),
        "cmd": data.get("cmd"),
        "value": data.get("value")
    }

    next_id += 1

    pending_commands.append(command)

    return jsonify({
        "status": "queued",
        "command": command
    })

# =========================================================
# NEXT COMMAND
# =========================================================

@app.route('/api/queue/next', methods=['GET'])
def next_command():

    if not pending_commands:
        return '', 204

    command = pending_commands.popleft()

    in_progress_commands[command["id"]] = command

    return jsonify(command)

# =========================================================
# ACK
# =========================================================

@app.route('/api/queue/ack', methods=['POST'])
def ack():

    data = request.json

    if not data:
        return jsonify({
            "status": "error",
            "message": "missing json"
        }), 400

    cmd_id = data.get("id")

    if cmd_id is None:
        return jsonify({
            "status": "error",
            "message": "missing id"
        }), 400

    if cmd_id not in in_progress_commands:

        return jsonify({
            "status": "error",
            "message": "command not found"
        }), 404

    command = in_progress_commands.pop(cmd_id)

    completed_commands[cmd_id] = command

    return jsonify({
        "status": "acknowledged",
        "id": cmd_id
    })

# =========================================================
# BUTTON EVENTS
# =========================================================

btn_event = "released"

@app.route('/api/btn/get', methods=['GET'])
def get_btn_state():

    return jsonify({
        "status": "success",
        "btn_state": btn_event,
        "btn_bool": btn_event == "pressed"
    })

@app.route('/api/btn/<event>', methods=['POST'])
def btn_handler(event):

    global btn_event

    btn_event = event

    print("[BTN]", btn_event)

    return jsonify({
        "status": "success",
        "event": btn_event
    })

# =========================================================
# ADC GRAPH
# =========================================================

graph_data = []

@app.route('/api/adc/get', methods=['GET'])
def get_adc_data():

    global graph_data

    if len(graph_data) == 0:

        return jsonify({
            "status": "empty"
        }), 204

    value = graph_data.pop(0)

    return jsonify({
        "status": "success",
        "voltage": value
    })

@app.route('/api/adc/<value>', methods=['POST'])
def adc_handler(value):

    global graph_data

    if len(graph_data) > 40:
        graph_data.pop(0)

    graph_data.append(value)

    return jsonify({
        "status": "saved"
    })

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)