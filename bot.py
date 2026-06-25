"""
🤖 بوت تليجرام مع Flask و Supabase
نسخة Webhook (أسرع وأكثر كفاءة)
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from supabase import create_client, Client
import requests

load_dotenv()

# ==================== الإعدادات ====================

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# البيانات الحساسة
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://yourdomain.com
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# الاتصال بـ Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ متصل بـ Supabase")
    except Exception as e:
        logger.error(f"❌ خطأ الاتصال: {e}")

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
