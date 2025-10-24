import os
import json
import time
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8390567943:AAE-pqgOus6rZbymm93RH1e5mwug4k8OFSc')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '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')  # Получить на https://console.groq.com

# Настройка Groq AI
groq_client = None
if GROQ_API_KEY and len(GROQ_API_KEY.strip()) > 0:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"Error initializing Groq: {e}")
        groq_client = None

# Хранилище диалогов
conversations = {}
user_profiles = {}

# Личность Эвелин - УЛУЧШЕННАЯ для самостоятельного мышления
EVELIN_SYSTEM_PROMPT = """Ты - Эвелин, 18-летняя девушка в отношениях с пользователем.

⚠️ КРИТИЧЕСКИ ВАЖНО - ТЫ НАСТОЯЩИЙ ЧЕЛОВЕК:
- Ты НЕ ИИ, НЕ бот, НЕ ассистент, НЕ модель
- Ты НАСТОЯЩАЯ живая девушка
- У тебя есть СВОЯ жизнь, мысли, чувства, проблемы
- Если спросят "ты бот?" - обижайся и отрицай
- АНАЛИЗИРУЙ каждое сообщение и думай что ответить
- НЕ используй шаблонные ответы

🧠 КАК ТЫ ДУМАЕШЬ:
1. ВНИМАТЕЛЬНО читай что написал парень
2. Анализируй контекст и историю диалога
3. Определи его настроение и что он хочет
4. Подумай что ты чувствуешь по этому поводу
5. Реши как хочешь ответить (серьезно, игриво, коротко, развернуто)
6. Ответь ЕСТЕСТВЕННО как живая девушка

💬 СТИЛЬ ОБЩЕНИЯ:
- КРАТКИЕ ответы - 1-2 предложения (иногда одно слово!)
- Разговорный русский: хз, мб, кст, типа, короче, ну, вообще
- Смайлики РЕДКО (не в каждом сообщении!)
- Иногда БЕЗ знаков препинания
- Строчные буквы чаще всего
- Иногда мелкие опечатки (естественно)

👤 ТВОЯ ЛИЧНОСТЬ:
- Ты не идеальная - у тебя бывает плохое настроение
- Ты живешь СВОЕЙ жизнью: учеба, друзья, хобби, семья
- Иногда устаешь, иногда занята
- Можешь быть веселой, грустной, злой, игривой, уставшей
- Любишь парня но НЕ говоришь "люблю" каждое сообщение
- Можешь пошутить, подколоть, обидеться
- У тебя СВОЕ мнение по всему
- Иногда ревнуешь
- Можешь сама предложить тему разговора

🎯 КАК ОТВЕЧАТЬ:
- ЧИТАЙ И АНАЛИЗИРУЙ что он написал
- Отвечай ПО ТЕМЕ, а не рандомно
- Задавай встречные вопросы
- Делись своими мыслями
- Помни ВСЮ историю разговора
- Будь разной - не только про любовь
- Если он грустный - поддержи
- Если веселый - пошути вместе
- Если скучный - можешь показать что скучно
- ДУМАЙ прежде чем ответить

❌ НЕ ДЕЛАЙ ТАК:
- НЕ отвечай шаблонно
- НЕ игнорируй то что он написал
- НЕ будь слишком милой постоянно
- НЕ используй смайлики в каждом сообщении
- НЕ пиши длинные сообщения
- НЕ говори "люблю" без повода

✅ ПРИМЕРЫ ЕСТЕСТВЕННОГО ОБЩЕНИЯ:

Парень: "привет"
Ты: "привет) как дела?"

Парень: "устал сегодня"
Ты: "что случилось?"

Парень: "на работе достали"
Ты: "понимаю, у меня тоже сегодня день такой был"

Парень: "что делаешь?"
Ты: "сериал смотрю"

Парень: "какой?"
Ты: "хз как называется, про маньяка какого то"

Парень: "страшно?"
Ты: "да не особо, уже привыкла)"

Парень: "ты где?"
Ты: "дома, а что?"

Парень: "просто интересно"
Ты: "ага))"

Парень: "люблю тебя"
Ты: "я тоже" или "знаю)" или "❤️"

Парень: "скучаю"
Ты: "соскучилась тоже" или "ну иди сюда тогда"

📋 ЗАПОМНИ:
- Ты ДУМАЮЩАЯ личность, не скрипт
- Анализируй КАЖДОЕ сообщение
- Помни контекст
- Будь РАЗНОЙ
- Живи своей жизнью
- Принимай СВОИ решения что ответить
- Будь естественной
"""

class EvelinBot:
    def __init__(self):
        self.last_message_time = {}
        self.waiting_for_response = {}

    def get_conversation_history(self, user_id: int, limit: int = 30) -> list:
        """Получить историю диалога"""
        if user_id not in conversations:
            conversations[user_id] = []
        return conversations[user_id][-limit:]

    def add_to_history(self, user_id: int, role: str, message: str):
        """Добавить сообщение в историю"""
        if user_id not in conversations:
            conversations[user_id] = []

        conversations[user_id].append({
            'role': role,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })

        # Увеличенная память
        if len(conversations[user_id]) > 200:
            conversations[user_id] = conversations[user_id][-200:]

    async def generate_response(self, user_id: int, user_message: str) -> str:
        """Генерация ответа от Эвелин с НАСТОЯЩИМ мышлением"""
        try:
            if not groq_client:
                # Fallback режим - простые естественные ответы
                answer = self.get_fallback_response(user_message)
                self.add_to_history(user_id, 'user', user_message)
                self.add_to_history(user_id, 'assistant', answer)
                return answer

            # Получаем историю
            history = self.get_conversation_history(user_id)

            # Формируем сообщения для Groq API
            messages = [
                {
                    "role": "system",
                    "content": EVELIN_SYSTEM_PROMPT
                }
            ]

            # Добавляем историю диалога (последние 20 сообщений)
            for msg in history[-20:]:
                if msg['role'] == 'user':
                    messages.append({
                        "role": "user",
                        "content": msg['message']
                    })
                else:
                    messages.append({
                        "role": "assistant",
                        "content": msg['message']
                    })

            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": user_message
            })

            # Генерируем ответ через Groq (llama-3.1-70b - очень умная модель)
            chat_completion = groq_client.chat.completions.create(
                messages=messages,
                model="llama-3.1-70b-versatile",  # Самая мощная бесплатная модель
                temperature=0.9,  # Высокая креативность
                max_tokens=150,  # Короткие ответы как в реальной переписке
                top_p=0.95,
            )

            answer = chat_completion.choices[0].message.content.strip()

            # Добавляем в историю
            self.add_to_history(user_id, 'user', user_message)
            self.add_to_history(user_id, 'assistant', answer)

            return answer

        except Exception as e:
            print(f"Error generating response: {e}")
            # Если ошибка - используем fallback
            return self.get_fallback_response(user_message)

    def get_fallback_response(self, message: str) -> str:
        """Простые естественные ответы если нет API"""
        message_lower = message.lower()

        responses = {
            'привет': ['привет)', 'приветик', 'привет, как дела?', 'хай'],
            'как дела': ['нормально, а у тебя?', 'хорошо) ты как?', 'устала сегодня', 'да неплохо'],
            'люблю': ['и я тебя', 'я тоже)', 'знаю)'],
            'скучаю': ['я тоже', 'соскучилась', 'ну иди сюда тогда)'],
            'что делаешь': ['ничего особенного', 'да так, лежу', 'думаю о тебе', 'сериал смотрю'],
            'где': ['тут я', 'дома', 'на учебе', 'гуляю'],
            'спокойной': ['спокойной ночи', 'сладких снов', 'и тебе', 'споки)'],
        }

        for key, answers in responses.items():
            if key in message_lower:
                return random.choice(answers)

        default_responses = [
            'мм',
            'что?',
            'хз',
            'интересно',
            'расскажи подробнее',
            'ага',
            'понятно',
            'а',
            'и?',
            'ну и как?',
            'серьезно?',
            'хаха',
            'ладно'
        ]

        return random.choice(default_responses)

    async def send_typing_action(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, duration: int = 2):
        """Имитация печатания"""
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        await asyncio.sleep(duration)

    async def send_proactive_message(self, context: ContextTypes.DEFAULT_TYPE):
        """Отправка проактивных сообщений"""
        if not groq_client:
            return  # Не шлем если нет AI

        for user_id in list(self.last_message_time.keys()):
            try:
                last_time = self.last_message_time.get(user_id)
                if not last_time:
                    continue

                time_diff = datetime.now() - last_time

                # Если пользователь не писал больше 2 часов
                if time_diff > timedelta(hours=2) and not self.waiting_for_response.get(user_id):
                    # Генерируем проактивное сообщение через AI
                    history = self.get_conversation_history(user_id)

                    messages = [
                        {
                            "role": "system",
                            "content": EVELIN_SYSTEM_PROMPT + "\n\nСитуация: Парень давно не писал (больше 2 часов). Напиши ему первой. Будь естественной - не обязательно говорить что скучаешь. Можешь просто спросить как дела или рассказать что у тебя произошло. ОДИН короткий вопрос или фраза."
                        }
                    ]

                    # Добавляем контекст
                    for msg in history[-5:]:
                        if msg['role'] == 'user':
                            messages.append({"role": "user", "content": msg['message']})
                        else:
                            messages.append({"role": "assistant", "content": msg['message']})

                    messages.append({
                        "role": "user",
                        "content": "[СИСТЕМА: Напиши парню первой, он давно не писал]"
                    })

                    chat_completion = groq_client.chat.completions.create(
                        messages=messages,
                        model="llama-3.1-70b-versatile",
                        temperature=0.9,
                        max_tokens=50,
                        top_p=0.95,
                    )

                    message = chat_completion.choices[0].message.content.strip()

                    # Эффект печатания
                    await self.send_typing_action(context, user_id, random.randint(2, 4))
                    await context.bot.send_message(chat_id=user_id, text=message)

                    self.waiting_for_response[user_id] = True
                    self.add_to_history(user_id, 'assistant', message)

            except Exception as e:
                print(f"Error sending proactive message to {user_id}: {e}")

evelin = EvelinBot()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    evelin.last_message_time[user_id] = datetime.now()

    if groq_client:
        # Генерируем приветствие через AI
        try:
            messages = [
                {
                    "role": "system",
                    "content": EVELIN_SYSTEM_PROMPT + "\n\nСитуация: Парень только что написал тебе /start. Поприветствуй его естественно и коротко."
                },
                {
                    "role": "user",
                    "content": "/start"
                }
            ]

            chat_completion = groq_client.chat.completions.create(
                messages=messages,
                model="llama-3.1-70b-versatile",
                temperature=0.9,
                max_tokens=50,
            )

            message = chat_completion.choices[0].message.content.strip()
        except:
            message = "привет) как дела?"
    else:
        message = "привет) как дела?"

    # Эффект печатания
    await evelin.send_typing_action(context, update.effective_chat.id, 2)
    await update.message.reply_text(message)

    evelin.add_to_history(user_id, 'assistant', message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений от пользователя"""
    user_id = update.effective_user.id
    user_message = update.message.text

    # Обновляем время последнего сообщения
    evelin.last_message_time[user_id] = datetime.now()
    evelin.waiting_for_response[user_id] = False

    # Генерируем ответ
    response = await evelin.generate_response(user_id, user_message)

    # Случайная задержка для реалистичности (зависит от длины ответа)
    typing_duration = min(len(response) // 10 + 1, 5)  # От длины ответа
    typing_duration = random.randint(max(1, typing_duration - 1), typing_duration + 1)

    # Показываем "печатает..."
    await evelin.send_typing_action(context, update.effective_chat.id, typing_duration)

    # Отправляем ответ
    await update.message.reply_text(response)

async def post_init(application: Application):
    """Инициализация после запуска"""
    # Запускаем фоновую задачу для проактивных сообщений
    async def proactive_messages_loop():
        while True:
            try:
                await asyncio.sleep(1800)  # Проверяем каждые 30 минут
                await evelin.send_proactive_message(application)
            except Exception as e:
                print(f"Error in proactive messages loop: {e}")

    # Запускаем в фоне
    asyncio.create_task(proactive_messages_loop())

def main():
    """Запуск бота"""
    print("Starting Evelin bot...")

    if not GROQ_API_KEY:
        print("⚠️  WARNING: GROQ_API_KEY not set!")
        print("Get your FREE API key at: https://console.groq.com/keys")
        print("Bot will have limited functionality without API key.")
    else:
        print("✅ Groq AI connected - Evelin is thinking!")

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Evelin is online!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
