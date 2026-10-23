import json, logging, os
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, ContextTypes, filters

TOKEN = os.environ['BOT_TOKEN']
ADMIN_ID = int(os.environ['ADMIN_ID'])
DATA = Path('portfolio.json')
WAIT_DETAILS, WAIT_CONTACT, WAIT_MEDIA, WAIT_TITLE = range(4)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
SERVICES = {'video': '🎬 AI-видео', 'image': '🖼️ AI-изображения', 'design': '✨ Дизайн / индивидуальный заказ'}

def load_items():
    try:
        data = json.loads(DATA.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def save_items(items):
    DATA.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🎬 AI-видео', callback_data='gallery:video:0'), InlineKeyboardButton('🖼️ AI-изображения', callback_data='gallery:image:0')],
        [InlineKeyboardButton('✨ Дизайн · индивидуальный заказ', callback_data='service:design')],
        [InlineKeyboardButton('🛒 Оформить заказ', callback_data='order:start')],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Привет! 👋 Добро пожаловать в rsmith.\n\n'
        'Выбирай подходящий стиль, изучай примеры и оформляй заказ. Можно выбрать готовый шаблон или заказать индивидуальный проект. Стоимость и детали обсудим лично.',
        reply_markup=menu())

async def gallery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, kind, page_s = q.data.split(':'); page = int(page_s)
    items = [x for x in load_items() if x.get('type') == kind]
    label = '🎬 Примеры AI-видео' if kind == 'video' else '🖼️ Примеры AI-изображений'
    if not items:
        await q.message.reply_text(f'{label}\n\nПока здесь нет примеров. Они появятся после загрузки владельцем.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='menu')]])); return
    size = 5; start = page * size
    await q.message.reply_text(f'{label}\nВыбери понравившийся шаблон:')
    for item in items[start:start+size]:
        caption = f"№{item['id']} · {item['title']}"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('✅ Выбрать этот шаблон', callback_data=f"choose:{item['id']}")]])
        try:
            if kind == 'video': await q.message.reply_video(item['file_id'], caption=caption, reply_markup=markup)
            else: await q.message.reply_photo(item['file_id'], caption=caption, reply_markup=markup)
        except Exception:
            log.exception('Failed to send portfolio item %s', item.get('id'))
            await q.message.reply_text(caption, reply_markup=markup)
    nav=[]
    if page: nav.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'gallery:{kind}:{page-1}'))
    if start+size < len(items): nav.append(InlineKeyboardButton('Ещё ➡️', callback_data=f'gallery:{kind}:{page+1}'))
    nav.append(InlineKeyboardButton('🏠 В меню', callback_data='menu'))
    await q.message.reply_text('Навигация:', reply_markup=InlineKeyboardMarkup([nav]))

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); await q.message.reply_text('Главное меню rsmith:', reply_markup=menu())

async def begin_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    await q.message.reply_text('Выбери направление:', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton('🎬 AI-видео', callback_data='order:video')],
        [InlineKeyboardButton('🖼️ AI-изображения', callback_data='order:image')],
        [InlineKeyboardButton('✨ Дизайн / индивидуально', callback_data='service:design')],
        [InlineKeyboardButton('⬅️ В меню', callback_data='menu')]]))
    return ConversationHandler.END

async def begin_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); kind=q.data.split(':')[1]
    context.user_data['order']={'service': SERVICES[kind], 'template_id': None, 'template_title': 'Индивидуальный заказ' if kind=='design' else 'Не выбран'}
    if kind=='design':
        await q.message.reply_text('✨ Индивидуальный заказ\n\nОпиши свою идею, желаемый результат и важные детали.')
        return WAIT_DETAILS
    items=[x for x in load_items() if x.get('type')==kind]
    if items:
        buttons=[[InlineKeyboardButton(f"№{x['id']} · {x['title']}", callback_data=f"choose:{x['id']}")] for x in items[:20]]
        buttons.append([InlineKeyboardButton('➡️ Продолжить без шаблона', callback_data='template:none')])
        await q.message.reply_text('Выбери шаблон или продолжи без него:', reply_markup=InlineKeyboardMarkup(buttons))
        return ConversationHandler.END
    await q.message.reply_text('Примеров пока нет. Продолжим без шаблона. Опиши, что нужно сделать:')
    return WAIT_DETAILS

async def choose_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    try: wid=int(q.data.split(':')[1])
    except (ValueError, IndexError): return ConversationHandler.END
    item=next((x for x in load_items() if x.get('id')==wid), None)
    if not item:
        await q.message.reply_text('Шаблон не найден. Открой галерею и выбери другой.'); return ConversationHandler.END
    context.user_data['order']={'service': SERVICES['video' if item['type']=='video' else 'image'], 'template_id':item['id'], 'template_title':item['title']}
    await q.message.reply_text(f"Выбран шаблон №{item['id']}: «{item['title']}».\n\nОпиши, что нужно изменить или добавить:")
    return WAIT_DETAILS

async def no_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    context.user_data.setdefault('order', {})['template_id']=None
    context.user_data['order']['template_title']='Не выбран'
    await q.message.reply_text('Опиши, что нужно сделать:')
    return WAIT_DETAILS

async def details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text=(update.message.text or '').strip()
    if not text:
        await update.message.reply_text('Напиши пару слов о заказе.'); return WAIT_DETAILS
    context.user_data.setdefault('order', {})['details']=text
    kb=ReplyKeyboardMarkup([[KeyboardButton('📱 Отправить мой номер', request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text('Оставь контакт для связи: отправь номер кнопкой или напиши его сообщением.', reply_markup=kb)
    return WAIT_CONTACT

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact: contact_text=update.message.contact.phone_number
    else:
        contact_text=(update.message.text or '').strip()
        if not contact_text:
            await update.message.reply_text('Отправь номер телефона или контакт сообщением.'); return WAIT_CONTACT
    order=context.user_data.get('order', {}); user=update.effective_user
    username=f"@{user.username}" if user and user.username else 'не указан'
    tid=order.get('template_id'); template=f"№{tid}" if tid else 'не выбран'
    note=('🆕 НОВАЯ ЗАЯВКА · rsmith\n\n'
          f"🧩 Услуга: {order.get('service','не указана')}\n"
          f"🎨 Шаблон: {template} — {order.get('template_title','не выбран')}\n"
          f"📝 Пожелания: {order.get('details','не указаны')}\n\n"
          f"👤 Клиент: {user.full_name if user else 'неизвестно'}\n🔗 Telegram: {username}\n"
          f"📞 Контакт: {contact_text}\n🆔 Telegram ID: {user.id if user else 'неизвестно'}")
    try: await context.bot.send_message(chat_id=ADMIN_ID, text=note)
    except Exception:
        log.exception('Could not notify admin')
        await update.message.reply_text('Не получилось отправить заявку. Попробуй позже.', reply_markup=ReplyKeyboardRemove()); return ConversationHandler.END
    await update.message.reply_text('✅ Заявка отправлена! rsmith свяжется с тобой, чтобы обсудить детали и стоимость.', reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text('Главное меню:', reply_markup=menu())
    context.user_data.pop('order', None); return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('order', None); context.user_data.pop('adding_type', None); context.user_data.pop('pending_file_id', None)
    await update.message.reply_text('Действие отменено.', reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text('Главное меню:', reply_markup=menu()); return ConversationHandler.END

def is_admin(update): return bool(update.effective_user and update.effective_user.id == ADMIN_ID)

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update):
        await update.message.reply_text('🛠 Управление портфолио\n/addvideo — добавить видео\n/addimage — добавить изображение\n/portfolio — список примеров\n/deletework ID — удалить пример (например /deletework 3)\n\nОтправь файл с названием в подписи. Если подписи нет, бот спросит название.')

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE): return await start_add(update, context, 'video')
async def add_image(update: Update, context: ContextTypes.DEFAULT_TYPE): return await start_add(update, context, 'image')
async def start_add(update, context, kind):
    if not is_admin(update): return ConversationHandler.END
    context.user_data['adding_type']=kind
    await update.message.reply_text('Отправь видео с подписью-названием.' if kind=='video' else 'Отправь фото с подписью-названием.')
    return WAIT_MEDIA

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return ConversationHandler.END
    kind=context.user_data.get('adding_type'); file_id=None
    if kind=='video' and update.message.video: file_id=update.message.video.file_id
    elif kind=='image' and update.message.photo: file_id=update.message.photo[-1].file_id
    elif kind=='image' and update.message.document and (update.message.document.mime_type or '').startswith('image/'): file_id=update.message.document.file_id
    if not file_id:
        await update.message.reply_text('Не тот тип файла. Для /addvideo отправь видео, для /addimage — фото.'); return WAIT_MEDIA
    context.user_data['pending_file_id']=file_id
    title=(update.message.caption or '').strip()
    if title: return await save_new(update, context, title)
    await update.message.reply_text('Как назвать этот пример?'); return WAIT_TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title=(update.message.text or '').strip()
    if not title:
        await update.message.reply_text('Напиши название примера.'); return WAIT_TITLE
    return await save_new(update, context, title)

async def save_new(update, context, title):
    items=load_items(); wid=max([int(x.get('id',0)) for x in items] or [0])+1
    items.append({'id':wid,'type':context.user_data.get('adding_type','image'),'title':title[:100], 'file_id':context.user_data.get('pending_file_id')})
    try: save_items(items)
    except OSError:
        log.exception('Cannot save portfolio'); await update.message.reply_text('Не удалось сохранить портфолио на диске Bothost.'); return ConversationHandler.END
    context.user_data.pop('adding_type',None); context.user_data.pop('pending_file_id',None)
    await update.message.reply_text(f'✅ Добавлено: №{wid} «{title}».'); return ConversationHandler.END

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    items=load_items()
    await update.message.reply_text('Портфолио пока пустое.' if not items else '📚 Примеры:\n'+'\n'.join(f"№{x['id']} · {'AI-видео' if x['type']=='video' else 'AI-изображение'} · {x['title']}" for x in items))

async def delete_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text('Использование: /deletework ID, например /deletework 3'); return
    wid=int(context.args[0]); items=load_items(); new=[x for x in items if x.get('id')!=wid]
    if len(new)==len(items): await update.message.reply_text('Пример с таким номером не найден.'); return
    try: save_items(new)
    except OSError: await update.message.reply_text('Не удалось сохранить изменения.'); return
    await update.message.reply_text(f'🗑 Пример №{wid} удалён.')

def main():
    app=Application.builder().token(TOKEN).build()
    order_flow=ConversationHandler(
        entry_points=[CallbackQueryHandler(begin_order, pattern=r'^order:start$'), CallbackQueryHandler(begin_service, pattern=r'^(service:design|order:(video|image))$'), CallbackQueryHandler(choose_template, pattern=r'^choose:\d+$'), CallbackQueryHandler(no_template, pattern=r'^template:none$')],
        states={WAIT_DETAILS:[MessageHandler(filters.TEXT & ~filters.COMMAND, details)], WAIT_CONTACT:[MessageHandler(filters.CONTACT, contact), MessageHandler(filters.TEXT & ~filters.COMMAND, contact)]},
        fallbacks=[CommandHandler('cancel', cancel)], per_message=False)
    add_flow=ConversationHandler(entry_points=[CommandHandler('addvideo', add_video), CommandHandler('addimage', add_image)], states={WAIT_MEDIA:[MessageHandler(filters.ALL & ~filters.COMMAND, receive_media)], WAIT_TITLE:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)]}, fallbacks=[CommandHandler('cancel', cancel)], per_message=False)
    app.add_handler(CommandHandler('start', start)); app.add_handler(CommandHandler('help', admin_help)); app.add_handler(CommandHandler('portfolio', portfolio)); app.add_handler(CommandHandler('deletework', delete_work))
    app.add_handler(add_flow); app.add_handler(order_flow)
    app.add_handler(CallbackQueryHandler(gallery, pattern=r'^gallery:(video|image):\d+$')); app.add_handler(CallbackQueryHandler(show_menu, pattern=r'^menu$'))
    log.info('rsmith bot starting'); app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__': main()
