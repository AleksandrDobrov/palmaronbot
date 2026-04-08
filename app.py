from flask import Flask, jsonify
import threading
import time

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "bot": "palamron-bot"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

def run_web_server():
    app.run(host='0.0.0.0', port=10000, threaded=True)

if __name__ == '__main__':
    run_web_server()
