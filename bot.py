import os
import logging
import json
import schedule
import time
from threading import Thread

import google.generativeai as genai
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Настройка логирования для отладки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Файл для хранения конфигурации
CONFIG_FILE = "config.json"

# Определяем этапы диалога для настройки
(
    GET_TOKEN,
    GET_GEMINI_KEY,
    GET_PROXY,
    GET_SCHEDULE_TIME,
    CONFIRMATION,
) = range(5)


# --- Функции для работы с конфигурацией ---
def load_config():
    """Загружает конфигурацию из файла config.json"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None


def save_config(data):
    """Сохраняет данные в файл config.json"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)
    logger.info("Конфигурация успешно сохранена.")


# --- Основные функции бота ---
def generate_motivational_phrase(api_key: str) -> str:
    """Генерирует фразу с помощью Google AI."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "Напиши одну короткую, но очень сильную и оригинальную мотивационную фразу на русском языке. Она должна вдохновлять и заряжать энергией на весь день. Не используй банальные цитаты."
        response = model.generate_content(prompt)
        logger.info("Фраза успешно сгенерирована.")
        return response.text
    except Exception as e:
        logger.error(f"Ошибка при генерации фразы: {e}")
        return "Никогда не сдавайся, и ты увидишь, как сдаются другие. (Резервная фраза)"


async def send_motivation(context: ContextTypes.DEFAULT_TYPE):
    """Задача, которая выполняется по расписанию."""
    config = load_config()
    if not config:
        logger.warning("Отправка невозможна: конфигурация отсутствует.")
        return

    chat_id = config.get("admin_chat_id")
    api_key = config.get("gemini_api_key")

    if not chat_id or not api_key:
        logger.error("Отправка невозможна: не найден chat_id или api_key в конфиге.")
        return

    phrase = generate_motivational_phrase(api_key)
    await context.bot.send_message(chat_id=chat_id, text=phrase)
    logger.info(f"Мотивация отправлена в чат {chat_id}.")


# --- Функции для диалога настройки ---
async def start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог настройки, если конфиг не найден."""
    context.user_data["config"] = {}
    await update.message.reply_text(
        "👋 Привет! Я твой будущий мотивационный бот. \n"
        "Похоже, это мой первый запуск. Давай настроим меня!\n\n"
        "Пожалуйста, отправь мне токен твоего бота, полученный от @BotFather."
    )
    return GET_TOKEN


async def get_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает и сохраняет токен."""
    token = update.message.text
    context.user_data["config"]["telegram_token"] = token
    logger.info("Токен получен.")
    await update.message.reply_text(
        "Отлично! Теперь, пожалуйста, отправь мне твой API ключ от Google AI (Gemini)."
    )
    return GET_GEMINI_KEY


async def get_gemini_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает и сохраняет ключ Gemini."""
    gemini_key = update.message.text
    context.user_data["config"]["gemini_api_key"] = gemini_key
    logger.info("Ключ Gemini получен.")
    await update.message.reply_text(
        "Ключ принят. Теперь введи URL для прокси. \n\n"
        "Формат: `socks5://user:pass@host:port` или `http://host:port`\n\n"
        "Если прокси не нужен, просто напиши 'нет' или 'пропустить'."
    )
    return GET_PROXY


async def get_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает URL прокси или пропускает шаг."""
    proxy_url = update.message.text
    if proxy_url.lower() in ["нет", "пропустить", "no", "skip"]:
        context.user_data["config"]["proxy_url"] = None
        logger.info("Настройка прокси пропущена.")
    else:
        context.user_data["config"]["proxy_url"] = proxy_url
        logger.info(f"Прокси установлен: {proxy_url}")

    await update.message.reply_text(
        "Хорошо. Теперь укажи время для ежедневной отправки сообщений.\n"
        "Введи его в формате `ЧЧ:ММ` (например, `04:00` или `07:30`)."
    )
    return GET_SCHEDULE_TIME


async def get_schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает и сохраняет время для расписания."""
    schedule_time = update.message.text
    context.user_data["config"]["schedule_time"] = schedule_time
    # Сохраняем ID пользователя, который проводит настройку
    context.user_data["config"]["admin_chat_id"] = update.effective_chat.id
    logger.info(f"Время установлено на {schedule_time}.")

    # Сохраняем все данные в файл
    save_config(context.user_data["config"])

    await update.message.reply_text(
        "🎉 **Настройка завершена!**\n\n"
        "Я сохранил все данные. Теперь я буду работать автономно и присылать тебе мотивацию каждый день.\n"
        "Чтобы изменения вступили в силу, меня нужно **перезапустить** на сервере.\n\n"
        "Спасибо!",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет процесс настройки."""
    await update.message.reply_text(
        "Настройка отменена.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# --- Основной цикл запуска ---
def run_scheduler(job_queue):
    """Функция, которая работает в отдельном потоке и проверяет расписание."""
    config = load_config()
    if not config:
        return
        
    schedule_time = config.get("schedule_time", "04:00")
    # Создаем задачу
    schedule.every().day.at(schedule_time).do(
        lambda: job_queue.run_once(send_motivation, 0)
    )
    logger.info(f"Задача запланирована на ежедневное выполнение в {schedule_time}.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)


def main() -> None:
    """Основная функция запуска бота."""
    config = load_config()

    if not config:
        # Если конфига нет, запускаем только настройку
        logger.warning("Файл конфигурации не найден. Запускаем бота в режиме настройки.")
        # Нужен временный токен, чтобы бот мог хотя бы запуститься для диалога.
        # Можно попросить пользователя ввести его в консоли или использовать заглушку.
        # Мы будем использовать заглушку, так как пользователь введет реальный токен в диалоге.
        temp_token = os.environ.get("TELEGRAM_TOKEN", "123:abc") # Пытаемся взять из переменных окружения или ставим заглушку
        
        application = Application.builder().token(temp_token).build()
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start_setup)],
            states={
                GET_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_token)],
                GET_GEMINI_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gemini_key)],
                GET_PROXY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_proxy)],
                GET_SCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_schedule_time)],
            },
            fallbacks=[CommandHandler("cancel", cancel_setup)],
        )
        application.add_handler(conv_handler)
        logger.info("Бот запущен. Отправьте /start для начала настройки.")

    else:
        # Если конфиг есть, запускаем бота в рабочем режиме
        logger.info("Конфигурация найдена. Запускаем бота в рабочем режиме.")
        
        # Строим приложение с данными из конфига
        builder = Application.builder().token(config["telegram_token"])
        if config.get("proxy_url"):
            proxy_url = config["proxy_url"]
            logger.info(f"Используется прокси: {proxy_url}")
            builder.proxy_url(proxy_url).get_updates_proxy_url(proxy_url)

        application = builder.build()
        
        # Запускаем планировщик в отдельном потоке
        scheduler_thread = Thread(target=run_scheduler, args=(application.job_queue,))
        scheduler_thread.daemon = True
        scheduler_thread.start()

    # Запускаем бота
    application.run_polling()


if __name__ == "__main__":
    main()
