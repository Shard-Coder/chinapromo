import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

MAIN_MENU, GET_SCREENSHOT, GET_BANK_NUMBER = range(3)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
STREAMERS_CHAT_ID = os.environ.get('STREAMERS_CHAT_ID')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("Пользователь %s начал диалог.", user.first_name)
    
    reply_keyboard = [['Подать заявку', 'Отмена']]
    
    await update.message.reply_text(
        '👋 Привет! Я бот для сбора заявок по промокоду.\n\n'
        'Нажми "Подать заявку", чтобы начать.',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True, input_field_placeholder='Выберите действие:'
        ),
    )

    return MAIN_MENU

async def handle_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    logger.info(f"Получен текст в главном меню: '{text}' от пользователя {update.message.from_user.first_name}")
    
    if text == 'Подать заявку':
        logger.info("Пользователь нажал 'Подать заявку'. Переход в GET_SCREENSHOT.")
        return await prompt_for_screenshot(update, context)
    elif text == 'Отмена':
        logger.info("Пользователь нажал 'Отмена'. Завершение диалога.")
        return await end_conversation(update, context)
    else:
        logger.warning(f"Получен непредусмотренный текст в меню: '{text}'")
        await update.message.reply_text("Пожалуйста, используйте кнопки на клавиатуре.")
        return MAIN_MENU

async def prompt_for_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        'Пожалуйста, отправь мне скриншот статистики твоего персонажа. '
        'На скриншоте должно быть видно, что ты ввёл промокод.',
        reply_markup=ReplyKeyboardRemove(),
    )
    return GET_SCREENSHOT


async def get_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    if not update.message.photo:
        await update.message.reply_text(
            'Это не похоже на скриншот. Пожалуйста, отправь именно изображение.'
        )
        return GET_SCREENSHOT

    photo_file_id = update.message.photo[-1].file_id
    context.user_data['photo_id'] = photo_file_id
    
    logger.info("Пользователь %s отправил скриншот.", user.first_name)
    
    await update.message.reply_text(
        '✅ Отлично, скриншот принят!\n\n'
        'Теперь, пожалуйста, отправь номер своего банковского счета в игре.'
    )

    return GET_BANK_NUMBER


async def get_bank_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    bank_number = update.message.text
    
    if not bank_number.isdigit():
        await update.message.reply_text(
            'Номер счета должен состоять только из цифр. Попробуй еще раз.'
        )
        return GET_BANK_NUMBER

    context.user_data['bank_number'] = bank_number
    logger.info("Пользователь %s отправил номер счета: %s", user.first_name, bank_number)

    try:
        caption = (
            f"🔥 Новая заявка\\!\n\n"
            f"👤 **Отправитель:** {user.mention_markdown_v2()} \\(ID: `{user.id}`\\)\n"
            f"💳 **Номер счета:** `{bank_number}`"
        )
        
        await context.bot.send_photo(
            chat_id=STREAMERS_CHAT_ID,
            photo=context.user_data['photo_id'],
            caption=caption,
            parse_mode='MarkdownV2'
        )
        logger.info("Заявка от %s успешно отправлена стримерам.", user.first_name)
        
        await update.message.reply_text(
            '🎉 Спасибо! Твоя заявка принята и отправлена на проверку. '
            'Ожидай своей награды!',
            reply_markup=ReplyKeyboardRemove()
        )
        return await start(update, context)

    except Exception as e:
        logger.error("Ошибка при отправке заявки в чат стримеров: %s", e)
        await update.message.reply_text(
            'Произошла внутренняя ошибка. '
            'Пожалуйста, попробуй позже или свяжись с администрацией.'
        )

    context.user_data.clear()
    return ConversationHandler.END

async def end_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("Пользователь %s завершил сессию.", user.first_name)
    await update.message.reply_text(
        'Диалог завершен. Чтобы начать заново, отправь /start.',
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    if not BOT_TOKEN:
        logger.critical("ОШИБКА: Переменная окружения BOT_TOKEN не найдена!")
        return
    if not STREAMERS_CHAT_ID:
        logger.critical("ОШИБКА: Переменная окружения STREAMERS_CHAT_ID не найдена!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_choice)
            ],
            GET_SCREENSHOT: [MessageHandler(filters.PHOTO & ~filters.COMMAND, get_screenshot)],
            GET_BANK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_number)],
        },
        fallbacks=[CommandHandler('cancel', end_conversation)],
    )

    application.add_handler(conv_handler)

    logger.info("Бот успешно запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()
