import os
import telebot
from groq import Groq
from flask import Flask
import threading

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TOKEN or not GROQ_API_KEY:
    print("Ошибка: не заданы TELEGRAM_TOKEN или GROQ_API_KEY")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TOKEN)

user_histories = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я умный бот на нейросети LLaMA. Задай мне любой вопрос!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    history = user_histories[user_id]
    history.append({"role": "user", "content": user_text})
    
    if len(history) > 10:
        history = history[-10:]
        user_histories[user_id] = history
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=history,
            temperature=0.7,
            max_tokens=500
        )
        
        answer = completion.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        bot.reply_to(message, answer)
        
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {str(e)}")

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    bot.polling(none_stop=True, interval=1)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
