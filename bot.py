import logging
import os
import sys
import time
import secrets
import sqlite3
import subprocess
import asyncio
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# ─── تنظیمات لاگ ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ─── ثابت‌ها ──────────────────────────────────────────────────────────────────
API_ID = 34434623
API_HASH = "d82c5dd13602eedc3041e9f549bcd813"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8731724435:AAFYu8ARPZ0Ov5rEG2bs3RziRWB0P9_OIDA")
OWNER_ID = int(os.environ.get("OWNER_ID", 8296865861))
DATABASE_DIR = "database"

if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

# ─── حالت‌های مکالمه ─────────────────────────────────────────────────────────
ACTIVATION_PANEL, GET_PHONE, GET_CODE, COIN_PURCHASE, CONFIRM_PURCHASE = range(5)

# ─── دیتابیس ──────────────────────────────────────────────────────────────────
def init_bot_db():
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        phone TEXT,
        coins INTEGER DEFAULT 0,
        invited_by INTEGER,
        join_date TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pending_purchases (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER,
        price INTEGER,
        status TEXT,
        timestamp TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS invite_links (
        code TEXT PRIMARY KEY,
        user_id INTEGER,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()

init_bot_db()

def get_user_coins(user_id):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_user_coins(user_id, amount):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, coins, join_date) VALUES (?, ?, datetime("now"))', (user_id, amount))
    conn.commit()
    conn.close()

def update_user_coins(user_id, amount):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_setting_db(key, default=None):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting_db(key, value):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def add_pending_purchase(purchase_id, user_id, amount, price):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pending_purchases (id, user_id, amount, price, status, timestamp) VALUES (?, ?, ?, ?, "pending", datetime("now"))',
                   (purchase_id, user_id, amount, price))
    conn.commit()
    conn.close()

def get_pending_purchase(purchase_id):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pending_purchases WHERE id = ?', (purchase_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"id": result[0], "user_id": result[1], "amount": result[2], "price": result[3], "status": result[4], "timestamp": result[5]}
    return None

def get_all_pending_purchases():
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pending_purchases WHERE status = "pending" ORDER BY timestamp DESC')
    results = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "amount": r[2], "price": r[3], "status": r[4], "timestamp": r[5]} for r in results]

def update_purchase_status(purchase_id, status):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('UPDATE pending_purchases SET status = ? WHERE id = ?', (status, purchase_id))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_total_coins():
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(coins) FROM users')
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0

def save_invite_link(code, user_id):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO invite_links (code, user_id, created_at) VALUES (?, ?, datetime("now"))', (code, user_id))
    conn.commit()
    conn.close()

def get_invite_link_user(code):
    conn = sqlite3.connect(os.path.join(DATABASE_DIR, "bot_users.db"))
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM invite_links WHERE code = ?', (code,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ─── کلاس اصلی ربات ──────────────────────────────────────────────────────────
class NexoBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.card_number = get_setting_db("card_number", "6037000000000000")
        self.admin_id = int(get_setting_db("admin_id", str(OWNER_ID)))
        self.user_sessions = {}
        self.invite_links = {}
        self.user_coins = {}
        
        self.setup_handlers()
    
    def setup_handlers(self):
        # ─── دستورات اصلی ──────────────────────────────────────────────────
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("admin", self.admin_panel))
        self.application.add_handler(CommandHandler("setcard", self.set_card_number))
        self.application.add_handler(CommandHandler("setadmin", self.set_admin_id))
        self.application.add_handler(CommandHandler("addcoins", self.add_coins_command))
        
        # ─── دکمه‌های منوی اصلی ────────────────────────────────────────────
        self.application.add_handler(CallbackQueryHandler(self.main_menu_callback, pattern='^main_menu$'))
        self.application.add_handler(CallbackQueryHandler(self.help_callback, pattern='^help$'))
        self.application.add_handler(CallbackQueryHandler(self.status_callback, pattern='^status$'))
        self.application.add_handler(CallbackQueryHandler(self.buy_callback, pattern='^buy$'))
        self.application.add_handler(CallbackQueryHandler(self.balance_callback, pattern='^balance$'))
        self.application.add_handler(CallbackQueryHandler(self.invite_callback, pattern='^invite$'))
        self.application.add_handler(CallbackQueryHandler(self.activate_callback, pattern='^activate$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_callback, pattern='^admin$'))
        
        # ─── دکمه‌های پنل مدیریت ──────────────────────────────────────────
        self.application.add_handler(CallbackQueryHandler(self.admin_manage_coins, pattern='^admin_manage_coins$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_set_card_callback, pattern='^admin_set_card$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_set_admin_callback, pattern='^admin_set_admin$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_view_stats, pattern='^admin_view_stats$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_view_pending, pattern='^admin_view_pending$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_back, pattern='^admin_back$'))
        
        # ─── دکمه‌های تایید/رد خرید ──────────────────────────────────────
        self.application.add_handler(CallbackQueryHandler(self.approve_purchase, pattern='^approve_'))
        self.application.add_handler(CallbackQueryHandler(self.reject_purchase, pattern='^reject_'))
        
        # ─── دکمه‌های خرید سکه ────────────────────────────────────────────
        self.application.add_handler(CallbackQueryHandler(self.coin_purchase, pattern='^(coin_|display_coins|coin_delete|coin_submit)'))
        
        # ─── دکمه‌های فعال‌سازی ──────────────────────────────────────────
        self.application.add_handler(CallbackQueryHandler(self.activation_panel, pattern='^(activate|support|buy_coins|back|stats|invite)$'))
        
        # ─── دکمه رمز دو مرحله‌ای ─────────────────────────────────────────
        self.application.add_handler(CallbackQueryHandler(self.skip_password, pattern='^skip_password$'))
        
        # ─── هندلرهای پیام ──────────────────────────────────────────────────
        self.application.add_handler(MessageHandler(filters.PHOTO & filters.REPLY, self.handle_receipt_photo))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_messages))
        
        # ─── Conversation Handler ──────────────────────────────────────────
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                ACTIVATION_PANEL: [
                    CallbackQueryHandler(self.activation_panel, pattern='^(activate|support|buy_coins|back|stats|invite)$')
                ],
                GET_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_phone_number)
                ],
                GET_CODE: [
                    CallbackQueryHandler(self.verify_code, pattern='^.*$'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_password_input)
                ],
                COIN_PURCHASE: [
                    CallbackQueryHandler(self.coin_purchase, pattern='^.*$')
                ],
                CONFIRM_PURCHASE: [
                    CallbackQueryHandler(self.confirm_purchase, pattern='^(confirm_purchase|cancel_purchase)$')
                ]
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel),
                CommandHandler('start', self.start)
            ],
            per_message=False
        )
        self.application.add_handler(conv_handler)
    
    def is_owner(self, user_id):
        return user_id == self.admin_id
    
    # ─── کیبوردها ──────────────────────────────────────────────────────────────
    def create_main_menu(self):
        keyboard = [
            [InlineKeyboardButton("📖 راهنما", callback_data="help")],
            [InlineKeyboardButton("📊 وضعیت سیستم", callback_data="status")],
            [InlineKeyboardButton("💰 خرید سکه", callback_data="buy")],
            [InlineKeyboardButton("💳 موجودی", callback_data="balance")],
            [InlineKeyboardButton("🎫 لینک دعوت", callback_data="invite")],
            [InlineKeyboardButton("🚀 فعال‌سازی سلف", callback_data="activate")],
            [InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin")],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_admin_menu(self):
        keyboard = [
            [InlineKeyboardButton("💰 مدیریت سکه‌ها", callback_data="admin_manage_coins")],
            [InlineKeyboardButton("💳 تنظیم شماره کارت", callback_data="admin_set_card")],
            [InlineKeyboardButton("👑 تنظیم آیدی مالک", callback_data="admin_set_admin")],
            [InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_view_stats")],
            [InlineKeyboardButton("📋 خریدهای در انتظار", callback_data="admin_view_pending")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_activation_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("🚀 فعال‌سازی سلف", callback_data="activate"),
                InlineKeyboardButton("💰 خرید سکه", callback_data="buy_coins")
            ],
            [
                InlineKeyboardButton("📊 آمار و موجودی", callback_data="stats"),
                InlineKeyboardButton("🎫 لینک دعوت", callback_data="invite")
            ],
            [
                InlineKeyboardButton("🛟 پشتیبانی", url="https://t.me/amele55")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_stats_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("💳 افزایش موجودی", callback_data="buy_coins"),
                InlineKeyboardButton("🎫 لینک دعوت", callback_data="invite")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="back")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_invite_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("📊 آمار دعوت", callback_data="stats"),
                InlineKeyboardButton("💳 خرید سکه", callback_data="buy_coins")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="back")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_phone_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_code_keyboard(self, current_code=""):
        display_code = current_code if current_code else "•••••"
        keyboard = [
            [InlineKeyboardButton(f"🔢 کد فعلی: {display_code}", callback_data="display")],
            [
                InlineKeyboardButton("1", callback_data="1"),
                InlineKeyboardButton("2", callback_data="2"),
                InlineKeyboardButton("3", callback_data="3")
            ],
            [
                InlineKeyboardButton("4", callback_data="4"),
                InlineKeyboardButton("5", callback_data="5"),
                InlineKeyboardButton("6", callback_data="6")
            ],
            [
                InlineKeyboardButton("7", callback_data="7"),
                InlineKeyboardButton("8", callback_data="8"),
                InlineKeyboardButton("9", callback_data="9")
            ],
            [
                InlineKeyboardButton("🗑️ حذف", callback_data="delete"),
                InlineKeyboardButton("0", callback_data="0"),
                InlineKeyboardButton("✅ تایید", callback_data="submit")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_coin_keyboard(self, current_amount=""):
        display_amount = current_amount if current_amount else "0"
        keyboard = [
            [InlineKeyboardButton(f"💌 تعداد سکه: {display_amount}", callback_data="display_coins")],
            [
                InlineKeyboardButton("1", callback_data="coin_1"),
                InlineKeyboardButton("2", callback_data="coin_2"),
                InlineKeyboardButton("3", callback_data="coin_3")
            ],
            [
                InlineKeyboardButton("4", callback_data="coin_4"),
                InlineKeyboardButton("5", callback_data="coin_5"),
                InlineKeyboardButton("6", callback_data="coin_6")
            ],
            [
                InlineKeyboardButton("7", callback_data="coin_7"),
                InlineKeyboardButton("8", callback_data="coin_8"),
                InlineKeyboardButton("9", callback_data="coin_9")
            ],
            [
                InlineKeyboardButton("🗑️ حذف", callback_data="coin_delete"),
                InlineKeyboardButton("0", callback_data="coin_0"),
                InlineKeyboardButton("✅ تایید", callback_data="coin_submit")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    # ─── دستورات اصلی ──────────────────────────────────────────────────────────
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        
        # بررسی لینک دعوت
        if context.args and len(context.args) > 0:
            invite_code = context.args[0]
            referrer_id = get_invite_link_user(invite_code)
            if referrer_id:
                referrer_coins = get_user_coins(referrer_id)
                add_user_coins(referrer_id, referrer_coins + 7)
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text="🎉 کاربر جدیدی با لینک دعوت شما وارد ربات شد!\n💰 7 سکه به عنوان پاداش دریافت کردید!"
                    )
                except:
                    pass
        
        # هدیه اولیه
        if get_user_coins(user_id) == 0 and not self.is_owner(user_id):
            add_user_coins(user_id, 5)
            await update.message.reply_text(
                "🎁 **هدیه ویژه!**\n\n"
                "به شما 5 سکه رایگان هدیه داده شد!\n"
                "💰 موجودی فعلی: 5 سکه"
            )
        
        welcome_text = (
            "💡 **به NexoSelf خوش آمدید!** 🔋\n\n"
            "🚀 لطفاً از منوی زیر گزینه مورد نظر خود را انتخاب کنید:\n\n"
            "👑 **مالک:** @amele55"
        )
        
        await update.message.reply_text(
            text=welcome_text,
            reply_markup=self.create_main_menu(),
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
┌─────────────────────
│  📖 **راهنمای NexoSelf**  
└─────────────────────

🎯 **دستورات اصلی:**
• /start - منوی اصلی
• /help - راهنما
• /admin - پنل مدیریت (فقط مالک)

💰 **اقتصادی:**
• خرید سکه - از منوی اصلی
• موجودی - از منوی اصلی

🚀 **فعال‌سازی سلف:**
• از منوی اصلی گزینه فعال‌سازی را انتخاب کنید
• برای فعال‌سازی به ۵ سکه نیاز دارید

💡 **نکات:**
• به ازای هر دعوت ۷ سکه پاداش دریافت می‌کنید
• قیمت هر سکه: ۲۰۰ تومن

🔮 **قدرت گرفته از:** @Ch_SelfNexo
        """
        await update.message.reply_text(help_text)
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ شما دسترسی به پنل مدیریت را ندارید!")
            return
        
        await update.message.reply_text(
            "👑 **پنل مدیریت NexoSelf**\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=self.create_admin_menu()
        )
    
    async def set_card_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ شما دسترسی به این دستور را ندارید!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ لطفاً شماره کارت را وارد کنید:\n"
                "مثال: `/setcard 6037999999999999`"
            )
            return
        
        card_number = context.args[0].strip()
        if len(card_number) != 16 or not card_number.isdigit():
            await update.message.reply_text("❌ شماره کارت باید ۱۶ رقمی باشد!")
            return
        
        set_setting_db("card_number", card_number)
        self.card_number = card_number
        await update.message.reply_text(f"✅ شماره کارت با موفقیت تغییر کرد:\n`{card_number}`")
    
    async def set_admin_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ شما دسترسی به این دستور را ندارید!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ لطفاً آیدی جدید مالک را وارد کنید:\n"
                "مثال: `/setadmin 123456789`"
            )
            return
        
        try:
            new_admin_id = int(context.args[0])
            set_setting_db("admin_id", str(new_admin_id))
            self.admin_id = new_admin_id
            await update.message.reply_text(f"✅ آیدی مالک با موفقیت تغییر کرد:\n`{new_admin_id}`")
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک آیدی عددی معتبر وارد کنید!")
    
    async def add_coins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ شما دسترسی به این دستور را ندارید!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ لطفاً یوزرنیم و تعداد سکه را مشخص کنید:\n"
                "مثال: `/addcoins @user123 10`"
            )
            return
        
        username = context.args[0].replace('@', '')
        try:
            amount = int(context.args[1])
            if amount <= 0:
                await update.message.reply_text("❌ تعداد سکه باید بیشتر از صفر باشد!")
                return
            
            # اینجا باید کاربر را با یوزرنیم پیدا کنید
            # فعلاً پیام می‌دهیم
            await update.message.reply_text(
                f"✅ {amount} سکه به کاربر @{username} اضافه شد!\n"
                f"💰 موجودی جدید: [در حال بررسی]"
            )
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر برای تعداد سکه وارد کنید!")
    
    # ─── دکمه‌های منو ──────────────────────────────────────────────────────────
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "📋 **منوی اصلی NexoSelf**\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=self.create_main_menu()
        )
    
    async def help_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        help_text = """
┌─────────────────────
│  📖 **راهنمای NexoSelf**  
└─────────────────────

🎯 **دستورات اصلی:**
• /start - منوی اصلی
• /help - راهنما

💰 **اقتصادی:**
• خرید سکه - از منوی اصلی
• موجودی - از منوی اصلی

🚀 **فعال‌سازی سلف:**
• از منوی اصلی گزینه فعال‌سازی را انتخاب کنید
• برای فعال‌سازی به ۵ سکه نیاز دارید

💡 **نکات:**
• به ازای هر دعوت ۷ سکه پاداش دریافت می‌کنید
• قیمت هر سکه: ۲۰۰ تومن

🔮 **قدرت گرفته از:** @Ch_SelfNexo
        """
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def status_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        coins = get_user_coins(user_id)
        
        status_text = f"""
┌─────────────────────
│  📊 **وضعیت سیستم NexoSelf**  
└─────────────────────

👤 **اطلاعات کاربر:**
• آیدی: `{user_id}`
• سکه: {coins}
• وضعیت: {'فعال' if coins >= 5 else 'غیرفعال'}

🖥 **وضعیت ربات:**
• وضعیت: ✅ آنلاین
• نسخه: 2.0

💰 **اقتصاد:**
• قیمت هر سکه: ۲۰۰ تومن
• ارزش سکه‌ها: {coins * 200:,} تومن

🔮 **قدرت گرفته از:** @Ch_SelfNexo
        """
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def buy_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        context.user_data['coin_amount'] = ''
        
        buy_text = f"""
💌 **خرید سکه NexoSelf** 💌

💰 هر عدد سکه: ۲۰۰ تومن

📝 تعداد سکه مورد نظر را با کیبورد زیر وارد کنید:

💳 شماره کارت برای واریز:
`{self.card_number}`

🆔 آیدی مالک برای پیگیری:
@amele55
        """
        await query.edit_message_text(
            buy_text,
            reply_markup=self.create_coin_keyboard()
        )
        return COIN_PURCHASE
    
    async def balance_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        coins = get_user_coins(user_id)
        
        balance_text = f"""
🥃 **موجودی شما**

💰 موجودی: {coins} سکه
💎 ارزش ریالی: {coins * 200:,} تومن
🕐 زمان: {datetime.now().strftime('%H:%M:%S')}
        """
        await query.edit_message_text(balance_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        invite_code = secrets.token_urlsafe(8)
        save_invite_link(invite_code, user_id)
        invite_link = f"https://t.me/{context.bot.username}?start={invite_code}"
        
        invite_text = f"""
🎫 **لینک دعوت شما**

🔗 لینک: `{invite_link}`

💎 **مزایای دعوت:**
• به ازای هر دعوت: **7 سکه** پاداش
• دعوت شده: **5 سکه** هدیه اولیه
• بدون محدودیت تعداد دعوت
        """
        await query.edit_message_text(invite_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def activate_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        coins = get_user_coins(user_id)
        if coins < 5:
            await query.edit_message_text(
                f"❌ موجودی سکه شما کافی نیست!\n\n"
                f"💰 موجودی فعلی: {coins} سکه\n"
                f"💸 برای فعال‌سازی سلف به ۵ سکه نیاز دارید.\n\n"
                f"لطفاً از بخش '💰 خرید سکه' اقدام به خرید نمایید.",
                reply_markup=self.create_activation_keyboard()
            )
            return
        
        phone_text = (
            "📱 لطفاً شماره تلفن خود را به صورت دستی ارسال کنید:\n\n"
            "📝 فرمت پیشنهادی:\n"
            "• +989123456789\n"
            "• 09123456789\n\n"
            "⚠️ شماره باید معتبر و قابل دریافت کد باشد."
        )
        
        await query.edit_message_text(
            phone_text,
            reply_markup=self.create_phone_keyboard()
        )
        return GET_PHONE
    
    # ─── پنل مدیریت ────────────────────────────────────────────────────────────
    async def admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به پنل مدیریت را ندارید!")
            return
        
        await query.edit_message_text(
            "👑 **پنل مدیریت NexoSelf**\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=self.create_admin_menu()
        )
    
    async def admin_manage_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        await query.edit_message_text(
            "💰 **مدیریت سکه‌ها**\n\n"
            "برای افزودن سکه به کاربر از دستور زیر استفاده کنید:\n"
            "`/addcoins @username تعداد`\n\n"
            "مثال: `/addcoins @user123 10`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_set_card_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        await query.edit_message_text(
            f"💳 **تنظیم شماره کارت**\n\n"
            f"شماره کارت فعلی:\n`{self.card_number}`\n\n"
            f"برای تغییر، از دستور زیر استفاده کنید:\n"
            f"`/setcard شماره_کارت`\n\n"
            f"مثال: `/setcard 6037999999999999`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_set_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        await query.edit_message_text(
            f"👑 **تنظیم آیدی مالک**\n\n"
            f"آیدی فعلی مالک: `{self.admin_id}`\n\n"
            f"برای تغییر، از دستور زیر استفاده کنید:\n"
            f"`/setadmin آیدی_جدید`\n\n"
            f"مثال: `/setadmin 123456789`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_view_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        total_users = get_total_users()
        total_coins = get_total_coins()
        pending = len(get_all_pending_purchases())
        
        stats_text = f"""
📊 **آمار کاربران NexoSelf**

👥 تعداد کاربران: {total_users}
💰 مجموع سکه‌ها: {total_coins}
📋 خریدهای در انتظار: {pending}
💳 شماره کارت: `{self.card_number}`
👑 آیدی مالک: `{self.admin_id}`
        """
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_view_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        pending = get_all_pending_purchases()
        
        if not pending:
            await query.edit_message_text(
                "📋 **هیچ خریدی در انتظار تایید نیست!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
            )
            return
        
        pending_text = "📋 **خریدهای در انتظار تایید:**\n\n"
        for p in pending[:10]:
            pending_text += f"""
🆔 کاربر: `{p['user_id']}`
💰 تعداد: {p['amount']} سکه
💵 مبلغ: {p['price']:,} تومن
⏰ زمان: {p['timestamp']}
---
"""
        await query.edit_message_text(
            pending_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "👑 **پنل مدیریت NexoSelf**\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=self.create_admin_menu()
        )
    
    # ─── تایید/رد خرید ─────────────────────────────────────────────────────────
    async def approve_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        purchase_id = query.data.replace('approve_', '')
        purchase = get_pending_purchase(purchase_id)
        
        if not purchase:
            await query.edit_message_text("❌ خرید یافت نشد!")
            return
        
        current_coins = get_user_coins(purchase['user_id'])
        add_user_coins(purchase['user_id'], current_coins + purchase['amount'])
        update_purchase_status(purchase_id, "approved")
        
        try:
            await context.bot.send_message(
                chat_id=purchase['user_id'],
                text=f"""
✅ **خرید شما تایید شد!**

🎉 {purchase['amount']} سکه به حساب شما اضافه شد.
💰 موجودی جدید: {current_coins + purchase['amount']} سکه

🙏 از اعتماد شما سپاسگزاریم!
                """
            )
        except:
            pass
        
        await query.edit_message_text(
            f"✅ خرید تایید شد!\n\n"
            f"👤 کاربر: `{purchase['user_id']}`\n"
            f"💰 تعداد سکه: {purchase['amount']}\n"
            f"💎 موجودی جدید: {current_coins + purchase['amount']} سکه"
        )
    
    async def reject_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        purchase_id = query.data.replace('reject_', '')
        purchase = get_pending_purchase(purchase_id)
        
        if not purchase:
            await query.edit_message_text("❌ خرید یافت نشد!")
            return
        
        update_purchase_status(purchase_id, "rejected")
        
        try:
            await context.bot.send_message(
                chat_id=purchase['user_id'],
                text=f"""
❌ **خرید شما رد شد!**

متأسفانه درخواست خرید {purchase['amount']} سکه شما تایید نشد.

📌 برای بررسی بیشتر با مالک تماس بگیرید:
🆔 @amele55
                """
            )
        except:
            pass
        
        await query.edit_message_text(
            f"❌ خرید رد شد!\n\n"
            f"👤 کاربر: `{purchase['user_id']}`\n"
            f"💰 تعداد سکه: {purchase['amount']}"
        )
    
    # ─── فرایند فعال‌سازی ──────────────────────────────────────────────────────
    async def activation_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "activate":
            coins = get_user_coins(user_id)
            if coins < 5:
                await query.edit_message_text(
                    f"❌ موجودی سکه شما کافی نیست!\n\n"
                    f"💰 موجودی فعلی: {coins} سکه\n"
                    f"💸 برای فعال‌سازی سلف به ۵ سکه نیاز دارید.\n\n"
                    f"لطفاً از بخش '💰 خرید سکه' اقدام به خرید نمایید.",
                    reply_markup=self.create_activation_keyboard()
                )
                return ACTIVATION_PANEL
            
            phone_text = (
                "📱 لطفاً شماره تلفن خود را به صورت دستی ارسال کنید:\n\n"
                "📝 فرمت پیشنهادی:\n"
                "• +989123456789\n"
                "• 09123456789\n\n"
                "⚠️ شماره باید معتبر و قابل دریافت کد باشد."
            )
            
            await query.edit_message_text(
                phone_text,
                reply_markup=self.create_phone_keyboard()
            )
            return GET_PHONE
        
        elif query.data == "buy_coins":
            context.user_data['coin_amount'] = ''
            coin_text = (
                "💌•••خرید سکه•••💌\n\n"
                "💰 هر عدد سکه: 200 تومن\n"
                "‼️ تعداد سکه مورد نظر خود را وارد کنید\n\n"
                "⌨️ از کیبورد زیر برای وارد کردن تعداد سکه استفاده کنید:"
            )
            await query.edit_message_text(coin_text, reply_markup=self.create_coin_keyboard())
            return COIN_PURCHASE
        
        elif query.data == "stats":
            coins = get_user_coins(user_id)
            total_value = coins * 200
            stats_text = (
                f"📊 **آمار و موجودی شما**\n\n"
                f"💰 **موجودی سکه:** {coins} سکه\n"
                f"💎 **ارزش ریالی:** {total_value:,} تومن\n"
                f"💡 **نکته:** به ازای هر دعوت موفق 7 سکه پاداش دریافت می‌کنید!"
            )
            await query.edit_message_text(stats_text, reply_markup=self.create_stats_keyboard())
            return ACTIVATION_PANEL
        
        elif query.data == "invite":
            invite_code = secrets.token_urlsafe(8)
            save_invite_link(invite_code, user_id)
            invite_link = f"https://t.me/{context.bot.username}?start={invite_code}"
            
            invite_text = (
                f"🎫 **لینک دعوت شما**\n\n"
                f"🔗 **لینک:** `{invite_link}`\n\n"
                f"💎 **مزایای دعوت:**\n"
                f"• به ازای هر دعوت: **7 سکه** پاداش\n"
                f"• دعوت شده: **5 سکه** هدیه اولیه\n"
                f"• بدون محدودیت تعداد دعوت"
            )
            await query.edit_message_text(invite_text, reply_markup=self.create_invite_keyboard(), parse_mode='Markdown')
            return ACTIVATION_PANEL
        
        elif query.data == "support":
            await query.edit_message_text(
                "🛟 در حال انتقال به پشتیبانی...",
                reply_markup=self.create_activation_keyboard()
            )
            return ACTIVATION_PANEL
        
        elif query.data == "back":
            activation_text = (
                "💡 **فعال‌سازی سلف خود را از منوی زیر شروع کنید** 🔋\n\n"
                "🚀 **برای فعال‌سازی سلف، روی دکمه زیر کلیک کنید** ⚙️"
            )
            await query.edit_message_text(
                activation_text,
                reply_markup=self.create_activation_keyboard()
            )
            return ACTIVATION_PANEL
    
    # ─── خرید سکه (هندلر اصلی) ────────────────────────────────────────────────
    async def coin_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if 'coin_amount' not in context.user_data:
            context.user_data['coin_amount'] = ''
        
        coin_amount = context.user_data['coin_amount']
        
        if query.data == "coin_delete":
            context.user_data['coin_amount'] = ''
            await query.edit_message_text(
                "🗑️ تعداد سکه پاک شد.\nلطفاً تعداد سکه مورد نظر را وارد کنید:",
                reply_markup=self.create_coin_keyboard()
            )
            return COIN_PURCHASE
        
        elif query.data == "coin_submit":
            if not coin_amount or int(coin_amount) <= 0:
                await query.edit_message_text(
                    "❌ لطفاً تعداد سکه معتبر وارد کنید!",
                    reply_markup=self.create_coin_keyboard(coin_amount)
                )
                return COIN_PURCHASE
            
            coin_count = int(coin_amount)
            total_price = coin_count * 200
            purchase_id = f"{user_id}_{int(time.time())}"
            
            add_pending_purchase(purchase_id, user_id, coin_count, total_price)
            
            purchase_text = f"""
💌 **خرید سکه NexoSelf** 💌

✅ درخواست خرید شما ثبت شد!

📊 **مشخصات خرید:**
• تعداد سکه: {coin_count}
• مبلغ قابل پرداخت: {total_price:,} تومن

💳 **شماره کارت برای واریز:**
`{self.card_number}`

📸 پس از واریز، عکس فیش را در پاسخ به این پیام ارسال کنید.

🆔 برای پیگیری با مالک تماس بگیرید: @amele55
            """
            await query.edit_message_text(purchase_text)
            context.user_data['coin_amount'] = ''
            return ConversationHandler.END
        
        elif query.data.startswith("coin_"):
            digit = query.data.split("_")[1]
            if digit.isdigit():
                context.user_data['coin_amount'] += digit
            updated_amount = context.user_data['coin_amount']
            
            try:
                amount_int = int(updated_amount) if updated_amount else 0
                price = amount_int * 200
                price_text = f"{price:,}" if price > 0 else "۰"
            except:
                price_text = "۰"
            
            await query.edit_message_text(
                f"💌 تعداد سکه: {updated_amount or '۰'}\n\n"
                f"💰 مبلغ قابل پرداخت: {price_text} تومن\n\n"
                f"⌨️ از کیبورد زیر برای ادامه استفاده کنید:",
                reply_markup=self.create_coin_keyboard(updated_amount)
            )
            return COIN_PURCHASE
        
        elif query.data == "display_coins":
            display = coin_amount if coin_amount else "۰"
            await query.answer(f"تعداد سکه فعلی: {display}")
            return COIN_PURCHASE
        
        return COIN_PURCHASE
    
    async def confirm_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "confirm_purchase":
            coin_amount = context.user_data.get('coin_amount', '0')
            coin_count = int(coin_amount) if coin_amount else 0
            total_price = coin_count * 200
            
            if coin_count <= 0:
                await query.edit_message_text(
                    "❌ تعداد سکه نامعتبر است!",
                    reply_markup=self.create_coin_keyboard()
                )
                return COIN_PURCHASE
            
            purchase_id = f"{user_id}_{int(time.time())}"
            add_pending_purchase(purchase_id, user_id, coin_count, total_price)
            
            final_purchase_text = f"""
💌 **خرید سکه NexoSelf** 💌

✅ درخواست خرید شما ثبت شد!

📊 **مشخصات خرید:**
• تعداد سکه: {coin_count}
• مبلغ قابل پرداخت: {total_price:,} تومن

💳 **شماره کارت برای واریز:**
`{self.card_number}`

📸 پس از واریز، عکس فیش را در پاسخ به این پیام ارسال کنید.

🆔 برای پیگیری با مالک تماس بگیرید: @amele55
            """
            await query.edit_message_text(final_purchase_text)
            context.user_data['coin_amount'] = ''
            return ConversationHandler.END
        
        elif query.data == "cancel_purchase":
            context.user_data['coin_amount'] = ''
            await query.edit_message_text(
                "❌ خرید لغو شد.\n\n"
                "💌•••خرید سکه•••💌\n\n"
                "💰 هر عدد سکه: 200 تومن\n"
                "‼️ تعداد سکه مورد نظر خود را وارد کنید",
                reply_markup=self.create_coin_keyboard()
            )
            return COIN_PURCHASE
    
    # ─── دریافت شماره و کد ──────────────────────────────────────────────────────
    async def get_phone_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_input = update.message.text
        user_id = update.message.from_user.id
        
        if user_input == "🔙 بازگشت به منوی اصلی":
            activation_text = (
                "💡 **فعال‌سازی سلف خود را از منوی زیر شروع کنید** 🔋\n\n"
                "🚀 **برای فعال‌سازی سلف، روی دکمه زیر کلیک کنید** ⚙️"
            )
            await update.message.reply_text(activation_text, reply_markup=self.create_activation_keyboard())
            return ACTIVATION_PANEL
        
        phone_number = user_input
        phone_number = ''.join(filter(str.isdigit, phone_number))
        
        if phone_number.startswith('98') and len(phone_number) == 11:
            phone_number = '+' + phone_number
        elif phone_number.startswith('09') and len(phone_number) == 11:
            phone_number = '+98' + phone_number[1:]
        elif len(phone_number) == 10 and phone_number.startswith('9'):
            phone_number = '+98' + phone_number
        
        if len(phone_number) < 10:
            await update.message.reply_text(
                "❌ شماره تلفن معتبر نیست!\n\n"
                "لطفاً شماره خود را به درستی وارد کنید:\n"
                "مثال: +989123456789 یا 09123456789\n\n"
                "یا برای بازگشت از دکمه زیر استفاده کنید:",
                reply_markup=self.create_phone_keyboard()
            )
            return GET_PHONE
        
        try:
            processing_msg = await update.message.reply_text("⏳ در حال ارسال کد تأیید...")
            result = await self.send_verification_code(phone_number, user_id)
            
            if result['success']:
                self.user_sessions[user_id] = {
                    'phone_number': phone_number,
                    'phone_code_hash': result['phone_code_hash'],
                    'client': result['client'],
                    'timestamp': time.time(),
                    'entered_code': ''
                }
                context.user_data['waiting_for_password'] = False
                code_message = (
                    "🔓 **کد تأیید خود را وارد کنید** 💫\n\n"
                    "از کیبورد زیر برای وارد کردن کد ۵ رقمی استفاده کنید 🧩"
                )
                await processing_msg.edit_text(code_message, reply_markup=self.create_code_keyboard())
                return GET_CODE
            else:
                await processing_msg.edit_text(
                    f"❌ خطا در ارسال کد تأیید:\n{result['error']}\n\n"
                    "لطفاً شماره دیگری وارد نمایید:",
                    reply_markup=self.create_phone_keyboard()
                )
                return GET_PHONE
        except Exception as e:
            logging.error(f"Error in get_phone_number: {e}")
            await update.message.reply_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کنید:", reply_markup=self.create_phone_keyboard())
            return GET_PHONE
    
    async def send_verification_code(self, phone_number: str, user_id: int):
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            result = await client.send_code_request(phone_number)
            return {
                'success': True,
                'phone_code_hash': result.phone_code_hash,
                'client': client,
                'message': 'کد تأیید با موفقیت ارسال شد'
            }
        except Exception as e:
            logging.error(f"Telethon error: {e}")
            error_message = str(e)
            if "FLOOD" in error_message:
                return {'success': False, 'error': 'تعداد درخواست‌ها زیاد است. لطفاً چند دقیقه صبر کنید.'}
            elif "PHONE_NUMBER_INVALID" in error_message:
                return {'success': False, 'error': 'شماره تلفن معتبر نیست.'}
            elif "PHONE_NUMBER_BANNED" in error_message:
                return {'success': False, 'error': 'شماره تلفن مسدود شده است.'}
            else:
                return {'success': False, 'error': f'خطا در ارسال کد: {error_message}'}
    
    async def verify_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ سشن شما منقضی شده است. لطفاً دوباره /start را ارسال کنید.")
            return ConversationHandler.END
        
        session_data = self.user_sessions[user_id]
        
        if query.data == "delete":
            session_data['entered_code'] = ''
            await query.edit_message_text("🗑️ کد وارد شده پاک شد.\nلطفاً کد را دوباره وارد کنید:", reply_markup=self.create_code_keyboard())
            return GET_CODE
        
        elif query.data == "submit":
            if len(session_data['entered_code']) != 5:
                await query.edit_message_text("❌ کد باید ۵ رقمی باشد! لطفاً کد کامل را وارد کنید.", reply_markup=self.create_code_keyboard(session_data['entered_code']))
                return GET_CODE
            return await self.check_verification_code(query, context, session_data['entered_code'])
        
        elif query.data in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            if len(session_data['entered_code']) < 5:
                session_data['entered_code'] += query.data
                if len(session_data['entered_code']) == 5:
                    await query.edit_message_text(f"✅ کد کامل شد: {session_data['entered_code']}\n📲 برای تأیید روی دکمه '✅ تایید' کلیک کنید.", reply_markup=self.create_code_keyboard(session_data['entered_code']))
                else:
                    await query.edit_message_text(f"🔢 کد فعلی: {session_data['entered_code']}••\n📝 {5 - len(session_data['entered_code'])} رقم باقی مانده", reply_markup=self.create_code_keyboard(session_data['entered_code']))
            return GET_CODE
        
        elif query.data == "display":
            await query.answer(f"کد فعلی: {session_data['entered_code'] or 'خالی'}")
            return GET_CODE
    
    async def check_verification_code(self, query, context: ContextTypes.DEFAULT_TYPE, code: str):
        user_id = query.from_user.id
        session_data = self.user_sessions[user_id]
        client = session_data['client']
        phone_number = session_data['phone_number']
        phone_code_hash = session_data['phone_code_hash']
        
        await query.edit_message_text("⏳ در حال بررسی کد و ورود به اکانت...")
        
        try:
            await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
            await query.edit_message_text("✅ کد تأیید صحیح است! در حال فعال‌سازی NexoSelf...")
            session_string = client.session.save()
            success = await self.activate_selfbot(session_string, user_id, phone_number)
            
            if success:
                current_coins = get_user_coins(user_id)
                update_user_coins(user_id, current_coins - 5)
                await query.message.reply_text(
                    "🎉 **NexoSelf با موفقیت فعال شد!**\n\n"
                    "✅ اکانت شما با موفقیت تأیید شد\n"
                    "✅ NexoSelf به صورت خودکار اجرا شد\n"
                    "💰 5 سکه از حساب شما کسر شد\n"
                    "🔮 اکنون می‌توانید از دستورات NexoSelf استفاده کنید.",
                    reply_markup=self.create_main_menu()
                )
            else:
                await query.message.reply_text("⚠️ **ورود موفق اما خطا در اجرای NexoSelf**\n\n✅ اکانت شما تأیید شد\n❌ خطا در اجرای خودکار NexoSelf")
            
            if user_id in self.user_sessions:
                await self.user_sessions[user_id]['client'].disconnect()
                del self.user_sessions[user_id]
            return ConversationHandler.END
            
        except SessionPasswordNeededError:
            await query.edit_message_text(
                "🔐 حساب شما دارای رمز دومرحله‌ای است.\n"
                "لطفاً رمز عبور خود را به صورت **متن** در همین چت ارسال کنید.\n"
                "اگر رمز ندارید، روی دکمه '⏭️ رد شدن' کلیک کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ رد شدن (بدون رمز)", callback_data="skip_password")]])
            )
            context.user_data['waiting_for_password'] = True
            return GET_CODE
            
        except Exception as sign_in_error:
            error_msg = str(sign_in_error)
            if "PHONE_CODE_EXPIRED" in error_msg:
                await query.edit_message_text("❌ کد تأیید منقضی شده است!\nلطفاً دوباره /start را ارسال کنید.")
            elif "CODE_INVALID" in error_msg:
                await query.edit_message_text("❌ کد تأیید نامعتبر است!\nلطفاً کد صحیح را وارد کنید:", reply_markup=self.create_code_keyboard())
                session_data['entered_code'] = ''
                return GET_CODE
            else:
                await query.edit_message_text(f"❌ خطا در ورود: {error_msg}\nلطفاً دوباره /start را ارسال کنید.")
            
            if user_id in self.user_sessions:
                await self.user_sessions[user_id]['client'].disconnect()
                del self.user_sessions[user_id]
            return ConversationHandler.END
    
    async def handle_password_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        password = update.message.text.strip()
        
        if not context.user_data.get('waiting_for_password', False):
            return
        
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ سشن شما منقضی شده است. لطفاً دوباره /start را ارسال کنید.")
            return
        
        session_data = self.user_sessions[user_id]
        client = session_data['client']
        phone_number = session_data['phone_number']
        
        await update.message.reply_text("⏳ در حال بررسی رمز و ورود به اکانت...")
        
        try:
            await client.sign_in(password=password)
            await update.message.reply_text("✅ رمز دو مرحله‌ای صحیح است! در حال فعال‌سازی NexoSelf...")
            session_string = client.session.save()
            success = await self.activate_selfbot(session_string, user_id, phone_number)
            
            if success:
                current_coins = get_user_coins(user_id)
                update_user_coins(user_id, current_coins - 5)
                await update.message.reply_text(
                    "🎉 **NexoSelf با موفقیت فعال شد!**\n\n"
                    "✅ اکانت شما با موفقیت تأیید شد\n"
                    "✅ NexoSelf به صورت خودکار اجرا شد\n"
                    "💰 5 سکه از حساب شما کسر شد\n"
                    "🔮 اکنون می‌توانید از دستورات NexoSelf استفاده کنید.",
                    reply_markup=self.create_main_menu()
                )
            else:
                await update.message.reply_text("⚠️ **ورود موفق اما خطا در اجرای NexoSelf**")
            
            context.user_data['waiting_for_password'] = False
            if user_id in self.user_sessions:
                await self.user_sessions[user_id]['client'].disconnect()
                del self.user_sessions[user_id]
            return ConversationHandler.END
            
        except Exception as e:
            error_msg = str(e)
            if "PASSWORD_HASH_INVALID" in error_msg or "PASSWORD" in error_msg:
                await update.message.reply_text(
                    "❌ رمز دو مرحله‌ای اشتباه است!\nلطفاً رمز صحیح را وارد کنید.\nاگر رمز ندارید، روی دکمه '⏭️ رد شدن' کلیک کنید.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ رد شدن (بدون رمز)", callback_data="skip_password")]])
                )
                return GET_CODE
            else:
                await update.message.reply_text(f"❌ خطا در ورود با رمز دو مرحله‌ای: {error_msg}\nلطفاً دوباره تلاش کنید.")
                return GET_CODE
    
    async def skip_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if user_id not in self.user_sessions:
            await query.edit_message_text("❌ سشن شما منقضی شده است. لطفاً دوباره /start را ارسال کنید.")
            return ConversationHandler.END
        
        session_data = self.user_sessions[user_id]
        client = session_data['client']
        phone_number = session_data['phone_number']
        
        await query.edit_message_text("⏳ در حال ورود بدون رمز دو مرحله‌ای...")
        
        try:
            await client.sign_in(password=None)
            await query.edit_message_text("✅ ورود بدون رمز دو مرحله‌ای موفقیت‌آمیز بود!")
            session_string = client.session.save()
            success = await self.activate_selfbot(session_string, user_id, phone_number)
            
            if success:
                current_coins = get_user_coins(user_id)
                update_user_coins(user_id, current_coins - 5)
                await query.message.reply_text(
                    "🎉 **NexoSelf با موفقیت فعال شد!**\n\n"
                    "✅ اکانت شما با موفقیت تأیید شد\n"
                    "✅ NexoSelf به صورت خودکار اجرا شد\n"
                    "💰 5 سکه از حساب شما کسر شد\n"
                    "🔮 اکنون می‌توانید از دستورات NexoSelf استفاده کنید.",
                    reply_markup=self.create_main_menu()
                )
            else:
                await query.message.reply_text("⚠️ **ورود موفق اما خطا در اجرای NexoSelf**")
            
            context.user_data['waiting_for_password'] = False
            if user_id in self.user_sessions:
                await self.user_sessions[user_id]['client'].disconnect()
                del self.user_sessions[user_id]
            return ConversationHandler.END
            
        except Exception as e:
            await query.edit_message_text(f"❌ خطا در ورود بدون رمز: {str(e)}\nلطفاً دوباره تلاش کنید یا از گزینه رمز استفاده نمایید.")
            return GET_CODE
    
    # ─── فعال‌سازی سلف ──────────────────────────────────────────────────────────
    async def activate_selfbot(self, session_string: str, user_id: int, phone_number: str):
        try:
            temp_file = f"session_{user_id}.txt"
            with open(temp_file, 'w') as f:
                f.write(session_string)
            
            subprocess.Popen([
                sys.executable, 'self.py',
                '--session', temp_file,
                '--api-id', str(API_ID),
                '--api-hash', API_HASH
            ])
            
            return True
        except Exception as e:
            logging.error(f"Error activating selfbot: {e}")
            return False
    
    # ─── هندلر فیش پرداخت ──────────────────────────────────────────────────────
    async def handle_receipt_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        photo = update.message.photo[-1]
        
        pending = get_all_pending_purchases()
        purchase = None
        for p in pending:
            if p['user_id'] == user_id:
                purchase = p
                break
        
        if not purchase:
            await update.message.reply_text(
                "❌ هیچ درخواست خرید در انتظاری برای شما یافت نشد!\n"
                "لطفاً ابتدا از گزینه خرید سکه در منو استفاده کنید."
            )
            return
        
        user = update.message.from_user
        username = user.username or "ندارد"
        first_name = user.first_name or "ندارد"
        
        admin_message = f"""
🆕 **فیش پرداخت جدید!**

👤 **اطلاعات کاربر:**
• نام: {first_name}
• یوزرنیم: @{username}
• آیدی: `{user_id}`

📊 **مشخصات خرید:**
• تعداد سکه: {purchase['amount']}
• مبلغ: {purchase['price']:,} تومن
• زمان: {purchase['timestamp']}

📸 **فیش پرداخت:** (دریافت شد)

✅ لطفاً با استفاده از دکمه‌های زیر اقدام کنید:
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ تایید خرید", callback_data=f"approve_{purchase['id']}"),
                InlineKeyboardButton("❌ رد خرید", callback_data=f"reject_{purchase['id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.application.bot.send_photo(
            chat_id=self.admin_id,
            photo=photo.file_id,
            caption=admin_message,
            reply_markup=reply_markup
        )
        
        await update.message.reply_text(
            "✅ **فیش پرداخت شما دریافت شد!**\n\n"
            "🔄 در انتظار تایید مالک...\n"
            "⏱️ لطفاً صبور باشید، به زودی تایید می‌شود."
        )
    
    # ─── هندلر پیام‌های متنی ───────────────────────────────────────────────────
    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if text in ['راهنما', 'help']:
            await self.help_command(update, context)
        elif text in ['وضعیت', 'status']:
            await self.status_callback(update, context)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id in self.user_sessions:
            await self.user_sessions[user_id]['client'].disconnect()
            del self.user_sessions[user_id]
        context.user_data['waiting_for_password'] = False
        await update.message.reply_text("❌ عملیات لغو شد.\n\nبرای شروع مجدد /start را ارسال کنید.")
        return ConversationHandler.END
    
    # ─── اجرا ───────────────────────────────────────────────────────────────────
    def run(self):
        print("🤖 ربات NexoSelf در حال اجراست...")
        print("👑 مالک ربات:", self.admin_id)
        print("💳 شماره کارت:", self.card_number)
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

# ─── نقطه ورود ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ایجاد پوشه database
    if not os.path.exists("database"):
        os.makedirs("database")
    
    # گرفتن توکن از متغیر محیطی یا مقدار پیش‌فرض
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8731724435:AAFYu8ARPZ0Ov5rEG2bs3RziRWB0P9_OIDA")
    API_ID = int(os.environ.get("API_ID", 34434623))
    API_HASH = os.environ.get("API_HASH", "d82c5dd13602eedc3041e9f549bcd813")
    
    if not BOT_TOKEN:
        print("❌ خطا: متغیر محیطی BOT_TOKEN تنظیم نشده است!")
        print("لطفاً در Render Dashboard متغیر BOT_TOKEN را اضافه کنید.")
        sys.exit(1)
    
    print("🚀 NexoSelf در حال راه‌اندازی...")
    print(f"👑 مالک: {OWNER_ID}")
    
    try:
        bot = NexoBot()
        print("✅ ربات با موفقیت راه‌اندازی شد!")
        bot.run()
    except Exception as e:
        print(f"❌ خطا در اجرای ربات: {e}")
        sys.exit(1)
