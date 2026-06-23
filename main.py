import os
import sqlite3
from datetime import datetime, timedelta
import asyncio

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncioScheduler

# ==================== НАСТРОЙКА БОТА ====================
TOKEN = "8721785219:AAGrI3BdN7Xe_SU4wcBAGR020fgDV00cqoU"
ADMIN_ID = 0  # Сюда можно вписать свой Telegram ID, чтобы получать уведомления о записях

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncioScheduler()

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect("beauty_booking.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            phone TEXT,
            service TEXT,
            date TEXT,
            time TEXT,
            reminded INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Временное хранилище шагов пользователя (замена FSM для простоты демо-версии)
user_sessions = {}

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="💅 Записаться на процедуру", callback_data="start_booking")
    builder.button(text="💰 Услуги и Цены", callback_data="show_prices")
    builder.button(text="📍 Контакты студии", callback_data="show_contacts")
    builder.adjust(1)
    return builder.as_markup()

def services_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✨ Классический маникюр — 1 500₽", callback_data="set_service:Маникюр")
    builder.button(text="💎 Наращивание ногтей — 2 500₽", callback_data="set_service:Наращивание")
    builder.button(text="🎨 Смарт-Педикюр — 2 000₽", callback_data="set_service:Педикюр")
    builder.button(text="« Назад в меню", callback_data="to_main")
    builder.adjust(1)
    return builder.as_markup()

def dates_keyboard():
    builder = InlineKeyboardBuilder()
    # Генерируем следующие 3 дня динамически
    now = datetime.now()
    for i in range(1, 4):
        day = now + timedelta(days=i)
        date_str = day.strftime("%d.%m")
        builder.button(text=f"📅 {date_str}", callback_data=f"set_date:{date_str}")
    builder.button(text="« Отмена", callback_data="to_main")
    builder.adjust(1)
    return builder.as_markup()

def times_keyboard():
    builder = InlineKeyboardBuilder()
    slots = ["10:00", "13:00", "16:00", "19:00"]
    for slot in slots:
        builder.button(text=f"⏰ {slot}", callback_data=f"set_time:{slot}")
    builder.button(text="« Отмена", callback_data="to_main")
    builder.adjust(2)
    return builder.as_markup()

# ==================== ХЭНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nДобро пожаловать в **Nail Studio**.\n"
        "Здесь вы можете быстро записаться на маникюр, узнать цены или связаться с мастером.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "to_main")
async def back_to_main(callback: types.CallbackQuery):
    user_sessions.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "Вы вернулись в главное меню. Выберите интересующий раздел:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "show_prices")
async def show_prices(callback: types.CallbackQuery):
    text = (
        "💳 **Прайс-лист на услуги:**\n\n"
        "• Классический маникюр + покрытие: 1 500₽\n"
        "• Наращивание ногтей (акригель): 2 500₽\n"
        "• Смарт-Педикюр с обработкой стопы: 2 000₽\n"
        "• Дизайн одного ногтя (френч/рисунок): 100₽"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="💅 Записаться прямо сейчас", callback_data="start_booking")
    builder.button(text="« Назад", callback_data="to_main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "show_contacts")
async def show_contacts(callback: types.CallbackQuery):
    text = (
        "📍 **Контакты и адрес:**\n\n"
        "🏠 Адрес: ул. Премиальная, д. 24, офис 302\n"
        "📞 Телефон мастера: +7 (999) 123-45-67\n"
        "📸 Наш Инстаграм: @aethera_nails\n\n"
        "✨ Работаем по предварительной записи с 10:00 до 21:00."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад", callback_data="to_main")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# Логика бронирования по шагам
@dp.callback_query(F.data == "start_booking")
async def start_booking(callback: types.CallbackQuery):
    user_sessions[callback.from_user.id] = {}
    await callback.message.edit_text("Выкатываем меню услуг. Что планируем делать? 👇", reply_markup=services_keyboard())

@dp.callback_query(F.data.startswith("set_service:"))
async def set_service(callback: types.CallbackQuery):
    service = callback.data.split(":")[1]
    user_sessions[callback.from_user.id]["service"] = service
    await callback.message.edit_text("Отлично! Теперь выберите удобную дату визита:", reply_markup=dates_keyboard())

@dp.callback_query(F.data.startswith("set_date:"))
async def set_date(callback: types.CallbackQuery):
    date = callback.data.split(":")[1]
    user_sessions[callback.from_user.id]["date"] = date
    await callback.message.edit_text("Осталось выбрать доступное время окошка:", reply_markup=times_keyboard())

@dp.callback_query(F.data.startswith("set_time:"))
async def set_time(callback: types.CallbackQuery):
    time = callback.data.split(":")[1]
    user_sessions[callback.from_user.id]["time"] = time
    
    await callback.message.edit_text(
        "📝 Напишите ваш **номер телефона** в чат ответным сообщением, чтобы мастер мог подтвердить запись:\n"
        "(Например: +79991234567)",
        parse_mode="Markdown"
    )
    user_sessions[callback.from_user.id]["step"] = "waiting_phone"

@dp.message(lambda msg: user_sessions.get(msg.from_user.id, {}).get("step") == "waiting_phone")
async def process_phone(message: types.Message):
    user_id = message.from_user.id
    phone = message.text
    session = user_sessions[user_id]
    
    service = session["service"]
    date = session["date"]
    time = session["time"]
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    
    # Сохраняем в базу данных
    conn = sqlite3.connect("beauty_booking.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO appointments (user_id, username, phone, service, date, time) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, phone, service, date, time)
    )
    conn.commit()
    conn.close()
    
    # Очищаем сессию шагов
    user_sessions.pop(user_id, None)
    
    # Ответ клиенту
    await message.answer(
        f"🎉 **Запись успешно оформлена!**\n\n"
        f"💅 Процедура: {service}\n"
        f"📅 Дата: {date}\n"
        f"⏰ Время: {time}\n\n"
        f"Мастер свяжется с вами по номеру {phone}. За день до визита я пришлю вам напоминание! Наш бот всегда активен.",
        parse_mode="Markdown"
    )
    
    # Уведомление мастеру (если ADMIN_ID настроен)
    if ADMIN_ID != 0:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🔥 **Новая запись на маникюр!**\n\n"
                f"👤 Клиент: {message.from_user.full_name} ({username})\n"
                f"📞 Телефон: {phone}\n"
                f"💅 Услуга: {service}\n"
                f"📆 Когда: {date} в {time}"
            )
        except Exception:
            pass

# ==================== НАПОМИНАЛКА (КРОН) ====================
async def check_reminders():
    # Эта функция крутится в фоне и раз в час проверяет базу
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%d.%m") # Формат "24.06"
    
    conn = sqlite3.connect("beauty_booking.db")
    cursor = conn.cursor()
    # Ищем записи на завтра, по которым еще не отправляли напоминание (reminded = 0)
    cursor.execute("SELECT id, user_id, service, time FROM appointments WHERE date = ? AND reminded = 0", (tomorrow_str,))
    rows = cursor.fetchall()
    
    for row in rows:
        app_id, user_id, service, time = row
        try:
            await bot.send_message(
                user_id,
                f"⏰ **Напоминание о записи!**\n\n"
                f"Здравствуйте! Напоминаем, что завтра вы записаны на **{service}**.\n"
                f"Ждем вас в **{time}**. Если ваши планы изменились, пожалуйста, предупредите мастера заранее!"
            )
            # Отмечаем в БД, что напомнили
            cursor.execute("UPDATE appointments SET reminded = 1 WHERE id = ?", (app_id,))
        except Exception:
            # Если пользователь заблокировал бота, просто пропускаем
            pass
            
    conn.commit()
    conn.close()

# ==================== ЗАПУСК БОТА ====================
async def main():
    # Настраиваем планировщик запускать проверку напоминаний каждый час
    scheduler.add_job(check_reminders, 'interval', hours=1)
    scheduler.start()
    
    print("Бот Nail Studio успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
