import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8800108942:AAGrffhtO1Ktsr_TXY_jHk3m7TS9RJ5zSjM")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "2083913926").split(",") if x.strip()]
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL", "@robaticaa")

db = Database()


async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not FORCE_JOIN_CHANNEL:
        return True
    try:
        member = await context.bot.get_chat_member(FORCE_JOIN_CHANNEL, user_id)
        return member.status not in ["left", "kicked"]
    except Exception:
        return True


async def get_referral_count(user_id: int) -> int:
    return db.get_referral_count(user_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    args = context.args

    db.add_user(user_id, user.username or user.first_name)

    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].split("_")[1])
            if referrer_id != user_id:
                db.add_referral(referrer_id, user_id)
        except Exception:
            pass

    if not await check_membership(user_id, context):
        channel = FORCE_JOIN_CHANNEL
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{channel.lstrip('@')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ برای استفاده از ربات باید عضو کانال ما باشید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    ref_count = await get_referral_count(user_id)
    configs_earned = ref_count // 4
    configs_used = db.get_configs_used(user_id)
    configs_available = configs_earned - configs_used

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    text = (
        f"سلام {user.first_name} عزیز! 👋\n\n"
        f"اینجا کمکت می‌کنیم تا به اینترنت آزاد وصل بمونی، اونم کاملاً رایگان 🆓\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 دوستان دعوت‌شده: {ref_count} نفر\n"
        f"🎁 کانفیگ قابل دریافت: {configs_available} عدد\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"به ازای هر ۴ نفری که دعوت کنی، یک کانفیگ رایگان می‌گیری! 📌\n\n"
        f"🔗 لینک دعوت تو:\n`{ref_link}`"
    )

    keyboard = [
        [InlineKeyboardButton("🆓 دریافت کانفیگ رایگان", callback_data="get_config")],
        [InlineKeyboardButton("👥 تعداد دعوت‌ها", callback_data="my_refs")],
    ]

    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "check_join":
        if await check_membership(user_id, context):
            await show_main_menu(update, context)
        else:
            await query.answer("❌ هنوز عضو کانال نشدید!", show_alert=True)

    elif data == "get_config":
        if not db.is_referral_active():
            await query.edit_message_text(
                "⏸ سیستم دریافت کانفیگ موقتاً غیرفعال است.\nلطفاً بعداً مراجعه کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]),
            )
            return

        ref_count = await get_referral_count(user_id)
        configs_earned = ref_count // 4
        configs_used = db.get_configs_used(user_id)
        configs_available = configs_earned - configs_used

        if configs_available <= 0:
            bot_username = (await context.bot.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            still_needed = 4 - (ref_count % 4)
            await query.edit_message_text(
                f"❌ کانفیگ رایگان موجود نیست!\n\n"
                f"👥 شما {ref_count} نفر دعوت کردید.\n"
                f"برای کانفیگ بعدی باید {still_needed} نفر دیگر دعوت کنید.\n\n"
                f"🔗 لینک دعوت:\n`{ref_link}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]),
                parse_mode="Markdown"
            )
            return

        config = db.get_and_mark_config(user_id)
        if not config:
            await query.edit_message_text(
                "⚠️ در حال حاضر کانفیگی موجود نیست. لطفاً بعداً تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]),
            )
            return

        await query.edit_message_text(
            f"✅ کانفیگ رایگان شما:\n\n`{config}`\n\n"
            f"📋 کپی کنید و در اپ V2Ray یا Hiddify وارد کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]),
            parse_mode="Markdown"
        )

        # Notify admins
        user = query.from_user
        ref_count = await get_referral_count(user_id)
        notify_text = (
            f"🎁 کانفیگ جدید دریافت شد!\n\n"
            f"👤 نام: {user.full_name}\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"👥 تعداد دعوت‌ها: {ref_count} نفر\n"
            f"🔗 یوزرنیم: @{user.username}" if user.username else
            f"🎁 کانفیگ جدید دریافت شد!\n\n"
            f"👤 نام: {user.full_name}\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"👥 تعداد دعوت‌ها: {ref_count} نفر\n"
            f"🔗 یوزرنیم: ندارد"
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(admin_id, notify_text, parse_mode="Markdown")
            except Exception:
                pass

    elif data == "my_refs":
        ref_count = await get_referral_count(user_id)
        configs_earned = ref_count // 4
        configs_used = db.get_configs_used(user_id)
        still_needed = 4 - (ref_count % 4) if ref_count % 4 != 0 else 0

        await query.edit_message_text(
            f"📊 آمار دعوت‌های شما:\n\n"
            f"👥 کل دعوت‌شده‌ها: {ref_count} نفر\n"
            f"🎁 کانفیگ‌های گرفته‌شده: {configs_used} عدد\n"
            f"✅ کانفیگ‌های قابل دریافت: {configs_earned - configs_used} عدد\n\n"
            f"{'✨ همین الان می‌تونی کانفیگ بگیری!' if configs_earned - configs_used > 0 else f'⏳ برای کانفیگ بعدی {still_needed} نفر دیگر دعوت کن.'}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]),
        )

    elif data == "back":
        await show_main_menu(update, context)


# ---- ADMIN PANEL ----

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ دسترسی ندارید.")
        return
    await show_admin_panel(update, context)


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_stats()
    referral_active = db.is_referral_active()
    referral_status = "✅ فعال" if referral_active else "❌ غیرفعال"
    referral_btn_text = "🔴 خاموش کردن رفرال" if referral_active else "🟢 روشن کردن رفرال"

    text = (
        f"🛠 پنل ادمین\n\n"
        f"👤 کل کاربران: {stats['users']}\n"
        f"📦 کانفیگ‌های موجود: {stats['configs']}\n"
        f"🎁 کانفیگ‌های داده‌شده: {stats['used']}\n"
        f"🔗 سیستم رفرال: {referral_status}\n"
        f"📢 کانال فورس‌جوین: {FORCE_JOIN_CHANNEL or 'تنظیم نشده'}"
    )
    keyboard = [
        [InlineKeyboardButton("➕ افزودن کانفیگ", callback_data="admin_add_config")],
        [InlineKeyboardButton("📋 لیست کانفیگ‌ها", callback_data="admin_list_configs")],
        [InlineKeyboardButton("🗑 حذف همه کانفیگ‌ها", callback_data="admin_clear_configs")],
        [InlineKeyboardButton(referral_btn_text, callback_data="admin_toggle_referral")],
    ]

    if isinstance(update, Update) and update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        return

    data = query.data

    if data == "admin_add_config":
        context.user_data["waiting_config"] = True
        await query.edit_message_text(
            "📝 کانفیگ(های) جدید را ارسال کنید.\n"
            "می‌توانید چند کانفیگ را با Enter جدا کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]),
        )

    elif data == "admin_list_configs":
        configs = db.get_all_configs()
        if not configs:
            text = "📋 هیچ کانفیگی موجود نیست."
        else:
            free = [c for c in configs if not c["used"]]
            used = [c for c in configs if c["used"]]
            text = f"📋 کانفیگ‌ها:\n✅ آزاد: {len(free)} عدد | ❌ داده‌شده: {len(used)} عدد\n\n"
            for i, c in enumerate(free[:10], 1):
                text += f"✅ {i}. `{c['config'][:45]}...`\n"
            if len(free) > 10:
                text += f"\n... و {len(free)-10} کانفیگ آزاد دیگر"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]),
            parse_mode="Markdown"
        )

    elif data == "admin_clear_configs":
        db.clear_configs()
        await query.edit_message_text(
            "✅ همه کانفیگ‌ها حذف شدند.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")]]),
        )

    elif data == "admin_toggle_referral":
        new_state = db.toggle_referral()
        status = "✅ روشن شد" if new_state else "❌ خاموش شد"
        await query.answer(f"سیستم رفرال {status}!", show_alert=True)
        await show_admin_panel(update, context)

    elif data == "admin_back":
        await show_admin_panel(update, context)


async def receive_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    if not context.user_data.get("waiting_config"):
        return

    text = update.message.text.strip()
    configs = [line.strip() for line in text.splitlines() if line.strip()]
    added = 0
    for cfg in configs:
        if db.add_config(cfg):
            added += 1

    context.user_data["waiting_config"] = False
    await update.message.reply_text(
        f"✅ {added} کانفیگ با موفقیت اضافه شد!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 پنل ادمین", callback_data="admin_back")]]),
    )


def main():
    token = BOT_TOKEN
    if not token:
        raise ValueError("BOT_TOKEN not set!")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_config))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
