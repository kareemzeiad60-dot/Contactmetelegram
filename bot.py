import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تحميل ملف .env محلياً (إذا كان موجوداً)
load_dotenv()

# تفعيل الـ Logging لمتابعة حالة البوت والأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# جلب معرف الآدمن وتحويله لرقم
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

# 1. أمر البداية /start للمستخدمين
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت التواصل! 📬✒️\nأرسل رسالتك هنا وسيقوم الدعم بالرد عليك مباشرة."
    )

# 2. إدارة وتوجيه الرسائل (الورك فلو الرئيسي)
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_text = update.message.text

    # إذا كانت الرسالة من مستخدم عادي -> تُحوّل للآدمن
    if chat_id != ADMIN_ID:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 **رسالة جديدة من:** {update.effective_user.mention_markdown_v2()}\n"
                 f"🆔 **ID المستخدم:** `{user_id}`\n\n"
                 f"💬 **الرسالة:**\n{message_text}",
            parse_mode="MarkdownV2"
        )
        await update.message.reply_text("☑️✔️ تم إرسال رسالتك بنجاح، سيتم الرد عليك قريباً.")

    # إذا كانت الرسالة من الآدمن -> يجب أن تكون ردًا (Reply) على رسالة مستخدم
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
                        text=f"🪽🌪️\n\n{message_text}"
                    )
                    await update.message.reply_text("💠✴️ تم إرسال ردك للمستخدم بنجاح.")
                else:
                    await update.message.reply_text("❌ لم أتمكن من العثور على ID المستخدم.")
            except Exception as e:
                await update.message.reply_text(f"✖️ حدث خطأ: {e}")
        else:
            await update.message.reply_text("☢️ للرد، قم بعمل Reply على رسالة المستخدم.")

# 3. الدالة الرئيسية التي تشغل الورك فلو
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN or ADMIN_ID == 0:
        print("❌ خطأ حرج: لم يتم العثور على BOT_TOKEN أو ADMIN_ID في متغيرات البيئة!")
        return

    # بناء تطبيق التليجرام
    application = Application.builder().token(TOKEN).build()

    # تسجيل الأوامر والمعالجات
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    # أمر بدء الاستماع الفعلي للبوت
    print("🔹🔷💠⚜️ البوت بدأ العمل الآن ومستعد لاستقبال الرسائل...")
    application.run_polling()

# نقطة انطلاق التشغيل من الـ Terminal
if __name__ == '__main__':
    main()
