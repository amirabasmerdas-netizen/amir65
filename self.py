import sys
import time
import asyncio
import random
import os
import psutil
import pytz
import requests
import sqlite3
import threading
import json
import re
from datetime import datetime
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import ChannelParticipantsAdmins, InputMediaDice
from telethon.tl.functions.messages import SetTypingRequest, ForwardMessagesRequest
from telethon.tl.types import SendMessageTypingAction, SendMessageRecordVideoAction, SendMessageUploadVideoAction
from telethon.tl.functions.account import UpdateStatusRequest, UpdateProfileRequest
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError, FloodWaitError

API_ID = 34434623
API_HASH = "d82c5dd13602eedc3041e9f549bcd813"

DATABASE_DIR = "database"
USERS_DB = os.path.join(DATABASE_DIR, "users.db")
ACCOUNTS_DB = os.path.join(DATABASE_DIR, "accounts.db")
ADMIN_ID = "8296865861"
GROUP_ID = "-1003214156615"
CHANNEL_ID = "-1003678402202"
MATH_CHAT_ID = -1002107981593  # @Gp_SelfNexo

if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

# ─── فونت‌ها ───────────────────────────────────────────────────────────────────
FONTS = {
    "0": lambda t: t,
    "1": lambda t: _convert_font(t, "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"),
    "2": lambda t: _convert_font(t, "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻"),
    "3": lambda t: _convert_font(t, "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣"),
    "4": lambda t: _convert_font(t, "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"),
    "5": lambda t: _convert_font(t, "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"),
    "6": lambda t: _convert_font(t, "𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹ℯℱℊℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵"),
    "7": lambda t: "".join(c + "\u0336" for c in t),
    "8": lambda t: "".join(c + "\u0332" for c in t),
}
_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# ─── پاسخ‌های دشمن و دوست ────────────────────────────────────────────────────
ENEMY_REPLIES = [
    "🤡 بیخیال بابا...",
    "😒 به تو چه؟",
    "🚫 نه تو...",
    "💀 بیا دیگه...",
    "😤 خفه شو!"
]

FRIEND_REPLIES = [
    "😊 سلام دوست عزیز!",
    "💚 خوشحالم می‌بینمت!",
    "🌸 چطوری؟",
    "🌺 همیشه خوش‌آمدی!",
    "💖 بهت افتخار می‌کنم!"
]

# ─── کش حافظه ──────────────────────────────────────────────────────────────────
_user_cache = {}
_user_cache_time = {}
_CACHE_TTL = 60

def get_cached_user(tg_id: int):
    now = time.time()
    if tg_id in _user_cache and (now - _user_cache_time.get(tg_id, 0) < _CACHE_TTL):
        return _user_cache[tg_id]
    account = get_account_by_tg_id(tg_id)
    _user_cache[tg_id] = account
    _user_cache_time[tg_id] = now
    return account

def clear_user_cache():
    _user_cache.clear()
    _user_cache_time.clear()

def _convert_font(text, chars):
    result = []
    for ch in text:
        if ch in _ALPHA:
            result.append(chars[_ALPHA.index(ch)])
        else:
            result.append(ch)
    return "".join(result)

def apply_font(owner_id, text):
    font_id = get_setting(owner_id, "selected_font", "0")
    fn = FONTS.get(font_id, FONTS["0"])
    return fn(text)

# ─── توابع دیتابیس ────────────────────────────────────────────────────────────
def init_db():
    """ایجاد دیتابیس‌های مورد نیاز"""
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER UNIQUE,
        telegram_id INTEGER,
        phone TEXT,
        token_balance INTEGER DEFAULT 0,
        is_owner INTEGER DEFAULT 0,
        created_date TEXT
    )''')
    
    # جدول تنظیمات
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        owner_id INTEGER,
        key TEXT,
        value TEXT,
        PRIMARY KEY (owner_id, key)
    )''')
    
    # جدول دشمنان
    cursor.execute('''CREATE TABLE IF NOT EXISTS enemies (
        owner_id INTEGER,
        user_id INTEGER,
        username TEXT,
        name TEXT,
        PRIMARY KEY (owner_id, user_id)
    )''')
    
    # جدول دوستان
    cursor.execute('''CREATE TABLE IF NOT EXISTS friends (
        owner_id INTEGER,
        user_id INTEGER,
        username TEXT,
        name TEXT,
        PRIMARY KEY (owner_id, user_id)
    )''')
    
    # جدول چالش‌های ریاضی
    cursor.execute('''CREATE TABLE IF NOT EXISTS math_challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        question TEXT,
        correct_answer TEXT,
        chat_id INTEGER,
        message_id INTEGER,
        solved INTEGER DEFAULT 0,
        created_date TEXT
    )''')
    
    # جدول تنظیمات چالش
    cursor.execute('''CREATE TABLE IF NOT EXISTS challenge_settings (
        owner_id INTEGER PRIMARY KEY,
        math_challenge_active INTEGER DEFAULT 0
    )''')
    
    # جدول پیام‌های زمان‌بندی شده
    cursor.execute('''CREATE TABLE IF NOT EXISTS scheduled_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        chat_id INTEGER,
        message TEXT,
        send_at TEXT,
        sent INTEGER DEFAULT 0
    )''')
    
    # جدول اسلات‌های ذخیره پیام
    cursor.execute('''CREATE TABLE IF NOT EXISTS saved_messages (
        owner_id INTEGER,
        slot INTEGER,
        content TEXT,
        PRIMARY KEY (owner_id, slot)
    )''')
    
    conn.commit()
    conn.close()

def get_user_by_owner_id(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE owner_id = ?', (owner_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_account_by_tg_id(tg_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (tg_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_setting(owner_id, key, default=None):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE owner_id = ? AND key = ?', (owner_id, key))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(owner_id, key, value):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (owner_id, key, value) VALUES (?, ?, ?)', (owner_id, key, value))
    conn.commit()
    conn.close()

def get_token_balance(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT token_balance FROM users WHERE owner_id = ?', (owner_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_tokens(owner_id, amount):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET token_balance = token_balance + ? WHERE owner_id = ?', (amount, owner_id))
    conn.commit()
    conn.close()

def deduct_tokens(owner_id, amount):
    balance = get_token_balance(owner_id)
    if balance < amount:
        return False
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET token_balance = token_balance - ? WHERE owner_id = ?', (amount, owner_id))
    conn.commit()
    conn.close()
    return True

def save_telegram_user_id(owner_id, tg_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET telegram_id = ? WHERE owner_id = ?', (tg_id, owner_id))
    conn.commit()
    conn.close()

def is_enemy(owner_id, user_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM enemies WHERE owner_id = ? AND user_id = ?', (owner_id, user_id))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def add_enemy(owner_id, user_id, username=None, name=None):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO enemies (owner_id, user_id, username, name) VALUES (?, ?, ?, ?)', 
                   (owner_id, user_id, username, name))
    conn.commit()
    conn.close()

def remove_enemy(owner_id, user_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM enemies WHERE owner_id = ? AND user_id = ?', (owner_id, user_id))
    conn.commit()
    conn.close()

def get_enemies(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, name FROM enemies WHERE owner_id = ?', (owner_id,))
    result = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "name": r[2]} for r in result]

def clear_enemies(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM enemies WHERE owner_id = ?', (owner_id,))
    conn.commit()
    conn.close()

def is_friend(owner_id, user_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM friends WHERE owner_id = ? AND user_id = ?', (owner_id, user_id))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def add_friend(owner_id, user_id, username=None, name=None):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO friends (owner_id, user_id, username, name) VALUES (?, ?, ?, ?)', 
                   (owner_id, user_id, username, name))
    conn.commit()
    conn.close()

def remove_friend(owner_id, user_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM friends WHERE owner_id = ? AND user_id = ?', (owner_id, user_id))
    conn.commit()
    conn.close()

def get_friends(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, name FROM friends WHERE owner_id = ?', (owner_id,))
    result = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "name": r[2]} for r in result]

def clear_friends(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM friends WHERE owner_id = ?', (owner_id,))
    conn.commit()
    conn.close()

def create_math_challenge(owner_id, question, answer, chat_id, message_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO math_challenges 
                     (owner_id, question, correct_answer, chat_id, message_id, created_date) 
                     VALUES (?, ?, ?, ?, ?, datetime("now"))''',
                   (owner_id, question, answer, chat_id, message_id))
    conn.commit()
    conn.close()

def get_math_challenge(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('''SELECT id, question, correct_answer, chat_id, message_id, solved 
                     FROM math_challenges WHERE owner_id = ? AND solved = 0 
                     ORDER BY id DESC LIMIT 1''', (owner_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"id": result[0], "question": result[1], "correct_answer": result[2], 
                "chat_id": result[3], "message_id": result[4], "solved": result[5]}
    return None

def solve_math_challenge(challenge_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('UPDATE math_challenges SET solved = 1 WHERE id = ?', (challenge_id,))
    conn.commit()
    conn.close()

def get_challenge_settings(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT math_challenge_active FROM challenge_settings WHERE owner_id = ?', (owner_id,))
    result = cursor.fetchone()
    conn.close()
    return {"math_challenge_active": result[0] if result else 0}

def set_challenge_setting(owner_id, key, value):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO challenge_settings (owner_id, math_challenge_active) VALUES (?, ?)', 
                   (owner_id, value))
    conn.commit()
    conn.close()

def add_scheduled_message(owner_id, chat_id, message, send_at):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO scheduled_messages (owner_id, chat_id, message, send_at) VALUES (?, ?, ?, ?)',
                   (owner_id, chat_id, message, send_at))
    conn.commit()
    conn.close()

def get_pending_scheduled(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('''SELECT id, chat_id, message FROM scheduled_messages 
                     WHERE owner_id = ? AND sent = 0 AND send_at <= datetime("now")''', (owner_id,))
    result = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "chat_id": r[1], "message": r[2]} for r in result]

def mark_scheduled_sent(msg_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('UPDATE scheduled_messages SET sent = 1 WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()

def save_message_slot(owner_id, slot, content):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO saved_messages (owner_id, slot, content) VALUES (?, ?, ?)',
                   (owner_id, slot, content))
    conn.commit()
    conn.close()

def get_message_slot(owner_id, slot):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT content FROM saved_messages WHERE owner_id = ? AND slot = ?', (owner_id, slot))
    result = cursor.fetchone()
    conn.close()
    return {"content": result[0]} if result else None

def is_owner(owner_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('SELECT is_owner FROM users WHERE owner_id = ?', (owner_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

# ─── کلاس AccountManager ────────────────────────────────────────────────────
class AccountManager:
    def __init__(self):
        self.accounts = {}
        self.active_clients = {}
        init_db()
        
    def add_account(self, phone, session_string):
        conn = sqlite3.connect(ACCOUNTS_DB)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO accounts 
                         (phone, session_string, is_active, created_date, last_used) 
                         VALUES (?, ?, 1, datetime("now"), datetime("now"))''',
                     (phone, session_string))
        conn.commit()
        conn.close()
        print(f"✅ اکانت {phone} به دیتابیس اضافه شد")
    
    def get_all_accounts(self):
        conn = sqlite3.connect(ACCOUNTS_DB)
        cursor = conn.cursor()
        cursor.execute('SELECT phone, session_string FROM accounts WHERE is_active = 1')
        accounts = cursor.fetchall()
        conn.close()
        return accounts
    
    def deactivate_account(self, phone):
        conn = sqlite3.connect(ACCOUNTS_DB)
        cursor = conn.cursor()
        cursor.execute('UPDATE accounts SET is_active = 0 WHERE phone = ?', (phone,))
        conn.commit()
        conn.close()
        print(f"✅ اکانت {phone} غیرفعال شد")

# ─── کلاس TelegramAccount ──────────────────────────────────────────────────
class TelegramAccount:
    def __init__(self, phone, session_string, account_manager):
        self.phone = phone
        self.session_string = session_string
        self.account_manager = account_manager
        self.client = None
        self.owner_id = None
        self.is_running = False
        self.shutdown_requested = False
        self.is_owner_user = False
        self.owner_tg_id = None
        
        self.connection_retries = 0
        self.max_retries = 5
        self.last_activity = time.time()
        self.health_check_interval = 120
        
        self.secretary_messages = {}
        self.auto_forward_settings = {}
        self.typing_users = {}
        self.last_time_update = 0
        
        # محدودیت‌های زمانی
        self._last_secretary_reply = {}
        self._last_friend_reply = {}
        self.SECRETARY_COOLDOWN = 86400  # 24 ساعت
        self.FRIEND_COOLDOWN = 3600      # 1 ساعت
        
    async def safe_initialize_client(self):
        try:
            print(f"🔄 در حال راه‌اندازی اکانت {self.phone}...")
            
            self.client = TelegramClient(
                StringSession(self.session_string), 
                API_ID, 
                API_HASH,
                device_model="iPhone 15 Pro",
                system_version="iOS 17.1",
                app_version="10.0.0",
                lang_code="fa",
                system_lang_code="fa",
                connection_retries=10,
                request_retries=5,
                auto_reconnect=True,
                flood_sleep_threshold=120,
                base_logger=None,
            )
            
            await asyncio.wait_for(self.client.connect(), timeout=30)
            
            if not await self.client.is_user_authorized():
                print(f"❌ سشن برای {self.phone} نامعتبر است")
                return False
                
            try:
                me = await asyncio.wait_for(self.client.get_me(), timeout=10)
                if me:
                    self.owner_id = me.id
                    self.owner_tg_id = me.id
                    self.connection_retries = 0
                    print(f"✅ اکانت {self.phone} با موفقیت لاگین شد")
                    print(f"👤 کاربر: {me.first_name} (ID: {me.id})")
                    
                    # بررسی اینکه آیا کاربر مالک است
                    if str(me.id) == ADMIN_ID:
                        self.is_owner_user = True
                        print(f"👑 کاربر {self.phone} به عنوان مالک شناسایی شد")
                    
                    return True
                else:
                    print(f"❌ دریافت اطلاعات کاربر برای {self.phone} ناموفق بود")
                    return False
                    
            except asyncio.TimeoutError:
                print(f"⏰ timeout دریافت اطلاعات کاربر برای {self.phone}")
                return False
            except Exception as e:
                print(f"❌ خطا در دریافت اطلاعات کاربر {self.phone}: {e}")
                return False
                
        except asyncio.TimeoutError:
            print(f"⏰ timeout اتصال برای {self.phone}")
            return False
        except Exception as e:
            print(f"❌ خطا در راه‌اندازی کلاینت برای {self.phone}: {e}")
            return False
    
    async def robust_initialize(self):
        for attempt in range(self.max_retries):
            try:
                print(f"🔄 تلاش {attempt + 1}/{self.max_retries} برای راه‌اندازی {self.phone}")
                
                if await self.safe_initialize_client():
                    await self.set_online_status()
                    await self.register_handlers()
                    await self.send_startup_message()
                    await self.send_login_notification()
                    
                    self.is_running = True
                    
                    asyncio.create_task(self.safe_maintain_online_status())
                    asyncio.create_task(self.health_monitor())
                    asyncio.create_task(self.safe_update_profile_time())
                    asyncio.create_task(self._scheduler_loop())
                    
                    # اگر مالک باشد چالش ریاضی فعال می‌شود
                    if self.is_owner_user:
                        asyncio.create_task(self._math_challenge_loop())
                        print(f"🧮 چالش ریاضی برای مالک {self.phone} فعال شد")
                    
                    print(f"✅ اکانت {self.phone} با موفقیت راه‌اندازی شد")
                    return True
                    
                else:
                    wait_time = (attempt + 1) * 10
                    print(f"⏳ انتظار {wait_time} ثانیه قبل از تلاش مجدد...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                print(f"❌ خطا در راه‌اندازی (تلاش {attempt + 1}): {e}")
                await asyncio.sleep(15)
        
        print(f"❌ راه‌اندازی اکانت {self.phone} پس از {self.max_retries} تلاش ناموفق بود")
        return False

    async def health_monitor(self):
        while self.is_running and not self.shutdown_requested:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                if not self.client.is_connected():
                    print(f"🔌 اتصال {self.phone} قطع شده، تلاش برای اتصال مجدد...")
                    await self.recover_connection()
                
                if time.time() - self.last_activity > 300:
                    print(f"🫀 بررسی سلامت اکانت {self.phone}")
                    await self.perform_health_check()
                
            except Exception as e:
                print(f"⚠️ خطا در مانیتورینگ سلامت {self.phone}: {e}")
                await asyncio.sleep(60)

    async def perform_health_check(self):
        try:
            me = await asyncio.wait_for(self.client.get_me(), timeout=10)
            if not me:
                raise Exception("عدم پاسخ از سرور")
            print(f"✅ سلامت اکانت {self.phone} تأیید شد")
            return True
        except Exception as e:
            print(f"❌ مشکل در سلامت اکانت {self.phone}: {e}")
            await self.recover_connection()
            return False

    async def recover_connection(self):
        try:
            print(f"🔄 بازیابی اتصال برای {self.phone}")
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
            
            wait_time = random.uniform(5, 15)
            await asyncio.sleep(wait_time)
            
            if await self.safe_initialize_client():
                print(f"✅ اتصال {self.phone} بازیابی شد")
                return True
            else:
                print(f"❌ بازیابی اتصال {self.phone} ناموفق بود")
                return False
        except Exception as e:
            print(f"❌ خطا در بازیابی اتصال {self.phone}: {e}")
            return False

    async def set_online_status(self):
        try:
            await self.client(UpdateStatusRequest(offline=False))
            print(f"✅ حالت آنلاین برای {self.phone} فعال شد")
        except Exception as e:
            print(f"خطا در تنظیم حالت آنلاین برای {self.phone}: {e}")
    
    async def safe_maintain_online_status(self):
        while self.is_running and not self.shutdown_requested:
            try:
                await self.client(UpdateStatusRequest(offline=False))
                await asyncio.sleep(60)
            except Exception as e:
                print(f"خطا در حفظ حالت آنلاین برای {self.phone}: {e}")
                await asyncio.sleep(60)

    async def send_startup_message(self):
        try:
            me = await self.client.get_me()
            welcome_text = f"""
┌─────────────────────
│  🌟 **NexoSelf فعال شد**  
└─────────────────────

✅ **اکانت با موفقیت فعال شد!**

📱 **شماره:** `{self.phone}`
🆔 **آیدی:** `{me.id}`
👤 **نام:** {me.first_name or '---'}

📝 **دستورات اصلی:**
• راهنما - نمایش منوی راهنما
• وضعیت - وضعیت سیستم
• تنظیمات - تنظیمات ربات
• منشی روشن/خاموش - فعال‌سازی منشی

🔮 **قدرت گرفته از:** @Ch_SelfNexo
            """
            await self.client.send_message('me', welcome_text)
            print(f"✅ پیام شروع برای {self.phone} ارسال شد")
        except Exception as e:
            print(f"خطا در ارسال پیام شروع برای {self.phone}: {e}")
    
    async def send_login_notification(self):
        try:
            me = await self.client.get_me()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            login_message = f"""
💌 **NexoSelf فعال شده در:** `{current_time}`

📱 **شماره:** `{self.phone}`
👤 **نام:** {me.first_name or '---'}
🔗 **یوزرنیم:** @{me.username or '---'}

🥀 **مالک:** @amele55
🔮 **چنل:** @Ch_SelfNexo
            """
            
            await self.client.send_message(ADMIN_ID, login_message)
            print(f"✅ اطلاعیه لاگین برای {self.phone} ارسال شد")
        except Exception as e:
            print(f"خطا در ارسال اطلاعیه لاگین برای {self.phone}: {e}")

    # ─── ثبت هندلرها ──────────────────────────────────────────────────────────
    async def register_handlers(self):
        @self.client.on(events.NewMessage(incoming=True))
        async def on_incoming(event):
            try:
                self.last_activity = time.time()
                msg = event.message
                sender = await event.get_sender()
                chat = await event.get_chat()
                sender_id = getattr(sender, "id", 0)
                chat_id = getattr(chat, "id", 0)
                text = msg.text or ""
                
                # اگر پیام از خود کاربر باشد یا از ادمین باشد
                if sender_id == self.owner_id or str(sender_id) == ADMIN_ID:
                    return
                
                # بررسی تگ شدن در گروه
                is_tagged = False
                if not event.is_private:
                    me = await self.client.get_me()
                    if msg.entities:
                        for entity in msg.entities:
                            if hasattr(entity, 'user_id') and entity.user_id == me.id:
                                is_tagged = True
                                break
                    replied_msg = await event.get_reply_message()
                    if replied_msg and replied_msg.sender_id == me.id:
                        is_tagged = True
                    if me.username and me.username.lower() in text.lower():
                        is_tagged = True
                
                # اگر در گروه است و تگ نشده، فقط کارهای خودکار
                if not event.is_private and not is_tagged:
                    # سین خودکار
                    if get_setting(self.owner_id, "auto_seen_active") == "1":
                        try:
                            await self.client.send_read_acknowledge(chat_id, msg)
                        except Exception:
                            pass
                    
                    # پاسخ به دشمن در گروه (حتی بدون تگ)
                    if get_setting(self.owner_id, "enemy_reply_active") == "1" and is_enemy(self.owner_id, sender_id):
                        try:
                            await event.reply(random.choice(ENEMY_REPLIES))
                        except Exception:
                            pass
                    
                    # ری‌اکشن خودکار در گروه
                    if get_setting(self.owner_id, "auto_reaction_active") == "1":
                        emoji = get_setting(self.owner_id, "auto_reaction_emoji", "❤️")
                        try:
                            from telethon.tl.functions.messages import SendReactionRequest
                            from telethon.tl.types import ReactionEmoji
                            await self.client(SendReactionRequest(
                                peer=chat_id,
                                msg_id=msg.id,
                                reaction=[ReactionEmoji(emoticon=emoji)],
                                big=False,
                                add_to_recent=True
                            ))
                        except Exception:
                            pass
                    return
                
                # سایلنت
                if get_setting(self.owner_id, f"silent_chat_{chat_id}", "0") == "1":
                    return
                if get_setting(self.owner_id, f"silent_user_{sender_id}", "0") == "1":
                    return
                
                # ذخیره خودکار مدیا
                if get_setting(self.owner_id, "auto_save_media") == "1" and msg.media:
                    try:
                        media_dir = f"saved_media/{self.owner_id}"
                        os.makedirs(media_dir, exist_ok=True)
                        await self.client.download_media(msg, file=media_dir + "/")
                    except Exception:
                        pass
                
                # سین خودکار
                if get_setting(self.owner_id, "auto_seen_active") == "1":
                    try:
                        await self.client.send_read_acknowledge(chat_id, msg)
                    except Exception:
                        pass
                
                # منشی (فقط پیوی - با محدودیت 24 ساعت)
                if get_setting(self.owner_id, "secretary_active") == "1" and event.is_private:
                    now = time.time()
                    last_reply = self._last_secretary_reply.get(chat_id, 0)
                    if now - last_reply >= self.SECRETARY_COOLDOWN:
                        sec_msg = get_setting(self.owner_id, "secretary_message", "در حال حاضر در دسترس نیستم.")
                        try:
                            await event.reply(f"🤖 منشی خودکار:\n{sec_msg}")
                            self._last_secretary_reply[chat_id] = now
                        except Exception:
                            pass
                
                # ری‌اکشن خودکار (پیوی)
                if get_setting(self.owner_id, "auto_reaction_active") == "1":
                    emoji = get_setting(self.owner_id, "auto_reaction_emoji", "❤️")
                    try:
                        from telethon.tl.functions.messages import SendReactionRequest
                        from telethon.tl.types import ReactionEmoji
                        await self.client(SendReactionRequest(
                            peer=chat_id,
                            msg_id=msg.id,
                            reaction=[ReactionEmoji(emoticon=emoji)],
                            big=False,
                            add_to_recent=True
                        ))
                    except Exception:
                        pass
                
                # پاسخ خودکار به دوستان (فقط پیوی - با محدودیت 1 ساعت)
                if event.is_private and is_friend(self.owner_id, sender_id):
                    now = time.time()
                    last_reply = self._last_friend_reply.get(sender_id, 0)
                    if now - last_reply >= self.FRIEND_COOLDOWN:
                        try:
                            await event.reply(random.choice(FRIEND_REPLIES))
                            self._last_friend_reply[sender_id] = now
                        except Exception:
                            pass
                
                # پاسخ به دشمن (پیوی)
                if get_setting(self.owner_id, "enemy_reply_active") == "1" and is_enemy(self.owner_id, sender_id):
                    try:
                        await event.reply(random.choice(ENEMY_REPLIES))
                    except Exception:
                        pass
                
                # ضد لینک (فقط پیوی)
                if get_setting(self.owner_id, "anti_link_active") == "1" and event.is_private:
                    link_pattern = re.compile(r"(https?://\S+|t\.me/\S+|telegram\.me/\S+|www\.\S+)", re.IGNORECASE)
                    if link_pattern.search(text):
                        try:
                            await msg.delete()
                        except Exception:
                            pass
                
                # قفل پیوی
                if get_setting(self.owner_id, "private_lock_active") == "1" and event.is_private:
                    try:
                        await msg.delete()
                    except Exception:
                        pass
                
                # پاسخ به چالش ریاضی (در گروه)
                if chat_id == MATH_CHAT_ID and event.is_reply:
                    replied = await event.get_reply_message()
                    if replied:
                        challenge = get_math_challenge(self.owner_id)
                        if challenge and not challenge.get('solved') and replied.id == challenge['message_id']:
                            user_answer = text.strip()
                            if user_answer == challenge['correct_answer']:
                                account = get_account_by_tg_id(sender_id)
                                if account:
                                    add_tokens(account[1], 1)  # account[1] = owner_id
                                    await event.reply(
                                        f"🎉 **تبریک!** @{sender.username or sender.first_name}\n"
                                        f"✅ پاسخ صحیح! ۱ الماس به حساب شما اضافه شد."
                                    )
                                    solve_math_challenge(challenge['id'])
                                else:
                                    await event.reply(
                                        f"❌ شما در پنل ثبت‌نام نکرده‌اید!\n"
                                        f"لطفاً ابتدا در ربات ثبت‌نام کنید."
                                    )
                                    
            except Exception as e:
                print(f"خطا در on_incoming برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(outgoing=True))
        async def on_outgoing(event):
            try:
                self.last_activity = time.time()
                text = event.raw_text.strip()
                
                # دستورات همیشه فعال
                if text == "سلف روشن":
                    set_setting(self.owner_id, "self_bot_active", "1")
                    await self._safe_edit(event, "✅ سلف‌بات روشن شد.")
                    return
                if text == "سلف خاموش":
                    set_setting(self.owner_id, "self_bot_active", "0")
                    await self._safe_edit(event, "❌ سلف‌بات خاموش شد.")
                    return
                
                # لیست دستورات تنظیماتی
                config_commands = [
                    "منشی روشن", "منشی خاموش", "پیام منشی",
                    "ضد حذف روشن", "ضد حذف خاموش",
                    "ضد لینک روشن", "ضد لینک خاموش",
                    "قفل پیوی روشن", "قفل پیوی خاموش",
                    "سین خودکار روشن", "سین خودکار خاموش",
                    "ری‌اکشن روشن", "ری‌اکشن خاموش",
                    "ذخیره مدیا روشن", "ذخیره مدیا خاموش",
                    "ساعت نام روشن", "ساعت نام خاموش",
                    "ساعت بیو روشن", "ساعت بیو خاموش",
                    "پاسخ دشمن روشن", "پاسخ دشمن خاموش",
                    "تنظیم دشمن", "حذف دشمن", "نمایش لیست دشمن", "پاک کردن لیست دشمن",
                    "تنظیم دوست", "حذف دوست", "نمایش لیست دوست", "پاک کردن لیست دوست",
                    "فونت ", "لیست فونت",
                    "وضعیت", "راهنما", "help",
                    "حذف بعد ",
                    "توقف سیو",
                    "چالش ریاضی روشن", "چالش ریاضی خاموش",  # اضافه شده
                    "بازی تاس", "فوتبال", "بسکتبال", "دارت", "اسلات",  # اضافه شده
                ]
                
                is_config_command = any(text.startswith(cmd) or text == cmd for cmd in config_commands)
                
                # اگر دستور تنظیماتی نیست و سلف خاموش است، اجرا نکن
                if not is_config_command and get_setting(self.owner_id, "self_bot_active") != "1":
                    return
                
                await self._handle_command(event, text)
                
            except Exception as e:
                print(f"خطا در on_outgoing برای {self.phone}: {e}")
        
        print(f"✅ تمام هندلرها برای {self.phone} ثبت شدند")

    # ─── پردازش دستورات ──────────────────────────────────────────────────────
    async def _handle_command(self, event, text):
        msg = event.message
        
        def gs(key, default=None):
            return get_setting(self.owner_id, key, default)
        
        def ss(key, value):
            set_setting(self.owner_id, key, value)
        
        async def edit(t):
            await self._safe_edit(event, t)
        
        # ─── دشمن ────────────────────────────────────────────────────────────────
        if text.startswith("تنظیم دشمن"):
            target = await self._resolve_target(event, text.split())
            if target:
                add_enemy(self.owner_id, target["id"], target.get("username"), target.get("name"))
                await edit(f"🔴 {target.get('name', target['id'])} به لیست دشمن اضافه شد.")
            else:
                await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text.startswith("حذف دشمن"):
            target = await self._resolve_target(event, text.split())
            if target:
                remove_enemy(self.owner_id, target["id"])
                await edit("✅ از لیست دشمن حذف شد.")
            else:
                await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text == "نمایش لیست دشمن":
            enemies = get_enemies(self.owner_id)
            if not enemies:
                await edit("📋 لیست دشمن خالی است.")
            else:
                lines = [f"🔴 لیست دشمن ({len(enemies)} نفر):\n"]
                for e in enemies:
                    lines.append(f"• {e['name'] or e['username'] or e['user_id']} — `{e['user_id']}`")
                await edit("\n".join(lines))

        elif text == "پاک کردن لیست دشمن":
            clear_enemies(self.owner_id)
            await edit("🗑️ لیست دشمن پاک شد.")

        # ─── دوست ────────────────────────────────────────────────────────────────
        elif text.startswith("تنظیم دوست"):
            target = await self._resolve_target(event, text.split())
            if target:
                add_friend(self.owner_id, target["id"], target.get("username"), target.get("name"))
                await edit(f"💚 {target.get('name', target['id'])} به لیست دوست اضافه شد.")
            else:
                await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text.startswith("حذف دوست"):
            target = await self._resolve_target(event, text.split())
            if target:
                remove_friend(self.owner_id, target["id"])
                await edit("✅ از لیست دوست حذف شد.")
            else:
                await edit("❗ روی پیام کاربر ریپلای کن یا آیدی عددی بنویس.")

        elif text == "نمایش لیست دوست":
            friends = get_friends(self.owner_id)
            if not friends:
                await edit("📋 لیست دوست خالی است.")
            else:
                lines = [f"💚 لیست دوست ({len(friends)} نفر):\n"]
                for f in friends:
                    lines.append(f"• {f['name'] or f['username'] or f['user_id']} — `{f['user_id']}`")
                await edit("\n".join(lines))

        elif text == "پاک کردن لیست دوست":
            clear_friends(self.owner_id)
            await edit("🗑️ لیست دوست پاک شد.")

        # ─── منشی ────────────────────────────────────────────────────────────────
        elif text == "منشی روشن":
            ss("secretary_active", "1")
            await edit("🤖 منشی خودکار روشن شد.\n💡 هر کاربر فقط هر 24 ساعت یک بار پاسخ می‌گیرد.")
        elif text == "منشی خاموش":
            ss("secretary_active", "0")
            await edit("🤖 منشی خودکار خاموش شد.")
        elif text.startswith("پیام منشی "):
            ss("secretary_message", text[len("پیام منشی "):].strip())
            await edit("✅ پیام منشی تنظیم شد.")

        # ─── ضد حذف ──────────────────────────────────────────────────────────────
        elif text == "ضد حذف روشن":
            ss("anti_delete_active", "1")
            await edit("🛡️ ضد حذف روشن شد.")
        elif text == "ضد حذف خاموش":
            ss("anti_delete_active", "0")
            await edit("🛡️ ضد حذف خاموش شد.")

        # ─── ضد لینک ─────────────────────────────────────────────────────────────
        elif text == "ضد لینک روشن":
            ss("anti_link_active", "1")
            await edit("🔗 ضد لینک روشن شد.")
        elif text == "ضد لینک خاموش":
            ss("anti_link_active", "0")
            await edit("🔗 ضد لینک خاموش شد.")

        # ─── قفل پیوی ────────────────────────────────────────────────────────────
        elif text == "قفل پیوی روشن":
            ss("private_lock_active", "1")
            await edit("🔒 قفل پیوی روشن شد.")
        elif text == "قفل پیوی خاموش":
            ss("private_lock_active", "0")
            await edit("🔓 قفل پیوی خاموش شد.")

        # ─── سین خودکار ──────────────────────────────────────────────────────────
        elif text == "سین خودکار روشن":
            ss("auto_seen_active", "1")
            await edit("👁️ سین خودکار روشن شد.")
        elif text == "سین خودکار خاموش":
            ss("auto_seen_active", "0")
            await edit("👁️ سین خودکار خاموش شد.")

        # ─── ری‌اکشن ─────────────────────────────────────────────────────────────
        elif text == "ری‌اکشن روشن":
            ss("auto_reaction_active", "1")
            await edit("❤️ ری‌اکشن خودکار روشن شد.")
        elif text == "ری‌اکشن خاموش":
            ss("auto_reaction_active", "0")
            await edit("❤️ ری‌اکشن خودکار خاموش شد.")
        elif text.startswith("ری‌اکشن "):
            emoji = text[len("ری‌اکشن "):].strip()
            ss("auto_reaction_emoji", emoji)
            await edit(f"✅ ری‌اکشن پیش‌فرض: {emoji}")

        # ─── ذخیره مدیا ──────────────────────────────────────────────────────────
        elif text == "ذخیره مدیا روشن":
            os.makedirs(f"saved_media/{self.owner_id}", exist_ok=True)
            ss("auto_save_media", "1")
            await edit("💾 ذخیره خودکار مدیا روشن شد.")
        elif text == "ذخیره مدیا خاموش":
            ss("auto_save_media", "0")
            await edit("💾 ذخیره خودکار مدیا خاموش شد.")

        # ─── سیو کانال ───────────────────────────────────────────────────────────
        elif text.startswith("سیو کانال "):
            parts = text.split()
            channel_input = parts[2] if len(parts) >= 3 else None
            limit = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 100
            if not channel_input:
                await edit("❗ فرمت: سیو کانال [لینک یا آیدی] [تعداد اختیاری]")
            else:
                await edit(f"⏳ در حال پردازش کانال، تا {limit} مدیا ذخیره می‌شود...")
                asyncio.create_task(self._save_channel_media(channel_input, limit))

        elif text == "توقف سیو":
            ss("channel_save_active", "0")
            await edit("🛑 سیو کانال متوقف شد.")

        # ─── پاسخ دشمن ───────────────────────────────────────────────────────────
        elif text == "پاسخ دشمن روشن":
            ss("enemy_reply_active", "1")
            await edit("⚔️ پاسخ خودکار به دشمن روشن شد.")
        elif text == "پاسخ دشمن خاموش":
            ss("enemy_reply_active", "0")
            await edit("⚔️ پاسخ خودکار به دشمن خاموش شد.")

        # ─── فونت ────────────────────────────────────────────────────────────────
        elif text.startswith("فونت "):
            parts = text.split()
            if len(parts) >= 2:
                last_part = parts[-1]
                if last_part.isdigit() and last_part in FONTS:
                    font_id = last_part
                    if len(parts) > 2:
                        text_to_convert = text.replace("فونت ", "").replace(f" {font_id}", "")
                        if text_to_convert:
                            fn = FONTS.get(font_id, FONTS["0"])
                            converted = fn(text_to_convert)
                            ss("selected_font", font_id)
                            await edit(f"🔤 {converted}\n\n✅ فونت {font_id} برای متن «{text_to_convert}» اعمال شد.")
                        else:
                            ss("selected_font", font_id)
                            await edit(f"🔤 فونت {font_id} انتخاب شد.\nاین فونت روی پیام‌ها و ساعت اعمال می‌شود.")
                    else:
                        ss("selected_font", font_id)
                        await edit(f"🔤 فونت {font_id} انتخاب شد.\nاین فونت روی پیام‌ها و ساعت اعمال می‌شود.")
                else:
                    await edit("❗ آخرین قسمت باید شماره فونت باشد (۰ تا ۸).")
            else:
                await edit("❗ فرمت: فونت [متن] [شماره] یا فونت [شماره]")
        
        elif text == "لیست فونت":
            test_text = "امیر"
            samples = {
                "0": "متن عادی",
                "1": "𝗕𝗼𝗹𝗱 𝗦𝗮𝗻𝘀", 
                "2": "𝘐𝘵𝘢𝘭𝘪𝘤 𝘚𝘢𝘯𝘴",
                "3": "𝙼𝚘𝚗𝚘𝚜𝚙𝚊𝚌𝚎",
                "4": "Ｆｕｌｌｗｉｄｔｈ",
                "5": "𝐒𝐞𝐫𝐢𝐟 𝐁𝐨𝐥𝐝",
                "6": "𝒮𝒸𝓇𝒾𝓅𝓉",
                "7": "S̶t̶r̶i̶k̶e̶t̶h̶r̶o̶u̶g̶h̶",
                "8": "U̲n̲d̲e̲r̲l̲i̲n̲e̲"
            }
            
            lines = ["📝 لیست فونت‌ها با نمونه:\n"]
            lines.append("─" * 35)
            
            for k, v in samples.items():
                fn = FONTS.get(k, FONTS["0"])
                converted = fn(test_text)
                lines.append(f"فونت {k} — {v}:")
                lines.append(f"  `{converted}`")
                lines.append("")
            
            lines.append("─" * 35)
            lines.append("\n💡 استفاده: فونت [متن] [شماره]")
            lines.append("مثال: `فونت امیر 3`")
            lines.append("یا: `فونت 3` برای تنظیم فونت پیش‌فرض")
            
            await edit("\n".join(lines))

        # ─── ساعت ────────────────────────────────────────────────────────────────
        elif text == "ساعت نام روشن":
            ss("clock_name_active", "1")
            await edit("⏰ ساعت در نام روشن شد.\n💡 فونت فعلی روی ساعت اعمال می‌شود.")
        elif text == "ساعت نام خاموش":
            ss("clock_name_active", "0")
            await edit("⏰ ساعت در نام خاموش شد.")
        elif text == "ساعت بیو روشن":
            ss("clock_bio_active", "1")
            await edit("⏰ ساعت در بیو روشن شد.\n💡 فونت فعلی روی ساعت اعمال می‌شود.")
        elif text == "ساعت بیو خاموش":
            ss("clock_bio_active", "0")
            await edit("⏰ ساعت در بیو خاموش شد.")

        # ─── چالش ریاضی ─────────────────────────────────────────────────────────
        elif text == "چالش ریاضی روشن":
            if not self.is_owner_user:
                await edit("❌ فقط مالک می‌تواند چالش ریاضی را فعال کند!")
                return
            set_challenge_setting(self.owner_id, "math_challenge_active", 1)
            await edit("🧮 چالش ریاضی روشن شد.\nهر ۲ ساعت یک چالش در گروه ارسال می‌شود.")
        elif text == "چالش ریاضی خاموش":
            if not self.is_owner_user:
                await edit("❌ فقط مالک می‌تواند چالش ریاضی را غیرفعال کند!")
                return
            set_challenge_setting(self.owner_id, "math_challenge_active", 0)
            await edit("🧮 چالش ریاضی خاموش شد.")

        # ─── بازی‌ها ─────────────────────────────────────────────────────────────
        elif text == "بازی تاس":
            await self.client.send_file(event.chat_id, InputMediaDice('🎲'))
            await msg.delete()
        elif text == "فوتبال":
            await self.client.send_file(event.chat_id, InputMediaDice('⚽'))
            await msg.delete()
        elif text == "بسکتبال":
            await self.client.send_file(event.chat_id, InputMediaDice('🏀'))
            await msg.delete()
        elif text == "دارت":
            await self.client.send_file(event.chat_id, InputMediaDice('🎯'))
            await msg.delete()
        elif text == "اسلات":
            await self.client.send_file(event.chat_id, InputMediaDice('🎰'))
            await msg.delete()

        # ─── اسپم ────────────────────────────────────────────────────────────────
        elif text.startswith("اسپم "):
            parts = text.split(" ", 2)
            if len(parts) >= 3 and parts[1].isdigit():
                count = min(int(parts[1]), 50)
                spam_text = parts[2]
                ss("spam_active", "1")
                await edit(f"💣 اسپم شروع شد — {count} بار")
                chat = await event.get_chat()
                asyncio.create_task(self._do_spam(chat.id, spam_text, count))
            else:
                await edit("❗ فرمت: اسپم [تعداد] [متن]")
        elif text == "توقف اسپم":
            ss("spam_active", "0")
            await edit("🛑 اسپم متوقف شد.")

        # ─── حذف خودکار ──────────────────────────────────────────────────────────
        elif text.startswith("حذف بعد "):
            parts = text.split()
            if len(parts) >= 3 and parts[2].isdigit():
                secs = int(parts[2])
                await edit(f"⏱️ پیام بعد از {secs} ثانیه حذف می‌شود.")
                await asyncio.sleep(secs)
                try:
                    await msg.delete()
                except Exception:
                    pass

        # ─── ذخیره پیام ──────────────────────────────────────────────────────────
        elif text.startswith("ذخیره "):
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                slot = int(parts[1])
                if 1 <= slot <= 10:
                    replied = await event.get_reply_message()
                    if replied:
                        save_message_slot(self.owner_id, slot, replied.text or "")
                        await edit(f"💾 پیام در اسلات {slot} ذخیره شد.")
                    else:
                        await edit("❗ روی پیام مورد نظر ریپلای کن.")
                else:
                    await edit("❗ اسلات باید بین ۱ تا ۱۰ باشد.")

        elif text.startswith("ارسال ذخیره "):
            parts = text.split()
            if len(parts) >= 3 and parts[2].isdigit():
                slot = int(parts[2])
                saved = get_message_slot(self.owner_id, slot)
                if saved:
                    chat = await event.get_chat()
                    await self.client.send_message(chat.id, saved["content"])
                    await msg.delete()
                else:
                    await edit(f"❗ اسلات {slot} خالی است.")

        # ─── وضعیت ───────────────────────────────────────────────────────────────
        elif text == "وضعیت":
            status_map = {
                "self_bot_active": "سلف‌بات", "secretary_active": "منشی",
                "anti_delete_active": "ضد حذف", "anti_link_active": "ضد لینک",
                "auto_seen_active": "سین خودکار", "auto_reaction_active": "ری‌اکشن",
                "private_lock_active": "قفل پیوی", "enemy_reply_active": "پاسخ دشمن",
                "auto_save_media": "ذخیره مدیا", "clock_name_active": "ساعت نام",
                "clock_bio_active": "ساعت بیو",
            }
            lines = [f"📊 وضعیت NexoSelf\n"]
            for key, label in status_map.items():
                icon = "✅" if gs(key) == "1" else "❌"
                lines.append(f"{icon} {label}")
            lines.append(f"\n🔤 فونت: {gs('selected_font', '0')}")
            lines.append(f"👥 دشمن: {len(get_enemies(self.owner_id))} نفر")
            lines.append(f"💚 دوست: {len(get_friends(self.owner_id))} نفر")
            await edit("\n".join(lines))

        # ─── راهنما ───────────────────────────────────────────────────────────────
        elif text in ("راهنما", "help"):
            await edit(self._help_text())

        # ─── ارسال زمان‌بندی شده ─────────────────────────────────────────────────
        elif text.startswith("ارسال زمان‌بندی "):
            m = re.match(r"^ارسال زمان‌بندی (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) (.+)$", text, re.DOTALL)
            if m:
                chat = await event.get_chat()
                add_scheduled_message(self.owner_id, chat.id, m.group(2), m.group(1) + ":00")
                await edit(f"📅 پیام در {m.group(1)} ارسال خواهد شد.")
            else:
                await edit("❗ فرمت: ارسال زمان‌بندی [YYYY-MM-DD HH:MM] متن")

    # ─── توابع کمکی ──────────────────────────────────────────────────────────
    async def _safe_edit(self, event, text):
        try:
            font_id = get_setting(self.owner_id, "selected_font", "0")
            fn = FONTS.get(font_id, FONTS["0"])
            await event.edit(fn(text))
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
        except Exception:
            pass

    async def _resolve_target(self, event, parts):
        replied = await event.get_reply_message()
        if replied:
            sender = await replied.get_sender()
            if sender:
                return {
                    "id": sender.id,
                    "username": getattr(sender, "username", None),
                    "name": getattr(sender, "first_name", str(sender.id)),
                }
        for p in parts[1:]:
            if p.lstrip("-").isdigit():
                return {"id": int(p), "username": None, "name": p}
        return None

    async def _do_spam(self, chat_id, text, count):
        delay = float(get_setting(self.owner_id, "spam_delay", "2"))
        for _ in range(count):
            if get_setting(self.owner_id, "spam_active") != "1":
                break
            try:
                await self.client.send_message(chat_id, text)
                await asyncio.sleep(delay)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 1)
            except Exception:
                break
        set_setting(self.owner_id, "spam_active", "0")

    async def _save_channel_media(self, channel_input, limit):
        set_setting(self.owner_id, "channel_save_active", "1")
        media_dir = f"saved_media/{self.owner_id}"
        os.makedirs(media_dir, exist_ok=True)
        try:
            me = await self.client.get_me()
            if channel_input.startswith("https://t.me/"):
                channel_input = channel_input.replace("https://t.me/", "")
            if channel_input.startswith("@"):
                channel_input = channel_input[1:]

            saved = skipped = 0
            async for msg in self.client.iter_messages(channel_input, limit=limit):
                if get_setting(self.owner_id, "channel_save_active") != "1":
                    break
                if msg.media:
                    try:
                        path = await self.client.download_media(msg, file=media_dir + "/")
                        if path:
                            caption = f"📥 سیو کانال\n📌 پیام #{msg.id}"
                            if msg.text:
                                caption += f"\n📝 {msg.text[:100]}"
                            await self.client.send_file(me.id, path, caption=caption)
                            saved += 1
                            await asyncio.sleep(0.1)
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds + 2)
                    except Exception:
                        skipped += 1
                else:
                    skipped += 1

            set_setting(self.owner_id, "channel_save_active", "0")
            await self.client.send_message(me.id,
                f"✅ سیو کانال تموم شد\n💾 ذخیره شد: {saved}\n⏭ رد شد: {skipped}")
        except Exception as e:
            set_setting(self.owner_id, "channel_save_active", "0")
            try:
                me = await self.client.get_me()
                await self.client.send_message(me.id, f"❌ خطا در سیو کانال: {e}")
            except Exception:
                pass

    def _help_text(self):
        return """📖 راهنمای NexoSelf

🔹 اصلی:
• سلف روشن / سلف خاموش
• وضعیت

🔹 لیست‌ها:
• تنظیم دشمن / حذف دشمن [ریپلای یا آیدی]
• نمایش لیست دشمن / پاک کردن لیست دشمن
• تنظیم دوست / حذف دوست
• نمایش لیست دوست / پاک کردن لیست دوست

🔹 منشی:
• منشی روشن / خاموش
• پیام منشی [متن]
💡 هر کاربر فقط هر 24 ساعت یک بار پاسخ می‌گیرد

🔹 امنیت:
• ضد حذف روشن / خاموش
• ضد لینک روشن / خاموش
• قفل پیوی روشن / خاموش
• پاسخ دشمن روشن / خاموش

🔹 اتوماسیون:
• سین خودکار روشن / خاموش
• ری‌اکشن روشن / خاموش / [ایموجی]
• ذخیره مدیا روشن / خاموش
• ساعت نام روشن / خاموش
• ساعت بیو روشن / خاموش

🔹 چالش‌ها و بازی‌ها (فقط مالک):
• چالش ریاضی روشن / خاموش
• بازی تاس
• فوتبال
• بسکتبال
• دارت
• اسلات

🔹 ابزار:
• حذف بعد [ثانیه]

🔹 اسپم:
• اسپم [تعداد] [متن]
• توقف اسپم

🔹 پیام:
• ذخیره [1-10] — ریپلای
• ارسال ذخیره [1-10]
• ارسال زمان‌بندی [YYYY-MM-DD HH:MM] متن

🔹 سیو مدیا:
• سیو کانال [@یوزرنیم یا لینک] [تعداد]
• توقف سیو

🔹 فونت:
• فونت [متن] [شماره] — تبدیل متن به فونت دلخواه
• فونت [شماره] — تغییر فونت پیش‌فرض
• لیست فونت — نمایش نمونه‌ها

💡 نکته: فونت انتخابی روی ساعت نام/بیو هم اعمال می‌شود!
💡 نکته: در گروه‌ها پاسخ به دشمن و ری‌اکشن حتی بدون تگ کار می‌کند!
💡 نکته: پاسخ به دوستان هر 1 ساعت یک بار!
"""

    # ─── حلقه‌های پس‌زمینه ──────────────────────────────────────────────────────
    async def safe_update_profile_time(self):
        while self.is_running and not self.shutdown_requested:
            try:
                await self._clock_loop()
            except Exception as e:
                print(f"⚠️ خطا در به‌روزرسانی زمان برای {self.phone}: {e}")
                await asyncio.sleep(60)

    async def _clock_loop(self):
        last_minute = -1
        
        while self.is_running and not self.shutdown_requested:
            try:
                iran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
                now = datetime.now(iran_tz)
                current_minute = now.minute
                
                if current_minute != last_minute:
                    last_minute = current_minute
                    time_str = f"{now.hour:02d}:{now.minute:02d}"
                    
                    font_id = get_setting(self.owner_id, "selected_font", "0")
                    fn = FONTS.get(font_id, FONTS["0"])
                    styled_time = fn(time_str)
                    
                    if get_setting(self.owner_id, "clock_name_active") == "1":
                        try:
                            await self.client(UpdateProfileRequest(last_name=styled_time[:64]))
                            print(f"⏰ [{self.phone}] ساعت نام به‌روز شد: {styled_time}")
                        except Exception as e:
                            print(f"❌ خطا در به‌روزرسانی نام: {e}")
                    
                    if get_setting(self.owner_id, "clock_bio_active") == "1":
                        try:
                            await self.client(UpdateProfileRequest(about=f"⏰ {styled_time}"[:70]))
                            print(f"⏰ [{self.phone}] ساعت بیو به‌روز شد: {styled_time}")
                        except Exception as e:
                            print(f"❌ خطا در به‌روزرسانی بیو: {e}")
                
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"❌ خطا در _clock_loop: {e}")
                await asyncio.sleep(10)

    async def _scheduler_loop(self):
        while self.is_running and not self.shutdown_requested:
            try:
                for p in get_pending_scheduled(self.owner_id):
                    try:
                        await self.client.send_message(p["chat_id"], p["message"])
                        mark_scheduled_sent(p["id"])
                    except Exception:
                        pass
            except Exception:
                pass
            await asyncio.sleep(30)

    async def _math_challenge_loop(self):
        """حلقه ارسال چالش ریاضی هر ۲ ساعت (فقط مالک)"""
        while self.is_running and not self.shutdown_requested:
            try:
                settings = get_challenge_settings(self.owner_id)
                if not settings.get('math_challenge_active', False):
                    await asyncio.sleep(30)
                    continue
                
                operations = ['+', '-', '×']
                op = random.choice(operations)
                
                if op == '+':
                    a = random.randint(10, 99)
                    b = random.randint(10, 99)
                    answer = str(a + b)
                    question = f"{a} + {b} = ?"
                elif op == '-':
                    a = random.randint(20, 99)
                    b = random.randint(10, a - 1)
                    answer = str(a - b)
                    question = f"{a} - {b} = ?"
                else:
                    a = random.randint(2, 12)
                    b = random.randint(2, 12)
                    answer = str(a * b)
                    question = f"{a} × {b} = ?"
                
                msg = await self.client.send_message(
                    MATH_CHAT_ID,
                    f"🧮 **چالش ریاضی!**\n\n"
                    f"❓ {question}\n\n"
                    f"⏱️ اولین نفر با پاسخ صحیح برنده ۱ الماس می‌شود!\n"
                    f"📝 پاسخ را به صورت عدد لاتین ریپلای کنید."
                )
                
                create_math_challenge(self.owner_id, question, answer, MATH_CHAT_ID, msg.id)
                
                await asyncio.sleep(7200)  # 2 ساعت
                
                challenge = get_math_challenge(self.owner_id)
                if challenge and not challenge.get('solved'):
                    await self.client.send_message(
                        MATH_CHAT_ID,
                        f"⏰ زمان چالش ریاضی به پایان رسید!\n"
                        f"پاسخ صحیح: `{answer}`"
                    )
                    solve_math_challenge(challenge['id'])
                    
            except Exception as e:
                print(f"❌ خطا در math_challenge_loop: {e}")
                await asyncio.sleep(60)

    # ─── اجرای اصلی ──────────────────────────────────────────────────────────
    async def run(self):
        try:
            success = await self.robust_initialize()
            if success:
                print(f"🚀 اکانت {self.phone} در حال اجرا است...")
                await self.client.run_until_disconnected()
            else:
                print(f"❌ اکانت {self.phone} راه‌اندازی نشد")
        except Exception as e:
            print(f"❌ خطا در اجرای اکانت {self.phone}: {e}")
        finally:
            self.is_running = False

# ─── توابع عمومی ────────────────────────────────────────────────────────────
async def create_session_file(phone, session_file):
    try:
        print(f"📱 ایجاد سشن جدید برای {phone}...")
        
        client = TelegramClient(StringSession(), API_ID, API_HASH,
                              device_model="iPhone 15 Pro",
                              system_version="iOS 17.1",
                              app_version="10.0.0")
        
        await client.connect()
        
        sent_code = await client.send_code_request(phone)
        print(f"✅ کد تأیید برای {phone} ارسال شد")
        
        code = input(f"📝 لطفاً کد تأیید ارسال شده برای {phone} را وارد کنید: ").strip()
        
        try:
            await client.sign_in(phone, code)
            print(f"✅ لاگین موفقیت‌آمیز برای {phone}")
        except SessionPasswordNeededError:
            password = input("🔐 لطفاً رمز دو مرحله‌ای را وارد کنید: ")
            await client.sign_in(password=password)
            print(f"✅ لاگین با رمز دو مرحله‌ای موفقیت‌آمیز برای {phone}")
        
        session_string = client.session.save()
        with open(session_file, 'w') as f:
            f.write(session_string)
        
        print(f"✅ سشن برای {phone} در {session_file} ذخیره شد")
        await client.disconnect()
        return session_string
        
    except Exception as e:
        print(f"❌ خطا در ایجاد سشن برای {phone}: {e}")
        return None

async def main():
    if len(sys.argv) < 3:
        print("""
🚀 **راه‌اندازی NexoSelf**

📝 **نحوه استفاده:**
├ • افزودن اکانت جدید:
│   python script.py <phone> <session_file>
│
├ • اجرای تمام اکانت‌ها:
│   python script.py --multi
│
├ • ایجاد سشن جدید:
│   python script.py --create <phone> <session_file>
└
📞 **مثال‌ها:**
├ • python script.py +1234567890 session1.txt
├ • python script.py --multi
└ • python script.py --create +1234567890 newsession.txt
        """)
        sys.exit(1)
    
    account_manager = AccountManager()
    
    if sys.argv[1] == "--create":
        if len(sys.argv) < 4:
            print("❌ لطفاً شماره و نام فایل سشن را وارد کنید")
            sys.exit(1)
        
        phone = sys.argv[2]
        session_file = sys.argv[3]
        
        session_string = await create_session_file(phone, session_file)
        if session_string:
            account_manager.add_account(phone, session_string)
            print(f"✅ اکانت {phone} با موفقیت اضافه شد")
        else:
            print(f"❌ خطا در ایجاد سشن برای {phone}")
        
    elif sys.argv[1] == "--multi":
        print("🔧 راه‌اندازی حالت چند اکانته...")
        accounts = account_manager.get_all_accounts()
        
        if not accounts:
            print("❌ هیچ اکانتی در دیتابیس یافت نشد.")
            print("برای افزودن اکانت از دستور زیر استفاده کنید:")
            print("python script.py --create <phone> <session_file>")
            sys.exit(1)
        
        print(f"✅ تعداد {len(accounts)} اکانت برای راه‌اندازی یافت شد")
        
        tasks = []
        for phone, session_string in accounts:
            print(f"🔄 راه‌اندازی اکانت {phone}...")
            account = TelegramAccount(phone, session_string, account_manager)
            task = asyncio.create_task(account.run())
            tasks.append(task)
            await asyncio.sleep(3)
        
        print("🚀 تمام اکانت‌ها در حال اجرا هستند...")
        await asyncio.gather(*tasks, return_exceptions=True)
        
    else:
        phone = sys.argv[1]
        session_file = sys.argv[2]
        
        if not os.path.exists(session_file):
            print(f"❌ فایل سشن {session_file} یافت نشد.")
            print("برای ایجاد سشن جدید از دستور زیر استفاده کنید:")
            print(f"python script.py --create {phone} {session_file}")
            sys.exit(1)
        
        try:
            with open(session_file, 'r') as f:
                session_str = f.read().strip()
        except Exception as e:
            print(f"❌ خطا در خواندن فایل سشن: {e}")
            sys.exit(1)
        
        if not session_str:
            print(f"❌ فایل سشن {session_file} خالی است.")
            print("برای ایجاد سشن جدید از دستور زیر استفاده کنید:")
            print(f"python script.py --create {phone} {session_file}")
            sys.exit(1)
        
        account_manager.add_account(phone, session_str)
        
        print(f"🔄 راه‌اندازی اکانت {phone}...")
        account = TelegramAccount(phone, session_str, account_manager)
        await account.run()

if __name__ == '__main__':
    try:
        print("""
┌────────────────────
│  🚀 **NexoSelf راه‌اندازی شد**  
│  🔮 **قدرت گرفته از:** @Ch_SelfNexo
└─────────────────────
        """)
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹ **برنامه توسط کاربر متوقف شد**")
    except Exception as e:
        print(f"❌ **خطای غیرمنتظره:** {e}")
