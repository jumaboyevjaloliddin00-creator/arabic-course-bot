import os
import sqlite3
from datetime import date, datetime
from calendar import monthrange

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters,
)

DB_PATH = os.getenv("DB_PATH", "students.db")
TOKEN = os.getenv("BOT_TOKEN")

GROUP, FULL_NAME, PAID_DATE, NEXT_DATE, METHOD, PHONE = range(6)
CANCEL = "Bekor qilish"
MENU = ReplyKeyboardMarkup(
    [
        ["➕ O‘quvchi qo‘shish", "📋 O‘quvchilar"],
        ["💳 To‘lovni qayd etish", "⏰ To‘lovi kelganlar"],
        [CANCEL],
    ],
    resize_keyboard=True,
)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            paid_date TEXT NOT NULL,
            next_date TEXT NOT NULL,
            method TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def add_month(iso_date: str) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    month = d.month + 1
    year = d.year
    if month == 13:
        month = 1
        year += 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day).isoformat()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db().close()
    await update.message.reply_text(
        "Assalomu alaykum! 📚\nArab tili kursi to‘lov botiga xush kelibsiz.\n"
        "Kerakli bo‘limni tanlang:", reply_markup=MENU
    )

async def begin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Guruh nomini yozing (masalan: Boshlang‘ich 1).")
    return GROUP

async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["group_name"] = update.message.text.strip()
    await update.message.reply_text("O‘quvchining ism-familiyasini yozing.")
    return FULL_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text("Oxirgi to‘lov sanasini YYYY-MM-DD shaklida yozing (masalan: 2026-10-27).")
    return PAID_DATE

async def get_paid_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Sana noto‘g‘ri. YYYY-MM-DD shaklida yozing, masalan 2026-10-27.")
        return PAID_DATE
    context.user_data["paid_date"] = value
    await update.message.reply_text("Keyingi to‘lov sanasini YYYY-MM-DD shaklida yozing.")
    return NEXT_DATE

async def get_next_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Sana noto‘g‘ri. YYYY-MM-DD shaklida yozing, masalan 2026-11-27.")
        return NEXT_DATE
    context.user_data["next_date"] = value
    await update.message.reply_text("To‘lov usulini tanlang: Naqd yoki Karta.", reply_markup=ReplyKeyboardMarkup([["Naqd", "Karta"], [CANCEL]], resize_keyboard=True))
    return METHOD

async def get_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if value.lower() not in ("naqd", "karta"):
        await update.message.reply_text("Iltimos, Naqd yoki Karta deb tanlang.")
        return METHOD
    context.user_data["method"] = value.title()
    await update.message.reply_text("Telefon raqamini yozing (masalan: +998901234567).")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    data["phone"] = update.message.text.strip()
    conn = db()
    conn.execute(
        "INSERT INTO students (group_name, full_name, paid_date, next_date, method, phone) VALUES (?, ?, ?, ?, ?, ?)",
        (data["group_name"], data["full_name"], data["paid_date"], data["next_date"], data["method"], data["phone"]),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "✅ O‘quvchi saqlandi!\n"
        f"Guruh: {data['group_name']}\nIsm-familiya: {data['full_name']}\n"
        f"To‘langan: {data['paid_date']}\nKeyingi to‘lov: {data['next_date']}\n"
        f"Usul: {data['method']}\nTelefon: {data['phone']}",
        reply_markup=MENU,
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi.", reply_markup=MENU)
    return ConversationHandler.END

async def students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db()
    rows = conn.execute(
        "SELECT id, group_name, full_name, next_date, method, phone FROM students ORDER BY group_name, full_name"
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Hozircha o‘quvchilar yo‘q.", reply_markup=MENU)
        return
    lines = ["📋 O‘quvchilar ro‘yxati:"]
    for sid, group_name, name, next_date, method, phone in rows:
        lines.append(f"#{sid} | {group_name}\n{name}\nKeyingi to‘lov: {next_date}\n{method} | {phone}")
    text = "\n\n".join(lines)
    # Telegram messages have a length limit; send in small batches.
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i+3500], reply_markup=MENU)

async def due(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today().isoformat()
    conn = db()
    rows = conn.execute(
        "SELECT group_name, full_name, next_date, phone FROM students WHERE next_date <= ? ORDER BY next_date",
        (today,),
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("🎉 Bugun to‘lovi kelgan o‘quvchilar yo‘q.", reply_markup=MENU)
        return
    lines = ["⏰ To‘lovi kelgan yoki muddati o‘tganlar:"]
    for group_name, name, next_date, phone in rows:
        lines.append(f"{group_name} — {name}\nSana: {next_date}\nTel: {phone}")
    await update.message.reply_text("\n\n".join(lines), reply_markup=MENU)

async def begin_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To‘lovni yangilash uchun o‘quvchining ro‘yxatdagi ID raqamini yozing.\n"
        "ID raqamini 📋 O‘quvchilar bo‘limidan ko‘rasiz."
    )
    return 10

async def payment_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sid = int(update.message.text.strip().lstrip("#"))
    except ValueError:
        await update.message.reply_text("ID raqamini son bilan yozing, masalan: 3.")
        return 10
    conn = db()
    row = conn.execute("SELECT full_name FROM students WHERE id = ?", (sid,)).fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("Bu ID topilmadi. 📋 O‘quvchilar bo‘limini tekshiring.", reply_markup=MENU)
        return ConversationHandler.END
    today = date.today().isoformat()
    next_date = add_month(today)
    conn.execute("UPDATE students SET paid_date = ?, next_date = ? WHERE id = ?", (today, next_date, sid))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ {row[0]} uchun to‘lov qayd etildi.\nTo‘lov sanasi: {today}\nKeyingi to‘lov: {next_date}",
        reply_markup=MENU,
    )
    return ConversationHandler.END

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing. Add it in the hosting service environment settings.")
    app = Application.builder().token(TOKEN).build()
    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ O‘quvchi qo‘shish$"), begin_add)],
        states={
            GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PAID_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_paid_date)],
            NEXT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_next_date)],
            METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_method)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Bekor qilish$"), cancel)],
    )
    pay_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 To‘lovni qayd etish$"), begin_payment)],
        states={10: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_id)]},
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^Bekor qilish$"), cancel)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv)
    app.add_handler(pay_conv)
    app.add_handler(MessageHandler(filters.Regex("^📋 O‘quvchilar$"), students))
    app.add_handler(MessageHandler(filters.Regex("^⏰ To‘lovi kelganlar$"), due))
    app.add_handler(MessageHandler(filters.Regex("^Bekor qilish$"), cancel))
    print("Arabic course payment bot is running.")
    app.run_polling()

if __name__ == "__main__":
    main()
