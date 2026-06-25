import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الحصول على البيانات الحساسة
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

print(f"📡 فحص الاتصال... URL: {bool(SUPABASE_URL)} | KEY: {bool(SUPABASE_KEY)}")

# الاتصال بـ Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ تم الاتصال بـ Supabase بنجاح!")
    except Exception as e:
        print(f"❌ خطأ الاتصال: {e}")
else:
    print("❌ لم تجد بيانات Supabase!")

# ==================== دوال قاعدة البيانات ====================

def save_user_to_db(user_id: int, username: str = None, full_name: str = None):
    """حفظ أو تحديث بيانات المستخدم"""
    if not supabase:
        logger.warning(f"⚠️ قاعدة البيانات غير متصلة - تخطي حفظ المستخدم {user_id}")
        return False
    
    try:
        data = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "last_message_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("users").upsert(data, on_conflict="user_id").execute()
        logger.info(f"✅ تم حفظ المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ حفظ المستخدم: {e}")
        return False

def save_message_to_db(user_id: int, message_text: str, message_type: str = "user"):
    """حفظ سجل الرسائل"""
    if not supabase:
        return False
    
    try:
        data = {
            "user_id": user_id,
            "message": message_text,
            "message_type": message_type,  # "user" أو "admin_reply"
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("messages").insert(data).execute()
        logger.info(f"💾 تم حفظ الرسالة من المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ حفظ الرسالة: {e}")
        return False

def get_user_stats():
    """الحصول على إحصائيات المستخدمين"""
    if not supabase:
        return None
    
    try:
        response = supabase.table("users").select("*").execute()
        return len(response.data), response.data
    except Exception as e:
        logger.error(f"❌ خطأ جلب الإحصائيات: {e}")
        return None, []

# ==================== أوامر البوت ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية"""
    user = update.effective_user
    save_user_to_db(user.id, user.username, user.full_name)
    
    keyboard = [
        [InlineKeyboardButton("📞 تواصل معنا", callback_data="contact")],
        [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="faq")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎉 أهلاً بك في بوت التواصل!\n\n"
        "📝 يمكنك إرسال رسالتك وسيتم الرد عليك مباشرة من الدعم الفني.\n\n"
        f"👤 اسمك: {user.full_name or 'زائر'}",
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات (للآدمن فقط)"""
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("🚫 عذراً، أنت غير مصرح!")
        return
    
    count, users = get_user_stats()
    if count is None:
        await update.message.reply_text("❌ خطأ في الاتصال بقاعدة البيانات")
        return
    
    stats_text = f"""
📊 **إحصائيات البوت:**
👥 عدد المستخدمين: {count}
🔌 حالة الاتصال: ✅ متصل

**آخر 5 مستخدمين:**
"""
    
    for user in users[-5:]:
        stats_text += f"\n• {user['full_name']} (@{user['username']})"
    
    await update.message.reply_text(stats_text, parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة جماعية (للآدمن فقط)"""
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("🚫 غير مصرح!")
        return
    
    if not supabase:
        await update.message.reply_text("❌ قاعدة البيانات غير متصلة!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ استخدم: `/broadcast الرسالة هنا`",
            parse_mode="Markdown"
        )
        return
    
    broadcast_message = " ".join(context.args)
    
    try:
        response = supabase.table("users").select("user_id").execute()
        user_rows = response.data
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        return
    
    if not user_rows:
        await update.message.reply_text("❌ لا يوجد مستخدمين!")
        return
    
    success = 0
    for row in user_rows:
        try:
            u_id = int(row["user_id"])
            if u_id != ADMIN_ID:
                await context.bot.send_message(
                    chat_id=u_id,
                    text=f"📢 **رسالة مهمة:**\n\n{broadcast_message}",
                    parse_mode="Markdown"
                )
                success += 1
            await asyncio.sleep(0.02)
        except Exception as e:
            logger.warning(f"⚠️ فشل الإرسال للمستخدم {row['user_id']}: {e}")
    
    await update.message.reply_text(f"✅ تم الإرسال إلى {success} مستخدم")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار المحادثة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "contact":
        await query.edit_message_text(
            text="📞 يمكنك إرسال رسالتك الآن:\n\n"
                 "اكتب أي استفسار أو شكوى وسيتم التعامل معها في أسرع وقت!"
        )
    elif query.data == "faq":
        await query.edit_message_text(
            text="❓ الأسئلة الشائعة:\n\n"
                 "🔹 متى سيتم الرد؟\n"
                 "الرد خلال 24 ساعة\n\n"
                 "🔹 كيف أتابع حالة طلبي؟\n"
                 "احفظ معرف رسالتك في البوت"
        )

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل الواردة"""
    user = update.effective_user
    message_text = update.message.text
    chat_id = update.effective_chat.id
    
    # حفظ بيانات المستخدم والرسالة
    save_user_to_db(user.id, user.username, user.full_name)
    save_message_to_db(user.id, message_text, "user")
    
    if chat_id != ADMIN_ID:
        # إرسال الرسالة للآدمن
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 **رسالة جديدة** من {user.mention_markdown_v2()}\n"
                 f"🆔 ID: `{user.id}`\n"
                 f"👤 Username: @{user.username or 'لا يوجد'}\n\n"
                 f"━━━━━━━━━━━━━━━━\n{message_text}",
            parse_mode="MarkdownV2"
        )
        
        await update.message.reply_text(
            "✅ شكراً! تم استقبال رسالتك\n"
            "⏳ سيتم الرد عليك قريباً"
        )
    
    else:  # الآدمن يرسل رسالة
        if update.message.reply_to_message:
            # محاولة استخراج ID المستخدم من الرسالة الأصلية
            original_text = update.message.reply_to_message.text
            try:
                # البحث عن ID في النص
                for line in original_text.split("\n"):
                    if "ID:" in line:
                        target_id = int(line.split("`")[1])
                        await context.bot.send_message(
                            chat_id=target_id,
                            text=f"💬 **رد من الدعم:**\n\n{message_text}",
                            parse_mode="Markdown"
                        )
                        save_message_to_db(target_id, message_text, "admin_reply")
                        await update.message.reply_text("✅ تم إرسال الرد")
                        return
            except Exception as e:
                logger.error(f"خطأ في استخراج ID: {e}")
            
            await update.message.reply_text("❌ لم أتمكن من معالجة الرد")
        else:
            await update.message.reply_text("⚠️ قم برد (Reply) على رسالة المستخدم!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    help_text = """
🤖 **أوامر البوت:**

*للمستخدمين:*
/start - بدء البوت
/help - هذه الرسالة

*للآدمن فقط:*
/stats - إحصائيات المستخدمين
/broadcast `رسالة` - إرسال رسالة جماعية
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def auto_shutdown(application: Application, seconds: int = 9000):
    """إغلاق البوت تلقائياً بعد فترة زمنية"""
    await asyncio.sleep(seconds)
    logger.info(f"⏱️ إيقاف البوت بعد {seconds} ثانية...")
    await application.stop()
    await application.shutdown()

# ==================== البرنامج الرئيسي ====================

def main():
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    
    if ADMIN_ID == 0:
        print("❌ خطأ: ADMIN_ID غير صحيح!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    logger.info("🚀 البوت يعمل الآن...")
    
    # إغلاق تلقائي بعد 150 دقيقة (للـ GitHub Actions)
    loop = asyncio.get_event_loop()
    loop.create_task(auto_shutdown(application, 9000))
    
    application.run_polling()

if __name__ == '__main__':
    main()
