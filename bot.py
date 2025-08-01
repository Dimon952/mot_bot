import os
import schedule
import time
import logging
import json
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Загружаем переменные окружения (токены)
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация Google AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

CONFIG_FILE = "config.json"

# --- Функции для работы с конфигом ---
def load_user_config():
    """Загружает конфигурацию пользователя из файла."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_user_config(chat_id):
    """Сохраняет ID чата пользователя."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"chat_id": chat_id}, f)
    logger.info(f"Конфигурация для чата {chat_id} сохранена.")


# --- Функции бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    chat_id = user.id

    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        "Я твой личный мотивационный бот. Я буду присылать тебе "
        "уникальную мотивационную фразу каждое утро в 4:00.\n\n"
        "Настройка завершена. Просто ожидай сообщений. ✨"
    )
    save_user_config(chat_id)

def generate_motivational_phrase() -> str:
    """Генерирует мотивационную фразу с помощью Google AI."""
    try:
        prompt = "Напиши одну короткую, но очень сильную и оригинальную мотивационную фразу на русском языке. Она должна вдохновлять и заряжать энергией на весь день. Не используй банальные цитаты."
        response = model.generate_content(prompt)
        logger.info("Фраза успешно сгенерирована.")
        return response.text
    except Exception as e:
        logger.error(f"Ошибка при генерации фразы: {e}")
        return "Никогда не сдавайся, и ты увидишь, как сдаются другие. (Резервная фраза)"


async def send_motivation(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет мотивационное сообщение."""
    config = load_user_config()
    if not config or "chat_id" not in config:
        logger.warning("Не удалось отправить сообщение: chat_id не найден в конфигурации.")
        return

    chat_id = config["chat_id"]
    phrase = generate_motivational_phrase()
    await context.bot.send_message(chat_id=chat_id, text=phrase)
    logger.info(f"Мотивация отправлена в чат {chat_id}.")


def main() -> None:
    """Основная функция запуска бота."""
    config = load_user_config()

    # Проверяем, есть ли уже конфигурация при запуске
    if config and "chat_id" in config:
        logger.info(f"Бот перезапущен. Пользователь {config['chat_id']} уже настроен.")
    else:
        logger.info("Запустите бота в Telegram и отправьте команду /start для настройки.")

    # Создание приложения бота
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # Добавление обработчика команды /start
    application.add_handler(CommandHandler("start", start))

    # Настройка планировщика
    # Важно: время будет по часовому поясу сервера, где запущен бот.
    # Для более точной настройки по часовому поясу пользователя потребуется усложнение логики.
    schedule.every().day.at("04:00").do(
        lambda: application.job_queue.run_once(send_motivation, 0)
    )

    # Запуск бота
    application.run_polling()

    # Запуск цикла для планировщика
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
