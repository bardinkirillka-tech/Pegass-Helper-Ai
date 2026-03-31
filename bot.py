import os
import telebot
from groq import Groq
from flask import Flask
import threading
import time
import random
import re
from datetime import datetime

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TOKEN or not GROQ_API_KEY:
    print("Ошибка: не заданы TELEGRAM_TOKEN или GROQ_API_KEY")
    exit(1)

# ========== ИНИЦИАЛИЗАЦИЯ ==========
client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TOKEN)
user_histories = {}

# ========== БАЗА ЗНАНИЙ (ВСТРОЕННЫЕ ОТВЕТЫ) ==========

MEDICAL_TERMS = {
    "гомеостаз": "Поддержание постоянства внутренней среды организма.",
    "анамнез": "Совокупность сведений о развитии болезни, условиях жизни, перенесённых заболеваниях.",
    "патогенез": "Механизм развития болезни.",
    "этиология": "Причина возникновения болезни.",
    "аускультация": "Метод выслушивания звуковых явлений при работе внутренних органов.",
}

NORMAL_VALUES = {
    "глюкоза": "3.3-5.5 ммоль/л (натощак)",
    "гемоглобин": "М: 130-160 г/л, Ж: 120-140 г/л",
    "холестерин": "менее 5.2 ммоль/л",
    "лейкоциты": "4.0-9.0 × 10⁹/л",
    "эритроциты": "М: 4.0-5.0 × 10¹²/л, Ж: 3.5-4.7 × 10¹²/л",
    "тромбоциты": "180-320 × 10⁹/л",
    "СОЭ": "М: 2-10 мм/ч, Ж: 2-15 мм/ч",
    "креатинин": "М: 62-115 мкмоль/л, Ж: 53-97 мкмоль/л",
    "мочевина": "2.5-8.3 ммоль/л",
    "билирубин": "3.4-17.1 мкмоль/л",
    "АЛТ": "до 40 Ед/л",
    "АСТ": "до 40 Ед/л",
}

ANATOMY = {
    "сердце": "Четырёхкамерный мышечный орган, обеспечивающий кровообращение. Расположено в грудной клетке.",
    "легкие": "Органы дыхания, расположены в грудной полости. Состоят из долей (правое - 3, левое - 2).",
    "печень": "Самая крупная железа. Функции: детоксикация, синтез белков, желчеобразование.",
    "почки": "Парные органы мочевыделительной системы. Фильтруют кровь, образуют мочу.",
    "мозг": "Центральный орган нервной системы. Состоит из больших полушарий, мозжечка, ствола.",
}

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_ai_response(prompt, user_id):
    """Универсальная функция для запроса к ИИ"""
    try:
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

# ========== КОМАНДЫ ==========

@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = """
🏥 *Pegass Medical AI* — твой помощник в учёбе!

📚 *Доступные команды:*

🔬 *Учебные:*
/term [термин] — определение медтермина
/drug [лекарство] — информация о препарате
/disease [болезнь] — описание заболевания
/anatomy [орган] — анатомическое строение
/symptom [симптом] — возможные причины

📝 *Экзамены:*
/quiz [тема] — вопрос для самопроверки
/explain [тема] — объяснение сложной темы
/test [предмет] — тест (анатомия/фармакология)

📊 *Инструменты:*
/normal [показатель] — нормы анализов
/calculate [формула] — медицинские расчёты
/latin [слово] — перевод с латыни

🎓 *Другое:*
/mnemo [тема] — мнемонические правила
/protocol [ситуация] — алгоритм действий
/help — все команды

Просто напиши вопрос, и я отвечу!
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def send_help(message):
    text = """
🏥 *Pegass Medical AI — полная справка*

🔬 *Учебные команды:*
`/term [термин]` — определение медицинского термина
`/drug [лекарство]` — фармакология, дозировки
`/disease [болезнь]` — этиология, патогенез, лечение
`/anatomy [орган]` — строение, функции, топография
`/symptom [симптом]` — дифференциальная диагностика

📝 *Подготовка к экзаменам:*
`/quiz [тема]` — вопрос для самопроверки
`/test [предмет]` — тест (анатомия/фармакология)
`/explain [тема]` — объяснение сложной темы простыми словами

📊 *Практические инструменты:*
`/normal [показатель]` — нормы лабораторных анализов
`/calculate [параметры]` — ИМТ, клиренс креатинина
`/latin [слово]` — перевод медицинских терминов с латыни

🎓 *Для запоминания:*
`/mnemo [тема]` — мнемонические правила
`/protocol [ситуация]` — алгоритм действий при неотложных состояниях

💡 *Общение:* просто задай любой вопрос по медицине
🔄 `/clear` — очистить историю диалога
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['term'])
def medical_term(message):
    """Определение медицинского термина"""
    term = message.text.replace('/term', '').strip()
    if not term:
        bot.reply_to(message, "📝 *Пример:* `/term гомеостаз`", parse_mode='Markdown')
        return
    
    # Проверка встроенной базы
    term_lower = term.lower()
    if term_lower in MEDICAL_TERMS:
        answer = f"📖 *{term.capitalize()}* — {MEDICAL_TERMS[term_lower]}"
    else:
        prompt = f"Дай краткое определение медицинского термина '{term}'. Ответ должен быть на русском языке, чёткий и информативный."
        answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['drug'])
def drug_info(message):
    """Информация о лекарстве"""
    drug = message.text.replace('/drug', '').strip()
    if not drug:
        bot.reply_to(message, "💊 *Пример:* `/drug амоксициллин`", parse_mode='Markdown')
        return
    
    prompt = f"""Дай информацию о лекарстве '{drug}' в формате:
💊 *Название:* {drug}
📋 *Действие:* ...
💊 *Дозировка:* ...
⚠️ *Противопоказания:* ...
📌 *Особые указания:* ...

Ответ должен быть на русском языке."""
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['disease'])
def disease_info(message):
    """Описание болезни"""
    disease = message.text.replace('/disease', '').strip()
    if not disease:
        bot.reply_to(message, "🩺 *Пример:* `/disease сахарный диабет`", parse_mode='Markdown')
        return
    
    prompt = f"""Дай информацию о заболевании '{disease}' в формате:
🩺 *{disease}*
📖 *Этиология:* ...
🔄 *Патогенез:* ...
📋 *Клиническая картина:* ...
💊 *Лечение:* ...

Ответ на русском языке."""
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['anatomy'])
def anatomy_info(message):
    """Анатомическое строение"""
    organ = message.text.replace('/anatomy', '').strip()
    if not organ:
        bot.reply_to(message, "🔬 *Пример:* `/anatomy сердце`", parse_mode='Markdown')
        return
    
    organ_lower = organ.lower()
    if organ_lower in ANATOMY:
        answer = f"🔬 *{organ.capitalize()}*\n{ANATOMY[organ_lower]}"
    else:
        prompt = f"Опиши анатомическое строение и функции '{organ}'. Ответ на русском языке."
        answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['symptom'])
def symptom_info(message):
    """Симптом и дифференциальная диагностика"""
    symptom = message.text.replace('/symptom', '').strip()
    if not symptom:
        bot.reply_to(message, "🩺 *Пример:* `/symptom кашель`", parse_mode='Markdown')
        return
    
    prompt = f"""Для симптома '{symptom}' укажи:
1. Возможные причины (3-5)
2. Какие заболевания сопровождаются этим симптомом
3. Когда нужно срочно обратиться к врачу

Ответ на русском языке."""
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['quiz'])
def quiz(message):
    """Вопрос для самопроверки"""
    topic = message.text.replace('/quiz', '').strip()
    if not topic:
        topic = "общая медицина"
    
    prompt = f"""Задай один вопрос для самопроверки по теме '{topic}' для студента медицинского вуза.
После вопроса дай правильный ответ с кратким объяснением.
Формат:
❓ *Вопрос:* ...
✅ *Ответ:* ...
📖 *Объяснение:* ..."""
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['explain'])
def explain_topic(message):
    """Объяснение сложной темы"""
    topic = message.text.replace('/explain', '').strip()
    if not topic:
        bot.reply_to(message, "📚 *Пример:* `/explain цикл Кребса`", parse_mode='Markdown')
        return
    
    prompt = f"""Объясни тему '{topic}' простыми словами, как для студента-медика. 
Используй аналогии, структурируй информацию, выдели главное. 
Ответ на русском языке."""
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['normal'])
def normal_values(message):
    """Нормы анализов"""
    test = message.text.replace('/normal', '').strip()
    if not test:
        tests_list = "\n".join([f"• {k.capitalize()}" for k in NORMAL_VALUES.keys()])
        bot.reply_to(message, f"📊 *Доступные показатели:*\n{tests_list}\n\nПример: `/normal глюкоза`", parse_mode='Markdown')
        return
    
    test_lower = test.lower()
    if test_lower in NORMAL_VALUES:
        answer = f"📊 *Норма {test.capitalize()}:*\n{NORMAL_VALUES[test_lower]}"
    else:
        prompt = f"Укажи нормальные значения для лабораторного показателя '{test}' в крови. Ответ на русском языке."
        answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['calculate'])
def medical_calc(message):
    """Медицинские расчёты"""
    params = message.text.replace('/calculate', '').strip()
    if not params:
        text = """
📐 *Медицинские расчёты:*

Примеры:
`/calculate ИМТ вес=70 рост=175`
`/calculate клиренс креатинина возраст=30 вес=70 пол=м`

Доступно: ИМТ, клиренс креатинина
"""
        bot.reply_to(message, text, parse_mode='Markdown')
        return
    
    prompt = f"Выполни медицинский расчёт: {params}. Ответ на русском языке с формулой и результатом."
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['latin'])
def latin_term(message):
    """Перевод с латыни"""
    word = message.text.replace('/latin', '').strip()
    if not word:
        bot.reply_to(message, "🏛️ *Пример:* `/latin cor`\n\nПереведу медицинский термин с латыни на русский.", parse_mode='Markdown')
        return
    
    prompt = f"Переведи медицинский термин '{word}' с латыни на русский. Укажи значение и пример использования. Ответ на русском языке."
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['mnemo'])
def mnemonics(message):
    """Мнемонические правила"""
    topic = message.text.replace('/mnemo', '').strip()
    if not topic:
        topic = "черепные нервы"
    
    prompt = f"Дай мнемонические правила для запоминания по теме '{topic}' в медицине. Ответ на русском языке."
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['protocol'])
def protocol(message):
    """Алгоритм действий"""
    situation = message.text.replace('/protocol', '').strip()
    if not situation:
        bot.reply_to(message, "🚑 *Пример:* `/protocol анафилактический шок`", parse_mode='Markdown')
        return
    
    prompt = f"Опиши алгоритм действий при '{situation}' (неотложное состояние). Формат: пошагово, что делать. Ответ на русском языке."
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['test'])
def test(message):
    """Генерация теста"""
    subject = message.text.replace('/test', '').strip()
    if not subject:
        subject = "анатомия"
    
    prompt = f"""Создай тест из 3 вопросов по предмету '{subject}' для студента медицинского вуза.
Для каждого вопроса дай 4 варианта ответа и укажи правильный.
Формат:
❓ Вопрос 1: ...
A) ...
B) ...
C) ...
D) ...
✅ Правильный ответ: ...

Ответ на русском языке."""
    answer = get_ai_response(prompt, message.from_user.id)
    bot.reply_to(message, answer, parse_mode='Markdown')

@bot.message_handler(commands=['clear'])
def clear_history(message):
    """Очистка истории"""
    user_id = message.from_user.id
    if user_id in user_histories:
        user_histories[user_id] = []
        bot.reply_to(message, "✅ *История диалога очищена!*", parse_mode='Markdown')
    else:
        bot.reply_to(message, "📭 *История и так пуста.*", parse_mode='Markdown')

# ========== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ==========

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
    
    # Добавляем медицинский контекст
    prompt = f"""Ты — ассистент для студента медицинского вуза. Отвечай на вопросы по медицине: анатомия, физиология, патология, фармакология, терапия, хирургия и другие медицинские дисциплины.
Будь точным, структурированным, используй профессиональную терминологию, но объясняй понятно.
Если вопрос не по медицине — вежливо направь к медицинской тематике.

Вопрос пользователя: {user_text}

Ответ:"""
    
    try:
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        answer = completion.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        bot.reply_to(message, answer)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}\nПопробуй позже.")

# ========== НАСТРОЙКА МЕНЮ ==========

def set_bot_commands():
    commands = [
        telebot.types.BotCommand("start", "🏥 Главное меню"),
        telebot.types.BotCommand("help", "📋 Все команды"),
        telebot.types.BotCommand("term", "📖 Определение термина"),
        telebot.types.BotCommand("drug", "💊 Лекарство"),
        telebot.types.BotCommand("disease", "🩺 Болезнь"),
        telebot.types.BotCommand("anatomy", "🔬 Анатомия"),
        telebot.types.BotCommand("symptom", "🩺 Симптомы"),
        telebot.types.BotCommand("quiz", "❓ Вопрос для проверки"),
        telebot.types.BotCommand("explain", "📚 Объяснить тему"),
        telebot.types.BotCommand("normal", "📊 Нормы анализов"),
        telebot.types.BotCommand("latin", "🏛️ Латынь"),
        telebot.types.BotCommand("mnemo", "🧠 Мнемоника"),
        telebot.types.BotCommand("protocol", "🚑 Алгоритм действий"),
        telebot.types.BotCommand("test", "📝 Тест"),
        telebot.types.BotCommand("clear", "🔄 Очистить историю"),
    ]
    try:
        bot.set_my_commands(commands)
        print("✅ Меню команд установлено")
    except Exception as e:
        print(f"Ошибка при установке меню: {e}")

# ========== FLASK ДЛЯ RENDER ==========

app = Flask(__name__)

@app.route('/')
def index():
    return "Pegass Medical AI Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

# ========== ЗАПУСК ==========

def run_bot():
    time.sleep(3)
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        print(f"Ошибка в polling: {e}")

if __name__ == "__main__":
    set_bot_commands()
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
