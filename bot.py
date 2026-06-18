import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import UserNotParticipantError, SessionPasswordNeededError
import asyncio
import time
import secrets
import os
import subprocess
import sys
import sqlite3
import random
from datetime import datetime

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# حالت‌های مکالمه
ACTIVATION_PANEL, GET_PHONE, GET_CODE, COIN_PURCHASE, CONFIRM_PURCHASE, ADMIN_PANEL, MANAGE_TOKENS, SET_CARD_NUMBER, SET_ADMIN_ID = range(9)

class TelegramAuthBot:
    def __init__(self, token, api_id, api_hash):
        self.token = token
        self.api_id = api_id
        self.api_hash = api_hash
        self.application = Application.builder().token(token).build()
        self.user_sessions = {}
        self.user_coins = {}
        self.active_selfbots = {}
        self.invite_links = {}
        self.user_referrals = {}
        self.user_first_start = {}
        self.active_bets = {}
        self.group_bets = {}
        self.channel_username = "Ch_SelfNexo"
        self.card_number = "6037000000000000"
        self.admin_id = int(os.environ.get("OWNER_ID", 8296865861))
        self.pending_purchases = {}
        
        self.init_users_db()
        self.user_coins[self.admin_id] = 999999999
        self.setup_handlers()
    
    def init_users_db(self):
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            coins INTEGER DEFAULT 0,
            invited_by INTEGER,
            join_date TEXT,
            is_active INTEGER DEFAULT 1
        )''')
        conn.commit()
        conn.close()
    
    def setup_handlers(self):
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.main_menu_callback, pattern='^main_menu$'))
        self.application.add_handler(CallbackQueryHandler(self.help_callback, pattern='^help$'))
        self.application.add_handler(CallbackQueryHandler(self.status_callback, pattern='^status$'))
        self.application.add_handler(CallbackQueryHandler(self.heart_callback, pattern='^heart$'))
        self.application.add_handler(CallbackQueryHandler(self.fun_callback, pattern='^fun$'))
        self.application.add_handler(CallbackQueryHandler(self.tools_callback, pattern='^tools$'))
        self.application.add_handler(CallbackQueryHandler(self.settings_callback, pattern='^settings$'))
        self.application.add_handler(CallbackQueryHandler(self.secretary_callback, pattern='^secretary$'))
        self.application.add_handler(CallbackQueryHandler(self.groups_callback, pattern='^groups$'))
        self.application.add_handler(CallbackQueryHandler(self.forward_callback, pattern='^forward$'))
        self.application.add_handler(CallbackQueryHandler(self.listfonts_callback, pattern='^listfonts$'))
        self.application.add_handler(CallbackQueryHandler(self.sessions_callback, pattern='^sessions$'))
        self.application.add_handler(CallbackQueryHandler(self.listcrash_callback, pattern='^listcrash$'))
        self.application.add_handler(CallbackQueryHandler(self.listenemy_callback, pattern='^listenemy$'))
        self.application.add_handler(CallbackQueryHandler(self.tagall_callback, pattern='^tagall$'))
        self.application.add_handler(CallbackQueryHandler(self.tagadmins_callback, pattern='^tagadmins$'))
        self.application.add_handler(CallbackQueryHandler(self.info_callback, pattern='^info$'))
        self.application.add_handler(CallbackQueryHandler(self.buy_callback, pattern='^buy$'))
        self.application.add_handler(CallbackQueryHandler(self.balance_callback, pattern='^balance$'))
        self.application.add_handler(CallbackQueryHandler(self.transfer_callback, pattern='^transfer$'))
        self.application.add_handler(CallbackQueryHandler(self.link_callback, pattern='^link$'))
        self.application.add_handler(CallbackQueryHandler(self.bet_callback, pattern='^bet$'))
        self.application.add_handler(CallbackQueryHandler(self.gbet_callback, pattern='^gbet$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_callback, pattern='^admin$'))
        
        # Admin sub-menu callbacks
        self.application.add_handler(CallbackQueryHandler(self.admin_manage_tokens, pattern='^admin_manage_tokens$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_set_card, pattern='^admin_set_card$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_set_admin, pattern='^admin_set_admin$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_view_stats, pattern='^admin_view_stats$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_view_pending, pattern='^admin_view_pending$'))
        self.application.add_handler(CallbackQueryHandler(self.admin_back, pattern='^admin_back$'))
        
        # Purchase handlers
        self.application.add_handler(CallbackQueryHandler(self.approve_purchase, pattern='^approve_purchase_'))
        self.application.add_handler(CallbackQueryHandler(self.reject_purchase, pattern='^reject_purchase_'))
        self.application.add_handler(CallbackQueryHandler(self.confirm_purchase, pattern='^(confirm_purchase|cancel_purchase)$'))
        self.application.add_handler(CallbackQueryHandler(self.skip_password, pattern='^skip_password$'))
        self.application.add_handler(CallbackQueryHandler(self.join_bet, pattern='^join_bet_'))
        self.application.add_handler(CallbackQueryHandler(self.join_group_bet, pattern='^join_gbet_'))
        self.application.add_handler(CallbackQueryHandler(self.cancel_group_bet, pattern='^cancel_gbet_'))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.PHOTO & filters.REPLY, self.handle_receipt_photo))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_messages))
        
        # Conversation Handler
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
    
    def is_owner(self, user_id: int) -> bool:
        return user_id == self.admin_id
    
    # ============ Main Menu Keyboard ============
    def create_main_menu_keyboard(self):
        keyboard = [
            [InlineKeyboardButton("📖 راهنما", callback_data="help")],
            [InlineKeyboardButton("📊 وضعیت سیستم", callback_data="status")],
            [InlineKeyboardButton("💖 قلب", callback_data="heart")],
            [InlineKeyboardButton("🎮 سرگرمی", callback_data="fun")],
            [InlineKeyboardButton("🛠 ابزارها", callback_data="tools")],
            [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
            [InlineKeyboardButton("🤖 منشی هوشمند", callback_data="secretary")],
            [InlineKeyboardButton("🏢 مدیریت گروه", callback_data="groups")],
            [InlineKeyboardButton("🔄 فوروارد خودکار", callback_data="forward")],
            [InlineKeyboardButton("🎨 لیست فونت‌ها", callback_data="listfonts")],
            [InlineKeyboardButton("🔐 نشست‌های فعال", callback_data="sessions")],
            [InlineKeyboardButton("💔 لیست کراش", callback_data="listcrash")],
            [InlineKeyboardButton("😈 لیست دشمنان", callback_data="listenemy")],
            [InlineKeyboardButton("👥 تگ همه", callback_data="tagall")],
            [InlineKeyboardButton("👮 تگ ادمین‌ها", callback_data="tagadmins")],
            [InlineKeyboardButton("ℹ️ اطلاعات کاربر", callback_data="info")],
            [InlineKeyboardButton("💰 خرید سکه", callback_data="buy")],
            [InlineKeyboardButton("💳 موجودی", callback_data="balance")],
            [InlineKeyboardButton("📤 انتقال سکه", callback_data="transfer")],
            [InlineKeyboardButton("🎫 لینک دعوت", callback_data="link")],
            [InlineKeyboardButton("🎰 شرط‌بندی", callback_data="bet")],
            [InlineKeyboardButton("🎰 شرط گروهی", callback_data="gbet")],
            [InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin")],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_admin_menu_keyboard(self):
        keyboard = [
            [InlineKeyboardButton("💰 مدیریت توکن‌ها", callback_data="admin_manage_tokens")],
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
    
    def create_purchase_confirmation_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("✅ تأیید خرید", callback_data="confirm_purchase"),
                InlineKeyboardButton("❌ انصراف", callback_data="cancel_purchase")
            ],
            [
                InlineKeyboardButton("📸 ارسال فیش", callback_data="send_receipt")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_bet_keyboard(self, bet_id):
        keyboard = [
            [
                InlineKeyboardButton("🎰 پیوستن به شرط", callback_data=f"join_bet_{bet_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def create_group_bet_keyboard(self, bet_id):
        keyboard = [
            [
                InlineKeyboardButton("🎰 پیوستن به شرط", callback_data=f"join_gbet_{bet_id}"),
                InlineKeyboardButton("❌ لغو شرط", callback_data=f"cancel_gbet_{bet_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    # ============ Main Menu Callbacks ============
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "📋 **منوی اصلی NexoSelf**\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=self.create_main_menu_keyboard()
        )
    
    async def help_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        help_text = """
┌─────────────────────
│  📖 **راهنمای کامل NexoSelf**  
└─────────────────────

🎯 **دستورات اصلی:**
• help - نمایش این راهنما
• status - وضعیت سیستم
• heart - انیمیشن قلب
• fun - منوی بازی‌ها
• tools - منوی ابزارها

👥 **مدیریت کاربران:**
• listcrash - لیست کراش
• listenemy - لیست دشمنان
• info - اطلاعات کاربر

🏢 **مدیریت گروه:**
• tagall - تگ همه اعضا
• tagadmins - تگ ادمین‌ها
• groups - منوی مدیریت گروه

🎨 **ظاهر:**
• listfonts - لیست فونت‌ها
• .font 1-10 - تغییر فونت

⚙️ **تنظیمات:**
• settings - منوی تنظیمات
• .online on/off - حالت آنلاین
• .typing on/off - تایپینگ
• .timename on/off - زمان در نام
• .timebio on/off - زمان در بیو

🤖 **منشی هوشمند:**
• secretary - منوی منشی
• .secretary on/off - فعال‌سازی
• .addreply الگو|پاسخ - افزودن پاسخ

🔄 **فوروارد خودکار:**
• forward - منوی فوروارد
• .autoforward on/off - فعال‌سازی

💰 **اقتصادی:**
• buy - خرید سکه
• balance - موجودی
• transfer - انتقال سکه

🔮 **قدرت گرفته از:** @Ch_SelfNexo
        """
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def status_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        user_coins = self.user_coins.get(user_id, 0)
        
        status_text = f"""
┌─────────────────────
│  📊 **وضعیت سیستم NexoSelf**  
└─────────────────────

👤 **اطلاعات کاربر:**
• آیدی: `{user_id}`
• سکه: {user_coins}
• وضعیت: {'فعال' if user_id in self.active_selfbots else 'غیرفعال'}

🖥 **وضعیت ربات:**
• وضعیت: ✅ آنلاین
• نسخه: 2.0

💰 **اقتصاد:**
• قیمت هر سکه: ۲۰۰ تومن
• ارزش سکه‌ها: {user_coins * 200:,} تومن

🔮 **قدرت گرفته از:** @Ch_SelfNexo
        """
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def heart_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("💫 شروع انیمیشن قلب...")
        
        animations = ["💖", "❤️", "🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍"]
        for x in range(3):
            for i in range(1, 11):
                heart = animations[i % len(animations)]
                txt = f"✨ {x+1} {heart * i} | {10 * i}%"
                await query.edit_message_text(txt)
                await asyncio.sleep(0.2)
        
        await query.edit_message_text(
            "💖 **انیمیشن قلب کامل شد!** ✨",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def fun_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        fun_text = """
┌─────────────────────
│  🎮 **بازی‌ها و سرگرمی**  
└─────────────────────

🎲 **بازی‌ها:**
• `.dice 1-6` - پرتاب تاس
• `.football` - فوتبال ⚽
• `.basket` - بسکتبال 🏀
• `.dart` - دارت 🎯
• `.slot` - اسلات 🎰

📝 **نحوه استفاده:**
دستورات را در پیوی خود ارسال کنید
        """
        await query.edit_message_text(fun_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def tools_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        tools_text = """
┌─────────────────────
│  🛠 **ابزارهای کاربردی**  
└─────────────────────

📁 **مدیریت فایل:**
• `.save` - ذخیره فایل
• `.download` - دانلود فایل
• `.rename نام` - تغییر نام فایل

🔍 **جستجو:**
• `.search متن` - جستجوی پیام‌ها
• `.find متن` - پیدا کردن متن
• `.history عدد` - تاریخچه پیام‌ها

🧹 **پاکسازی:**
• `.clean تعداد` - پاک کردن پیام‌ها
        """
        await query.edit_message_text(tools_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        settings_text = """
┌─────────────────────
│  ⚙️ **تنظیمات NexoSelf**  
└─────────────────────

🌐 **حالت آنلاین:**
• `.online on` - همیشه آنلاین
• `.online off` - حالت عادی

⌨️ **اکشن تایپینگ:**
• `.typing on` - فعال‌سازی تایپینگ
• `.typing off` - غیرفعال‌سازی
• `.typing 10` - تنظیم مدت زمان

🤖 **قابلیت‌های هوشمند:**
• `.secretary on/off` - منشی هوشمند
• `.autoreply on/off` - پاسخ خودکار
• `.autoforward on/off` - فوروارد خودکار

🎨 **ظاهر:**
• `.timename on/off` - زمان در نام
• `.timebio on/off` - زمان در بیو
• `.font 1-10` - تغییر فونت

👥 **مدیریت کاربران:**
• `.addcrash ID` - افزودن به کراش
• `.delcrash ID` - حذف از کراش
• `.addenemy ID` - افزودن به دشمنان
• `.delenemy ID` - حذف از دشمنان
        """
        await query.edit_message_text(settings_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def secretary_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        secretary_text = """
┌─────────────────────
│  🤖 **منشی هوشمند NexoSelf**  
└─────────────────────

⚙️ **تنظیمات اصلی:**
• `.secretary on` - فعال‌سازی منشی
• `.secretary off` - غیرفعال‌سازی
• `.autoreply on` - پاسخ خودکار
• `.autoreply off` - غیرفعال‌سازی

📝 **مدیریت پاسخ‌ها:**
• `.addreply الگو|پاسخ` - افزودن پاسخ
• `.listreplies` - لیست پاسخ‌ها
• `.delreply شماره` - حذف پاسخ

💡 **پاسخ‌های پیش‌فرض:**
• سلام/hello → خوش‌آمدگویی
• چطوری/حالتون → احوالپرسی
• ساعت/time → نمایش ساعت
• تاریخ/date → نمایش تاریخ
        """
        await query.edit_message_text(secretary_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def groups_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        groups_text = """
┌─────────────────────
│  🏢 **مدیریت گروه**  
└─────────────────────

👥 **مدیریت اعضا:**
• `.promote @user` - ارتقا به ادمین
• `.demote @user` - کاهش از ادمین
• `.ban @user` - بن کاربر
• `.unban @user` - رفع بن
• `.mute @user` - میوت کاربر
• `.unmute @user` - رفع میوت

📌 **دستورات سریع:**
• `tagall` - تگ همه اعضا
• `tagadmins` - تگ ادمین‌ها
        """
        await query.edit_message_text(groups_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def forward_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        forward_text = """
┌─────────────────────
│  🔄 **فوروارد خودکار**  
└─────────────────────

📡 **قابلیت‌ها:**
• فوروارد خودکار پیام‌ها
• پشتیبانی از چندین کانال
• فوروارد لحظه‌ای

⚙️ **تنظیمات:**
• `.autoforward on` - فعال‌سازی
• `.autoforward off` - غیرفعال‌سازی
        """
        await query.edit_message_text(forward_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def listfonts_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        fonts_list = "┌─────────────────────\n│  🎨 **لیست فونت‌ها**  \n└─────────────────────\n\n"
        fonts = [
            "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵", "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
            "₀₁₂₃₄₅₆₇₈₉", "0123456789", "０１２３４５６７８９",
            "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗", "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡",
            "🄌➀➁➂➃➄➅➆➇➈", "⓪①②③④⑤⑥⑦⑧⑨"
        ]
        for i, font in enumerate(fonts, 1):
            sample = "۱۲:۳۴"
            try:
                converted = sample.translate(str.maketrans("۱۲۳۴", font[:4]))
                fonts_list += f"**{i}.** `{converted}` - فونت {i}\n"
            except:
                fonts_list += f"**{i}.** `{sample}` - فونت {i}\n"
        fonts_list += "\n📝 **نحوه استفاده:** `.font شماره`\n**مثال:** `.font 3`"
        await query.edit_message_text(fonts_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def sessions_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        sessions_text = """
┌─────────────────────
│  🔐 **نشست‌های فعال**  
└─────────────────────

📱 **دستگاه‌های متصل:**
• برای مشاهده نشست‌های فعال از ربات سلف استفاده کنید
• دستور: `sessions` در پیوی سلف

💡 **نکته:**
برای مشاهده نشست‌ها باید سلف فعال باشد
        """
        await query.edit_message_text(sessions_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def listcrash_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "💖 **لیست کراش:**\n\n• لیست کراش شما خالی است.\nبرای افزودن از `.addcrash ID` استفاده کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def listenemy_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "😈 **لیست دشمنان:**\n\n• لیست دشمنان شما خالی است.\nبرای افزودن از `.addenemy ID` استفاده کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def tagall_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "👥 **تگ همه اعضا:**\n\n⚠️ این دستور فقط در گروه قابل استفاده است.\nلطفاً در گروه مورد نظر دستور `tagall` را ارسال کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def tagadmins_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "👮 **تگ ادمین‌ها:**\n\n⚠️ این دستور فقط در گروه قابل استفاده است.\nلطفاً در گروه مورد نظر دستور `tagadmins` را ارسال کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def info_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "ℹ️ **اطلاعات کاربر:**\n\n⚠️ لطفاً روی پیام کاربر مورد نظر ریپلای کنید و سپس این گزینه را انتخاب کنید.\n\nیا دستور `/info` را با ریپلای ارسال کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def buy_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        buy_text = f"""
💌 **خرید سکه (توکن) NexoSelf** 💌

💰 هر عدد سکه: ۲۰۰ تومن

📝 برای خرید، از دستور زیر استفاده کنید:
`/buy تعداد`

💳 شماره کارت برای واریز:
`{self.card_number}`

🆔 آیدی مالک برای پیگیری:
@amele55

📸 پس از واریز، عکس فیش را در پاسخ به پیام خرید ارسال کنید.
        """
        await query.edit_message_text(buy_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def balance_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        user_coins = self.user_coins.get(user_id, 0)
        total_value = user_coins * 200
        current_time = datetime.now().strftime("%H:%M:%S")
        
        balance_text = f"""
🥃 **موجودی شما**

💰 موجودی: {user_coins} سکه
💎 ارزش ریالی: {total_value:,} تومن
🕐 زمان: {current_time}
        """
        await query.edit_message_text(balance_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def transfer_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "📤 **انتقال سکه:**\n\n⚠️ لطفاً روی پیام کاربر مورد نظر ریپلای کنید و سپس از دستور زیر استفاده کنید:\n`/transfer تعداد`\n\nمثال: `/transfer 10`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        username = query.from_user.username or f"user_{user_id}"
        
        invite_code = secrets.token_urlsafe(8)
        self.invite_links[invite_code] = user_id
        invite_link = f"https://t.me/{context.bot.username}?start={invite_code}"
        referrals_count = len(self.user_referrals.get(user_id, []))
        
        invite_text = f"""
🎫 **لینک دعوت شما**

🔗 لینک: `{invite_link}`

💎 **مزایای دعوت:**
• به ازای هر دعوت: **7 سکه** پاداش
• دعوت شده: **5 سکه** هدیه اولیه
• بدون محدودیت تعداد دعوت

📊 آمار دعوت‌های شما: {referrals_count} نفر
💰 سکه‌های کسب شده: {referrals_count * 7} سکه
        """
        await query.edit_message_text(invite_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]))
    
    async def bet_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "🎰 **شرط‌بندی:**\n\nلطفاً از دستور زیر استفاده کنید:\n`/bet تعداد`\n\nمثال: `/bet 10`\n\n⚠️ برای شرط‌بندی حداقل ۱۰ سکه نیاز است.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def gbet_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "🎰 **شرط‌بندی گروهی:**\n\nلطفاً از دستور زیر استفاده کنید:\n`/gbet تعداد`\n\nمثال: `/gbet 10`\n\n⚠️ این دستور فقط در گروه قابل استفاده است.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
        )
    
    async def admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text(
                "❌ شما دسترسی به پنل مدیریت را ندارید!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]])
            )
            return
        
        await query.edit_message_text(
            "👑 **پنل مدیریت NexoSelf**\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=self.create_admin_menu_keyboard()
        )
    
    # ============ Admin Menu Callbacks ============
    async def admin_manage_tokens(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "💰 **مدیریت توکن‌ها**\n\n"
            "برای افزودن توکن به کاربر از دستور زیر استفاده کنید:\n"
            "`/give_token @username تعداد`\n\n"
            "مثال: `/give_token @user123 10`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_set_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            f"💳 **تنظیم شماره کارت**\n\n"
            f"شماره کارت فعلی:\n`{self.card_number}`\n\n"
            f"برای تغییر، از دستور زیر استفاده کنید:\n"
            f"`/setcard شماره_کارت`\n\n"
            f"مثال: `/setcard 6037999999999999`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_set_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
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
        total_users = len(self.user_coins)
        total_coins = sum(self.user_coins.values())
        total_pending = len(self.pending_purchases)
        
        stats_text = f"""
📊 **آمار کاربران NexoSelf**

👥 تعداد کاربران: {total_users}
💰 مجموع سکه‌ها: {total_coins}
📋 خریدهای در انتظار: {total_pending}
        """
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
        )
    
    async def admin_view_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if not self.pending_purchases:
            await query.edit_message_text(
                "📋 **هیچ خریدی در انتظار تایید نیست!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin")]])
            )
            return
        
        pending_text = "📋 **خریدهای در انتظار تایید:**\n\n"
        for pid, purchase in self.pending_purchases.items():
            pending_text += f"""
🆔 کاربر: `{purchase['user_id']}`
💰 تعداد: {purchase['amount']} سکه
💵 مبلغ: {purchase['price']:,} تومن
⏰ زمان: {purchase['timestamp']}
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
            reply_markup=self.create_admin_menu_keyboard()
        )
    
    # ============ Purchase Handlers ============
    async def approve_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        purchase_id = query.data.replace('approve_purchase_', '')
        if purchase_id in self.pending_purchases:
            purchase = self.pending_purchases[purchase_id]
            user_id_purchase = purchase['user_id']
            amount = purchase['amount']
            
            if user_id_purchase not in self.user_coins:
                self.user_coins[user_id_purchase] = 0
            self.user_coins[user_id_purchase] += amount
            purchase['status'] = 'approved'
            
            try:
                await self.application.bot.send_message(
                    chat_id=user_id_purchase,
                    text=f"""
✅ **خرید شما تایید شد!**

🎉 {amount} سکه به حساب شما اضافه شد.
💰 موجودی جدید: {self.user_coins[user_id_purchase]} سکه

🙏 از اعتماد شما سپاسگزاریم!
                    """
                )
            except:
                pass
            
            await query.edit_message_caption(
                caption=f"""
✅ **خرید تایید شد!**

👤 کاربر: `{user_id_purchase}`
💰 تعداد سکه: {amount}
💎 موجودی جدید: {self.user_coins[user_id_purchase]} سکه

⏰ تایید شده در: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            )
            del self.pending_purchases[purchase_id]
            await query.edit_message_reply_markup(reply_markup=None)
    
    async def reject_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not self.is_owner(user_id):
            await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید!")
            return
        
        purchase_id = query.data.replace('reject_purchase_', '')
        if purchase_id in self.pending_purchases:
            purchase = self.pending_purchases[purchase_id]
            user_id_purchase = purchase['user_id']
            amount = purchase['amount']
            
            purchase['status'] = 'rejected'
            
            try:
                await self.application.bot.send_message(
                    chat_id=user_id_purchase,
                    text=f"""
❌ **خرید شما رد شد!**

متأسفانه درخواست خرید {amount} سکه شما تایید نشد.

📌 برای بررسی بیشتر با مالک تماس بگیرید:
🆔 @amele55
                    """
                )
            except:
                pass
            
            await query.edit_message_caption(
                caption=f"""
❌ **خرید رد شد!**

👤 کاربر: `{user_id_purchase}`
💰 تعداد سکه: {amount}

⏰ رد شده در: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            )
            del self.pending_purchases[purchase_id]
            await query.edit_message_reply_markup(reply_markup=None)
    
    # ============ Start and Activation ============
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        
        if self.is_owner(user_id):
            self.user_coins[user_id] = 999999999
        
        if context.args and len(context.args) > 0:
            invite_code = context.args[0]
            if invite_code in self.invite_links:
                referrer_id = self.invite_links[invite_code]
                if referrer_id not in self.user_coins:
                    self.user_coins[referrer_id] = 0
                self.user_coins[referrer_id] += 7
                if referrer_id not in self.user_referrals:
                    self.user_referrals[referrer_id] = []
                self.user_referrals[referrer_id].append(user_id)
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 کاربر جدیدی با لینک دعوت شما وارد ربات شد!\n💰 7 سکه به عنوان پاداش دریافت کردید!"
                    )
                except:
                    pass
        
        if user_id not in self.user_first_start and not self.is_owner(user_id):
            self.user_first_start[user_id] = True
            if user_id not in self.user_coins:
                self.user_coins[user_id] = 5
                await update.message.reply_text(
                    "🎁 **هدیه ویژه!**\n\n"
                    "به شما 5 سکه رایگان هدیه داده شد!\n"
                    "💰 موجودی فعلی: 5 سکه"
                )
        
        activation_text = (
            "💡 **به NexoSelf خوش آمدید!** 🔋\n\n"
            "🚀 لطفاً از منوی زیر گزینه مورد نظر خود را انتخاب کنید:\n\n"
            "👑 **مالک:** @amele55"
        )
        
        await update.message.reply_text(
            text=activation_text,
            reply_markup=self.create_main_menu_keyboard(),
            parse_mode='Markdown'
        )
        return ACTIVATION_PANEL
    
    async def activation_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "activate":
            user_coins = self.user_coins.get(user_id, 0)
            if user_coins < 5:
                await query.edit_message_text(
                    f"❌ موجودی سکه شما کافی نیست!\n\n"
                    f"💰 موجودی فعلی: {user_coins} سکه\n"
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
            coin_text = (
                "💌•••خرید سکه(توکن)•••💌\n\n"
                "💰 هر عدد سکه: 200 تومن\n"
                "‼️ تعداد سکه مورد نظر خود را وارد کنید\n\n"
                "⌨️ از کیبورد زیر برای وارد کردن تعداد سکه استفاده کنید:"
            )
            await query.edit_message_text(coin_text, reply_markup=self.create_coin_keyboard())
            return COIN_PURCHASE
        
        elif query.data == "stats":
            await self.show_stats_panel(query)
            return ACTIVATION_PANEL
        
        elif query.data == "invite":
            await self.show_invite_panel(query, context)
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
    
    async def show_stats_panel(self, query):
        user_id = query.from_user.id
        user_coins = self.user_coins.get(user_id, 0)
        total_value = user_coins * 200
        referrals_count = len(self.user_referrals.get(user_id, []))
        
        stats_text = (
            f"📊 **آمار و موجودی شما**\n\n"
            f"💰 **موجودی سکه:** {user_coins} سکه\n"
            f"💎 **ارزش ریالی:** {total_value:,} تومن\n"
            f"👥 **تعداد دعوت‌ها:** {referrals_count} نفر\n"
            f"🎁 **سکه از دعوت:** {referrals_count * 7} سکه\n\n"
            f"💡 **نکته:** به ازای هر دعوت موفق 7 سکه پاداش دریافت می‌کنید!"
        )
        await query.edit_message_text(stats_text, reply_markup=self.create_stats_keyboard())
    
    async def show_invite_panel(self, query, context: ContextTypes.DEFAULT_TYPE):
        user_id = query.from_user.id
        username = query.from_user.username or f"user_{user_id}"
        
        invite_code = secrets.token_urlsafe(8)
        self.invite_links[invite_code] = user_id
        invite_link = f"https://t.me/{context.bot.username}?start={invite_code}"
        referrals_count = len(self.user_referrals.get(user_id, []))
        
        invite_text = (
            f"🎫 **لینک دعوت شما**\n\n"
            f"🔗 **لینک:** `{invite_link}`\n\n"
            f"💎 **مزایای دعوت:**\n"
            f"• به ازای هر دعوت: **7 سکه** پاداش\n"
            f"• دعوت شده: **5 سکه** هدیه اولیه\n"
            f"• بدون محدودیت تعداد دعوت\n\n"
            f"📊 **آمار دعوت‌های شما:** {referrals_count} نفر\n"
            f"💰 **سکه‌های کسب شده:** {referrals_count * 7} سکه"
        )
        await query.edit_message_text(invite_text, reply_markup=self.create_invite_keyboard(), parse_mode='Markdown')
    
    # ============ Coin Purchase ============
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
            self.pending_purchases[purchase_id] = {
                'user_id': user_id,
                'amount': coin_count,
                'status': 'pending',
                'price': total_price,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            purchase_text = f"""
💌 **خرید سکه (توکن) NexoSelf** 💌

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
            context.user_data['coin_amount'] += digit
            updated_amount = context.user_data['coin_amount']
            await query.edit_message_text(
                f"💌 تعداد سکه: {updated_amount}\n\n"
                f"💰 مبلغ قابل پرداخت: {int(updated_amount or 0) * 200:,} تومن\n\n"
                f"⌨️ از کیبورد زیر برای ادامه استفاده کنید:",
                reply_markup=self.create_coin_keyboard(updated_amount)
            )
            return COIN_PURCHASE
        
        elif query.data == "display_coins":
            await query.answer(f"تعداد سکه فعلی: {coin_amount or '0'}")
            return COIN_PURCHASE
    
    async def confirm_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "confirm_purchase":
            coin_amount = context.user_data.get('coin_amount', '0')
            coin_count = int(coin_amount)
            total_price = coin_count * 200
            
            if user_id not in self.user_coins:
                self.user_coins[user_id] = 0
            self.user_coins[user_id] += coin_count
            
            final_purchase_text = (
                f"💌••• تأیید خرید سکه •••💌\n\n"
                f"🩸 مبلغ: {total_price:,} تومن\n"
                f"💌 تعداد سکه: {coin_count} سکه\n\n"
                f"💳 شماره کارت برای واریز:\n`{self.card_number}`\n\n"
                f"😘 کاربر گرامی برای خرید ابتدا مبلغ تعیین شده رو به شماره کارت بالا انتقال داده سپس عکس از رسید را برای مالک سلف ارسال کنید ❤️‍🩹 @amele55"
            )
            await query.edit_message_text(final_purchase_text)
            context.user_data['coin_amount'] = ''
            return ConversationHandler.END
        
        elif query.data == "cancel_purchase":
            context.user_data['coin_amount'] = ''
            await query.edit_message_text(
                "❌ خرید لغو شد.\n\n"
                "💌•••خرید سکه(کوین)•••💌\n\n"
                "💰 هر عدد سکه: 200 تومن\n"
                "‼️ تعداد سکه مورد نظر خود را وارد کنید",
                reply_markup=self.create_coin_keyboard()
            )
            return COIN_PURCHASE
    
    # ============ Phone and Code Verification ============
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
            client = TelegramClient(StringSession(), self.api_id, self.api_hash)
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
                if user_id in self.user_coins and self.user_coins[user_id] >= 5:
                    self.user_coins[user_id] -= 5
                await query.message.reply_text(
                    "🎉 **NexoSelf با موفقیت فعال شد!**\n\n"
                    "✅ اکانت شما با موفقیت تأیید شد\n"
                    "✅ NexoSelf به صورت خودکار اجرا شد\n"
                    "💰 5 سکه از حساب شما کسر شد\n"
                    "🔮 اکنون می‌توانید از دستورات NexoSelf استفاده کنید.",
                    reply_markup=self.create_main_menu_keyboard()
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
                if user_id in self.user_coins and self.user_coins[user_id] >= 5:
                    self.user_coins[user_id] -= 5
                await update.message.reply_text(
                    "🎉 **NexoSelf با موفقیت فعال شد!**\n\n"
                    "✅ اکانت شما با موفقیت تأیید شد\n"
                    "✅ NexoSelf به صورت خودکار اجرا شد\n"
                    "💰 5 سکه از حساب شما کسر شد\n"
                    "🔮 اکنون می‌توانید از دستورات NexoSelf استفاده کنید.",
                    reply_markup=self.create_main_menu_keyboard()
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
                if user_id in self.user_coins and self.user_coins[user_id] >= 5:
                    self.user_coins[user_id] -= 5
                await query.message.reply_text(
                    "🎉 **NexoSelf با موفقیت فعال شد!**\n\n"
                    "✅ اکانت شما با موفقیت تأیید شد\n"
                    "✅ NexoSelf به صورت خودکار اجرا شد\n"
                    "💰 5 سکه از حساب شما کسر شد\n"
                    "🔮 اکنون می‌توانید از دستورات NexoSelf استفاده کنید.",
                    reply_markup=self.create_main_menu_keyboard()
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
    
    async def activate_selfbot(self, session_string: str, user_id: int, phone_number: str):
        try:
            temp_file = f"session_{user_id}.txt"
            with open(temp_file, 'w') as f:
                f.write(session_string)
            subprocess.Popen([
                sys.executable, 'self.py',
                '--session', temp_file,
                '--api-id', str(self.api_id),
                '--api-hash', self.api_hash
            ])
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute('''INSERT OR REPLACE INTO users 
                           (user_id, phone, coins, join_date, is_active) 
                           VALUES (?, ?, ?, datetime('now'), 1)''',
                         (user_id, phone_number, self.user_coins.get(user_id, 0)))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Error activating selfbot: {e}")
            return False
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id in self.user_sessions:
            await self.user_sessions[user_id]['client'].disconnect()
            del self.user_sessions[user_id]
        context.user_data['waiting_for_password'] = False
        await update.message.reply_text("❌ عملیات لغو شد.\n\nبرای شروع مجدد /start را ارسال کنید.")
        return ConversationHandler.END
    
    # ============ Betting Handlers ============
    async def create_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        username = update.message.from_user.username or f"user_{user_id}"
        
        if not context.args:
            await update.message.reply_text("❌ لطفاً تعداد سکه شرط را مشخص کنید:\nمثال: `/bet 10`")
            return
        
        try:
            coin_amount = int(context.args[0])
            if coin_amount <= 0:
                await update.message.reply_text("❌ تعداد سکه باید بیشتر از صفر باشد!")
                return
            
            if user_id not in self.user_coins or self.user_coins[user_id] < coin_amount:
                await update.message.reply_text(f"❌ موجودی سکه شما کافی نیست!\n💰 موجودی فعلی: {self.user_coins.get(user_id, 0)} سکه")
                return
            
            bet_id = str(int(time.time()))
            self.active_bets[bet_id] = {
                'creator_id': user_id,
                'creator_username': username,
                'coin_amount': coin_amount,
                'participants': [user_id],
                'message_id': None
            }
            self.user_coins[user_id] -= coin_amount
            
            bet_text = f"🎰●شرط بندی ساخته شده●🎰\n\n👤 ساخته شده توسط: @{username}\n💌 تعداد کوین: {coin_amount} سکه\n💰 مبلغ: {coin_amount * 200:,} تومن"
            message = await update.message.reply_text(bet_text, reply_markup=self.create_bet_keyboard(bet_id))
            self.active_bets[bet_id]['message_id'] = message.message_id
            await update.message.reply_text(f"✅ شرط‌بندی با موفقیت ایجاد شد!\n💎 {coin_amount} سکه شما بلوکه شد.\n⏳ منتظر شرکت کننده دوم باشید...")
            
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
    
    async def create_group_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        username = update.message.from_user.username or f"user_{user_id}"
        chat_id = update.message.chat_id
        
        if update.message.chat.type == 'private':
            await update.message.reply_text("❌ این دستور فقط در گروه‌ها قابل استفاده است!")
            return
        
        if not context.args:
            await update.message.reply_text("❌ لطفاً تعداد سکه شرط را مشخص کنید:\nمثال: `/gbet 10`")
            return
        
        try:
            coin_amount = int(context.args[0])
            if coin_amount <= 0:
                await update.message.reply_text("❌ تعداد سکه باید بیشتر از صفر باشد!")
                return
            
            if user_id not in self.user_coins or self.user_coins[user_id] < coin_amount:
                await update.message.reply_text(f"❌ موجودی سکه شما کافی نیست!\n💰 موجودی فعلی: {self.user_coins.get(user_id, 0)} سکه")
                return
            
            bet_id = str(int(time.time()))
            self.group_bets[bet_id] = {
                'creator_id': user_id,
                'creator_username': username,
                'chat_id': chat_id,
                'coin_amount': coin_amount,
                'participants': [user_id],
                'message_id': None,
                'created_at': time.time()
            }
            self.user_coins[user_id] -= coin_amount
            
            bet_text = f"🎰●شرط بندی گروهی●🎰\n\n👤 سازنده: @{username}\n💌 تعداد کوین: {coin_amount} سکه\n💰 مبلغ: {coin_amount * 200:,} تومن\n👥 شرکت‌کنندگان: 1 نفر\n\n⏰ زمان باقی‌مانده: 5 دقیقه"
            message = await update.message.reply_text(bet_text, reply_markup=self.create_group_bet_keyboard(bet_id))
            self.group_bets[bet_id]['message_id'] = message.message_id
            asyncio.create_task(self.finish_group_bet(bet_id, context))
            
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
    
    async def finish_group_bet(self, bet_id: str, context: ContextTypes.DEFAULT_TYPE):
        await asyncio.sleep(300)
        if bet_id not in self.group_bets:
            return
        
        bet = self.group_bets[bet_id]
        if len(bet['participants']) < 2:
            if bet['creator_id'] in self.user_coins:
                self.user_coins[bet['creator_id']] += bet['coin_amount']
            try:
                await context.bot.edit_message_text(
                    chat_id=bet['chat_id'],
                    message_id=bet['message_id'],
                    text=f"❌ شرط‌بندی گروهی لغو شد!\n\n👤 سازنده: @{bet['creator_username']}\n💌 تعداد کوین: {bet['coin_amount']} سکه\n💰 علت: تعداد شرکت‌کنندگان کافی نبود\n💎 سکه‌ها به حساب سازنده بازگردانده شد."
                )
            except:
                pass
            del self.group_bets[bet_id]
            return
        
        winner_id = random.choice(bet['participants'])
        total_coins = bet['coin_amount'] * len(bet['participants'])
        
        if winner_id not in self.user_coins:
            self.user_coins[winner_id] = 0
        self.user_coins[winner_id] += total_coins
        
        winner_username = bet['creator_username'] if winner_id == bet['creator_id'] else "یکی از شرکت‌کنندگان"
        result_text = f"🎲شرط بندی گروهی انجام شد🎮\n\n🏆 برنده: @{winner_username}\n👥 تعداد شرکت‌کنندگان: {len(bet['participants'])} نفر\n🪙 مجموع جوایز: {total_coins} سکه\n💰 ارزش: {total_coins * 200:,} تومن\n🔮 ساعت: {datetime.now().strftime('%H:%M:%S')}"
        
        try:
            await context.bot.edit_message_text(chat_id=bet['chat_id'], message_id=bet['message_id'], text=result_text)
        except:
            pass
        
        try:
            await context.bot.send_message(chat_id=winner_id, text=f"🎉 شما در شرط‌بندی گروهی برنده شدید!\n💰 {total_coins} سکه به حساب شما اضافه شد!")
        except:
            pass
        del self.group_bets[bet_id]
    
    async def join_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        username = query.from_user.username or f"user_{user_id}"
        bet_id = query.data.replace('join_bet_', '')
        
        if bet_id not in self.active_bets:
            await query.edit_message_text("❌ این شرط‌بندی منقضی شده است!")
            return
        
        bet = self.active_bets[bet_id]
        
        if user_id == bet['creator_id']:
            await query.answer("❌ شما سازنده این شرط هستید!", show_alert=True)
            return
        
        if user_id in bet['participants']:
            await query.answer("❌ شما قبلاً در این شرط شرکت کرده‌اید!", show_alert=True)
            return
        
        if user_id not in self.user_coins or self.user_coins[user_id] < bet['coin_amount']:
            await query.answer(f"❌ موجودی سکه شما کافی نیست!\n💰 موجودی مورد نیاز: {bet['coin_amount']} سکه", show_alert=True)
            return
        
        bet['participants'].append(user_id)
        self.user_coins[user_id] -= bet['coin_amount']
        
        winner_id = random.choice(bet['participants'])
        loser_id = bet['creator_id'] if winner_id != bet['creator_id'] else user_id
        winner_username = bet['creator_username'] if winner_id == bet['creator_id'] else username
        loser_username = username if winner_id == bet['creator_id'] else bet['creator_username']
        total_coins = bet['coin_amount'] * 2
        
        if winner_id not in self.user_coins:
            self.user_coins[winner_id] = 0
        self.user_coins[winner_id] += total_coins
        
        del self.active_bets[bet_id]
        result_text = f"🎲شرط بندی انجام شد🎮\n\n🏆 برنده: @{winner_username}\n🥀 بازنده: @{loser_username}\n🪙 کوین: {total_coins} سکه\n🔮 ساعت: {datetime.now().strftime('%H:%M:%S')}\n🌋 مبلغ: {total_coins * 200:,} تومن"
        await query.edit_message_text(result_text)
        
        try:
            await context.bot.send_message(chat_id=winner_id, text=f"🎉 شما در شرط‌بندی برنده شدید!\n💰 {total_coins} سکه به حساب شما اضافه شد!")
        except:
            pass
        try:
            await context.bot.send_message(chat_id=loser_id, text=f"💔 متأسفانه در شرط‌بندی بازنده شدید.\n💎 {bet['coin_amount']} سکه از حساب شما کسر شد.")
        except:
            pass
    
    async def join_group_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        bet_id = query.data.replace('join_gbet_', '')
        
        if bet_id not in self.group_bets:
            await query.answer("❌ این شرط‌بندی منقضی شده است!", show_alert=True)
            return
        
        bet = self.group_bets[bet_id]
        
        if user_id in bet['participants']:
            await query.answer("❌ شما قبلاً در این شرط شرکت کرده‌اید!", show_alert=True)
            return
        
        if user_id not in self.user_coins or self.user_coins[user_id] < bet['coin_amount']:
            await query.answer(f"❌ موجودی سکه شما کافی نیست!\n💰 موجودی مورد نیاز: {bet['coin_amount']} سکه", show_alert=True)
            return
        
        bet['participants'].append(user_id)
        self.user_coins[user_id] -= bet['coin_amount']
        
        remaining_time = 300 - (time.time() - bet['created_at'])
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        updated_text = f"🎰●شرط بندی گروهی●🎰\n\n👤 سازنده: @{bet['creator_username']}\n💌 تعداد کوین: {bet['coin_amount']} سکه\n💰 مبلغ: {bet['coin_amount'] * 200:,} تومن\n👥 شرکت‌کنندگان: {len(bet['participants'])} نفر\n\n⏰ زمان باقی‌مانده: {minutes:02d}:{seconds:02d}"
        await query.edit_message_text(updated_text, reply_markup=self.create_group_bet_keyboard(bet_id))
        await query.answer(f"✅ شما با موفقیت به شرط پیوستید! {bet['coin_amount']} سکه از حساب شما کسر شد.")
    
    async def cancel_group_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        bet_id = query.data.replace('cancel_gbet_', '')
        
        if bet_id not in self.group_bets:
            await query.answer("❌ این شرط‌بندی منقضی شده است!", show_alert=True)
            return
        
        bet = self.group_bets[bet_id]
        if user_id != bet['creator_id']:
            await query.answer("❌ فقط سازنده شرط می‌تواند آن را لغو کند!", show_alert=True)
            return
        
        for participant_id in bet['participants']:
            if participant_id in self.user_coins:
                self.user_coins[participant_id] += bet['coin_amount']
        
        await query.edit_message_text(f"❌ شرط‌بندی گروهی توسط سازنده لغو شد!\n\n💌 تعداد کوین: {bet['coin_amount']} سکه\n👥 شرکت‌کنندگان: {len(bet['participants'])} نفر\n💎 سکه‌ها به حساب همه بازگردانده شد.")
        del self.group_bets[bet_id]
    
    # ============ Other Handlers ============
    async def create_invite_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        username = update.message.from_user.username or f"user_{user_id}"
        invite_code = secrets.token_urlsafe(8)
        self.invite_links[invite_code] = user_id
        invite_link = f"https://t.me/{context.bot.username}?start={invite_code}"
        referrals_count = len(self.user_referrals.get(user_id, []))
        invite_text = f"🎫 **لینک دعوت شما**\n\n🔗 لینک: `{invite_link}`\n\n💎 **مزایا:**\n• به ازای هر دعوت: **7 سکه** پاداش\n• دعوت شده: **5 سکه** هدیه اولیه\n• بدون محدودیت تعداد دعوت\n\n📊 آمار دعوت‌های شما: {referrals_count} نفر\n💰 سکه‌های کسب شده: {referrals_count * 7} سکه"
        await update.message.reply_text(invite_text, parse_mode='Markdown')
    
    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._show_balance(update, context)
    
    async def show_balance_farsi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._show_balance(update, context)
    
    async def _show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        username = update.message.from_user.first_name or "کاربر"
        user_coins = self.user_coins.get(user_id, 0)
        total_value = user_coins * 200
        current_time = datetime.now().strftime("%H:%M:%S")
        balance_text = f"🥃 کاربر: {username}\n🚜 موجودی: {user_coins} سکه\n🫟 قیمت: {total_value:,} تومن\n🍺 ساعت: {current_time}"
        await update.message.reply_text(balance_text)
    
    async def transfer_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._transfer_coins(update, context)
    
    async def transfer_coins_farsi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._transfer_coins(update, context)
    
    async def _transfer_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        username = update.message.from_user.username or f"user_{user_id}"
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ لطفاً روی پیام کاربر مورد نظر ریپلای کنید و دستور را ارسال نمایید:\nمثال: `انتقال 10` یا `/transfer 10`")
            return
        
        message_text = update.message.text
        coin_amount = 0
        
        try:
            if message_text.startswith('/transfer') and context.args:
                coin_amount = int(context.args[0])
            elif message_text.startswith('انتقال'):
                parts = message_text.split()
                if len(parts) >= 2:
                    coin_amount = int(parts[1])
            else:
                await update.message.reply_text("❌ فرمت دستور نادرست است!\nمثال: `انتقال 10` یا `/transfer 10`")
                return
        except (ValueError, IndexError):
            await update.message.reply_text("❌ لطفاً تعداد سکه را به درستی مشخص کنید:\nمثال: `انتقال 10` یا `/transfer 10`")
            return
        
        if coin_amount <= 0:
            await update.message.reply_text("❌ تعداد سکه باید بیشتر از صفر باشد!")
            return
        
        if user_id not in self.user_coins or self.user_coins[user_id] < coin_amount:
            await update.message.reply_text(f"❌ موجودی سکه شما کافی نیست!\n💰 موجودی فعلی: {self.user_coins.get(user_id, 0)} سکه")
            return
        
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_username = target_user.first_name or "کاربر"
        
        if target_user_id == user_id:
            await update.message.reply_text("❌ نمی‌توانید به خودتان سکه انتقال دهید!")
            return
        
        self.user_coins[user_id] -= coin_amount
        if target_user_id not in self.user_coins:
            self.user_coins[target_user_id] = 0
        self.user_coins[target_user_id] += coin_amount
        
        transfer_text = f"💸 **انتقال سکه انجام شد**\n\n👤 از: {username}\n👥 به: {target_username}\n💰 مبلغ: {coin_amount} سکه\n💎 ارزش: {coin_amount * 200:,} تومن\n🕐 زمان: {datetime.now().strftime('%H:%M:%S')}"
        await update.message.reply_text(transfer_text)
        
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"🎉 شما {coin_amount} سکه از کاربر {username} دریافت کردید!\n💰 موجودی جدید: {self.user_coins[target_user_id]} سکه")
        except:
            pass
    
    async def kasr_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ شما دسترسی به این دستور را ندارید!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ لطفاً روی پیام کاربر مورد نظر ریپلای کنید و دستور را ارسال نمایید:\nمثال: `/kasr 10`")
            return
        
        if not context.args:
            await update.message.reply_text("❌ لطفاً تعداد سکه را مشخص کنید:\nمثال: `/kasr 10`")
            return
        
        try:
            coin_amount = int(context.args[0])
            if coin_amount <= 0:
                await update.message.reply_text("❌ تعداد سکه باید بیشتر از صفر باشد!")
                return
            
            target_user = update.message.reply_to_message.from_user
            target_user_id = target_user.id
            target_username = target_user.first_name or "کاربر"
            current_coins = self.user_coins.get(target_user_id, 0)
            
            if current_coins < coin_amount:
                coins_to_deduct = current_coins
                self.user_coins[target_user_id] = 0
            else:
                coins_to_deduct = coin_amount
                self.user_coins[target_user_id] -= coin_amount
            
            kasr_text = f"⚡ **کسر سکه توسط مالک**\n\n👤 کاربر: {target_username}\n🆔 آیدی: `{target_user_id}`\n💰 مبلغ کسر شده: {coins_to_deduct} سکه\n💎 موجودی جدید: {self.user_coins.get(target_user_id, 0)} سکه\n🕐 زمان: {datetime.now().strftime('%H:%M:%S')}"
            await update.message.reply_text(kasr_text)
            
            try:
                await context.bot.send_message(chat_id=target_user_id, text=f"⚠️ {coins_to_deduct} سکه از حساب شما توسط مالک کسر شد!\n💰 موجودی جدید: {self.user_coins.get(target_user_id, 0)} سکه")
            except:
                pass
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
    
    async def add_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ شما دسترسی به این دستور را ندارید!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ لطفاً روی پیام کاربر مورد نظر ریپلای کنید و دستور را ارسال نمایید:\nمثال: `/addcoins 10`")
            return
        
        if not context.args:
            await update.message.reply_text("❌ لطفاً تعداد سکه را مشخص کنید:\nمثال: `/addcoins 10`")
            return
        
        try:
            coin_amount = int(context.args[0])
            if coin_amount <= 0:
                await update.message.reply_text("❌ تعداد سکه باید بیشتر از صفر باشد!")
                return
            
            target_user = update.message.reply_to_message.from_user
            target_user_id = target_user.id
            target_username = target_user.first_name or "کاربر"
            
            if target_user_id not in self.user_coins:
                self.user_coins[target_user_id] = 0
            self.user_coins[target_user_id] += coin_amount
            
            add_text = f"🎁 **افزودن سکه توسط مالک**\n\n👤 کاربر: {target_username}\n🆔 آیدی: `{target_user_id}`\n💰 مبلغ افزوده شده: {coin_amount} سکه\n💎 موجودی جدید: {self.user_coins.get(target_user_id, 0)} سکه\n🕐 زمان: {datetime.now().strftime('%H:%M:%S')}"
            await update.message.reply_text(add_text)
            
            try:
                await context.bot.send_message(chat_id=target_user_id, text=f"🎉 {coin_amount} سکه توسط مالک به حساب شما افزوده شد!\n💰 موجودی جدید: {self.user_coins.get(target_user_id, 0)} سکه")
            except:
                pass
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")
    
    async def get_user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ شما دسترسی به این دستور را ندارید!")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ لطفاً روی پیام کاربر مورد نظر ریپلای کنید و دستور را ارسال نمایید:\nمثال: `/id`")
            return
        
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id
        target_username = target_user.username or "ندارد"
        target_first_name = target_user.first_name or "ندارد"
        target_last_name = target_user.last_name or "ندارد"
        user_coins = self.user_coins.get(target_user_id, 0)
        total_value = user_coins * 200
        
        user_info_text = f"👤 **اطلاعات کاربر**\n\n🆔 **آیدی عددی:** `{target_user_id}`\n👁️ **نام کاربری:** @{target_username}\n📛 **نام:** {target_first_name}\n📛 **نام خانوادگی:** {target_last_name}\n💰 **تعداد سکه:** {user_coins}\n💎 **ارزش سکه‌ها:** {total_value:,} تومن\n🎯 **وضعیت NexoSelf:** {'فعال' if target_user_id in self.active_selfbots else 'غیرفعال'}\n📊 **تعداد دعوت‌ها:** {len(self.user_referrals.get(target_user_id, []))}\n🕐 **زمان:** {datetime.now().strftime('%H:%M:%S')}"
        await update.message.reply_text(user_info_text, parse_mode='Markdown')
    
    # ============ Handle Receipt Photo ============
    async def handle_receipt_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        photo = update.message.photo[-1]
        
        pending_purchase = None
        purchase_id = None
        for pid, data in self.pending_purchases.items():
            if data['user_id'] == user_id and data['status'] == 'pending':
                pending_purchase = data
                purchase_id = pid
                break
        
        if not pending_purchase:
            await update.message.reply_text("❌ هیچ درخواست خرید در انتظاری برای شما یافت نشد!\nلطفاً ابتدا با دستور `/buy تعداد` درخواست خرید ثبت کنید.")
            return
        
        user = update.message.from_user
        username = user.username or "ندارد"
        first_name = user.first_name or "ندارد"
        
        admin_message = f"""
🆕 **درخواست خرید جدید!**

👤 **اطلاعات کاربر:**
• نام: {first_name}
• یوزرنیم: @{username}
• آیدی: `{user_id}`

📊 **مشخصات خرید:**
• تعداد سکه: {pending_purchase['amount']}
• مبلغ: {pending_purchase['price']:,} تومن
• زمان: {pending_purchase['timestamp']}

📸 **فیش پرداخت:** (دریافت شد)

✅ لطفاً با استفاده از دکمه‌های زیر اقدام کنید:
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ تایید خرید", callback_data=f"approve_purchase_{purchase_id}"),
                InlineKeyboardButton("❌ رد خرید", callback_data=f"reject_purchase_{purchase_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.application.bot.send_photo(
            chat_id=self.admin_id,
            photo=photo.file_id,
            caption=admin_message,
            reply_markup=reply_markup
        )
        
        await update.message.reply_text("✅ **فیش پرداخت شما دریافت شد!**\n\n🔄 در انتظار تایید مالک...\n⏱️ لطفاً صبور باشید، به زودی تایید می‌شود.")
    
    # ============ Handle Text Messages ============
    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        text = update.message.text.strip()
        
        if text.startswith('/buy') or text.startswith('خرید'):
            try:
                parts = text.split()
                if len(parts) >= 2:
                    amount = int(parts[1])
                    if amount > 0:
                        purchase_id = f"{user_id}_{int(time.time())}"
                        self.pending_purchases[purchase_id] = {
                            'user_id': user_id,
                            'amount': amount,
                            'status': 'pending',
                            'price': amount * 200,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        purchase_text = f"""
💌 **خرید سکه (توکن) NexoSelf** 💌

✅ درخواست خرید شما ثبت شد!

📊 **مشخصات خرید:**
• تعداد سکه: {amount}
• مبلغ قابل پرداخت: {amount * 200:,} تومن

💳 **شماره کارت برای واریز:**
`{self.card_number}`

📸 پس از واریز، عکس فیش را در پاسخ به این پیام ارسال کنید.

🆔 برای پیگیری با مالک تماس بگیرید: @amele55
                        """
                        await update.message.reply_text(purchase_text)
                        return
            except ValueError:
                pass
    
    def run(self):
        print("🤖 ربات NexoSelf در حال اجراست...")
        print("🔑 API ID:", self.api_id)
        print("👑 مالک ربات:", self.admin_id)
        print("💰 موجودی مالک: نامحدود")
        print("💳 شماره کارت:", self.card_number)
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8731724435:AAESif1eCVP75--LGxGI8VYNasFjXYDZVo0")
    API_ID = int(os.environ.get("API_ID", 34434623))
    API_HASH = os.environ.get("API_HASH", "d82c5dd13602eedc3041e9f549bcd813")
    
    if not os.path.exists("database"):
        os.makedirs("database")
    
    bot = TelegramAuthBot(BOT_TOKEN, API_ID, API_HASH)
    bot.run()
