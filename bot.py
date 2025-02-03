import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler
)
import requests
import os

# ========== КОНФИГУРАЦИЯ ========== #
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Токен из переменных окружения
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")  # URL Google Apps Script
SECRET_TOKEN = os.getenv("SECRET_TOKEN")  # Секретный ключ
ACCOUNTS = ["Сбер", "Тинькофф", "Альфа", "МТС", "Райффайзен"]

# Состояния диалога
SELECT_ACTION, ENTER_AMOUNT, SELECT_ACCOUNT = range(3)

# ========== ОСНОВНЫЕ ФУНКЦИИ ========== #
def start(update: Update, context: CallbackContext) -> int:
    """Начало работы с ботом"""
    buttons = [["💵 Доход", "💸 Расход"], ["📊 Общий баланс"]]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    update.message.reply_text(
        "💰 <b>Финансовый помощник</b>\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    return SELECT_ACTION

def handle_action(update: Update, context: CallbackContext) -> int:
    """Обработка выбора действия"""
    text = update.message.text
    user_data = context.user_data

    if text == "📊 Общий баланс":
        return get_balance(update, context)
    else:
        user_data["type"] = "доход" if "Доход" in text else "расход"
        update.message.reply_text("⬇️ Введите сумму:", reply_markup=ReplyKeyboardRemove())
        return ENTER_AMOUNT

def handle_amount(update: Update, context: CallbackContext) -> int:
    """Обработка ввода суммы"""
    user_data = context.user_data
    text = update.message.text

    try:
        amount = float(text.replace(",", "."))
        if amount <= 0:
            raise ValueError
            
        user_data["amount"] = amount
        
        buttons = [ACCOUNTS[i:i+2] for i in range(0, len(ACCOUNTS), 2)]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        update.message.reply_text("🏦 Выберите счет:", reply_markup=reply_markup)
        return SELECT_ACCOUNT

    except (ValueError, TypeError):
        update.message.reply_text("❌ Некорректная сумма! Введите число:")
        return ENTER_AMOUNT

def handle_account(update: Update, context: CallbackContext) -> int:
    """Обработка выбора счета"""
    user_data = context.user_data
    account = update.message.text

    if account not in ACCOUNTS:
        update.message.reply_text("❌ Выберите счет из списка!")
        return SELECT_ACCOUNT

    # Отправка данных в Google Таблицу
    payload = {
        "token": SECRET_TOKEN,
        "type": user_data["type"],
        "amount": user_data["amount"],
        "account": account
    }

    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=payload)
        if "✅" in response.text:
            update.message.reply_text(
                f"✅ Данные сохранены!\n"
                f"Счет: {account}\n"
                f"Сумма: {user_data['amount']} руб.\n"
                f"Тип: {user_data['type']}"
            )
        else:
            update.message.reply_text("❌ Ошибка при сохранении!")
    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        update.message.reply_text("🚫 Сервис временно недоступен")

    user_data.clear()
    return start(update, context)

def get_balance(update: Update, context: CallbackContext) -> int:
    """Получение баланса"""
    try:
        response = requests.get(GOOGLE_SCRIPT_URL)
        update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        update.message.reply_text("🚫 Не удалось получить баланс")
    
    return start(update, context)

def cancel(update: Update, context: CallbackContext) -> int:
    """Отмена операции"""
    context.user_data.clear()
    update.message.reply_text("❌ Операция отменена")
    return start(update, context)

def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_ACTION: [
                MessageHandler(Filters.regex(r'^(💵 Доход|💸 Расход|📊 Общий баланс)$'), handle_action)
            ],
            ENTER_AMOUNT: [
                MessageHandler(Filters.text & ~Filters.command, handle_amount)
            ],
            SELECT_ACCOUNT: [
                MessageHandler(Filters.text & ~Filters.command, handle_account)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    dispatcher.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()