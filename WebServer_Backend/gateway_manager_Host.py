#backend para servidor

import time

from flask import Flask,\
    request, render_template,\
    redirect, url_for, jsonify 


pending_commands = {}
in_progress_commands = {}
completed_commands = {}

next_id = 0

app = Flask(__name__)

# ----- main page
@app.route('/')
def index():
    return redirect(url_for('dashboard'))
@app.route('/dashboard')
def dashboard():
    return render_template(
        'index.html',
        title='Dashboard'
    )


# ================== API ==================

# curl -X POST http://127.0.0.1:5000/api/queue/add -H "Content-Type: application/json" -d "{\"pin\":46, \"cmd\":\"toggle_led\"}"
# ==== acciones que salen al ESP32 ====
# -- add to pending commands: recibe desde JS
@app.route('/api/queue/add', methods=['POST'])
def add_command():
    global next_id

    data = request.json
    cmd_id = next_id
    next_id += 1

    command = {
        "id": cmd_id,
        "pin": data["pin"],
        "cmd": data["cmd"],
        "value": data["value"]
    }

    pending_commands[cmd_id] = command

    return jsonify({
        "status": "queued",
        "command": command
    })

# -- (DISPATCHER) itera entre los comandos para enviarlos: recibe desde ESP32
@app.route('/api/queue/next')
def next_command():
    timeout = 30
    start = time.time()

    while time.time() - start < timeout:
        if pending_commands:
            cmd_id = next(iter(pending_commands))
            command = pending_commands.pop(cmd_id)
            in_progress_commands[cmd_id] = command
            return jsonify(command)

        time.sleep(0.1)

    return jsonify({"status":"empty"})


# curl -X POST http://127.0.0.1:5000/api/queue/ack -H "Content-Type: application/json" -d "{\"id\":0}" 
# --- acknowledgement: termina de ejecutar comando: recibe desde ESP32
@app.route('/api/queue/ack', methods=['POST'])
def ack():

    data = request.json
    cmd_id = data["id"]

    if cmd_id not in in_progress_commands:
        return jsonify({
            "status": "error",
            "message": "command not found"
        }), 400
    
    command = in_progress_commands.pop(cmd_id)

    completed_commands[cmd_id] = command

    return jsonify({"status":"acknowledged"})

# ==== acciones que recibe el servidor ====
btn_event = "released"
graph_data = []

''' boton '''
# -- GET: llamada desde el JS para el estado del boton
@app.route('/api/btn/get', methods=['GET'])
def get_btn_state():
    global btn_event
    if request.method == 'GET':
        return jsonify({
            "status": "success",
            "btn_state": btn_event,
            "btn_bool": True if btn_event == "pressed" else False
        })
#curl -X POST http://127.0.0.1:5000/api/btn/pressed -H "Content-Type: application/json"
# -- activada desde ESP32
@app.route('/api/btn/<event>', methods=['POST'])
def btn_handler(event):
    global btn_event
    if request.method == 'POST':
        btn_event = event
        return jsonify({"message": f"GPIO BTN is set {btn_event}"})

''' grafica'''
# -- GET: llamada desde el JS para recibir datos para la grafica
@app.route('/api/adc/get', methods=['GET'])
def get_adc_data():
    if request.method == 'GET':
        global graph_data
        if len(graph_data) < 1:
            return jsonify({
                "status": "error",
                "message": "no data in dict",
                "voltage": None
            })
        
        return jsonify({
            "status": "success",
            "message": 'data received',
            "voltage": graph_data.pop(0)
        })

# curl -X POST http://127.0.0.1:5000/api/adc/4 -H "Content-Type: application/json" 
# -- activada desde ESP32: agrega a graph data
@app.route('/api/adc/<value>', methods=['POST'])
def adc_handler(value):
    global graph_data
    if len(graph_data) > 40:
        graph_data.pop(0)
    
    graph_data.append(value)

    return jsonify({
        "status": "success",
        "message": "value saved"
    })


if __name__ == "__main__":
    app.run()


