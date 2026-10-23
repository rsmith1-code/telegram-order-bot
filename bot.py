import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

ORDER, CONTACT = range(2)

logging.basicConfig(level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton(
            "🛒 Оформить заказ",
            callback_data="order"
        )
    ]]

    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Здесь ты можешь оставить заявку на заказ.\n"
        "Нажми кнопку ниже, чтобы начать.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def begin_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "Что ты хочешь заказать?\n\n"
        "Опиши заказ одним сообщением."
    )

    return ORDER


async def get_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    context.user_data["order"] = update.message.text

    keyboard = [[
        KeyboardButton(
            "📱 Отправить номер телефона",
            request_contact=True
        )
    ]]

    await update.message.reply_text(
        "Оставь свой номер телефона, чтобы мы могли связаться с тобой.\n\n"
        "Нажми кнопку ниже или напиши контакт вручную.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return CONTACT


async def get_contact(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    if update.message.contact:
        contact = update.message.contact.phone_number
    else:
        contact = update.message.text

    order = context.user_data.get("order", "Не указан")

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "🔔 НОВЫЙ ЗАКАЗ!\n\n"
            f"👤 Имя: {user.full_name}\n"
            f"🆔 Telegram ID: {user.id}\n"
            f"📦 Заказ: {order}\n"
            f"📞 Контакт: {contact}"
        ),
    )

    await update.message.reply_text(
        "✅ Заявка отправлена!\n\n"
        "Спасибо! С тобой свяжутся для уточнения деталей.",
        reply_markup=ReplyKeyboardMarkup(
            [["🏠 В начало"]],
            resize_keyboard=True,
        ),
    )

    return ConversationHandler.END


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    context.user_data.clear()

    await update.message.reply_text(
        "Оформление отменено. Чтобы начать заново, напиши /start."
    )

    return ConversationHandler.END


def main():
    app = Application.builder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(begin_order, pattern="^order$")
        ],
        states={
            ORDER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_order
                )
            ],
            CONTACT: [
                MessageHandler(
                    filters.CONTACT
                    | (filters.TEXT & ~filters.COMMAND),
                    get_contact
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conversation)

    app.run_polling()


if __name__ == "__main__":
    main()
