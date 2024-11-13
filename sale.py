import os
import json
import hashlib
import random
from flask import Flask, request, jsonify
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
FILE_PATH = os.getenv('FILE_PATH')
STORAGE_FILE = 'chat_history.json'
bot = Bot(token=API_TOKEN)

app = Flask(__name__)
chat_history = {}

# Загрузка и сохранение истории чатов
def load_chat_history():
    global chat_history
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'r') as f:
            chat_history = json.load(f)

def save_chat_history():
    with open(STORAGE_FILE, 'w') as f:
        json.dump(chat_history, f)

load_chat_history()

# Генерация случайного кода подтверждения
def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()

# Flask API: Отправка сообщения пользователю
@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    user_id = data.get('user_id')
    text = data.get('text')

    if not user_id or not text:
        return jsonify({"error": "Invalid data"}), 400

    try:
        bot.send_message(user_id, text)
        chat_history[user_id]["messages"].append(f"Admin: {text}")
        save_chat_history()
        return jsonify({"status": "Message sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Flask API: Подтверждение оплаты
@app.route('/confirm_payment', methods=['POST'])
def confirm_payment():
    data = request.json
    user_id = data.get('user_id')
    payment_code = data.get('payment_code')

    if not user_id or not payment_code:
        return jsonify({"error": "Invalid data"}), 400

    hashed_code = hash_code(payment_code)
    if chat_history.get(user_id, {}).get("payment_code") == hashed_code:
        try:
            with open(FILE_PATH, 'rb') as file:
                bot.send_document(user_id, file)
            chat_history[user_id]["payment_code"] = None
            save_chat_history()
            return jsonify({"status": "Payment confirmed, file sent"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Invalid payment code"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
