import os
import logging
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تحميل ملف .env محلياً (إذا كان موجوداً)
load_dotenv()

# تفعيل الـ Logging لمتابعة حالة البوت والأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# جلب بيانات السيكريتس
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# اختبار طباعة أولي للتأكد من وصول السيكريتس للبوت
print(f"📡 فحص الاتصال... URL موجود: {bool(SUPABASE_URL)} | KEY موجود: {bool(SUPABASE_KEY)}")

# الاتصال بقاعدة بيانات Supabase
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ تم إنشاء اتصال كود البوت بـ Supabase بنجاح!")
    except Exception as connection_error:
        print(f"❌ فشل إنشاء كائن الاتصال بـ Supabase: {connection_error}")
        supabase = None
else:
    print("❌ خطأ حرج: لم يتم العثور على بيانات اتصال Supabase في الـ Secrets!")
    supabase = None

# دالة لحفظ المستخدم في قاعدة البيانات السحابية بأمان مع طباعة مفصلة للخطأ
def save_user_to_db(user_id):
    if not supabase:
        print(f"⚠️ تخطي الحفظ للمستخدم {user_id}: قاعدة البيانات غير متصلة (supabase=None)")
        return
    try:
        print(f"⏳ محاولة حفظ/تحديث المستخدم {user_id} في جدول Supabase...")
        response = supabase.table("users").upsert({"user_id": user_id}).execute()
        print(f"🚀 [نجاح سحابي] تم حفظ الـ ID: {user_id} بنجاح في الجدول! الاستجابة: {response.data}")
    except Exception as e:
        print(f"❌ [خطأ حرج] فشلت عملية الحفظ في الداتا بيس للمستخدم {user_id}. السبب: {e}")

# 1. أمر البداية /start للمستخدمين
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"👤 مستخدم ضغط /start، معرفه: {user_id}")
    save_user_to_db(user_id) # حفظ في سوبابيس
    
    await update.message.reply_text(
        "أهلاً بك في بوت التواصل! ✉️📬\nأرسل رسالتك هنا وسيقوم الدعم بالرد عليك مباشرة."
    )

# 2. أمر الإرسال الجماعي (للآدمن فقط) جلب البيانات من السحابة مع فحص ذكي للاتصال
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id != ADMIN_ID:
        print(f"🚫 محاولة برودكاست مرفوضة من مستخدم غير مصرح له: {chat_id}")
        return

    # الفحص الذكي: لو استدعيت الأمر وقاعدة البيانات غير متصلة، سيخبرك البوت بالسبب في الشات فوراً
    if not supabase:
        url_status = "✅ موجود وقرأه البوت" if os.getenv("SUPABASE_URL") else "❌ غير موجود أو فارغ"
        key_status = "✅ موجود وقرأه البوت" if os.getenv("SUPABASE_KEY") else "❌ غير موجود أو فارغ"
        
        error_report = (
            f"❌ **قاعدة البيانات غير متصلة حالياً!**\n\n"
            f"🕵️‍♂️ **تقرير فحص الـ Secrets في السيرفر:**\n"
            f"🌐 `SUPABASE_URL`: {url_status}\n"
            f"🔑 `SUPABASE_KEY`: {key_status}\n\n"
            f"💡 *حل المشكلة:* إذا كانت النتيجة (❌)، اذهب إلى إعدادات جيت هاب (Settings -> Secrets -> Actions) وتأكد من إضافة المتغيرات بالحروف الكبيرة وبدون مسافات، ثم أعد تشغيل البوت عبر Run workflow لتحديث السيرفر."
        )
        await update.message.reply_text(error_report, parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text("⚠️ يرجى كتابة الرسالة بعد الأمر. مثال:\n`/broadcast أهلاً بالجميع`", parse_mode="Markdown")
        return

    broadcast_message = " ".join(context.args)

    # جلب كل المستخدمين من جدول سوبابيس
    try:
        response = supabase.table("users").select("user_id").execute()
        user_rows = response.data
    except Exception as e:
        await update.message.reply_text(f"❌ فشل جلب المستخدمين من السحابة: {e}")
        return

    if not user_rows:
        await update.message.reply_text("❌ لا يوجد مستخدمين مسجلين في قاعدة البيانات حالياً.")
        return

    await update.message.reply_text(f"📢 جاري بدء الإرسال الجماعي السحابي إلى {len(user_rows)} مستخدم...")

    success_count = 0
    for row in user_rows:
        u_id = row["user_id"]
        try:
            if int(u_id) == ADMIN_ID:
                continue
            await context.bot.send_message(chat_id=int(u_id), text=broadcast_message)
            success_count += 1
            await asyncio.sleep(0.05) # حماية من الحظر
        except Exception as send_err:
            print(f"⚠️ تعذر الإرسال للمعرف {u_id}: {send_err}")
            continue

    await update.message.reply_text(f"✅ تم إرسال الرسالة الجماعية بنجاح إلى {success_count} مستخدم.")

# 3. إدارة وتوجيه الرسائل (الورك فلو الرئيسي)
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_text = update.message.text

    print(f"📩 رسالة واردة من الشات: {chat_id} | نصها: {message_text}")
    save_user_to_db(user_id) # حفظ في سوبابيس عند إرسال أي رسالة

    if chat_id != ADMIN_ID:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 **رسالة جديدة من:** {update.effective_user.mention_markdown_v2()}\n"
                 f"🆔 **ID المستخدم:** `{user_id}`\n\n"
                 f"🔻🔻\n{message_text}",
            parse_mode="MarkdownV2"
        )
        await update.message.reply_text("💌 تم إرسال رسالتك بنجاح، سيتم الرد عليك قريباً.")

    else:
        if update.message.reply_to_message:
            original_text = update.message.reply_to_message.text
            try:
                lines = original_text.split("\n")
                target_user_id = None
                for line in lines:
                    if "ID المستخدم:" in line:
                        target_user_id = int(line.split(":")[1].strip())
                        break
                
                if target_user_id:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"🌪️\n\n{message_text}"
                    )
                    await update.message.reply_text("🔹🔷💠🌐 تم إرسال ردك للمستخدم بنجاح.")
                else:
                    await update.message.reply_text("❌ لم أتمكن من العثور على ID المستخدم في الرسالة الأصلية.")
            except Exception as e:
                await update.message.reply_text(f"✖️ حدث خطأ أثناء معالجة الرد: {e}")
        else:
            await update.message.reply_text("☢️ للرد, قم بعمل Reply على رسالة المستخدم.")

# دالة مخصصة لإغلاق البوت بعد وقت محدد بأمان ليتيح لـ GitHub Actions إعادة تشغيله
async def auto_shutdown(application: Application, seconds: int):
    await asyncio.sleep(seconds)
    print(f"⏱️ مرت {seconds} ثانية. يتم الآن إغلاق البوت لإعادة التشغيل الجدولي الآمن...")
    await application.stop()
    await application.shutdown()

# 4. الدالة الرئيسية
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN or ADMIN_ID == 0:
        print(f"❌ خطأ حرج: لم يتم العثور على BOT_TOKEN (موجود: {bool(TOKEN)}) أو ADMIN_ID (موجود: {ADMIN_ID != 0})!")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("🔹🔷💠⚜️ البوت يعمل الآن بكفاءة ومستعد لاستقبال الأحداث...")

    loop = asyncio.get_event_loop()
    loop.create_task(auto_shutdown(application, 9000))

    application.run_polling()

if __name__ == '__main__':
    main()
