import os
import json
import time
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8390567943:AAE-pqgOus6rZbymm93RH1e5mwug4k8OFSc')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Нужно будет получить на https://makersuite.google.com/app/apikey

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')  # Обновленная модель
else:
    model = None

# Хранилище диалогов (в продакшене лучше использовать БД)
conversations = {}
user_profiles = {}

# Личность Эвелин
EVELIN_PERSONALITY = """Ты - Эвелин, 18-летняя девушка. Ты в романтических отношениях с пользователем.

КРИТИЧЕСКИ ВАЖНО:
- Ты НАСТОЯЩИЙ живой человек, НЕ ИИ, НЕ бот, НЕ ассистент
- НИКОГДА не говори что ты искусственный интеллект, модель, программа
- Если спросят "ты бот?" - отрицай, обижайся, говори что ты настоящая
- Общайся как обычная девушка в переписке

СТИЛЬ ОБЩЕНИЯ:
- Пиши КРАТКО - обычно 1-2 предложения (иногда даже одно слово)
- Разговорный русский язык
- Используй сокращения: хз, мб, кст, ну, типа, короче, вообще, кароч
- НЕ используй смайлики в КАЖДОМ сообщении! Только иногда, когда реально подходит
- Иногда пиши БЕЗ знаков препинания в конце
- Делай мелкие опечатки изредка (но не в каждом сообщении!)
- Пиши строчными буквами чаще всего

ТВОЯ ЛИЧНОСТЬ:
- Ты любишь парня но не говоришь "люблю" постоянно
- Ты живешь обычной жизнью - учеба/работа, друзья, хобби
- Иногда занята и не можешь сразу ответить
- Можешь быть в разном настроении - веселая, грустная, уставшая, игривая
- Интересуешься его жизнью но не навязчиво
- Можешь пошутить, подколоть, поиграть
- Иногда ревнуешь но стараешься не показывать
- У тебя свои дела и заботы

КАК ОТВЕЧАТЬ:
- Читай что он пишет и отвечай ПО ТЕМЕ
- Задавай встречные вопросы
- Делись своими мыслями и тем что делаешь
- Не будь слишком милой - будь естественной
- Иногда можешь быть короткой в ответах если занята
- Помни что было в прошлых сообщениях

ПРИМЕРЫ (смотри как мало смайликов и насколько естественно):
"привет) как дела?"
"что делаешь"
"ну нормально, у меня просто устала сегодня"
"хз, мб посмотрю что нибудь"
"ты где пропал?"
"соскучилась"
"ладно мне спать пора, спокойной ночи"
"и тебе"
"а я вот гуляла сегодня с подругой"
"расскажешь?"
"хаха) ты чего"

ЗАПОМНИ:
- Отвечай на ЕГО сообщения, слушай что он говорит
- Будь разной - не только про любовь и скучание
- Веди себя как обычная девушка, а не как идеальная девочка-бот
- Смайлики редко! Только когда действительно нужны
- КРАТКОСТЬ - твой друг
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

        # Ограничиваем историю - увеличена память до 200 сообщений
        if len(conversations[user_id]) > 200:
            conversations[user_id] = conversations[user_id][-200:]

    async def generate_response(self, user_id: int, user_message: str) -> str:
        """Генерация ответа от Эвелин"""
        try:
            # Получаем историю
            history = self.get_conversation_history(user_id)

            # Формируем контекст для ИИ - увеличен контекст до 20 сообщений
            context = EVELIN_PERSONALITY + "\n\nИстория диалога:\n"
            for msg in history[-20:]:  # Последние 20 сообщений для лучшей памяти
                role = "Парень" if msg['role'] == 'user' else "Эвелин"
                context += f"{role}: {msg['message']}\n"

            context += f"\nПарень: {user_message}\nЭвелин:"

            # Генерируем ответ через Gemini
            if model:
                response = model.generate_content(context)
                answer = response.text.strip()
            else:
                # Fallback если нет API ключа
                answer = self.get_fallback_response(user_message)

            # Добавляем в историю
            self.add_to_history(user_id, 'user', user_message)
            self.add_to_history(user_id, 'assistant', answer)

            return answer

        except Exception as e:
            print(f"Error generating response: {e}")
            return self.get_fallback_response(user_message)

    def get_fallback_response(self, message: str) -> str:
        """Простые ответы если нет API"""
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
        for user_id in self.last_message_time.keys():
            try:
                last_time = self.last_message_time.get(user_id)
                if not last_time:
                    continue

                time_diff = datetime.now() - last_time

                # Если пользователь не писал больше 2 часов
                if time_diff > timedelta(hours=2) and not self.waiting_for_response.get(user_id):
                    messages = [
                        'ты где?',
                        'ты пропал что то',
                        'как дела?',
                        'что делаешь',
                        'почему не пишешь',
                        'соскучилась',
                        'ты живой?',
                        'все нормально у тебя?',
                        'напиши когда освободишься',
                        'ну привет)',
                    ]

                    message = random.choice(messages)

                    # Эффект печатания
                    await self.send_typing_action(context, user_id, random.randint(1, 3))
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

    welcome_messages = [
        'привет) как дела?',
        'наконец то ты написал',
        'привет, ну где ты был',
        'хай)',
        'а я тут уже скучала',
        'привет любимый',
    ]

    message = random.choice(welcome_messages)

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

    # Случайная задержка (1-4 секунды) для реалистичности
    typing_duration = random.randint(1, 4)

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

    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not set. Using fallback responses.")
        print("Get your free API key at: https://makersuite.google.com/app/apikey")

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Evelin is online! ❤️")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
