import os
import json
import asyncio
import logging
import base64
import requests as _requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============ BOT CONFIGURATION ============
BOT_TOKEN = "8768410197:AAHOoLsZ7Ry2y4_FfyGkENRkPWHG7IVNPT8"
OWNER_ID = 6162078955
# ===========================================

load_dotenv()

import main as fb

_executor = ThreadPoolExecutor(max_workers=32)

GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO   = "yuennix/FB-TGBOT"
GITHUB_BRANCH = "main"
GITHUB_API    = f"https://api.github.com/repos/{GITHUB_REPO}/contents/users.json"

USERS_FILE = "users.json"

def _gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_from_github():
    if not GITHUB_TOKEN:
        return
    try:
        r = _requests.get(GITHUB_API, headers=_gh_headers(), params={"ref": GITHUB_BRANCH}, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            with open(USERS_FILE, "w") as f:
                f.write(content)
    except Exception:
        pass

def sync_to_github():
    if not GITHUB_TOKEN:
        return
    try:
        with open(USERS_FILE, "r") as f:
            content = f.read()
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        r = _requests.get(GITHUB_API, headers=_gh_headers(), params={"ref": GITHUB_BRANCH}, timeout=10)
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {
            "message": "chore: sync users.json",
            "content": encoded,
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha
        _requests.put(GITHUB_API, headers=_gh_headers(), json=payload, timeout=10)
    except Exception:
        pass

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_data       = {}
seen_users      = set()
approved_users  = set()
pending_users   = {}
stop_flags      = {}
created_accounts= []
user_credits    = {}
owner_action    = {}
creating_msg    = {}

def load_users():
    global seen_users, approved_users, user_credits, pending_users, created_accounts
    try:
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
        seen_users     = set(data.get("seen_users", []))
        approved_users = set(data.get("approved_users", []))
        user_credits   = {int(k): v for k, v in data.get("user_credits", {}).items()}
        for uid_str, info in data.get("pending_users", {}).items():
            uid = int(uid_str)
            if uid not in pending_users:
                pending_users[uid] = info
        created_accounts = data.get("created_accounts", [])
    except Exception:
        pass

def save_users():
    try:
        with open(USERS_FILE, "w") as f:
            json.dump({
                "seen_users":       list(seen_users),
                "approved_users":   list(approved_users),
                "user_credits":     {str(k): v for k, v in user_credits.items()},
                "pending_users":    {str(k): v for k, v in pending_users.items()},
                "created_accounts": created_accounts,
            }, f)
        sync_to_github()
    except Exception:
        pass

def make_start_kb(uid=0):
    is_owner = (uid == OWNER_ID)
    rows = [
        [InlineKeyboardButton(text="✨ START CREATION ✨", callback_data="menu:create")]
    ]
    if is_owner:
        rows.append([
            [InlineKeyboardButton(text="👤 MY ACCOUNTS", callback_data="menu:myaccs")],
            [InlineKeyboardButton(text="🌍 BOT ACCOUNTS", callback_data="menu:botaccs")],
        ])
        rows.append([InlineKeyboardButton(text="⚙️ OWNER PANEL ⚙️", callback_data="menu:admin")])
    else:
        rows.append([InlineKeyboardButton(text="👤 MY ACCOUNTS", callback_data="menu:myaccs")])
        rows.append([InlineKeyboardButton(text="💎 MY CREDITS", callback_data="menu:mycredits")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def make_name_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇵🇭 FILIPINO NAMES", callback_data="name:1")],
        [InlineKeyboardButton(text="🔥 RPW NAMES", callback_data="name:2")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="back:main")],
    ])

def make_gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 MALE", callback_data="gender:1")],
        [InlineKeyboardButton(text="👩 FEMALE", callback_data="gender:2")],
        [InlineKeyboardButton(text="🌈 MIXED", callback_data="gender:3")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="back:name")],
    ])

def make_acc_pass_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 CUSTOM PASSWORD", callback_data="accpass:custom")],
        [InlineKeyboardButton(text="🎲 RANDOM PASSWORD", callback_data="accpass:random")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="back:gender")],
    ])

def make_stop_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ STOP CREATION ⛔", callback_data=f"stop:{uid}")]
    ])

def make_approval_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ APPROVE", callback_data=f"access:ok:{user_id}"),
            InlineKeyboardButton(text="❌ DENY", callback_data=f"access:no:{user_id}"),
        ]
    ])

def make_credit_give_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5", callback_data=f"credits:give:{user_id}:5"),
         InlineKeyboardButton(text="10", callback_data=f"credits:give:{user_id}:10"),
         InlineKeyboardButton(text="20", callback_data=f"credits:give:{user_id}:20")],
        [InlineKeyboardButton(text="50", callback_data=f"credits:give:{user_id}:50"),
         InlineKeyboardButton(text="100", callback_data=f"credits:give:{user_id}:100"),
         InlineKeyboardButton(text="✏️ CUSTOM", callback_data=f"credits:give:{user_id}:custom")],
    ])

def make_admin_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 APPROVED USERS", callback_data="menu:users")],
        [InlineKeyboardButton(text="📋 CREATED ACCOUNTS", callback_data="menu:accounts")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")],
    ])

def make_users_kb():
    rows = []
    users = [u for u in approved_users if u != OWNER_ID]
    if not users:
        rows.append([InlineKeyboardButton(text="— NO APPROVED USERS —", callback_data="noop")])
    else:
        for u in users:
            info    = pending_users.get(u, {})
            label   = info.get("name", str(u))
            credits = user_credits.get(u, 0)
            rows.append([InlineKeyboardButton(
                text=f"👤 {label} ({u}) | 💳 {credits} CREDITS",
                callback_data="noop"
            )])
            rows.append([
                InlineKeyboardButton(text="➕ ADD CREDITS", callback_data=f"credits:add:{u}"),
                InlineKeyboardButton(text="🚫 REVOKE", callback_data=f"revoke:{u}"),
            ])
    rows.append([InlineKeyboardButton(text="◀️ BACK", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def make_accounts_kb():
    rows = []
    if created_accounts:
        rows.append([InlineKeyboardButton(
            text=f"🗑 CLEAR ALL ({len(created_accounts)} ACCS)",
            callback_data="accounts:clear"
        )])
    else:
        rows.append([InlineKeyboardButton(text="— NO ACCOUNTS YET —", callback_data="noop")])
    rows.append([InlineKeyboardButton(text="◀️ BACK", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def is_allowed(uid):
    return uid == OWNER_ID or uid in approved_users

async def _del(chat_id, msg_id, delay=0):
    try:
        if delay:
            await asyncio.sleep(delay)
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid        = message.from_user.id
    first_name = message.from_user.first_name or "there"
    username   = f"@{message.from_user.username}" if message.from_user.username else "no username"

    user_data.pop(uid, None)
    owner_action.pop(uid, None)
    banner_id = creating_msg.pop(uid, None)
    if banner_id:
        asyncio.create_task(_del(uid, banner_id))

    if uid == OWNER_ID:
        approved_users.add(uid)

    if uid not in seen_users:
        seen_users.add(uid)
        save_users()
        await message.answer(
            f"┌─────────────────────────────────────┐\n"
            f"│  ✨ *WELCOME, {first_name}!* ✨      │\n"
            f"├─────────────────────────────────────┤\n"
            f"│  🤖 *FACEBOOK AUTO CREATOR BOT*      │\n"
            f"├─────────────────────────────────────┤\n"
            f"│  🔥 FAST & RELIABLE                  │\n"
            f"│  📧 YANDEX EMAIL SUPPORT              │\n"
            f"│  🔐 AUTO OTP FETCH                   │\n"
            f"└─────────────────────────────────────┘\n\n"
            f"📌 *HOW TO USE:*\n"
            f"▸ 1️⃣ Tap *START CREATION*\n"
            f"▸ 2️⃣ Choose name style\n"
            f"▸ 3️⃣ Choose gender\n"
            f"▸ 4️⃣ Set account password\n"
            f"▸ 5️⃣ Type how many accounts\n"
            f"▸ 6️⃣ Get results instantly!\n\n"
            f"⚠️ *NOTE:* ACCESS REQUIRES OWNER APPROVAL.",
            parse_mode="Markdown"
        )

    if is_allowed(uid):
        await message.answer(
            "┌─────────────────────────────────────┐\n"
            "│  🤖 *FACEBOOK AUTO CREATOR*         │\n"
            "├─────────────────────────────────────┤\n"
            "│  👇 *SELECT AN OPTION BELOW* 👇      │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )
        return

    if uid in pending_users:
        await message.answer(
            "┌─────────────────────────────────────┐\n"
            "│  ⏳ *ACCESS REQUEST PENDING*         │\n"
            "├─────────────────────────────────────┤\n"
            "│  YOUR REQUEST IS WAITING FOR         │\n"
            "│  OWNER APPROVAL. PLEASE WAIT.        │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown"
        )
        return

    pending_users[uid] = {"name": first_name, "username": username}
    save_users()
    req_msg = await message.answer(
        "┌─────────────────────────────────────┐\n"
        "│  🔒 *ACCESS REQUIRED*               │\n"
        "├─────────────────────────────────────┤\n"
        "│  THIS BOT REQUIRES APPROVAL TO USE.  │\n"
        "│  YOUR REQUEST HAS BEEN SENT TO THE   │\n"
        "│  OWNER. PLEASE WAIT FOR APPROVAL.   │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown"
    )
    pending_users[uid]["req_msg_id"] = req_msg.message_id
    try:
        await bot.send_message(
            OWNER_ID,
            f"┌─────────────────────────────────────┐\n"
            f"│  🔔 *NEW ACCESS REQUEST*            │\n"
            f"├─────────────────────────────────────┤\n"
            f"│  👤 NAME: *{first_name}*             │\n"
            f"│  🆔 USER ID: `{uid}`                 │\n"
            f"│  📛 USERNAME: {username}             │\n"
            f"└─────────────────────────────────────┘\n\n"
            f"APPROVE OR DENY BELOW:",
            parse_mode="Markdown",
            reply_markup=make_approval_kb(uid)
        )
    except Exception:
        pass

@dp.message(Command("credits"))
async def cmd_credits(message: types.Message):
    uid = message.from_user.id
    banner_id = creating_msg.pop(uid, None)
    if banner_id:
        asyncio.create_task(_del(uid, banner_id))
    if uid == OWNER_ID:
        await message.answer(
            "┌─────────────────────────────────────┐\n"
            "│  👑 *OWNER*                         │\n"
            "├─────────────────────────────────────┤\n"
            "│  YOU HAVE *UNLIMITED CREDITS*.       │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown"
        )
        return
    if not is_allowed(uid):
        return
    credits = user_credits.get(uid, 0)
    await message.answer(
        f"┌─────────────────────────────────────┐\n"
        f"│  💎 *YOUR CREDITS*                  │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  AVAILABLE: *{credits}* CREDIT(S)    │\n"
        f"│  _(1 CREDIT = 1 FACEBOOK ACCOUNT)_  │\n"
        f"└─────────────────────────────────────┘",
        parse_mode="Markdown"
    )

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("🔒 OWNER ONLY COMMAND.", parse_mode="Markdown")
        return
    total_seen      = len(seen_users)
    total_approved  = len([u for u in approved_users if u != OWNER_ID])
    total_pending   = len(pending_users)
    total_credits_remaining = sum(user_credits.values())
    total_accounts  = len(created_accounts)
    await message.answer(
        f"┌─────────────────────────────────────┐\n"
        f"│  📊 *BOT STATISTICS*                │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  👥 USERS SEEN: *{total_seen}*       │\n"
        f"│  ✅ APPROVED: *{total_approved}*      │\n"
        f"│  ⏳ PENDING: *{total_pending}*       │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  💳 CREDITS USED: *{total_accounts}* │\n"
        f"│  💰 CREDITS LEFT: *{total_credits_remaining}* │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  🤖 ACCOUNTS CREATED: *{total_accounts}* │\n"
        f"└─────────────────────────────────────┘",
        parse_mode="Markdown"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer(
        "┌─────────────────────────────────────┐\n"
        "│  ⚙️ *OWNER MENU*                    │\n"
        "├─────────────────────────────────────┤\n"
        "│  CHOOSE A SECTION:                  │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown",
        reply_markup=make_admin_menu_kb()
    )

@dp.callback_query(lambda c: c.data.startswith("access:"))
async def cb_approval(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("YOU ARE NOT THE OWNER.", show_alert=True)
        return

    parts     = callback.data.split(":")
    action    = parts[1]
    target_id = int(parts[2])
    user_info = pending_users.get(target_id, {})
    name      = user_info.get("name", "User")

    if action == "ok":
        approved_users.add(target_id)
        pending_users.pop(target_id, None)
        await callback.message.edit_text(
            f"┌─────────────────────────────────────┐\n"
            f"│  ✅ *APPROVED!*                     │\n"
            f"├─────────────────────────────────────┤\n"
            f"│  👤 {name} (`{target_id}`)          │\n"
            f"└─────────────────────────────────────┘\n\n"
            f"💳 *HOW MANY CREDITS TO GIVE THIS USER?*\n"
            f"_(1 CREDIT = 1 ACCOUNT)_",
            parse_mode="Markdown",
            reply_markup=make_credit_give_kb(target_id)
        )
    else:
        pending_users.pop(target_id, None)
        await callback.message.edit_text(
            f"┌─────────────────────────────────────┐\n"
            f"│  ❌ *DENIED*                        │\n"
            f"├─────────────────────────────────────┤\n"
            f"│  👤 {name} (`{target_id}`)          │\n"
            f"│  HAS BEEN REJECTED.                 │\n"
            f"└─────────────────────────────────────┘",
            parse_mode="Markdown"
        )
        await bot.send_message(
            target_id,
            "┌─────────────────────────────────────┐\n"
            "│  ❌ *ACCESS DENIED*                 │\n"
            "├─────────────────────────────────────┤\n"
            "│  YOUR ACCESS REQUEST WAS DENIED.    │\n"
            "│  CONTACT THE OWNER IF YOU THINK     │\n"
            "│  THIS IS A MISTAKE.                 │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown"
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("credits:give:"))
async def cb_give_credits(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("OWNER ONLY.", show_alert=True)
        return

    parts     = callback.data.split(":")
    target_id = int(parts[2])
    amount    = parts[3]

    if amount == "custom":
        owner_action[OWNER_ID] = {
            "action":       "add_credits",
            "target":       target_id,
            "prompt_msg_id": callback.message.message_id,
        }
        await callback.message.edit_text(
            f"✏️ *TYPE THE NUMBER OF CREDITS TO GIVE* 👤 `{target_id}`:\n\n_(SEND A NUMBER, E.G. 30)_",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    amount = int(amount)
    user_credits[target_id] = user_credits.get(target_id, 0) + amount
    total = user_credits[target_id]
    save_users()

    target_info = pending_users.get(target_id, {})
    name = target_info.get("name", str(target_id))

    await callback.message.edit_text(
        f"┌─────────────────────────────────────┐\n"
        f"│  ✅ *CREDITS ADDED!*                │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  👤 {name} (`{target_id}`)          │\n"
        f"│  💳 NEW TOTAL: *{total}* CREDIT(S)  │\n"
        f"└─────────────────────────────────────┘",
        parse_mode="Markdown"
    )
    try:
        req_msg_id = pending_users.get(target_id, {}).get("req_msg_id")
        if req_msg_id:
            asyncio.create_task(_del(target_id, req_msg_id))
        await bot.send_message(
            target_id,
            f"┌─────────────────────────────────────┐\n"
            f"│  ✅ *ACCESS APPROVED!*              │\n"
            f"├─────────────────────────────────────┤\n"
            f"│  💳 YOU'VE BEEN GIVEN *{amount}*     │\n"
            f"│  CREDIT(S).                         │\n"
            f"│  _(1 CREDIT = 1 FACEBOOK ACCOUNT)_  │\n"
            f"├─────────────────────────────────────┤\n"
            f"│  📧 EMAIL: YANDEX ALIAS WILL BE USED│\n"
            f"└─────────────────────────────────────┘\n\n"
            f"👇 *TAP BELOW TO START* 👇",
            parse_mode="Markdown",
            reply_markup=make_start_kb(target_id)
        )
    except Exception:
        pass
    await callback.answer(f"✅ GAVE {amount} CREDITS!", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("credits:add:"))
async def cb_add_credits(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("OWNER ONLY.", show_alert=True)
        return
    target_id = int(callback.data.split(":")[2])
    info  = pending_users.get(target_id, {})
    name  = info.get("name", str(target_id))
    total = user_credits.get(target_id, 0)
    await callback.message.edit_text(
        f"┌─────────────────────────────────────┐\n"
        f"│  💳 *ADD CREDITS*                   │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  👤 {name} (`{target_id}`)          │\n"
        f"│  💰 CURRENT: *{total}* CREDIT(S)    │\n"
        f"└─────────────────────────────────────┘\n\n"
        f"HOW MANY TO ADD?",
        parse_mode="Markdown",
        reply_markup=make_credit_give_kb(target_id)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:admin")
async def cb_admin_menu(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("OWNER ONLY.", show_alert=True)
        return
    await callback.message.edit_text(
        "┌─────────────────────────────────────┐\n"
        "│  ⚙️ *OWNER MENU*                    │\n"
        "├─────────────────────────────────────┤\n"
        "│  CHOOSE A SECTION:                  │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown",
        reply_markup=make_admin_menu_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:back")
async def cb_menu_back(callback: types.CallbackQuery):
    uid = callback.from_user.id
    await callback.message.edit_text(
        "┌─────────────────────────────────────┐\n"
        "│  🤖 *FACEBOOK AUTO CREATOR*         │\n"
        "├─────────────────────────────────────┤\n"
        "│  👇 *SELECT AN OPTION BELOW* 👇      │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown",
        reply_markup=make_start_kb(uid)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:users")
async def cb_menu_users(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("OWNER ONLY.", show_alert=True)
        return
    users  = [u for u in approved_users if u != OWNER_ID]
    header = f"┌─────────────────────────────────────┐\n│  👥 *APPROVED USERS* — {len(users)} USER(S) │\n└─────────────────────────────────────┘\n\nMANAGE CREDITS & ACCESS:"
    await callback.message.edit_text(header, parse_mode="Markdown", reply_markup=make_users_kb())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("revoke:"))
async def cb_revoke(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("OWNER ONLY.", show_alert=True)
        return
    target = int(callback.data.split(":")[1])
    approved_users.discard(target)
    user_credits.pop(target, None)
    save_users()
    try:
        await bot.send_message(target, "🚫 YOUR ACCESS TO THIS BOT HAS BEEN REVOKED.")
    except Exception:
        pass
    users  = [u for u in approved_users if u != OWNER_ID]
    header = f"┌─────────────────────────────────────┐\n│  👥 *APPROVED USERS* — {len(users)} USER(S) │\n└─────────────────────────────────────┘\n\nMANAGE CREDITS & ACCESS:"
    await callback.message.edit_text(header, parse_mode="Markdown", reply_markup=make_users_kb())
    await callback.answer(f"🚫 REVOKED ACCESS FOR {target}", show_alert=True)

@dp.callback_query(lambda c: c.data == "menu:accounts")
async def cb_menu_accounts(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("OWNER ONLY.", show_alert=True)
        return
    if not created_accounts:
        text = "┌─────────────────────────────────────┐\n│  📋 *CREATED ACCOUNTS*                 │\n├─────────────────────────────────────┤\n│  NO ACCOUNTS HAVE BEEN CREATED YET.  │\n└─────────────────────────────────────┘"
    else:
        lines = []
        for i, acc in enumerate(created_accounts, 1):
            lines.append(
                f"┌─────────────────────────────────────┐\n"
                f"│  *{i}.* 👤 `{acc['name']}`               │\n"
                f"│      📧 `{acc['email']}`               │\n"
                f"│      🔑 `{acc['password']}`            │\n"
                f"│      🆔 `{acc['uid']}`                 │"
            )
            if acc.get('cookies'):
                lines.append(f"│      🍪 `{acc['cookies'][:80]}...`        │")
            lines.append(f"└─────────────────────────────────────┘")
        body = "\n\n".join(lines)
        text = f"┌─────────────────────────────────────┐\n│  📋 *CREATED ACCOUNTS* — {len(created_accounts)} TOTAL │\n└─────────────────────────────────────┘\n\n{body}"
        if len(text) > 4000:
            text = text[:3950] + "\n\n_...TRUNCATED_"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=make_accounts_kb())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "accounts:clear")
async def cb_accounts_clear(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("OWNER ONLY.", show_alert=True)
        return
    count = len(created_accounts)
    created_accounts.clear()
    save_users()
    await callback.message.edit_text(
        f"┌─────────────────────────────────────┐\n"
        f"│  🗑 *CLEARED!*                      │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  {count} ACCOUNT RECORD(S) REMOVED.  │\n"
        f"└─────────────────────────────────────┘\n\n"
        f"┌─────────────────────────────────────┐\n"
        f"│  📋 *CREATED ACCOUNTS*              │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  NO ACCOUNTS YET.                   │\n"
        f"└─────────────────────────────────────┘",
        parse_mode="Markdown",
        reply_markup=make_accounts_kb()
    )
    await callback.answer("✅ CLEARED!", show_alert=True)

@dp.callback_query(lambda c: c.data == "menu:myaccs")
async def cb_my_accounts(callback: types.CallbackQuery):
    uid  = callback.from_user.id
    if not is_allowed(uid):
        await callback.answer("NO ACCESS.", show_alert=True)
        return
    mine = [a for a in created_accounts if a.get("by") == uid]
    if not mine:
        text = "┌─────────────────────────────────────┐\n│  📋 *MY ACCOUNTS*                    │\n├─────────────────────────────────────┤\n│  YOU HAVEN'T CREATED ANY ACCOUNTS    │\n│  YET.                               │\n└─────────────────────────────────────┘"
    else:
        lines = []
        for i, acc in enumerate(mine, 1):
            otp_line = f"\n│      🔢 *OTP:* `{acc.get('otp_code', 'N/A')}`" if acc.get('otp_code') else ""
            lines.append(
                f"┌─────────────────────────────────────┐\n"
                f"│  *{i}.* 👤 `{acc['name']}`               │\n"
                f"│      📧 `{acc['email']}`               │\n"
                f"│      🔑 `{acc['password']}`            │\n"
                f"│      🆔 `{acc['uid']}`                 │{otp_line}"
            )
            if acc.get('cookies'):
                lines.append(f"│      🍪 `{acc['cookies'][:80]}...`        │")
            lines.append(f"└─────────────────────────────────────┘")
        body = "\n\n".join(lines)
        text = f"┌─────────────────────────────────────┐\n│  📋 *MY ACCOUNTS* — {len(mine)} TOTAL │\n└─────────────────────────────────────┘\n\n{body}"
        if len(text) > 4000:
            text = text[:3950] + "\n\n_...TRUNCATED_"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")]
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:botaccs")
async def cb_bot_accounts(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if not is_allowed(uid):
        await callback.answer("NO ACCESS.", show_alert=True)
        return
    is_owner = (uid == OWNER_ID)
    mine = created_accounts if is_owner else [a for a in created_accounts if a.get("by") == uid]
    label = "🌍 *BOT ACCOUNTS*" if is_owner else "📋 *MY ACCOUNTS*"
    if not mine:
        text = f"┌─────────────────────────────────────┐\n│  {label}                 │\n├─────────────────────────────────────┤\n│  NO ACCOUNTS CREATED YET.            │\n└─────────────────────────────────────┘"
    else:
        lines = []
        for i, acc in enumerate(mine, 1):
            by_line = f"\n│      👤 BY `{acc.get('by', '?')}`" if is_owner else ""
            otp_line = f"\n│      🔢 *OTP:* `{acc.get('otp_code', 'N/A')}`" if acc.get('otp_code') else ""
            lines.append(
                f"┌─────────────────────────────────────┐\n"
                f"│  *{i}.* 👤 `{acc['name']}`               │\n"
                f"│      📧 `{acc['email']}`               │\n"
                f"│      🔑 `{acc['password']}`            │\n"
                f"│      🆔 `{acc['uid']}`                 │{by_line}{otp_line}"
            )
            if acc.get('cookies'):
                lines.append(f"│      🍪 `{acc['cookies'][:80]}...`        │")
            lines.append(f"└─────────────────────────────────────┘")
        body = "\n\n".join(lines)
        text = f"┌─────────────────────────────────────┐\n│  {label} — {len(mine)} ACCOUNT(S) │\n└─────────────────────────────────────┘\n\n{body}"
        if len(text) > 4000:
            text = text[:3950] + "\n\n_...TRUNCATED_"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")]
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:mycredits")
async def cb_my_credits(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if not is_allowed(uid):
        await callback.answer("NO ACCESS.", show_alert=True)
        return
    credits = user_credits.get(uid, 0)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")]
    ])
    await callback.message.edit_text(
        f"┌─────────────────────────────────────┐\n"
        f"│  💎 *MY CREDITS*                    │\n"
        f"├─────────────────────────────────────┤\n"
        f"│  AVAILABLE: *{credits}* CREDIT(S)    │\n"
        f"│  _(1 CREDIT = 1 FACEBOOK ACCOUNT)_  │\n"
        f"└─────────────────────────────────────┘",
        parse_mode="Markdown",
        reply_markup=back_kb
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "noop")
async def cb_noop(callback: types.CallbackQuery):
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:create")
async def cb_name_style(callback: types.CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ YOU DON'T HAVE ACCESS.", show_alert=True)
        return
    await callback.message.edit_text(
        "┌─────────────────────────────────────┐\n"
        "│  📛 *CHOOSE NAME STYLE*             │\n"
        "├─────────────────────────────────────┤\n"
        "│  SELECT ONE:                        │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown", reply_markup=make_name_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("back:"))
async def cb_back(callback: types.CallbackQuery):
    uid  = callback.from_user.id
    step = callback.data.split(":")[1]
    if uid in user_data:
        user_data[uid].pop("awaiting", None)
        user_data[uid].pop("prompt_msg_id", None)
    if step == "main":
        user_data.pop(uid, None)
        await callback.message.edit_text(
            "┌─────────────────────────────────────┐\n"
            "│  🤖 *FACEBOOK AUTO CREATOR*         │\n"
            "├─────────────────────────────────────┤\n"
            "│  👇 *SELECT AN OPTION BELOW* 👇      │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )
    elif step == "name":
        await callback.message.edit_text(
            "┌─────────────────────────────────────┐\n"
            "│  📛 *CHOOSE NAME STYLE*             │\n"
            "├─────────────────────────────────────┤\n"
            "│  SELECT ONE:                        │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown", reply_markup=make_name_kb()
        )
    elif step == "gender":
        await callback.message.edit_text(
            "┌─────────────────────────────────────┐\n"
            "│  ⚤ *CHOOSE GENDER*                 │\n"
            "├─────────────────────────────────────┤\n"
            "│  SELECT ONE:                        │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown", reply_markup=make_gender_kb()
        )
    elif step == "accpass":
        await callback.message.edit_text(
            "┌─────────────────────────────────────┐\n"
            "│  🔑 *SET ACCOUNT PASSWORD*          │\n"
            "├─────────────────────────────────────┤\n"
            "│  CHOOSE OPTION:                     │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=make_acc_pass_kb()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("name:"))
async def cb_gender(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user_data[uid] = {"name": callback.data.split(":")[1]}
    await callback.message.edit_text(
        "┌─────────────────────────────────────┐\n"
        "│  ⚤ *CHOOSE GENDER*                 │\n"
        "├─────────────────────────────────────┤\n"
        "│  SELECT ONE:                        │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown", reply_markup=make_gender_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("gender:"))
async def cb_gender_select(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_data:
        await callback.answer("SESSION EXPIRED. USE /START", show_alert=True)
        return
    user_data[uid]["gender"] = callback.data.split(":")[1]
    user_data[uid]["domain"] = "yandex"
    await callback.message.edit_text(
        "┌─────────────────────────────────────┐\n"
        "│  🔑 *SET ACCOUNT PASSWORD*          │\n"
        "├─────────────────────────────────────┤\n"
        "│  CHOOSE OPTION:                     │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown",
        reply_markup=make_acc_pass_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("accpass:"))
async def cb_acc_pass(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_data:
        await callback.answer("SESSION EXPIRED. USE /START", show_alert=True)
        return
    choice = callback.data.split(":")[1]
    if choice == "random":
        user_data[uid]["password"]      = None
        user_data[uid]["awaiting"]      = "count"
        user_data[uid]["prompt_msg_id"] = callback.message.message_id
        await callback.message.edit_text(
            "┌─────────────────────────────────────────────────┐\n"
            "│  🔢 *HOW MANY ACCOUNTS?*                       │\n"
            "├─────────────────────────────────────────────────┤\n"
            "│  _(TYPE A NUMBER, E.G. 5)_                     │\n"
            "├─────────────────────────────────────────────────┤\n"
            "│  📧 EMAIL: YANDEX ALIAS WILL BE USED            │\n"
            "│  ✅ OTP WILL BE AUTO-FETCHED FROM YANDEX EMAIL  │\n"
            "│  🔄 WILL RETRY TWICE IF OTP NOT FOUND           │\n"
            "└─────────────────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ BACK", callback_data="back:accpass")]
            ])
        )
    else:
        user_data[uid]["awaiting"]      = "custom_pass"
        user_data[uid]["prompt_msg_id"] = callback.message.message_id
        await callback.message.edit_text(
            "┌─────────────────────────────────────┐\n"
            "│  🔑 *TYPE YOUR CUSTOM PASSWORD*     │\n"
            "├─────────────────────────────────────┤\n"
            "│  _(MINIMUM 6 CHARACTERS)_           │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ BACK", callback_data="back:accpass")]
            ])
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("stop:"))
async def cb_stop(callback: types.CallbackQuery):
    uid = int(callback.data.split(":")[1])
    if callback.from_user.id != uid and callback.from_user.id != OWNER_ID:
        await callback.answer("NOT YOUR SESSION.", show_alert=True)
        return
    stop_flags[uid] = True
    creating_msg.pop(uid, None)
    await callback.answer("⛔ STOPPED!", show_alert=False)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await bot.send_message(
        uid,
        "┌─────────────────────────────────────┐\n"
        "│  ⛔ *CREATION STOPPED.*             │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown"
    )
    await bot.send_message(
        uid,
        "┌─────────────────────────────────────┐\n"
        "│  🤖 *FACEBOOK AUTO CREATOR*         │\n"
        "├─────────────────────────────────────┤\n"
        "│  👇 *SELECT AN OPTION BELOW* 👇      │\n"
        "└─────────────────────────────────────┘",
        parse_mode="Markdown",
        reply_markup=make_start_kb(uid)
    )

# ============ MAIN CREATION FUNCTION ============
async def _start_creation(uid, count, data, chat_id, is_continuation=False):
    stop_flags[uid] = False

    if not is_continuation:
        banner = await bot.send_message(
            chat_id,
            f"┌─────────────────────────────────────────────────┐\n"
            f"│  ⚡ *CREATING {count} ACCOUNT(S)...*               │\n"
            f"├─────────────────────────────────────────────────┤\n"
            f"│  📧 YANDEX ALIAS WILL BE USED                    │\n"
            f"│  🔐 OTP AUTO-FETCHED                             │\n"
            f"│  🔄 RETRY TWICE IF FAIL                          │\n"
            f"│  ⏰ 2 MIN WAIT FOR OTP                           │\n"
            f"└─────────────────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=make_stop_kb(uid)
        )
        creating_msg[uid] = banner.message_id

    name_val   = str(data.get("name", "1"))
    gender_val = str(data.get("gender", "1"))
    custom_pw  = data.get("password", None)

    N_WORKERS = 2
    session_executor = ThreadPoolExecutor(max_workers=N_WORKERS, thread_name_prefix=f"fb_{uid}")

    success = 0
    lock = asyncio.Lock()
    stopped = False

    async def _worker():
        nonlocal success, stopped
        while True:
            if stopped or stop_flags.get(uid):
                return
            if success >= count:
                return

            def _register():
                try:
                    result = fb.register_account_for_bot(
                        domain_choice="yandex",
                        name_option=name_val,
                        gender_option=gender_val,
                        custom_pass=custom_pw,
                    )
                    return result
                except Exception as e:
                    print(f"[ERROR] Registration error: {e}")
                    return {"error": str(e)}

            try:
                result = await asyncio.to_thread(_register)
            except Exception as e:
                result = {"error": str(e)}

            if stop_flags.get(uid):
                async with lock:
                    stopped = True
                return

            if result and isinstance(result, dict) and result.get("uid"):
                async with lock:
                    if stopped or success >= count:
                        return
                    success += 1
                    current = success
                    if uid != OWNER_ID:
                        user_credits[uid] = max(0, user_credits.get(uid, 0) - 1)
                    credits_left = "" if uid == OWNER_ID else f"\n│  💳 CREDITS LEFT: *{user_credits.get(uid, 0)}*"
                    
                    otp_code_value = result.get("otp_code")
                    if otp_code_value and otp_code_value != "N/A" and otp_code_value != "None":
                        otp_line = f"\n│  🔢 *OTP USED:* `{otp_code_value}`"
                    else:
                        otp_line = ""
                    
                    cookies_full = result.get("cookies", "")
                    
                    account_data = {
                        "name":     result.get("name", "Unknown"),
                        "email":    result.get("email", "N/A"),
                        "password": result.get("password", "N/A"),
                        "uid":      result.get("uid", "N/A"),
                        "cookies":  cookies_full,
                        "otp_code": otp_code_value if otp_code_value else None,
                        "by":       uid,
                    }
                    created_accounts.append(account_data)
                    save_users()
                    
                    cookie_msg = f"\n│  🍪 *COOKIES:* `{cookies_full[:150]}...`" if cookies_full else ""
                    
                await bot.send_message(
                    chat_id,
                    f"┌─────────────────────────────────────────────────┐\n"
                    f"│  ✅ *ACCOUNT {current}/{count} CREATED!*           │\n"
                    f"├─────────────────────────────────────────────────┤\n"
                    f"│  👤 *NAME:* `{result.get('name', 'Unknown')}`     │\n"
                    f"│  📧 *EMAIL:* `{result.get('email', 'N/A')}`       │\n"
                    f"│  🔑 *PASSWORD:* `{result.get('password', 'N/A')}` │\n"
                    f"│  🆔 *UID:* `{result.get('uid', 'N/A')}`           │{otp_line}{cookie_msg}{credits_left}\n"
                    f"└─────────────────────────────────────────────────┘\n\n"
                    f"🔗 *LOGIN:* https://facebook.com/{result.get('uid', '')}",
                    parse_mode="Markdown"
                )
                
                if current >= count:
                    return
            
            elif result and isinstance(result, dict) and result.get("error"):
                await asyncio.sleep(3)
            
            else:
                await asyncio.sleep(2)

    tasks = [asyncio.create_task(_worker()) for _ in range(N_WORKERS)]
    try:
        await asyncio.gather(*tasks)
    finally:
        session_executor.shutdown(wait=False)

    if not is_continuation:
        banner_id = creating_msg.pop(uid, None)
        if banner_id:
            asyncio.create_task(_del(chat_id, banner_id))

    stop_flags.pop(uid, None)
    credits_summary = (
        "" if uid == OWNER_ID
        else f"\n│  💳 CREDITS REMAINING: *{user_credits.get(uid, 0)}*"
    )

    if success == 0:
        await bot.send_message(
            chat_id,
            "┌─────────────────────────────────────────────────┐\n"
            "│  ❌ *NO ACCOUNTS CREATED.*                      │\n"
            "├─────────────────────────────────────────────────┤\n"
            "│  FACEBOOK MAY BE BLOCKING REGISTRATIONS FROM    │\n"
            "│  THIS SERVER'S IP. TRY AGAIN LATER OR           │\n"
            "│  CONTACT THE OWNER.                             │\n"
            "├─────────────────────────────────────────────────┤\n"
            "│  💡 *TIP:* MAKE SURE YOUR YANDEX EMAIL IS       │\n"
            "│     WORKING AND CHECK SPAM FOLDER.              │\n"
            "└─────────────────────────────────────────────────┘",
            parse_mode="Markdown"
        )
        await bot.send_message(
            chat_id,
            "┌─────────────────────────────────────┐\n"
            "│  🤖 *FACEBOOK AUTO CREATOR*         │\n"
            "├─────────────────────────────────────┤\n"
            "│  👇 *SELECT AN OPTION BELOW* 👇      │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )
    else:
        await bot.send_message(
            chat_id,
            f"┌─────────────────────────────────────────────────┐\n"
            f"│  🎉 *DONE!* {success}/{count} ACCOUNTS CREATED.{credits_summary} │\n"
            f"└─────────────────────────────────────────────────┘",
            parse_mode="Markdown"
        )
        await bot.send_message(
            chat_id,
            "┌─────────────────────────────────────┐\n"
            "│  🤖 *FACEBOOK AUTO CREATOR*         │\n"
            "├─────────────────────────────────────┤\n"
            "│  👇 *SELECT AN OPTION BELOW* 👇      │\n"
            "└─────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )

@dp.message()
async def handle_text(message: types.Message):
    uid      = message.from_user.id
    chat_id  = message.chat.id
    entered  = (message.text or "").strip()

    data     = user_data.get(uid)
    awaiting = data.get("awaiting") if data else None

    if not data or awaiting not in ("custom_pass", "count"):
        return

    prompt_msg_id = data.pop("prompt_msg_id", None)

    asyncio.create_task(_del(chat_id, message.message_id))

    if awaiting == "custom_pass":
        if prompt_msg_id:
            asyncio.create_task(_del(chat_id, prompt_msg_id))
        if len(entered) < 6:
            err = await message.answer(
                "┌─────────────────────────────────────┐\n"
                "│  ⚠️ PASSWORD TOO SHORT              │\n"
                "├─────────────────────────────────────┤\n"
                "│  _(MIN 6 CHARS). TRY AGAIN:_        │\n"
                "└─────────────────────────────────────┘",
                parse_mode="Markdown"
            )
            asyncio.create_task(_del(chat_id, err.message_id, delay=4))
            user_data[uid]["awaiting"]      = "custom_pass"
            user_data[uid]["prompt_msg_id"] = err.message_id
            return
        user_data[uid]["password"] = entered
        user_data[uid].pop("awaiting", None)
        prompt = await message.answer(
            "✅ *CUSTOM PASSWORD SET!*\n\n"
            "┌─────────────────────────────────────────────────┐\n"
            "│  🔢 *HOW MANY ACCOUNTS?*                       │\n"
            "├─────────────────────────────────────────────────┤\n"
            "│  _(TYPE A NUMBER, E.G. 5)_                     │\n"
            "├─────────────────────────────────────────────────┤\n"
            "│  📧 EMAIL: YANDEX ALIAS WILL BE USED            │\n"
            "│  ✅ OTP WILL BE AUTO-FETCHED FROM YANDEX EMAIL  │\n"
            "└─────────────────────────────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ BACK", callback_data="back:accpass")]
            ])
        )
        user_data[uid]["awaiting"]      = "count"
        user_data[uid]["prompt_msg_id"] = prompt.message_id
        return

    if awaiting == "count":
        if prompt_msg_id:
            asyncio.create_task(_del(chat_id, prompt_msg_id))
        if not entered.isdigit() or int(entered) <= 0:
            err = await message.answer(
                "┌─────────────────────────────────────┐\n"
                "│  ⚠️ PLEASE TYPE A *VALID NUMBER*    │\n"
                "├─────────────────────────────────────┤\n"
                "│  _(E.G. 5)_                         │\n"
                "└─────────────────────────────────────┘",
                parse_mode="Markdown"
            )
            asyncio.create_task(_del(chat_id, err.message_id, delay=4))
            user_data[uid]["awaiting"]      = "count"
            user_data[uid]["prompt_msg_id"] = err.message_id
            return
        count = int(entered)
        if count > 50:
            count = 50
            await message.answer("⚠️ MAX 50 ACCOUNTS PER BATCH. CREATING 50.", parse_mode="Markdown")
        if uid != OWNER_ID:
            available = user_credits.get(uid, 0)
            if available <= 0:
                err = await message.answer(
                    "┌─────────────────────────────────────┐\n"
                    "│  ❌ *YOU HAVE NO CREDITS LEFT.*     │\n"
                    "├─────────────────────────────────────┤\n"
                    "│  CONTACT THE OWNER TO GET MORE      │\n"
                    "│  CREDITS.                           │\n"
                    "└─────────────────────────────────────┘",
                    parse_mode="Markdown"
                )
                asyncio.create_task(_del(chat_id, err.message_id, delay=6))
                user_data.pop(uid, None)
                return
            if count > available:
                count = available
                note = await message.answer(
                    f"⚠️ YOU ONLY HAVE *{available}* CREDIT(S). CREATING *{available}* ACCOUNT(S).",
                    parse_mode="Markdown"
                )
                asyncio.create_task(_del(chat_id, note.message_id, delay=5))

        data = user_data.pop(uid)
        await _start_creation(uid, count, data, message.chat.id)

async def main():
    print("=" * 70)
    print("🤖 FACEBOOK AUTO CREATOR BOT 🤖")
    print("=" * 70)
    print(f"📧 EMAIL: YANDEX (jerryxd@yandex.com)")
    print(f"📧 FORMAT: jerryxd+accountname@yandex.com")
    print(f"👑 OWNER ID: {OWNER_ID}")
    print("🔐 OTP: AUTO-FETCHED FROM YANDEX (2 MIN WAIT + RETRY)")
    print("📢 OTP WILL BE DISPLAYED WITH EACH ACCOUNT!")
    print("🍪 FULL COOKIES WILL BE DISPLAYED WITH EACH ACCOUNT!")
    print("=" * 70)
    logging.basicConfig(level=logging.INFO)
    load_from_github()
    load_users()

    await bot.delete_webhook(drop_pending_updates=True)
    
    await bot.set_my_commands([
        types.BotCommand(command="start",    description="🚀 START THE BOT"),
        types.BotCommand(command="credits",  description="💳 CHECK YOUR CREDITS"),
        types.BotCommand(command="myaccs",   description="📋 MY CREATED ACCOUNTS"),
    ])

    await bot.set_my_commands(
        [
            types.BotCommand(command="start",       description="🚀 START THE BOT"),
            types.BotCommand(command="myaccs",      description="📋 MY CREATED ACCOUNTS"),
            types.BotCommand(command="botaccs",     description="🌍 ALL BOT ACCOUNTS"),
            types.BotCommand(command="credits",     description="💳 CREDITS INFO"),
            types.BotCommand(command="stats",       description="📊 BOT STATISTICS"),
            types.BotCommand(command="menu",        description="⚙️ OWNER MENU"),
        ],
        scope=types.BotCommandScopeChat(chat_id=OWNER_ID)
    )

    print("✅ BOT IS RUNNING! PRESS CTRL+C TO STOP.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
