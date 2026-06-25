"""
🤖 بوت تليجرام Flask + Supabase
يعمل على GitHub Actions مع Polling
"""

import os
import logging
import asyncio
import threading
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from supabase import create_client, Client
import requests

load_dotenv()

# ==================== الإعدادات الأساسية ====================

app = Flask(__name__)

# الـ Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# البيانات الحساسة من Environment
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("=" * 60)
print("🚀 بوت Flask + Telegram يبدأ...")
print("=" * 60)

print(f"✅ BOT_TOKEN: {'موجود' if BOT_TOKEN else '❌ ناقص'}")
print(f"✅ ADMIN_ID: {ADMIN_ID if ADMIN_ID != 0 else '❌ ناقص'}")
print(f"✅ SUPABASE_URL: {'موجود' if SUPABASE_URL else '❌ ناقص'}")
print(f"✅ SUPABASE_KEY: {'موجود' if SUPABASE_KEY else '❌ ناقص'}")
print("=" * 60)

# ==================== الاتصال بـ Supabase ====================

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ متصل بـ Supabase!")
    except Exception as e:
        print(f"❌ خطأ الاتصال بـ Supabase: {e}")
else:
    print("❌ بيانات Supabase ناقصة!")

# ==================== متغيرات Global ====================

last_update_id = 0
polling_active = True

# ==================== دوال Telegram API ====================

def send_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """إرسال رسالة عبر Telegram API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        result = response.json()
        if result.get("ok"):
            logger.info(f"📤 رسالة مرسلة للـ chat {chat_id}")
            return True
        else:
            logger.error(f"❌ فشل الإرسال: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ خطأ الإرسال: {e}")
        return False

def get_updates(timeout: int = 30):
    """جلب التحديثات من Telegram"""
    global last_update_id
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    payload = {
        "offset": last_update_id + 1,
        "timeout": timeout,
        "allowed_updates": ["message", "callback_query"]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=timeout + 5)
        result = response.json()
        
        if result.get("ok"):
            return result.get("result", [])
        else:
            logger.error(f"❌ خطأ جلب التحديثات: {result}")
            return []
    except Exception as e:
        logger.error(f"❌ خطأ الاتصال: {e}")
        return []

# ==================== دوال قاعدة البيانات ====================

def save_user_to_db(user_id: int, username: str = None, full_name: str = None):
    """حفظ المستخدم في Supabase"""
    if not supabase:
        logger.warning(f"⚠️ قاعدة البيانات غير متصلة")
        return False
    
    try:
        data = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "last_message_at": datetime.utcnow().isoformat()
        }
        supabase.table("users").upsert(data, on_conflict="user_id").execute()
        logger.info(f"✅ تم حفظ المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ حفظ المستخدم: {e}")
        return False

def save_message_to_db(user_id: int, message_text: str, message_type: str = "user"):
    """حفظ الرسالة في Supabase"""
    if not supabase:
        return False
    
    try:
        data = {
            "user_id": user_id,
            "message": message_text,
            "message_type": message_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("messages").insert(data).execute()
        logger.info(f"💾 تم حفظ الرسالة من {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ حفظ الرسالة: {e}")
        return False

def get_user_stats():
    """الحصول على إحصائيات المستخدمين"""
    if not supabase:
        return 0, []
    
    try:
        response = supabase.table("users").select("*").execute()
        return len(response.data), response.data
    except Exception as e:
        logger.error(f"❌ خطأ جلب الإحصائيات: {e}")
        return 0, []

# ==================== معالجات الأوامر ====================

def handle_start(chat_id: int, user: dict):
    """معالج /start"""
    save_user_to_db(user['id'], user.get('username'), user.get('first_name'))
    
    text = (
        "🎉 <b>أهلاً بك في بوت التواصل!</b>\n\n"
        "📝 يمكنك إرسال رسالتك وسيتم الرد عليك من الدعم الفني.\n\n"
        f"👤 <b>اسمك:</b> {user.get('first_name', 'زائر')}"
    )
    send_message(chat_id, text)

def handle_help(chat_id: int):
    """معالج /help"""
    text = (
        "🤖 <b>أوامر البوت:</b>\n\n"
        "/start - بدء البوت\n"
        "/help - هذه الرسالة\n\n"
        "<b>للآدمن:</b>\n"
        "/stats - إحصائيات\n"
        "/broadcast - رسالة جماعية"
    )
    send_message(chat_id, text)

def handle_stats(chat_id: int):
    """معالج /stats"""
    if chat_id != ADMIN_ID:
        send_message(chat_id, "🚫 عذراً، أنت غير مصرح!")
        return
    
    count, users = get_user_stats()
    text = (
        f"📊 <b>إحصائيات البوت:</b>\n\n"
        f"👥 <b>عدد المستخدمين:</b> {count}\n"
        f"🔌 <b>حالة الاتصال:</b> ✅ متصل"
    )
    
    if count > 0 and count <= 5:
        text += "\n\n<b>المستخدمون:</b>\n"
        for user in users:
            text += f"• {user['full_name']} (@{user['username']})\n"
    
    send_message(chat_id, text)

def handle_broadcast(chat_id: int, message: str):
    """معالج /broadcast"""
    if chat_id != ADMIN_ID:
        send_message(chat_id, "🚫 غير مصرح!")
        return
    
    if not supabase:
        send_message(chat_id, "❌ قاعدة البيانات غير متصلة!")
        return
    
    try:
        response = supabase.table("users").select("user_id").execute()
        users = response.data
        
        if not users:
            send_message(chat_id, "❌ لا يوجد مستخدمين!")
            return
        
        success = 0
        for user in users:
            user_id = int(user["user_id"])
            if user_id != ADMIN_ID:
                text = f"📢 <b>رسالة مهمة:</b>\n\n{message}"
                if send_message(user_id, text):
                    success += 1
                asyncio.sleep(0.05)  # منع الـ rate limiting
        
        send_message(chat_id, f"✅ تم الإرسال إلى {success} مستخدم")
    except Exception as e:
        send_message(chat_id, f"❌ خطأ: {e}")

def handle_user_message(user_id: int, chat_id: int, message_text: str, user: dict):
    """معالج الرسائل العادية"""
    save_user_to_db(user_id, user.get('username'), user.get('first_name'))
    save_message_to_db(user_id, message_text, "user")
    
    # إرسال للآدمن
    admin_text = (
        f"📩 <b>رسالة جديدة من</b> {user.get('first_name', 'مستخدم')}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{user.get('username', 'لا يوجد')}\n\n"
        f"━━━━━━━━━━━━━━━━\n{message_text}"
    )
    send_message(ADMIN_ID, admin_text)
    
    # رسالة تأكيد للمستخدم
    user_text = (
        "✅ <b>شكراً!</b> تم استقبال رسالتك\n"
        "⏳ سيتم الرد عليك قريباً"
    )
    send_message(chat_id, user_text)

def handle_admin_reply(admin_message: str):
    """معالج رد من الآدمن"""
    # هذا يفترض أن الآدمن يرد على الرسالة الأصلية
    # نحتاج معالجة إضافية للـ reply
    pass

# ==================== معالجة التحديثات ====================

def process_update(update: dict):
    """معالجة تحديث واحد"""
    global last_update_id
    
    try:
        update_id = update.get("update_id")
        last_update_id = max(last_update_id, update_id)
        
        # رسالة عادية
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            user = message["from"]
            user_id = user["id"]
            message_text = message.get("text", "")
            
            logger.info(f"📨 رسالة من {user_id}: {message_text}")
            
            # معالجة الأوامر
            if message_text.startswith("/start"):
                handle_start(chat_id, user)
            
            elif message_text.startswith("/help"):
                handle_help(chat_id)
            
            elif message_text.startswith("/stats"):
                handle_stats(chat_id)
            
            elif message_text.startswith("/broadcast "):
                broadcast_msg = message_text.replace("/broadcast ", "", 1)
                handle_broadcast(chat_id, broadcast_msg)
            
            else:
                # رسالة عادية
                handle_user_message(user_id, chat_id, message_text, user)
    
    except Exception as e:
        logger.error(f"❌ خطأ معالجة التحديث: {e}")

# ==================== Polling Thread ====================

def polling_loop():
    """حلقة الـ polling الرئيسية"""
    global polling_active
    
    logger.info("🔄 بدء حلقة الـ polling...")
    
    while polling_active:
        try:
            updates = get_updates(timeout=20)
            
            for update in updates:
                process_update(update)
            
            if not updates:
                logger.debug("⏳ لا توجد تحديثات جديدة")
        
        except KeyboardInterrupt:
            logger.info("⏹️ إيقاف الـ polling...")
            polling_active = False
            break
        except Exception as e:
            logger.error(f"❌ خطأ في حلقة الـ polling: {e}")
            asyncio.sleep(5)

# ==================== مسارات Flask ====================

@app.route('/', methods=['GET'])
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        "status": "ok",
        "bot": "telegram_bot",
        "version": "1.0",
        "framework": "Flask",
        "database": "Supabase"
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """فحص صحة السيرفر"""
    return jsonify({
        "status": "ok",
        "bot_token": "present" if BOT_TOKEN else "missing",
        "database": "connected" if supabase else "disconnected",
        "polling": "active" if polling_active else "inactive"
    }), 200

@app.route('/stats', methods=['GET'])
def stats_api():
    """API للإحصائيات"""
    count, users = get_user_stats()
    return jsonify({
        "total_users": count,
        "users": users
    }), 200

# ==================== البرنامج الرئيسي ====================

def main():
    """الدالة الرئيسية"""
    
    # تحقق من البيانات الأساسية
    if not BOT_TOKEN or ADMIN_ID == 0:
        logger.error("❌ خطأ: BOT_TOKEN أو ADMIN_ID ناقص!")
        return
    
    # ابدأ حلقة الـ polling في thread منفصل
    polling_thread = threading.Thread(target=polling_loop, daemon=True)
    polling_thread.start()
    logger.info("✅ تم بدء thread الـ polling")
    
    # ابدأ Flask
    logger.info("🌐 Flask يعمل على المنفذ 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()        logger.error(f"❌ خطأ الاتصال: {e}")

# ==================== دوال المساعدة ====================

def send_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """إرسال رسالة عبر Telegram Bot API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"❌ خطأ الإرسال: {e}")
        return None

def save_user_to_db(user_id: int, username: str = None, full_name: str = None):
    """حفظ المستخدم في Supabase"""
    if not supabase:
        return False
    
    try:
        data = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "last_message_at": datetime.utcnow().isoformat()
        }
        supabase.table("users").upsert(data, on_conflict="user_id").execute()
        logger.info(f"✅ تم حفظ المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ حفظ المستخدم: {e}")
        return False

def save_message_to_db(user_id: int, message_text: str, message_type: str = "user"):
    """حفظ الرسالة في قاعدة البيانات"""
    if not supabase:
        return False
    
    try:
        data = {
            "user_id": user_id,
            "message": message_text,
            "message_type": message_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("messages").insert(data).execute()
        logger.info(f"💾 تم حفظ الرسالة من {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ حفظ الرسالة: {e}")
        return False

# ==================== معالجات الأحداث ====================

def handle_start(chat_id: int, user):
    """معالج أمر /start"""
    save_user_to_db(user['id'], user.get('username'), user.get('first_name'))
    
    text = (
        "🎉 أهلاً بك في بوت التواصل!\n\n"
        "📝 يمكنك إرسال رسالتك وسيتم الرد عليك من الدعم الفني.\n\n"
        f"👤 اسمك: {user.get('first_name', 'زائر')}"
    )
    send_message(chat_id, text)

def handle_stats(chat_id: int):
    """معالج أمر /stats (للآدمن فقط)"""
    if chat_id != ADMIN_ID:
        send_message(chat_id, "🚫 عذراً، أنت غير مصرح!")
        return
    
    if not supabase:
        send_message(chat_id, "❌ قاعدة البيانات غير متصلة!")
        return
    
    try:
        response = supabase.table("users").select("*").execute()
        users_count = len(response.data)
        
        text = (
            f"📊 <b>إحصائيات البوت:</b>\n\n"
            f"👥 عدد المستخدمين: {users_count}\n"
            f"🔌 حالة الاتصال: ✅ متصل"
        )
        send_message(chat_id, text, parse_mode="HTML")
    except Exception as e:
        send_message(chat_id, f"❌ خطأ: {e}")

def handle_broadcast(chat_id: int, message: str):
    """معالج أمر /broadcast (للآدمن فقط)"""
    if chat_id != ADMIN_ID:
        send_message(chat_id, "🚫 غير مصرح!")
        return
    
    if not supabase:
        send_message(chat_id, "❌ قاعدة البيانات غير متصلة!")
        return
    
    try:
        response = supabase.table("users").select("user_id").execute()
        users = response.data
        
        success = 0
        for user in users:
            user_id = int(user["user_id"])
            if user_id != ADMIN_ID:
                send_message(user_id, f"📢 <b>رسالة مهمة:</b>\n\n{message}", parse_mode="HTML")
                success += 1
        
        send_message(chat_id, f"✅ تم الإرسال إلى {success} مستخدم")
    except Exception as e:
        send_message(chat_id, f"❌ خطأ: {e}")

def handle_user_message(user_id: int, chat_id: int, message_text: str, user):
    """معالج الرسائل من المستخدمين"""
    save_user_to_db(user_id, user.get('username'), user.get('first_name'))
    save_message_to_db(user_id, message_text, "user")
    
    # إرسال الرسالة للآدمن
    send_message(
        ADMIN_ID,
        f"📩 <b>رسالة جديدة من</b> {user.get('first_name', 'مستخدم')}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{user.get('username', 'لا يوجد')}\n\n"
        f"━━━━━━━━━━━━━━━━\n{message_text}",
        parse_mode="HTML"
    )
    
    # رسالة تأكيد للمستخدم
    send_message(
        chat_id,
        "✅ شكراً! تم استقبال رسالتك\n⏳ سيتم الرد عليك قريباً"
    )

# ==================== مسارات Flask ====================

@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من Telegram"""
    try:
        update = request.json
        
        # تحديث عادي
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            user = message['from']
            user_id = user['id']
            message_text = message.get('text', '')
            
            logger.info(f"📨 رسالة من {user_id}: {message_text}")
            
            # معالجة الأوامر
            if message_text.startswith('/start'):
                handle_start(chat_id, user)
            
            elif message_text.startswith('/stats'):
                handle_stats(chat_id)
            
            elif message_text.startswith('/broadcast '):
                broadcast_msg = message_text.replace('/broadcast ', '', 1)
                handle_broadcast(chat_id, broadcast_msg)
            
            elif message_text.startswith('/help'):
                help_text = (
                    "🤖 <b>أوامر البوت:</b>\n\n"
                    "/start - بدء البوت\n"
                    "/help - المساعدة\n\n"
                    "<b>للآدمن:</b>\n"
                    "/stats - الإحصائيات\n"
                    "/broadcast - رسالة جماعية"
                )
                send_message(chat_id, help_text, parse_mode="HTML")
            
            else:
                # رسالة عادية
                handle_user_message(user_id, chat_id, message_text, user)
        
        # تحديث رد على رسالة (للآدمن)
        elif 'callback_query' in update:
            callback_query = update['callback_query']
            logger.info(f"🔘 زر من {callback_query['from']['id']}")
        
        return jsonify({"ok": True}), 200
    
    except Exception as e:
        logger.error(f"❌ خطأ معالجة التحديث: {e}")
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    """فحص صحة السيرفر"""
    return jsonify({
        "status": "ok",
        "bot": "alive" if BOT_TOKEN else "missing token",
        "database": "connected" if supabase else "disconnected"
    }), 200

@app.route('/set_webhook', methods=['POST'])
def set_webhook():
    """ضبط webhook للبوت (اشغل مرة واحدة فقط)"""
    if not WEBHOOK_URL:
        return jsonify({"error": "WEBHOOK_URL not set"}), 400
    
    webhook_url = f"{WEBHOOK_URL}/webhook"
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    
    payload = {"url": webhook_url}
    
    try:
        response = requests.post(api_url, json=payload)
        return jsonify(response.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/delete_webhook', methods=['POST'])
def delete_webhook():
    """حذف webhook"""
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    try:
        response = requests.post(api_url)
        return jsonify(response.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ==================== البرنامج الرئيسي ====================

if __name__ == '__main__':
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN مفقود!")
        exit(1)
    
    logger.info("🚀 السيرفر يعمل على المنفذ 5000")
    logger.info(f"📍 Webhook URL: {WEBHOOK_URL}/webhook")
    
    # للتطوير المحلي
    app.run(debug=True, port=5000)
    
    # للإنتاج (استخدم Gunicorn):
    # gunicorn -w 4 -b 0.0.0.0:5000 bot_flask:app
