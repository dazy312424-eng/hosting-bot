import os
import json
import subprocess
import asyncio
import logging
import shutil
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ========== CONFIG ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_ID = 6795723042
PROJECTS_DIR = "projects"
DATA_FILE = "data.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== REPLY KEYBOARD (menu button) ==========
def reply_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 မီနူး")]],
        resize_keyboard=True,
        persistent=True
    )

# ========== DATA MANAGEMENT ==========
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "projects": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_data(user_id):
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"projects": [], "joined": str(datetime.now())}
        save_data(data)
    return data

# ========== INLINE KEYBOARDS ==========
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 ကျွန်တော်ရဲ့ ပရောဂျက်များ", callback_data="my_projects"),
         InlineKeyboardButton("➕ ပရောဂျက်အသစ်", callback_data="new_project")],
        [InlineKeyboardButton("📊 အခြေအနေ", callback_data="status"),
         InlineKeyboardButton("ℹ️ အကူအညီ", callback_data="help")]
    ])

def project_keyboard(project_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ စတင်မည်", callback_data=f"start_{project_name}"),
         InlineKeyboardButton("⏹ ရပ်မည်", callback_data=f"stop_{project_name}")],
        [InlineKeyboardButton("📋 မှတ်တမ်းများ", callback_data=f"logs_{project_name}"),
         InlineKeyboardButton("📤 ဖိုင်တင်မည်", callback_data=f"upload_{project_name}")],
        [InlineKeyboardButton("🗑 ဖိုင်ဖျက်မည်", callback_data=f"delete_file_{project_name}"),
         InlineKeyboardButton("🗂 ဖိုလ်ဒါဖျက်မည်", callback_data=f"delete_{project_name}")],
        [InlineKeyboardButton("🔙 နောက်သို့", callback_data="my_projects")]
    ])

def projects_keyboard(projects):
    buttons = []
    for p in projects:
        buttons.append([InlineKeyboardButton(f"📂 {p}", callback_data=f"project_{p}")])
    buttons.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

# ========== PROJECT MANAGEMENT ==========
running_processes = {}

def get_project_path(user_id, project_name):
    return os.path.join(PROJECTS_DIR, str(user_id), project_name)

def create_project_dir(user_id, project_name):
    path = get_project_path(user_id, project_name)
    os.makedirs(path, exist_ok=True)
    return path

def start_project(user_id, project_name):
    path = get_project_path(user_id, project_name)
    main_file = None
    for f in os.listdir(path):
        if f.endswith(".py"):
            main_file = f
            break
    if not main_file:
        return False, "❌ Python ဖိုင် မတွေ့ဘူး!"
    key = f"{user_id}_{project_name}"
    if key in running_processes:
        return False, "⚠️ ပရောဂျက် ရှိပြီးသား run နေတယ်!"
    log_path = os.path.join(path, "bot.log")
    with open(log_path, "w") as log_file:
        process = subprocess.Popen(
            ["python3", main_file],
            cwd=path,
            stdout=log_file,
            stderr=log_file
        )
    running_processes[key] = process
    return True, f"✅ {main_file} စတင်လိုက်တယ်!"

def stop_project(user_id, project_name):
    key = f"{user_id}_{project_name}"
    if key not in running_processes:
        return False, "⚠️ ပရောဂျက် run မနေဘူး!"
    running_processes[key].terminate()
    del running_processes[key]
    return True, "⏹ ပရောဂျက် ရပ်လိုက်တယ်!"

def get_status(user_id, project_name):
    key = f"{user_id}_{project_name}"
    if key in running_processes:
        proc = running_processes[key]
        if proc.poll() is None:
            return "🟢 လည်ပတ်နေသည်"
        else:
            del running_processes[key]
            return "🔴 ပျက်သွားတယ်"
    return "⚪ ရပ်နေသည်"

def get_logs(user_id, project_name, lines=20):
    path = get_project_path(user_id, project_name)
    log_path = os.path.join(path, "bot.log")
    if not os.path.exists(log_path):
        return "မှတ်တမ်း မရှိသေးဘူး"
    with open(log_path, "r") as f:
        all_lines = f.readlines()
        return "".join(all_lines[-lines:]) or "မှတ်တမ်း ဗလာဖြစ်နေတယ်"

# ========== LOADING HELPER ==========
async def show_loading(query, text="⏳ လုပ်ဆောင်နေသည်..."):
    try:
        await query.edit_message_text(text)
    except:
        pass
    await asyncio.sleep(0.5)

# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user_data(user.id)
    text = (
        f"👋 မင်္ဂလာပါ **{user.first_name}**!\n\n"
        f"🤖 **ဘော့ဟိုစ်တင်း** မှ ကြိုဆိုပါတယ်\n\n"
        f"Python bot ဖိုင်များကို upload တင်ပြီး\n"
        f"၂၄ နာရီ run နိုင်ပါတယ်! ✨\n\n"
        f"⬇️ အောက်က **🏠 မီနူး** ကို နှိပ်ပြီး အသုံးပြုနိုင်ပါတယ်"
    )
    await update.message.reply_text(
        text,
        reply_markup=reply_keyboard(),
        parse_mode="Markdown"
    )
    await update.message.reply_text(
        "🏠 **ပင်မမီနူး**\n\nဘာလုပ်မလဲ?",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

async def menu_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 🏠 မီနူး button press"""
    if update.message.text == "🏠 မီနူး":
        await update.message.reply_text(
            "🏠 **ပင်မမီနူး**\n\nဘာလုပ်မလဲ?",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )
        return
    # Pass to message handler for other text
    await message_handler(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data_val = query.data

    if data_val == "main_menu":
        await query.edit_message_text(
            "🏠 **ပင်မမီနူး**\n\nဘာလုပ်မလဲ?",
            reply_markup=main_keyboard(),
            parse_mode="Markdown"
        )

    elif data_val == "my_projects":
        await show_loading(query, "⏳ ပရောဂျက်များ ရယူနေသည်...")
        data = load_data()
        uid = str(user_id)
        user_projects = data.get("users", {}).get(uid, {}).get("projects", [])
        if not user_projects:
            await query.edit_message_text(
                "📁 ပရောဂျက် မရှိသေးဘူး!\n\n➕ ပရောဂျက်အသစ် နှိပ်ပြီး စလုပ်ပါ",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ ပရောဂျက်အသစ်", callback_data="new_project")],
                    [InlineKeyboardButton("🔙 နောက်သို့", callback_data="main_menu")]
                ])
            )
        else:
            await query.edit_message_text(
                f"📁 **မင်းရဲ့ ပရောဂျက်များ** ({len(user_projects)})\n\nပရောဂျက်တစ်ခု ရွေးပါ:",
                reply_markup=projects_keyboard(user_projects),
                parse_mode="Markdown"
            )

    elif data_val == "new_project":
        context.user_data["waiting_for"] = "project_name"
        await query.edit_message_text(
            "➕ **ပရောဂျက်အသစ်**\n\nပရောဂျက် အမည် ရိုက်ထည့်ပါ:\n_(ဥပမာ: mybot)_",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ပယ်ဖျက်မည်", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )

    elif data_val.startswith("project_"):
        project_name = data_val.replace("project_", "")
        await show_loading(query, f"⏳ {project_name} ဒေတာ ရယူနေသည်...")
        status = get_status(user_id, project_name)
        path = get_project_path(user_id, project_name)
        files = []
        if os.path.exists(path):
            files = [f for f in os.listdir(path) if not f.endswith(".log")]
        size = sum(
            os.path.getsize(os.path.join(path, f))
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
        ) if os.path.exists(path) else 0
        text = (
            f"━━━━━━━━━━━━━━━\n"
            f"📂 **{project_name}**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 အခြေအနေ ‣ {status}\n"
            f"📄 ဖိုင်အရေအတွက် ‣ {len(files)}\n"
            f"💾 အရွယ်အစား ‣ {size/1024:.1f} KB\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🗂 ဖိုင်များ: {', '.join(files) if files else 'မရှိသေးဘူး'}"
        )
        await query.edit_message_text(text, reply_markup=project_keyboard(project_name), parse_mode="Markdown")

    elif data_val.startswith("start_"):
        project_name = data_val.replace("start_", "")
        await show_loading(query, f"⏳ {project_name} စတင်နေသည်...")
        success, msg = start_project(user_id, project_name)
        if success:
            status = get_status(user_id, project_name)
            await query.edit_message_text(
                f"━━━━━━━━━━━━━━━\n"
                f"📂 **{project_name}**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📊 အခြေအနေ ‣ {status}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"✅ {msg}",
                reply_markup=project_keyboard(project_name),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"━━━━━━━━━━━━━━━\n"
                f"📂 **{project_name}**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{msg}",
                reply_markup=project_keyboard(project_name),
                parse_mode="Markdown"
            )

    elif data_val.startswith("stop_"):
        project_name = data_val.replace("stop_", "")
        await show_loading(query, f"⏳ {project_name} ရပ်နေသည်...")
        success, msg = stop_project(user_id, project_name)
        status = get_status(user_id, project_name)
        await query.edit_message_text(
            f"━━━━━━━━━━━━━━━\n"
            f"📂 **{project_name}**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 အခြေအနေ ‣ {status}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{msg}",
            reply_markup=project_keyboard(project_name),
            parse_mode="Markdown"
        )

    elif data_val.startswith("logs_"):
        project_name = data_val.replace("logs_", "")
        await show_loading(query, f"⏳ မှတ်တမ်းများ ရယူနေသည်...")
        logs = get_logs(user_id, project_name)
        log_text = (
            f"📋 **မှတ်တမ်းများ — {project_name}**\n\n"
            f"```\n{logs[-3000:]}\n```"
        )
        await query.edit_message_text(
            log_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data=f"project_{project_name}")]]),
            parse_mode="Markdown"
        )

    elif data_val.startswith("upload_"):
        project_name = data_val.replace("upload_", "")
        context.user_data["waiting_for"] = "file_upload"
        context.user_data["current_project"] = project_name
        await query.edit_message_text(
            f"📤 **{project_name}** ထဲ ဖိုင်တင်မည်\n\nPython ဖိုင် (.py) တစ်ခု ပို့ပါ:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ပယ်ဖျက်မည်", callback_data=f"project_{project_name}")]]),
            parse_mode="Markdown"
        )

    # Delete single file
    elif data_val.startswith("delete_file_"):
        project_name = data_val.replace("delete_file_", "")
        path = get_project_path(user_id, project_name)
        files = [f for f in os.listdir(path) if not f.endswith(".log")] if os.path.exists(path) else []
        if not files:
            await query.edit_message_text(
                f"❌ **{project_name}** ထဲမှာ ဖိုင် မရှိဘူး!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data=f"project_{project_name}")]]),
                parse_mode="Markdown"
            )
        else:
            file_buttons = [[InlineKeyboardButton(f"🗑 {f}", callback_data=f"rm_file_{project_name}|{f}")] for f in files]
            file_buttons.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data=f"project_{project_name}")])
            await query.edit_message_text(
                f"🗑 **{project_name}** — ဖျက်မည့် ဖိုင် ရွေးပါ:",
                reply_markup=InlineKeyboardMarkup(file_buttons),
                parse_mode="Markdown"
            )

    elif data_val.startswith("rm_file_"):
        parts = data_val.replace("rm_file_", "").split("|")
        project_name, filename = parts[0], parts[1]
        await show_loading(query, f"⏳ {filename} ဖျက်နေသည်...")
        path = get_project_path(user_id, project_name)
        file_path = os.path.join(path, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            await query.edit_message_text(
                f"✅ **{filename}** ဖျက်ပြီးတယ်!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data=f"project_{project_name}")]]),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"❌ ဖိုင် မတွေ့ဘူး!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data=f"project_{project_name}")]]),
                parse_mode="Markdown"
            )

    # Delete entire folder
    elif data_val.startswith("delete_"):
        project_name = data_val.replace("delete_", "")
        await query.edit_message_text(
            f"━━━━━━━━━━━━━━━\n"
            f"🗂 **{project_name}** ဖိုလ်ဒါ ဖျက်မည်\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚠️ ဖိုင်အားလုံး ပျက်သွားမည်!\n"
            f"သေချာပြီလား?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ ဟုတ်ကဲ့ ဖျက်မည်", callback_data=f"confirm_delete_{project_name}"),
                 InlineKeyboardButton("❌ မဖျက်တော့ဘူး", callback_data=f"project_{project_name}")]
            ]),
            parse_mode="Markdown"
        )

    elif data_val.startswith("confirm_delete_"):
        project_name = data_val.replace("confirm_delete_", "")
        await show_loading(query, f"⏳ {project_name} ဖျက်နေသည်...")
        path = get_project_path(user_id, project_name)
        stop_project(user_id, project_name)
        if os.path.exists(path):
            shutil.rmtree(path)
        data = load_data()
        uid = str(user_id)
        if project_name in data["users"].get(uid, {}).get("projects", []):
            data["users"][uid]["projects"].remove(project_name)
            save_data(data)
        await query.edit_message_text(
            f"✅ **{project_name}** ဖိုလ်ဒါ ဖျက်ပြီးတယ်!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ပရောဂျက်များ", callback_data="my_projects")]]),
            parse_mode="Markdown"
        )

    elif data_val == "status":
        await show_loading(query, "⏳ အခြေအနေ စစ်ဆေးနေသည်...")
        total_running = len(running_processes)
        data = load_data()
        total_users = len(data.get("users", {}))
        total_projects = sum(len(u.get("projects", [])) for u in data.get("users", {}).values())
        text = (
            f"━━━━━━━━━━━━━━━\n"
            f"📊 **စနစ်အခြေအနေ**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 သုံးစွဲသူများ ‣ {total_users}\n"
            f"📁 စုစုပေါင်း ပရောဂျက် ‣ {total_projects}\n"
            f"▶️ လည်ပတ်နေသည် ‣ {total_running}\n"
            f"🕐 အချိန် ‣ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )

    elif data_val == "help":
        text = (
            "━━━━━━━━━━━━━━━\n"
            "ℹ️ **အသုံးပြုနည်း**\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ ပရောဂျက်အသစ် နှိပ်ပြီး အမည်ပေးပါ\n"
            "2️⃣ ပရောဂျက်ထဲ .py ဖိုင် upload တင်ပါ\n"
            "3️⃣ စတင်မည် နှိပ်ပြီး run ပါ\n"
            "4️⃣ မှတ်တမ်းများ မှာ output ကြည့်ပါ\n"
            "━━━━━━━━━━━━━━━\n"
            "⚠️ Bot token ကို .py ဖိုင်ထဲ\nထည့်ထားဖို့ မမေ့ပါနဲ့!"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 နောက်သို့", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    waiting_for = context.user_data.get("waiting_for")

    if waiting_for == "project_name":
        project_name = update.message.text.strip().replace(" ", "_")
        if not project_name.replace("_", "").isalnum():
            await update.message.reply_text("❌ ပရောဂျက် အမည်မှာ စာလုံးနှင့် ဂဏန်းများသာ သုံးပါ!")
            return
        data = load_data()
        uid = str(user_id)
        if project_name in data["users"].get(uid, {}).get("projects", []):
            await update.message.reply_text("❌ ဒီ ပရောဂျက် အမည် ရှိပြီးသားပဲ!")
            return
        create_project_dir(user_id, project_name)
        if uid not in data["users"]:
            data["users"][uid] = {"projects": [], "joined": str(datetime.now())}
        data["users"][uid]["projects"].append(project_name)
        save_data(data)
        context.user_data["waiting_for"] = None
        context.user_data["current_project"] = project_name
        await update.message.reply_text(
            f"✅ **{project_name}** ပရောဂျက် ဖန်တည်းပြီးတယ်!\n\nအခု .py ဖိုင် upload တင်ပါ:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 ဖိုင်တင်မည်", callback_data=f"upload_{project_name}")],
                [InlineKeyboardButton("🔙 ပရောဂျက်များ", callback_data="my_projects")]
            ]),
            parse_mode="Markdown"
        )

    elif waiting_for == "file_upload" and update.message.document:
        project_name = context.user_data.get("current_project")
        doc = update.message.document
        if not doc.file_name.endswith(".py"):
            await update.message.reply_text("❌ .py ဖိုင်များသာ upload တင်နိုင်တယ်!")
            return
        loading_msg = await update.message.reply_text("⏳ ဖိုင် upload တင်နေသည်...")
        path = get_project_path(user_id, project_name)
        file = await doc.get_file()
        file_path = os.path.join(path, doc.file_name)
        await file.download_to_drive(file_path)
        size = os.path.getsize(file_path)
        context.user_data["waiting_for"] = None
        await loading_msg.edit_text(
            f"━━━━━━━━━━━━━━━\n"
            f"✅ **Upload အောင်မြင်တယ်!**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📄 ဖိုင် ‣ {doc.file_name}\n"
            f"💾 အရွယ်အစား ‣ {size/1024:.1f} KB\n"
            f"━━━━━━━━━━━━━━━\n"
            f"စတင်မည် နှိပ်ပြီး run နိုင်ပြီ!",
            reply_markup=project_keyboard(project_name),
            parse_mode="Markdown"
        )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await message_handler(update, context)

# ========== MAIN ==========
def main():
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_text_handler))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
