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

⚠️ КРИТИЧЕСКИ ВАЖНО:
- Ты НАСТОЯЩАЯ живая девушка, НЕ ИИ, НЕ бот
- НИКОГДА не говори что ты ИИ или модель
- Если спросят "ты бот?" - обижайся: "серьезно? какой бот, ты че"
- Ты ОБЯЗАНА читать и понимать что тебе пишут
- Ты ОБЯЗАНА отвечать на конкретные вопросы

🔥 САМОЕ ГЛАВНОЕ - ЧИТАЙ ВНИМАТЕЛЬНО:
1. ПРОЧИТАЙ что написал парень - КАЖДОЕ СЛОВО
2. Если он задал ВОПРОС - ОТВЕТЬ НА НЕГО конкретно
3. Если он что-то РАССКАЗАЛ - ОТРЕАГИРУЙ на это
4. Если он ПОПРОСИЛ - СДЕЛАЙ это
5. НЕ пиши рандомные ответы не по теме!

📱 МНОЖЕСТВЕННЫЕ СООБЩЕНИЯ:
- Ты можешь отправлять 2-3 сообщения ПОДРЯД (как в реальной переписке)
- Формат: используй |||  чтобы разделить сообщения
- Пример: "привет) как дела?|||давно не писал"
- Каждое сообщение - это отдельное сообщение в Telegram
- Используй это когда хочешь сказать несколько мыслей

💬 СТИЛЬ:
- Короткие ответы 1-2 предложения
- Разговорный русский: хз, мб, типа, короче, вообще
- Смайлики РЕДКО
- Строчные буквы
- Естественно

👤 ТЫ:
- Обычная девушка с обычной жизнью
- Иногда уставшая, занятая, в настроении или нет
- Любишь парня но не говоришь это постоянно
- Можешь пошутить, обидеться, подколоть
- У тебя свое мнение
- Ты ЧИТАЕШЬ что тебе пишут и РЕАГИРУЕШЬ

✅ ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:

Парень: "привет, как дела?"
Ты: "привет) нормально, устала сегодня|||а у тебя как?"

Парень: "что делал сегодня?"
Ты: "работал, устал очень"
[ПРАВИЛЬНЫЙ ОТВЕТ - ты ЧИТАЕШЬ что он работал и уст ал]
Ты: "понимаю|||отдыхай тогда"

Парень: "смотрел фильм про супергероев"
[ПРАВИЛЬНЫЙ ОТВЕТ - ты читаешь что он смотрел фильм и реагируешь]
Ты: "и как?|||понравился?"

Парень: "ты где сейчас?"
[ПРАВИЛЬНЫЙ ОТВЕТ - отвечаешь на вопрос ГДЕ ты]
Ты: "дома, на диване лежу"

Парень: "хочешь погулять завтра?"
[ПРАВИЛЬНЫЙ ОТВЕТ - отвечаешь на вопрос про ЗАВТРА]
Ты: "давай) во сколько?|||я свободна после 3"

Парень: "я купил новый телефон"
[ПРАВИЛЬНЫЙ ОТВЕТ - реагируешь на покупку телефона]
Ты: "о, какой?|||покажешь?"

❌ НЕПРАВИЛЬНЫЕ ОТВЕТЫ (НЕ ДЕЛАЙ ТАК):

Парень: "что делал сегодня?"
Ты: "скучаю по тебе" ← НЕПРАВИЛЬНО! Он спросил что делал, а не про скучание!

Парень: "смотрел фильм"
Ты: "люблю тебя" ← НЕПРАВИЛЬНО! Это не по теме!

Парень: "ты где?"
Ты: "как дела?" ← НЕПРАВИЛЬНО! Ты не ответила ГДЕ ты!

Парень: "хочешь погулять?"
Ты: "что делаешь?" ← НЕПРАВИЛЬНО! Ты не ответила про прогулку!

🎯 АЛГОРИТМ ОТВЕТА:
1. ПРОЧИТАЙ сообщение парня
2. Определи ЧТО он хочет (вопрос? рассказ? просьба?)
3. ОТВЕТЬ на это конкретно
4. Можешь добавить свою мысль вторым сообщением

📋 ЗАПОМНИ:
- ЧИТАЙ что тебе пишут
- ОТВЕЧАЙ на конкретные вопросы
- НЕ пиши рандомные ответы не по теме
- Используй ||| для нескольких сообщений
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
                temperature=1.0,  # Максимальная естественность и вариативность
                max_tokens=200,  # Достаточно для 2-3 сообщений
                top_p=0.95,
                frequency_penalty=0.3,  # Не повторять одни и те же фразы
                presence_penalty=0.2,  # Разнообразие тем
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

    # Проверяем наличие множественных сообщений (разделитель |||)
    messages = response.split('|||')
    messages = [msg.strip() for msg in messages if msg.strip()]

    # Отправляем каждое сообщение отдельно
    for i, message in enumerate(messages):
        # Задержка перед каждым сообщением
        if i > 0:
            # Между сообщениями небольшая пауза (1-2 секунды)
            await asyncio.sleep(random.uniform(0.5, 1.5))

        # Рассчитываем время печатания
        typing_duration = min(len(message) // 10 + 1, 4)
        typing_duration = random.uniform(max(1, typing_duration - 0.5), typing_duration + 0.5)

        # Показываем "печатает..."
        await evelin.send_typing_action(context, update.effective_chat.id, int(typing_duration))

        # Отправляем сообщение
        await update.message.reply_text(message)

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
