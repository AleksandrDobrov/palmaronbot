import threading
import time
import os
from flask import Flask, jsonify
import telebot
from telebot import types

# Flask app для health check
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "bot": "palamron-bot"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

def run_web_server():
    app.run(host='0.0.0.0', port=10000, threaded=True)

# Импортируем и запускаем бота
def run_bot():
    # Здесь будет импорт вашего бота
    exec(open('bot.py').read())

if __name__ == '__main__':
    # Запускаем веб-сервер в фоне
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Запускаем бота
    run_bot()
