from flask import Flask, jsonify
from system_info import get_system_info, get_top_processes

app = Flask(__name__)

@app.route('/')
def home():
    return "System Monitoring API is running. Endpoints: /api/system , /api/processes"

@app.route('/api/system')
def system_api():
    return jsonify(get_system_info())

@app.route('/api/processes')
def processes_api():
    return jsonify(get_top_processes())

if __name__ == '__main__':
    app.run(debug=True)
