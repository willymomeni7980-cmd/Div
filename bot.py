# bot.py
import asyncio
import sqlite3
import datetime
import json
import os
import re
from typing import Tuple, Optional, Dict, List

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.markdown import hbold

from config import *

# ==================== دیتابیس ====================
DB_NAME = "vpn_bot.db"
SETTINGS_FILE = "settings.json"

# تنظیمات پیش‌فرض
default_settings: Dict = {
    "vpn_plans": [
        {"name": "🟦 1 گیگ", "price": 185000, "days": 30, "callback": "vpn_1gb"},
        {"name": "🟦 2 گیگ", "price": 370000, "days": 60, "callback": "vpn_2gb"},
        {"name": "🟦 4 گیگ", "price": 740000, "days": 120, "callback": "vpn_4gb"},
        {"name": "🟦 6 گیگ", "price": 1110000, "days": 180, "callback": "vpn_6gb"},
        {"name": "🟦 10 گیگ", "price": 1850000, "days": 300, "callback": "vpn_10gb"}
    ],
    "education_text": """
📚 *آموزش اتصال VPN* 📚

🔹 *مرحله 1:* نرم‌افزار V2RayNG (اندروید) / V2RayX (ویندوز) / Shadowrocket (iOS) را نصب کنید.

🔹 *مرحله 2:* فایل کانفیگ دریافتی را داخل برنامه import کنید.

🔹 *مرحله 3:* دکمه اتصال را بزنید و از اینترنت امن لذت ببرید.

🔹 *نکته:* در صورت مشکل، از دکمه پشتیبانی کمک بگیرید.
""",
    "welcome_text": "✨ به ربات *فروش VPN* خوش آمدید {full_name} ✨\n\n🔐 بهترین و پرسرعت‌ترین اکانت‌های VPN با پشتیبانی ۲۴ ساعته\n👇 لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
}

# دیکشنری برای ذخیره حالت‌های موقت ادمین
admin_states = {}

def load_settings() -> Dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default_settings
    else:
        save_settings(default_settings)
        return default_settings

def save_settings(settings: Dict) -> None:
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

settings = load_settings()

def init_db() -> None:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        total_purchases INTEGER DEFAULT 0,
        vpn_expiry TEXT DEFAULT NULL,
        register_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_name TEXT,
        price INTEGER,
        days INTEGER,
        payment_method TEXT,
        status TEXT DEFAULT 'pending',
        date TEXT
    )''')
    conn.commit()
    conn.close()

def add_user(user_id: int, username: str, full_name: str) -> None:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, full_name, register_date) VALUES (?, ?, ?, ?)",
                  (user_id, username, full_name, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    conn.close()

def get_user(user_id: int) -> Optional[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_all_users() -> List[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, full_name, total_purchases, vpn_expiry, register_date FROM users")
    users = c.fetchall()
    conn.close()
    return users

def get_pending_purchases() -> List[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, user_id, plan_name, price, date FROM purchases WHERE status='pending' ORDER BY date DESC")
    purchases = c.fetchall()
    conn.close()
    return purchases

def confirm_purchase(purchase_id: int) -> None:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE purchases SET status='confirmed' WHERE id=?", (purchase_id,))
    conn.commit()
    conn.close()

def add_purchase(user_id: int, plan_name: str, price: int, days: int, payment_method: str) -> None:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO purchases (user_id, plan_name, price, days, payment_method, date) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, plan_name, price, days, payment_method, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def update_user_purchase(user_id: int) -> None:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET total_purchases = total_purchases + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_vpn_expiry(user_id: int, days: int) -> None:
    expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET vpn_expiry = ? WHERE user_id = ?", (expiry, user_id))
    conn.commit()
    conn.close()

# ==================== کیبوردها ====================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✨ خرید اشتراک جدید"), KeyboardButton(text="💰 حساب من")],
        [KeyboardButton(text="🔗 کانفیگ های من"), KeyboardButton(text="📚 آموزش")],
        [KeyboardButton(text="💬 پشتیبانی"), KeyboardButton(text="👑 پنل ادمین")]
    ],
    resize_keyboard=True
)

def get_vpn_plans_inline() -> InlineKeyboardMarkup:
    keyboard = []
    for plan in settings["vpn_plans"]:
        keyboard.append([InlineKeyboardButton(
            text=f"{plan['name']} — {plan['price']:,} تومان",
            callback_data=f"vpn_{plan['callback']}|{plan['price']}|{plan['days']}|{plan['name']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_payment_methods(plan_name: str, price: int, days: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 کارت به کارت", callback_data=f"pay_card|{plan_name}|{price}|{days}")],
        [InlineKeyboardButton(text="🪙 ارز دیجیتال", callback_data=f"pay_crypto|{plan_name}|{price}|{days}")]
    ])

def get_admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 آمار ربات", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 سفارشات در انتظار", callback_data="admin_pending")],
        [InlineKeyboardButton(text="📦 مدیریت پلن‌ها", callback_data="admin_plans")],
        [InlineKeyboardButton(text="✏️ ویرایش متن خوش‌آمدگویی", callback_data="admin_welcome")],
        [InlineKeyboardButton(text="📚 ویرایش متن آموزش", callback_data="admin_education")],
        [InlineKeyboardButton(text="💳 ویرایش کارت به کارت", callback_data="admin_card")],
        [InlineKeyboardButton(text="🪙 ویرایش کیف پول‌ها", callback_data="admin_crypto")],
        [InlineKeyboardButton(text="📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 لیست کاربران", callback_data="admin_users")],
        [InlineKeyboardButton(text="❌ بستن", callback_data="admin_close")]
    ])

def get_plans_manager() -> InlineKeyboardMarkup:
    keyboard = []
    for i, plan in enumerate(settings["vpn_plans"]):
        keyboard.append([InlineKeyboardButton(
            text=f"✏️ {plan['name']} - {plan['price']:,} تومان",
            callback_data=f"edit_plan_{i}"
        )])
    keyboard.append([InlineKeyboardButton(text="➕ افزودن پلن جدید", callback_data="add_plan")])
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==================== مقداردهی اولیه ====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== هندلرهای کاربر ====================

@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    add_user(user_id, username, full_name)
    
    welcome_text = settings["welcome_text"].format(full_name=hbold(full_name))
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_menu)

@dp.message(F.text == "✨ خرید اشتراک جدید")
async def buy_vpn(message: Message):
    await message.answer(
        "📦 *لطفاً پلن مورد نظر خود را انتخاب کنید:*\n\n"
        "✅ هر پلن شامل حجم مشخص و اعتبار تعیین شده می‌باشد.\n"
        "⭐️ پشتیبانی دائمی و تحویل فوری کانفیگ",
        parse_mode="Markdown",
        reply_markup=get_vpn_plans_inline()
    )

@dp.message(F.text == "💰 حساب من")
async def my_account(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ کاربر یافت نشد!", parse_mode="Markdown")
        return
    
    vpn_status = "✅ فعال تا " + user[4] if user[4] else "❌ غیرفعال"
    text = (
        f"👤 *پروفایل کاربری*\n\n"
        f"🆔 *آیدی:* `{user[0]}`\n"
        f"📊 *تعداد خرید:* {user[3]}\n"
        f"🔐 *وضعیت VPN:* {vpn_status}\n"
        f"📅 *تاریخ عضویت:* {user[5]}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🔗 کانفیگ های من")
async def my_configs(message: Message):
    user = get_user(message.from_user.id)
    if user and user[4] and user[4] >= datetime.datetime.now().strftime("%Y-%m-%d"):
        await message.answer(
            "🔗 *کانفیگ‌های فعال شما:*\n\n"
            "لطفاً از ادمین بخواهید کانفیگ خود را ارسال کند.\n"
            f"🆔 آیدی ادمین: @{SUPPORT_USERNAME}",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ شما اشتراک فعالی ندارید. لطفاً ابتدا اشتراک تهیه کنید.", parse_mode="Markdown")

@dp.message(F.text == "📚 آموزش")
async def education(message: Message):
    await message.answer(settings["education_text"], parse_mode="Markdown")

@dp.message(F.text == "💬 پشتیبانی")
async def support(message: Message):
    await message.answer(
        f"💬 *پشتیبانی:*\n\n"
        f"جهت رفع مشکلات و دریافت کانفیگ با پشتیبانی در ارتباط باشید:\n"
        f"🆔 آیدی: @{SUPPORT_USERNAME}\n\n"
        f"📧 یا از طریق آیدی عددی: `{SUPPORT_ID}`",
        parse_mode="Markdown"
    )

@dp.message(F.text == "👑 پنل ادمین")
async def admin_panel(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👑 *پنل مدیریت ربات*\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=get_admin_panel()
        )
    else:
        await message.answer("❌ شما دسترسی به این بخش را ندارید!", parse_mode="Markdown")

# ==================== هندلرهای خرید ====================

@dp.callback_query(lambda c: c.data and c.data.startswith("vpn_"))
async def select_vpn_plan(callback: CallbackQuery):
    try:
        _, price_str, days_str, plan_name = callback.data.split("|")
        price = int(price_str)
        days = int(days_str)
        
        await callback.message.edit_text(
            f"✅ *{plan_name}*\n💰 مبلغ: {price:,} تومان\n⏳ اعتبار: {days} روز\n\n"
            "لطفاً روش پرداخت خود را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=get_payment_methods(plan_name, price, days)
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"خطا: {str(e)}", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("pay_"))
async def payment_method_selected(callback: CallbackQuery):
    try:
        parts = callback.data.split("|")
        method = parts[0]
        plan_name = parts[1]
        price = int(parts[2])
        days = int(parts[3])
        
        add_purchase(callback.from_user.id, plan_name, price, days, method.replace("pay_", ""))
        
        if method == "pay_card":
            card_text = (
                "💳 *پرداخت کارت به کارت*\n\n"
                f"🏦 *شماره کارت:* `{CARD_NUMBER}`\n"
                f"👤 *صاحب حساب:* {CARD_OWNER}\n\n"
                "📸 پس از واریز، *تصویر رسید* را برای ما ارسال کنید.\n"
                "✅ بلافاصله پس از تایید، کانفیگ شما ارسال می‌شود."
            )
            await callback.message.edit_text(card_text, parse_mode="Markdown")
        
        elif method == "pay_crypto":
            crypto_lines = []
            for coin, wallet in CRYPTO_WALLETS.items():
                crypto_lines.append(f"🔹 *{coin}:* `{wallet}`")
            
            crypto_text = (
                "🪙 *پرداخت با ارز دیجیتال*\n\n"
                + "\n".join(crypto_lines)
                + "\n\n✅ پس از ارسال تراکنش موفق، تصویر رسید را برای ما ارسال کنید."
            )
            await callback.message.edit_text(crypto_text, parse_mode="Markdown")
        
        await callback.answer("✅ روش پرداخت انتخاب شد", show_alert=True)
        
    except Exception as e:
        await callback.answer(f"خطا: {str(e)}", show_alert=True)

@dp.message(F.photo)
async def handle_receipt(message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "بدون یوزرنیم"
        full_name = message.from_user.full_name
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT plan_name, price FROM purchases WHERE user_id = ? AND status='pending' ORDER BY id DESC LIMIT 1", 
                  (user_id,))
        last_purchase = c.fetchone()
        conn.close()
        
        if not last_purchase:
            await message.answer("❌ هیچ سفارش در انتظار پرداختی برای شما یافت نشد.", parse_mode="Markdown")
            return
        
        plan_name, price = last_purchase
        
        caption = (
            f"📸 *رسید جدید*\n\n"
            f"👤 کاربر: {hbold(full_name)}\n"
            f"🆔 آیدی: `{user_id}`\n"
            f"📛 یوزرنیم: @{username}\n"
            f"📦 پلن: {plan_name}\n"
            f"💰 مبلغ: {price:,} تومان\n"
            f"⏰ زمان: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await message.photo[-1].forward(chat_id=ADMIN_ID)
        await bot.send_message(ADMIN_ID, caption, parse_mode="Markdown")
        
        await message.answer(
            "✅ *رسید شما با موفقیت ثبت شد*\n\n"
            "🕒 پس از تأیید ادمین، کانفیگ برای شما ارسال خواهد شد.\n"
            "🙏 از صبر و شکیبایی شما سپاسگزاریم.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await message.answer(f"❌ خطا در ثبت رسید: {str(e)}", parse_mode="Markdown")

# ==================== پنل ادمین ====================

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    users = get_all_users()
    pending = get_pending_purchases()
    active_users = sum(1 for u in users if u[4] and u[4] >= datetime.datetime.now().strftime("%Y-%m-%d"))
    
    stats_text = (
        f"📊 *آمار ربات*\n\n"
        f"👥 کل کاربران: {len(users)}\n"
        f"✅ کاربران فعال: {active_users}\n"
        f"💰 سفارشات در انتظار: {len(pending)}\n"
        f"📦 تعداد پلن‌ها: {len(settings['vpn_plans'])}"
    )
    await callback.message.edit_text(stats_text, parse_mode="Markdown", reply_markup=get_admin_panel())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_pending")
async def admin_pending(callback: CallbackQuery):
    pending = get_pending_purchases()
    
    if not pending:
        await callback.message.edit_text("✅ هیچ سفارش در انتظاری وجود ندارد.", parse_mode="Markdown", reply_markup=get_admin_panel())
        await callback.answer()
        return
    
    text = "💰 *سفارشات در انتظار تایید:*\n\n"
    keyboard = []
    for p in pending:
        text += f"🆔 سفارش #{p[0]} | کاربر: {p[1]} | {p[2]} | {p[3]:,} تومان\n"
        keyboard.append([InlineKeyboardButton(text=f"✅ تایید سفارش #{p[0]}", callback_data=f"confirm_{p[0]}")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("confirm_"))
async def confirm_order(callback: CallbackQuery):
    try:
        purchase_id = int(callback.data.split("_")[1])
        confirm_purchase(purchase_id)
        await callback.message.edit_text(
            f"✅ سفارش #{purchase_id} با موفقیت تایید شد.\nلطفاً کانفیگ را برای کاربر ارسال کنید.",
            parse_mode="Markdown",
            reply_markup=get_admin_panel()
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"خطا: {str(e)}", show_alert=True)

@dp.callback_query(lambda c: c.data == "admin_plans")
async def admin_plans(callback: CallbackQuery):
    await callback.message.edit_text(
        "📦 *مدیریت پلن‌ها*\n\nبرای ویرایش هر پلن روی آن کلیک کنید:",
        parse_mode="Markdown",
        reply_markup=get_plans_manager()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("edit_plan_"))
async def edit_plan(callback: CallbackQuery):
    try:
        plan_index = int(callback.data.split("_")[2])
        plan = settings["vpn_plans"][plan_index]
        
        await callback.message.edit_text(
            f"✏️ *ویرایش پلن*\n\n"
            f"نام فعلی: {plan['name']}\n"
            f"قیمت فعلی: {plan['price']:,} تومان\n"
            f"اعتبار فعلی: {plan['days']} روز\n\n"
            f"لطفاً اطلاعات جدید را به صورت زیر ارسال کنید:\n"
            f"`نام پلن|قیمت|تعداد روز`\n\n"
            f"مثال: `🟦 20 گیگ|2500000|60`",
            parse_mode="Markdown"
        )
        await callback.answer()
        
        # ذخیره در دیکشنری admin_states
        admin_states[callback.from_user.id] = {"editing_plan_index": plan_index}
        
    except Exception as e:
        await callback.answer(f"خطا: {str(e)}", show_alert=True)

@dp.callback_query(lambda c: c.data == "add_plan")
async def add_plan(callback: CallbackQuery):
    await callback.message.edit_text(
        f"➕ *افزودن پلن جدید*\n\n"
        f"لطفاً اطلاعات پلن جدید را به صورت زیر ارسال کنید:\n"
        f"`نام پلن|قیمت|تعداد روز`\n\n"
        f"مثال: `🟣 50 گیگ|5000000|90`",
        parse_mode="Markdown"
    )
    await callback.answer()
    admin_states[callback.from_user.id] = {"adding_plan": True}

@dp.callback_query(lambda c: c.data == "admin_welcome")
async def edit_welcome(callback: CallbackQuery):
    # ✅ رفع خطا: حذف متغیر full_name که تعریف نشده بود
    await callback.message.edit_text(
        f"✏️ *ویرایش متن خوش‌آمدگویی*\n\n"
        f"متن فعلی:\n{settings['welcome_text']}\n\n"
        f"لطفاً متن جدید را ارسال کنید.\n(از `{'{full_name}'}` برای نمایش نام کاربر استفاده کنید)",
        parse_mode="Markdown"
    )
    await callback.answer()
    admin_states[callback.from_user.id] = {"editing_welcome": True}

@dp.callback_query(lambda c: c.data == "admin_education")
async def edit_education(callback: CallbackQuery):
    await callback.message.edit_text(
        f"✏️ *ویرایش متن آموزش*\n\n"
        f"متن فعلی:\n{settings['education_text']}\n\n"
        f"لطفاً متن جدید را ارسال کنید.",
        parse_mode="Markdown"
    )
    await callback.answer()
    admin_states[callback.from_user.id] = {"editing_education": True}

@dp.callback_query(lambda c: c.data == "admin_card")
async def edit_card(callback: CallbackQuery):
    await callback.message.edit_text(
        f"✏️ *ویرایش اطلاعات کارت به کارت*\n\n"
        f"شماره کارت فعلی: `{CARD_NUMBER}`\n"
        f"صاحب حساب فعلی: {CARD_OWNER}\n\n"
        f"لطفاً اطلاعات جدید را به صورت زیر ارسال کنید:\n"
        f"`شماره کارت|نام صاحب حساب`\n\n"
        f"مثال: `6037-9972-1234-5678|محمد رضایی`",
        parse_mode="Markdown"
    )
    await callback.answer()
    admin_states[callback.from_user.id] = {"editing_card": True}

@dp.callback_query(lambda c: c.data == "admin_crypto")
async def edit_crypto(callback: CallbackQuery):
    crypto_text = "🪙 *ویرایش کیف پول‌های ارز دیجیتال*\n\nکیف پول‌های فعلی:\n"
    for coin, wallet in CRYPTO_WALLETS.items():
        crypto_text += f"🔹 {coin}: `{wallet}`\n"
    
    crypto_text += "\nلطفاً اطلاعات جدید را به صورت JSON ارسال کنید:\n"
    crypto_text += "`{\"USDT (TRC20)\": \"آدرس جدید\", \"TRX\": \"آدرس جدید\"}`"
    
    await callback.message.edit_text(crypto_text, parse_mode="Markdown")
    await callback.answer()
    admin_states[callback.from_user.id] = {"editing_crypto": True}

@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def broadcast_message(callback: CallbackQuery):
    await callback.message.edit_text(
        "📢 *ارسال پیام همگانی*\n\n"
        "لطفاً پیام خود را ارسال کنید.\n"
        "⚠️ پیام به *همه کاربران* ارسال خواهد شد.",
        parse_mode="Markdown"
    )
    await callback.answer()
    admin_states[callback.from_user.id] = {"broadcasting": True}

@dp.callback_query(lambda c: c.data == "admin_users")
async def list_users(callback: CallbackQuery):
    users = get_all_users()
    text = "👥 *لیست کاربران*\n\n"
    for user in users[:20]:
        status = "✅ فعال" if user[4] and user[4] >= datetime.datetime.now().strftime("%Y-%m-%d") else "❌ غیرفعال"
        text += f"🆔 {user[0]} | @{user[1] if user[1] else 'ندارد'} | {status}\n"
    
    if len(users) > 20:
        text += f"\n... و {len(users) - 20} کاربر دیگر"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_panel())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    """بازگشت به پنل ادمین"""
    await callback.message.edit_text(
        "👑 *پنل مدیریت ربات*\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=get_admin_panel()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "admin_close")
async def admin_close(callback: CallbackQuery):
    """بستن پنل ادمین"""
    await callback.message.delete()
    await callback.answer()


# ==================== هندلر دریافت متن از ادمین ====================

@dp.message(F.text,lambda m: m.from_user.id == ADMIN_ID)
async def handle_admin_text(message: Message):
    """پردازش متن‌های ارسالی از ادمین برای ویرایش"""
    global settings
    
    user_id = message.from_user.id
    
    if user_id not in admin_states:
        return
    
    state = admin_states[user_id]
    
    # ویرایش پلن
    if "editing_plan_index" in state:
        try:
            parts = message.text.split("|")
            if len(parts) == 3:
                name = parts[0].strip()
                price = int(parts[1].strip())
                days = int(parts[2].strip())
                
                index = state["editing_plan_index"]
                settings["vpn_plans"][index] = {
                    "name": name,
                    "price": price,
                    "days": days,
                    "callback": f"custom_{index}"
                }
                save_settings(settings)
                await message.answer(f"✅ پلن با موفقیت ویرایش شد!\n\n{name}\n💰 {price:,} تومان\n⏳ {days} روز", parse_mode="Markdown")
                del admin_states[user_id]
            else:
                await message.answer("❌ فرمت اشتباه! لطفاً به صورت `نام پلن|قیمت|تعداد روز` ارسال کنید.", parse_mode="Markdown")
        except ValueError:
            await message.answer("❌ قیمت و تعداد روز باید عدد باشند!", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ خطا: {str(e)}", parse_mode="Markdown")
        return
    
    # افزودن پلن جدید
    if "adding_plan" in state:
        try:
            parts = message.text.split("|")
            if len(parts) == 3:
                name = parts[0].strip()
                price = int(parts[1].strip())
                days = int(parts[2].strip())
                
                settings["vpn_plans"].append({
                    "name": name,
                    "price": price,
                    "days": days,
                    "callback": f"custom_{len(settings['vpn_plans'])}"
                })
                save_settings(settings)
                await message.answer(f"✅ پلن جدید با موفقیت اضافه شد!\n\n{name}\n💰 {price:,} تومان\n⏳ {days} روز", parse_mode="Markdown")
                del admin_states[user_id]
            else:
                await message.answer("❌ فرمت اشتباه! لطفاً به صورت `نام پلن|قیمت|تعداد روز` ارسال کنید.", parse_mode="Markdown")
        except ValueError:
            await message.answer("❌ قیمت و تعداد روز باید عدد باشند!", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ خطا: {str(e)}", parse_mode="Markdown")
        return
    
    # ویرایش متن خوش‌آمدگویی
    if "editing_welcome" in state:
        settings["welcome_text"] = message.text
        save_settings(settings)
        await message.answer("✅ متن خوش‌آمدگویی با موفقیت ویرایش شد!", parse_mode="Markdown")
        del admin_states[user_id]
        return
    
    # ویرایش متن آموزش
    if "editing_education" in state:
        settings["education_text"] = message.text
        save_settings(settings)
        await message.answer("✅ متن آموزش با موفقیت ویرایش شد!", parse_mode="Markdown")
        del admin_states[user_id]
        return
    
    # ویرایش کارت به کارت
    if "editing_card" in state:
        try:
            parts = message.text.split("|")
            if len(parts) == 2:
                new_card = parts[0].strip()
                new_owner = parts[1].strip()
                
                with open("config.py", "r", encoding="utf-8") as f:
                    config_lines = f.readlines()
                
                new_lines = []
                for line in config_lines:
                    if line.startswith("CARD_NUMBER"):
                        new_lines.append(f'CARD_NUMBER = "{new_card}"\n')
                    elif line.startswith("CARD_OWNER"):
                        new_lines.append(f'CARD_OWNER = "{new_owner}"\n')
                    else:
                        new_lines.append(line)
                
                with open("config.py", "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                
                await message.answer(f"✅ اطلاعات کارت ویرایش شد!\n\n🏦 شماره کارت: `{new_card}`\n👤 صاحب حساب: {new_owner}", parse_mode="Markdown")
                del admin_states[user_id]
            else:
                await message.answer("❌ فرمت: `شماره کارت|نام صاحب حساب`", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ خطا: {str(e)}", parse_mode="Markdown")
        return
    
    # ویرایش کیف پول‌ها
    if "editing_crypto" in state:
        try:
            new_wallets = json.loads(message.text)
            
            # بروزرسانی در فایل config.py
            with open("config.py", "r", encoding="utf-8") as f:
                config_content = f.read()
            
            wallets_str = "CRYPTO_WALLETS = " + json.dumps(new_wallets, ensure_ascii=False, indent=4)
            pattern = r'CRYPTO_WALLETS = \{.*?\n\}'
            config_content = re.sub(pattern, wallets_str, config_content, flags=re.DOTALL)
            
            with open("config.py", "w", encoding="utf-8") as f:
                f.write(config_content)
            
            await message.answer(
                "✅ کیف پول‌ها با موفقیت ویرایش شدند!\n\n" +
                "\n".join([f"🔹 {k}: `{v}`" for k, v in new_wallets.items()]) +
                "\n\n⚠️ لطفاً ربات را ریستارت کنید تا تغییرات اعمال شود.",
                parse_mode="Markdown"
            )
            del admin_states[user_id]
        except json.JSONDecodeError:
            await message.answer("❌ فرمت JSON اشتباه! لطفاً دیکشنری معتبر ارسال کنید.", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ خطا: {str(e)}", parse_mode="Markdown")
        return
    
    # ارسال پیام همگانی
    if "broadcasting" in state:
        users = get_all_users()
        success = 0
        fail = 0
        
        status_msg = await message.answer("🔄 در حال ارسال پیام همگانی...")
        
        for user in users:
            try:
                await bot.copy_message(chat_id=user[0], from_chat_id=ADMIN_ID, message_id=message.message_id)
                success += 1
            except:
                fail += 1
        
        await status_msg.edit_text(f"✅ پیام همگانی ارسال شد!\n\n✅ موفق: {success}\n❌ ناموفق: {fail}")
        del admin_states[user_id]

# ==================== ارسال کانفیگ توسط ادمین ====================

@dp.message(F.text.startswith("/sendconfig"))
async def admin_send_config(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ شما دسترسی به این دستور را ندارید!")
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply(
            "📝 *راهنمای ارسال کانفیگ:*\n\n"
            "فرمت: `/sendconfig [user_id] [کانفیگ]`\n\n"
            "مثال: `/sendconfig 123456789 vless://example.com`",
            parse_mode="Markdown"
        )
        return
    
    try:
        user_id = int(parts[1])
        config_text = parts[2]
        
        # بروزرسانی تاریخ انقضا (30 روز)
        set_vpn_expiry(user_id, 30)
        
        await bot.send_message(
            user_id,
            f"🔗 *کانفیگ شما:*\n\n`{config_text}`\n\n✅ اشتراک شما به مدت 30 روز فعال شد.",
            parse_mode="Markdown"
        )
        await message.reply(f"✅ کانفیگ با موفقیت به کاربر {user_id} ارسال شد و اشتراک ایشان فعال گردید.")
        
    except ValueError:
        await message.reply("❌ آیدی کاربر باید عددی باشد!")
    except Exception as e:
        await message.reply(f"❌ خطا در ارسال: {str(e)}")

# ==================== اجرای اصلی ====================

async def main():
    init_db()
    print("=" * 50)
    print("✅ ربات فروش VPN با موفقیت اجرا شد...")
    print(f"👑 پنل ادمین برای آیدی {ADMIN_ID} فعال است.")
    print(f"📊 تعداد پلن‌های فعال: {len(settings['vpn_plans'])}")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
