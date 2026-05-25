import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN = "8979966075:AAHOlUPn7g6q49Om-D2ogufEYQvzG07l5jM"
ADMIN_IDS = [7882729721]

(ANIME_NOMI, ANIME_JANR, ANIME_KOD, ANIME_RASM, ANIME_VIDEO_FILE, ANIME_TURI) = range(6)
(SERIYA_ANIME_ID, SERIYA_NOMI, SERIYA_VIDEO) = range(10, 13)
IZLASH_HOLAT = 20
QOLLANMA_EDIT, REKLAMA_EDIT = 30, 31
POST_MATN = 40
ALOHIDA_ID, ALOHIDA_MATN = 50, 51
MAJBURIY_KANAL = 60
STAFF_ID = 70
TOLOV_CHECK = 80
VIP_NARX_EDIT = 90
XUSH_EDIT = 100
BAN_ID = 110
UNBAN_ID = 120

logging.basicConfig(level=logging.INFO)

# ===== DATABASE =====
def db():
    conn = sqlite3.connect("anime.db")
    conn.row_factory = sqlite3.Row
    return conn

def db_setup():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS animelar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomi TEXT NOT NULL, janr TEXT, kod TEXT,
            rasm TEXT, video TEXT, turi TEXT DEFAULT 'anime',
            vip INTEGER DEFAULT 0, korishlar INTEGER DEFAULT 0,
            tavsif TEXT, reyting REAL DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS seriyalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER, nomi TEXT, video TEXT,
            FOREIGN KEY(anime_id) REFERENCES animelar(id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS foydalanuvchilar (
            user_id INTEGER PRIMARY KEY, ism TEXT, username TEXT,
            vip INTEGER DEFAULT 0, vip_so_rov INTEGER DEFAULT 0,
            staff INTEGER DEFAULT 0, ban INTEGER DEFAULT 0,
            ban_sabab TEXT, referral_id INTEGER DEFAULT 0,
            referrallar INTEGER DEFAULT 0, joined TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS sozlamalar (
            kalit TEXT PRIMARY KEY, qiymat TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS kanallar (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kanal_id TEXT, nomi TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS tolovlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, chek TEXT,
            holat TEXT DEFAULT 'kutilmoqda', sana TEXT
        )""")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('qollanma', 'Botdan foydalanish qollanmasi')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('reklama', 'Reklama uchun: @admin')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('vip_narx', '10000')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('vip_mud', '30')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('xush_kelibsiz', 'Anime Botga xush kelibsiz!')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('texnik', '0')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('bot_holat', '1')")
        conn.commit()

def is_admin(uid): return uid in ADMIN_IDS
def is_staff(uid):
    if is_admin(uid): return True
    with db() as conn:
        r = conn.execute("SELECT staff FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        return r and r["staff"] == 1
def is_vip(uid):
    with db() as conn:
        r = conn.execute("SELECT vip FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        return r and r["vip"] == 1
def is_banned(uid):
    with db() as conn:
        r = conn.execute("SELECT ban FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        return r and r["ban"] == 1
def is_texnik():
    with db() as conn:
        r = conn.execute("SELECT qiymat FROM sozlamalar WHERE kalit='texnik'").fetchone()
        return r and r["qiymat"] == "1"

def get_sozlama(k):
    with db() as conn:
        r = conn.execute("SELECT qiymat FROM sozlamalar WHERE kalit=?", (k,)).fetchone()
        return r["qiymat"] if r else ""

def register_user(uid, ism, username=None, ref=None):
    with db() as conn:
        ex = conn.execute("SELECT user_id FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        if not ex:
            conn.execute("INSERT INTO foydalanuvchilar (user_id, ism, username, referral_id, joined) VALUES (?,?,?,?,?)",
                (uid, ism, username or '', ref or 0, datetime.now().strftime("%Y-%m-%d")))
            if ref and ref != uid:
                conn.execute("UPDATE foydalanuvchilar SET referrallar=referrallar+1 WHERE user_id=?", (ref,))
            conn.commit()

async def majburiy_tekshir(uid, context):
    with db() as conn:
        kanallar = conn.execute("SELECT * FROM kanallar").fetchall()
    if not kanallar: return True
    for k in kanallar:
        try:
            m = await context.bot.get_chat_member(k["kanal_id"], uid)
            if m.status in ["left", "kicked"]: return False
        except: pass
    return True

# ===== MENYULAR =====
def user_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔍 Anime izlash")],
        [KeyboardButton("🔴 Shorts"), KeyboardButton("📚 Qollanma")],
        [KeyboardButton("💎 VIP"), KeyboardButton("👥 Referral")],
        [KeyboardButton("💰 Reklama")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔍 Anime izlash")],
        [KeyboardButton("🔴 Shorts"), KeyboardButton("📚 Qollanma")],
        [KeyboardButton("💎 VIP"), KeyboardButton("👥 Referral")],
        [KeyboardButton("💰 Reklama")],
        [KeyboardButton("⚙️ Admin Panel")]
    ], resize_keyboard=True)

def admin_panel_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🆕 Anime qoshish"), KeyboardButton("📁 Animelar royxati")],
        [KeyboardButton("➕ Seriya qoshish"), KeyboardButton("🗑 Anime ochirish")],
        [KeyboardButton("📮 Post yuborish"), KeyboardButton("👤 Alohida xabar")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("👥 Foydalanuvchilar")],
        [KeyboardButton("🚫 Ban qilish"), KeyboardButton("✅ Unban qilish")],
        [KeyboardButton("📋 Banlar royxati"), KeyboardButton("👨‍💼 Staff qoshish")],
        [KeyboardButton("🔒 Majburiy azo"), KeyboardButton("💳 Tolovlar")],
        [KeyboardButton("✏️ Qollanma"), KeyboardButton("💰 Reklama matni")],
        [KeyboardButton("💎 VIP narxi"), KeyboardButton("👋 Xush kelibsiz")],
        [KeyboardButton("🔧 Texnik rejim"), KeyboardButton("🏠 Bosh sahifa")]
    ], resize_keyboard=True)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref = None
    if context.args:
        try: ref = int(context.args[0])
        except: pass
    register_user(user.id, user.first_name, user.username, ref)

    if is_banned(user.id):
        with db() as conn:
            r = conn.execute("SELECT ban_sabab FROM foydalanuvchilar WHERE user_id=?", (user.id,)).fetchone()
        sabab = r["ban_sabab"] if r and r["ban_sabab"] else "Sabab ko'rsatilmagan"
        await update.message.reply_text(f"🚫 Siz ban qilindingiz!\n\nSabab: {sabab}")
        return

    if is_texnik() and not is_staff(user.id):
        await update.message.reply_text("🔧 Texnik ishlar olib borilmoqda. Iltimos kuting...")
        return

    if not await majburiy_tekshir(user.id, context):
        with db() as conn:
            kanallar = conn.execute("SELECT * FROM kanallar").fetchall()
        kb = [[InlineKeyboardButton(f"📢 {k['nomi']}", url=f"https://t.me/{k['kanal_id'].replace('@','')}")] for k in kanallar]
        kb.append([InlineKeyboardButton("✅ Tekshirish", callback_data="obuna_tekshir")])
        await update.message.reply_text("⚠️ Botdan foydalanish uchun kanallarga obuna boling:", reply_markup=InlineKeyboardMarkup(kb))
        return

    vip = is_vip(user.id)
    xush = get_sozlama("xush_kelibsiz")
    kb = [
        [InlineKeyboardButton("🔍 Nom boyicha", callback_data="izlash_nom"), InlineKeyboardButton("🔑 Kod boyicha", callback_data="izlash_kod")],
        [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
        [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime"), InlineKeyboardButton("🆕 Yangi", callback_data="yangi_anime")],
    ]
    menu = admin_menu() if is_staff(user.id) else user_menu()
    await update.message.reply_text(
        f"{xush}\n\n👤 {user.first_name}\n{'💎 VIP' if vip else '👤 Oddiy'}\n\nQuyidagilardan birini tanlang:",
        reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("📌 Menyu:", reply_markup=menu)

async def obuna_tekshir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if await majburiy_tekshir(user.id, context):
        kb = [
            [InlineKeyboardButton("🔍 Nom boyicha", callback_data="izlash_nom"), InlineKeyboardButton("🔑 Kod boyicha", callback_data="izlash_kod")],
            [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
            [InlineKeyboardButton("🔥 Top", callback_data="top_anime"), InlineKeyboardButton("🆕 Yangi", callback_data="yangi_anime")],
        ]
        await query.edit_message_text(f"✅ Xush kelibsiz, {user.first_name}!\n{'💎 VIP' if is_vip(user.id) else '👤 Oddiy'}", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query.answer("⚠️ Hali obuna bolmadingiz!", show_alert=True)

async def start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    kb = [
        [InlineKeyboardButton("🔍 Nom boyicha", callback_data="izlash_nom"), InlineKeyboardButton("🔑 Kod boyicha", callback_data="izlash_kod")],
        [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
        [InlineKeyboardButton("🔥 Top", callback_data="top_anime"), InlineKeyboardButton("🆕 Yangi", callback_data="yangi_anime")],
    ]
    await query.edit_message_text(
        f"🏠 Bosh sahifa\n\n👤 {user.first_name} | {'💎 VIP' if is_vip(user.id) else 'Oddiy'}",
        reply_markup=InlineKeyboardMarkup(kb))

# ===== IZLASH =====
async def izlash_nom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["izlash_turi"] = "nom"
    await query.edit_message_text("🔍 Anime nomini yozing:")
    return IZLASH_HOLAT

async def izlash_kod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["izlash_turi"] = "kod"
    await query.edit_message_text("🔑 Anime kodini yozing:")
    return IZLASH_HOLAT

async def izlash_natija(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matn = update.message.text
    turi = context.user_data.get("izlash_turi", "nom")
    uid = update.effective_user.id
    vip = is_vip(uid)
    with db() as conn:
        if turi == "kod":
            rows = conn.execute("SELECT * FROM animelar WHERE kod=? AND turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0"), (matn,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM animelar WHERE nomi LIKE ? AND turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0"), (f"%{matn}%",)).fetchall()
    if not rows:
        await update.message.reply_text("😕 Natija topilmadi!")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{'💎' if r['vip'] else '🎌'} {r['nomi']} | {r['janr'] or '-'}", callback_data=f"anime_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="start")])
    await update.message.reply_text(f"🔍 Natijalar: {len(rows)} ta", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ===== ANIMELAR =====
async def barcha_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text("😔 Hozircha anime yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="start")]]))
        return
    kb = [[InlineKeyboardButton(f"{'💎' if r['vip'] else '🎌'} {r['nomi']} | {r['janr'] or '-'}", callback_data=f"anime_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="start")])
    await query.edit_message_text("📋 Barcha animelar:", reply_markup=InlineKeyboardMarkup(kb))

async def top_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY korishlar DESC LIMIT 10").fetchall()
    if not rows:
        await query.edit_message_text("😔 Hozircha anime yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="start")]]))
        return
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    kb = [[InlineKeyboardButton(f"{medals[i]} {r['nomi']} | 👁 {r['korishlar']}", callback_data=f"anime_{r['id']}")] for i, r in enumerate(rows)]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="start")])
    await query.edit_message_text("🔥 Top 10 animelar:", reply_markup=InlineKeyboardMarkup(kb))

async def yangi_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC LIMIT 10").fetchall()
    if not rows:
        await query.edit_message_text("😔 Hozircha anime yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="start")]]))
        return
    kb = [[InlineKeyboardButton(f"🆕 {r['nomi']}", callback_data=f"anime_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="start")])
    await query.edit_message_text("🆕 Yangi qoshilgan:", reply_markup=InlineKeyboardMarkup(kb))

async def anime_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_id = int(query.data.split("_")[1])
    uid = query.from_user.id
    with db() as conn:
        anime = conn.execute("SELECT * FROM animelar WHERE id=?", (anime_id,)).fetchone()
        conn.execute("UPDATE animelar SET korishlar=korishlar+1 WHERE id=?", (anime_id,))
        seriyalar = conn.execute("SELECT * FROM seriyalar WHERE anime_id=? ORDER BY id", (anime_id,)).fetchall()
        conn.commit()
    if not anime:
        await query.edit_message_text("Anime topilmadi.")
        return
    if anime["vip"] and not is_vip(uid) and not is_admin(uid):
        kb = [[InlineKeyboardButton("💎 VIP olish", callback_data="vip_olish_cb")], [InlineKeyboardButton("🔙 Orqaga", callback_data="barcha_anime")]]
        await query.edit_message_text("💎 Bu anime faqat VIP uchun!\n\nVIP oling va barcha animelarga kiring!", reply_markup=InlineKeyboardMarkup(kb))
        return

    reyting = f"⭐ {anime['reyting']}/10" if anime["reyting"] else "⭐ -"
    matn = f"{'💎' if anime['vip'] else '🎌'} {anime['nomi']}\n\n"
    matn += f"📂 Janr: {anime['janr'] or '-'}\n"
    matn += f"🔑 Kod: {anime['kod'] or '-'}\n"
    matn += f"👁 Korishlar: {anime['korishlar']}\n"
    matn += f"{reyting}\n"
    if anime["tavsif"]:
        matn += f"\n📝 {anime['tavsif']}"

    kb = []
    if seriyalar:
        matn += f"\n\n🎬 Seriyalar: {len(seriyalar)} ta"
        for s in seriyalar:
            kb.append([InlineKeyboardButton(f"▶️ {s['nomi']}", callback_data=f"seriya_{s['id']}")])
    if is_staff(uid):
        kb.append([InlineKeyboardButton("🗑 Ochirish", callback_data=f"del_{anime_id}")])
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="barcha_anime")])

    if anime["video"] and not seriyalar:
        await query.message.reply_video(video=anime["video"], caption=matn, reply_markup=InlineKeyboardMarkup(kb))
        await query.delete_message()
    elif anime["rasm"]:
        await query.message.reply_photo(photo=anime["rasm"], caption=matn, reply_markup=InlineKeyboardMarkup(kb))
        await query.delete_message()
    else:
        await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup(kb))

async def seriya_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split("_")[1])
    with db() as conn:
        s = conn.execute("SELECT * FROM seriyalar WHERE id=?", (sid,)).fetchone()
    if not s:
        await query.edit_message_text("Seriya topilmadi.")
        return
    kb = [[InlineKeyboardButton("🔙 Orqaga", callback_data=f"anime_{s['anime_id']}")]]
    if s["video"]:
        await query.message.reply_video(video=s["video"], caption=f"▶️ {s['nomi']}", reply_markup=InlineKeyboardMarkup(kb))
        await query.delete_message()
    else:
        await query.edit_message_text(s["nomi"], reply_markup=InlineKeyboardMarkup(kb))

# ===== VIP =====
async def vip_olish_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if is_vip(uid):
        await query.edit_message_text("💎 Siz allaqachon VIP!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="start")]]))
        return
    narx = get_sozlama("vip_narx")
    mud = get_sozlama("vip_mud")
    kb = [
        [InlineKeyboardButton("💳 Tolov qilish", callback_data="vip_tolov")],
        [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="start")]
    ]
    await query.edit_message_text(
        f"💎 VIP obuna\n\nNarxi: {narx} som\nMuddati: {mud} kun\n\n✅ Barcha VIP animelarga kirish\n✅ Seriyalarga kirish\n✅ Tezkor yangilanishlar\n\nTolov usulini tanlang:",
        reply_markup=InlineKeyboardMarkup(kb))

async def vip_tolov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    narx = get_sozlama("vip_narx")
    kb = [[InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")], [InlineKeyboardButton("🔙 Orqaga", callback_data="start")]]
    await query.edit_message_text(
        f"💳 Tolov\n\nNarxi: {narx} som\n\nRekvizitlar:\n🏦 Payme: 8600XXXXXXXXXXXXXXXX\n💳 Click: 8600XXXXXXXXXXXXXXXX\n\nTolov qilib chek rasmini yuboring:",
        reply_markup=InlineKeyboardMarkup(kb))

async def chek_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📸 Tolov cheki rasmini yuboring:")
    return TOLOV_CHECK

async def chek_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    chek_id = None
    if update.message.photo:
        chek_id = update.message.photo[-1].file_id
    elif update.message.document:
        chek_id = update.message.document.file_id
    if not chek_id:
        await update.message.reply_text("Rasm yuboring!")
        return TOLOV_CHECK
    with db() as conn:
        conn.execute("INSERT INTO tolovlar (user_id, chek, sana) VALUES (?,?,?)", (uid, chek_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        tolov_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    for admin_id in ADMIN_IDS:
        try:
            kb = [[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"vip_tasdiq_{uid}"), InlineKeyboardButton("❌ Rad etish", callback_data=f"vip_rad_{uid}")]]
            await context.bot.send_photo(chat_id=admin_id, photo=chek_id,
                caption=f"💳 VIP Tolov #{tolov_id}\n\n👤 {user.first_name}\n🆔 {uid}\n@{user.username or 'yoq'}",
                reply_markup=InlineKeyboardMarkup(kb))
        except: pass
    await update.message.reply_text("✅ Chek qabul qilindi! Admin tekshirgandan keyin VIP beriladi.")
    return ConversationHandler.END

async def vip_tasdiq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    tid = int(query.data.split("_")[2])
    with db() as conn:
        conn.execute("UPDATE foydalanuvchilar SET vip=1, vip_so_rov=0 WHERE user_id=?", (tid,))
        conn.commit()
    try:
        await context.bot.send_message(tid, "💎 Tabriklaymiz! Siz endi VIP!\n\n/start bosing!")
    except: pass
    await query.edit_message_caption(caption=query.message.caption + "\n\n✅ TASDIQLANDI")

async def vip_rad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    tid = int(query.data.split("_")[2])
    try:
        await context.bot.send_message(tid, "❌ Tolovingiz rad etildi.")
    except: pass
    await query.edit_message_caption(caption=query.message.caption + "\n\n❌ RAD ETILDI")

# ===== TEXT HANDLER =====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    uid = update.effective_user.id

    if is_banned(uid):
        await update.message.reply_text("🚫 Siz ban qilindingiz!")
        return

    if is_texnik() and not is_staff(uid):
        await update.message.reply_text("🔧 Texnik ishlar olib borilmoqda.")
        return

    # USER tugmalari
    if t == "🔍 Anime izlash":
        kb = [
            [InlineKeyboardButton("🔍 Nom boyicha", callback_data="izlash_nom"), InlineKeyboardButton("🔑 Kod boyicha", callback_data="izlash_kod")],
            [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
            [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime"), InlineKeyboardButton("🆕 Yangi", callback_data="yangi_anime")],
        ]
        await update.message.reply_text("Quyidagilardan birini tanlang:", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "🔴 Shorts":
        vip = is_vip(uid)
        with db() as conn:
            rows = conn.execute("SELECT * FROM animelar WHERE turi='shorts'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC").fetchall()
        if not rows:
            await update.message.reply_text("😔 Hozircha shorts yoq.")
            return
        kb = [[InlineKeyboardButton(f"🎬 {r['nomi']}", callback_data=f"anime_{r['id']}")] for r in rows]
        await update.message.reply_text("🔴 Shorts bolim:", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "📚 Qollanma":
        await update.message.reply_text(f"📚 Qollanma:\n\n{get_sozlama('qollanma')}")

    elif t == "💎 VIP":
        if is_vip(uid):
            await update.message.reply_text("💎 Siz allaqachon VIP foydalanuvchisiz!")
            return
        narx = get_sozlama("vip_narx")
        mud = get_sozlama("vip_mud")
        kb = [[InlineKeyboardButton("💳 Tolov qilish", callback_data="vip_tolov")], [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")]]
        await update.message.reply_text(f"💎 VIP obuna\n\nNarxi: {narx} som\nMuddati: {mud} kun\n\n✅ Barcha VIP animelarga kirish\n✅ Seriyalarga kirish", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "👥 Referral":
        with db() as conn:
            r = conn.execute("SELECT referrallar FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        ref_soni = r["referrallar"] if r else 0
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={uid}"
        await update.message.reply_text(f"👥 Referral tizimi\n\nHavola:\n{link}\n\nJalb qilganlar: {ref_soni} ta\n\n5 ta referral = 1 kun VIP!")

    elif t == "💰 Reklama":
        await update.message.reply_text(f"💰 Reklama:\n\n{get_sozlama('reklama')}")

    elif t == "⚙️ Admin Panel" and is_staff(uid):
        with db() as conn:
            a = conn.execute("SELECT COUNT(*) as c FROM animelar").fetchone()["c"]
            u = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
            v = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip=1").fetchone()["c"]
            b = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE ban=1").fetchone()["c"]
            t_soni = conn.execute("SELECT COUNT(*) as c FROM tolovlar WHERE holat='kutilmoqda'").fetchone()["c"]
        texnik = "🔧 YOQIQ" if is_texnik() else "✅ NORMAL"
        await update.message.reply_text(
            f"⚙️ Admin Panel\n\nAnimelar: {a}\nFoydalanuvchilar: {u}\nVIP: {v}\nBan: {b}\nKutilayotgan tolovlar: {t_soni}\nHolat: {texnik}",
            reply_markup=admin_panel_menu())

    # ADMIN tugmalari
    elif t == "🆕 Anime qoshish" and is_staff(uid):
        context.user_data["ya"] = {"turi": "anime"}
        await update.message.reply_text("1. Anime nomini yozing:")
        return ANIME_NOMI

    elif t == "📁 Animelar royxati" and is_staff(uid):
        with db() as conn:
            rows = conn.execute("SELECT * FROM animelar ORDER BY id DESC").fetchall()
        if not rows:
            await update.message.reply_text("Anime yoq.")
            return
        kb = [[InlineKeyboardButton(f"{'💎' if r['vip'] else '🎌'} {r['nomi']}", callback_data=f"del_{r['id']}")] for r in rows]
        await update.message.reply_text("📁 Animelar (ochirish uchun bosing):", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "➕ Seriya qoshish" and is_staff(uid):
        with db() as conn:
            rows = conn.execute("SELECT id, nomi FROM animelar WHERE turi='anime' ORDER BY id DESC").fetchall()
        if not rows:
            await update.message.reply_text("Avval anime qoshing.")
            return
        kb = [[InlineKeyboardButton(f"🎌 {r['nomi']}", callback_data=f"sa_{r['id']}")] for r in rows]
        await update.message.reply_text("Qaysi animega seriya?", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "🗑 Anime ochirish" and is_staff(uid):
        with db() as conn:
            rows = conn.execute("SELECT id, nomi FROM animelar ORDER BY id DESC").fetchall()
        if not rows:
            await update.message.reply_text("Anime yoq.")
            return
        kb = [[InlineKeyboardButton(f"🗑 {r['nomi']}", callback_data=f"del_{r['id']}")] for r in rows]
        await update.message.reply_text("Qaysi animeni ochirish?", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "📮 Post yuborish" and is_staff(uid):
        await update.message.reply_text("Post matnini yozing (rasm ham yuborishingiz mumkin):")
        return POST_MATN

    elif t == "👤 Alohida xabar" and is_admin(uid):
        await update.message.reply_text("User ID yozing:")
        return ALOHIDA_ID

    elif t == "📊 Statistika" and is_staff(uid):
        with db() as conn:
            a = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='anime'").fetchone()["c"]
            sh = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='shorts'").fetchone()["c"]
            se = conn.execute("SELECT COUNT(*) as c FROM seriyalar").fetchone()["c"]
            u = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
            v = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip=1").fetchone()["c"]
            b = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE ban=1").fetchone()["c"]
            bugun = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE joined=date('now')").fetchone()["c"]
            top = conn.execute("SELECT nomi, korishlar FROM animelar ORDER BY korishlar DESC LIMIT 5").fetchall()
        top_t = "\n".join([f"{i+1}. {r['nomi']} - {r['korishlar']} ta" for i, r in enumerate(top)])
        await update.message.reply_text(
            f"📊 Statistika\n\nAnimelar: {a}\nShorts: {sh}\nSeriyalar: {se}\nFoydalanuvchilar: {u}\nBugun: +{bugun}\nVIP: {v}\nBan: {b}\n\nTop 5:\n{top_t}")

    elif t == "👥 Foydalanuvchilar" and is_staff(uid):
        with db() as conn:
            rows = conn.execute("SELECT * FROM foydalanuvchilar ORDER BY vip DESC LIMIT 30").fetchall()
        matn = "👥 Foydalanuvchilar:\n\n"
        for r in rows:
            holat = "🚫" if r["ban"] else "💎" if r["vip"] else "👤"
            matn += f"{holat} {r['ism']} | {r['user_id']}\n"
        await update.message.reply_text(matn)

    elif t == "🚫 Ban qilish" and is_admin(uid):
        await update.message.reply_text("Ban qilinadigan user ID yozing:")
        return BAN_ID

    elif t == "✅ Unban qilish" and is_admin(uid):
        await update.message.reply_text("Unban qilinadigan user ID yozing:")
        return UNBAN_ID

    elif t == "📋 Banlar royxati" and is_admin(uid):
        with db() as conn:
            rows = conn.execute("SELECT * FROM foydalanuvchilar WHERE ban=1").fetchall()
        if not rows:
            await update.message.reply_text("Banlangan foydalanuvchi yoq.")
            return
        matn = "🚫 Banlangan foydalanuvchilar:\n\n"
        for r in rows:
            matn += f"🚫 {r['ism']} | {r['user_id']}\nSabab: {r['ban_sabab'] or '-'}\n\n"
        await update.message.reply_text(matn)

    elif t == "👨‍💼 Staff qoshish" and is_admin(uid):
        with db() as conn:
            stafflar = conn.execute("SELECT * FROM foydalanuvchilar WHERE staff=1").fetchall()
        matn = "👨‍💼 Stafflar:\n"
        if stafflar:
            for s in stafflar:
                matn += f"- {s['ism']} ({s['user_id']})\n"
        else:
            matn += "Staff yoq\n"
        matn += "\nYangi staff ID yozing:"
        await update.message.reply_text(matn)
        return STAFF_ID

    elif t == "🔒 Majburiy azo" and is_admin(uid):
        with db() as conn:
            kanallar = conn.execute("SELECT * FROM kanallar").fetchall()
        matn = "🔒 Majburiy kanallar:\n\n"
        for k in kanallar:
            matn += f"- {k['nomi']} ({k['kanal_id']})\n"
        matn += "\n@kanal_username yozing:"
        await update.message.reply_text(matn)
        return MAJBURIY_KANAL

    elif t == "💳 Tolovlar" and is_admin(uid):
        with db() as conn:
            rows = conn.execute("SELECT * FROM tolovlar ORDER BY id DESC LIMIT 20").fetchall()
        if not rows:
            await update.message.reply_text("Tolovlar yoq.")
            return
        matn = "💳 Tolovlar:\n\n"
        for r in rows:
            matn += f"#{r['id']} | {r['user_id']} | {r['holat']} | {r['sana']}\n"
        await update.message.reply_text(matn)

    elif t == "✏️ Qollanma" and is_staff(uid):
        await update.message.reply_text(f"Hozirgi:\n{get_sozlama('qollanma')}\n\nYangi matnni yozing:")
        return QOLLANMA_EDIT

    elif t == "💰 Reklama matni" and is_staff(uid):
        await update.message.reply_text(f"Hozirgi:\n{get_sozlama('reklama')}\n\nYangi matnni yozing:")
        return REKLAMA_EDIT

    elif t == "💎 VIP narxi" and is_admin(uid):
        await update.message.reply_text(f"Hozirgi: {get_sozlama('vip_narx')} som\n\nYangi narxni yozing:")
        return VIP_NARX_EDIT

    elif t == "👋 Xush kelibsiz" and is_admin(uid):
        await update.message.reply_text(f"Hozirgi:\n{get_sozlama('xush_kelibsiz')}\n\nYangi matnni yozing:")
        return XUSH_EDIT

    elif t == "🔧 Texnik rejim" and is_admin(uid):
        texnik = get_sozlama("texnik")
        yangi = "0" if texnik == "1" else "1"
        with db() as conn:
            conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='texnik'", (yangi,))
            conn.commit()
        holat = "YOQILDI 🔧" if yangi == "1" else "OCHIRILDI ✅"
        await update.message.reply_text(f"Texnik rejim {holat}")

    elif t == "🏠 Bosh sahifa":
        await start(update, context)

# ===== ANIME QO'SHISH =====
async def a_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["nomi"] = update.message.text
    await update.message.reply_text("2. Janrini yozing:")
    return ANIME_JANR

async def a_janr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["janr"] = update.message.text
    await update.message.reply_text("3. Kod:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_kod")]]))
    return ANIME_KOD

async def a_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["kod"] = update.message.text
    await update.message.reply_text("4. Rasm:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_rasm")]]))
    return ANIME_RASM

async def skip_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("4. Rasm:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_rasm")]]))
    return ANIME_RASM

async def a_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["ya"]["rasm"] = update.message.photo[-1].file_id
    await update.message.reply_text("5. Video:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_video")]]))
    return ANIME_VIDEO_FILE

async def skip_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("5. Video:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_video")]]))
    return ANIME_VIDEO_FILE

async def a_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        context.user_data["ya"]["video"] = update.message.video.file_id
    await update.message.reply_text("6. VIP yoki Bepul?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 VIP", callback_data="av_vip"), InlineKeyboardButton("🆓 Bepul", callback_data="av_bepul")]]))
    return ANIME_TURI

async def skip_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("6. VIP yoki Bepul?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 VIP", callback_data="av_vip"), InlineKeyboardButton("🆓 Bepul", callback_data="av_bepul")]]))
    return ANIME_TURI

async def a_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vip = 1 if query.data == "av_vip" else 0
    ya = context.user_data.get("ya", {})
    with db() as conn:
        conn.execute("INSERT INTO animelar (nomi, janr, kod, rasm, video, vip, turi) VALUES (?,?,?,?,?,?,?)",
            (ya.get("nomi"), ya.get("janr"), ya.get("kod"), ya.get("rasm"), ya.get("video"), vip, ya.get("turi","anime")))
        conn.commit()
    await query.edit_message_text(f"✅ {ya.get('nomi')} qoshildi! {'💎 VIP' if vip else '🆓 Bepul'}")
    return ConversationHandler.END

# ===== SERIYA =====
async def seriya_anime_sel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    aid = int(query.data.split("_")[1])
    context.user_data["seriya"] = {"anime_id": aid}
    await query.edit_message_text("Seriya nomini yozing (1-qism):")
    return SERIYA_NOMI

async def seriya_nomi_f(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["seriya"]["nomi"] = update.message.text
    await update.message.reply_text("Seriya videosini yuboring:")
    return SERIYA_VIDEO

async def seriya_video_f(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = context.user_data.get("seriya", {})
    vid = update.message.video.file_id if update.message.video else None
    with db() as conn:
        conn.execute("INSERT INTO seriyalar (anime_id, nomi, video) VALUES (?,?,?)", (s.get("anime_id"), s.get("nomi"), vid))
        conn.commit()
    await update.message.reply_text(f"✅ {s.get('nomi')} qoshildi!")
    return ConversationHandler.END

async def anime_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    aid = int(query.data.split("_")[1])
    with db() as conn:
        anime = conn.execute("SELECT nomi FROM animelar WHERE id=?", (aid,)).fetchone()
        conn.execute("DELETE FROM seriyalar WHERE anime_id=?", (aid,))
        conn.execute("DELETE FROM animelar WHERE id=?", (aid,))
        conn.commit()
    await query.edit_message_text(f"🗑 {anime['nomi']} ochirildi!")

# ===== BAN/UNBAN =====
async def ban_id_olish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        bid = int(update.message.text)
        context.user_data["ban_id"] = bid
        await update.message.reply_text("Ban sababini yozing:")
        return BAN_ID + 1
    except:
        await update.message.reply_text("Notogri ID!")
        return ConversationHandler.END

async def ban_sabab_olish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bid = context.user_data.get("ban_id")
    sabab = update.message.text
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO foydalanuvchilar (user_id, ism) VALUES (?,'Noma\\'lum')", (bid,))
        conn.execute("UPDATE foydalanuvchilar SET ban=1, ban_sabab=? WHERE user_id=?", (sabab, bid))
        conn.commit()
    try:
        await context.bot.send_message(bid, f"🚫 Siz ban qilindingiz!\nSabab: {sabab}")
    except: pass
    await update.message.reply_text(f"✅ {bid} ban qilindi!\nSabab: {sabab}")
    return ConversationHandler.END

async def unban_id_olish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        with db() as conn:
            conn.execute("UPDATE foydalanuvchilar SET ban=0, ban_sabab=NULL WHERE user_id=?", (uid,))
            conn.commit()
        try:
            await context.bot.send_message(uid, "✅ Sizning baningiz olib tashlandi!")
        except: pass
        await update.message.reply_text(f"✅ {uid} unban qilindi!")
    except:
        await update.message.reply_text("Notogri ID!")
    return ConversationHandler.END

# ===== POST =====
async def post_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        users = conn.execute("SELECT user_id FROM foydalanuvchilar WHERE ban=0").fetchall()
    yuborildi = 0
    for u in users:
        try:
            await update.message.copy_to(chat_id=u["user_id"])
            yuborildi += 1
        except: pass
    await update.message.reply_text(f"✅ Post yuborildi! {yuborildi}/{len(users)} ta")
    return ConversationHandler.END

# ===== ALOHIDA =====
async def alohida_id_f(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["alohida_id"] = int(update.message.text)
        await update.message.reply_text("Xabar yozing:")
        return ALOHIDA_MATN
    except:
        await update.message.reply_text("Notogri ID!")
        return ConversationHandler.END

async def alohida_matn_f(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = context.user_data.get("alohida_id")
    try:
        await update.message.copy_to(chat_id=tid)
        await update.message.reply_text("✅ Xabar yuborildi!")
    except:
        await update.message.reply_text("Yuborib bolmadi.")
    return ConversationHandler.END

# ===== SOZLAMALAR =====
async def majburiy_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kanal = update.message.text.strip()
    if not kanal.startswith("@"):
        await update.message.reply_text("@ bilan boshlang!")
        return MAJBURIY_KANAL
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO kanallar (kanal_id, nomi) VALUES (?,?)", (kanal, kanal))
        conn.commit()
    await update.message.reply_text(f"✅ {kanal} qoshildi!")
    return ConversationHandler.END

async def staff_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sid = int(update.message.text)
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO foydalanuvchilar (user_id, ism) VALUES (?,'Staff')", (sid,))
            conn.execute("UPDATE foydalanuvchilar SET staff=1 WHERE user_id=?", (sid,))
            conn.commit()
        await update.message.reply_text(f"✅ {sid} staff qilindi!")
    except:
        await update.message.reply_text("Notogri ID!")
    return ConversationHandler.END

async def qollanma_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='qollanma'", (update.message.text,))
        conn.commit()
    await update.message.reply_text("✅ Qollanma yangilandi!")
    return ConversationHandler.END

async def reklama_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='reklama'", (update.message.text,))
        conn.commit()
    await update.message.reply_text("✅ Reklama yangilandi!")
    return ConversationHandler.END

async def vip_narx_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        narx = int(update.message.text)
        with db() as conn:
            conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='vip_narx'", (str(narx),))
            conn.commit()
        await update.message.reply_text(f"✅ VIP narxi {narx} som!")
    except:
        await update.message.reply_text("Faqat son kiriting!")
    return ConversationHandler.END

async def xush_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='xush_kelibsiz'", (update.message.text,))
        conn.commit()
    await update.message.reply_text("✅ Yangilandi!")
    return ConversationHandler.END

def main():
    db_setup()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    izlash_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(izlash_nom_start, "^izlash_nom$"), CallbackQueryHandler(izlash_kod_start, "^izlash_kod$")],
        states={IZLASH_HOLAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, izlash_natija)]},
        fallbacks=[CommandHandler("start", start)])

    anime_conv = ConversationHandler(
        entry_points=[],
        states={
            ANIME_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_nomi)],
            ANIME_JANR: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_janr)],
            ANIME_KOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_kod), CallbackQueryHandler(skip_kod, "^skip_kod$")],
            ANIME_RASM: [MessageHandler(filters.PHOTO, a_rasm), CallbackQueryHandler(skip_rasm, "^skip_rasm$")],
            ANIME_VIDEO_FILE: [MessageHandler(filters.VIDEO, a_video), CallbackQueryHandler(skip_video, "^skip_video$")],
            ANIME_TURI: [CallbackQueryHandler(a_saqlash, "^av_(vip|bepul)$")],
        },
        fallbacks=[CommandHandler("start", start)])

    seriya_conv = ConversationHandler(
        entry_points=[],
        states={
            SERIYA_ANIME_ID: [CallbackQueryHandler(seriya_anime_sel, "^sa_\\d+$")],
            SERIYA_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, seriya_nomi_f)],
            SERIYA_VIDEO: [MessageHandler(filters.VIDEO, seriya_video_f)],
        },
        fallbacks=[CommandHandler("start", start)])

    tolov_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chek_yuborish, "^chek_yuborish$")],
        states={TOLOV_CHECK: [MessageHandler(filters.PHOTO | filters.Document.ALL, chek_qabul)]},
        fallbacks=[CommandHandler("start", start)])

    post_conv = ConversationHandler(
        entry_points=[],
        states={POST_MATN: [MessageHandler(filters.ALL & ~filters.COMMAND, post_yuborish)]},
        fallbacks=[CommandHandler("start", start)])

    alohida_conv = ConversationHandler(
        entry_points=[],
        states={
            ALOHIDA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, alohida_id_f)],
            ALOHIDA_MATN: [MessageHandler(filters.ALL & ~filters.COMMAND, alohida_matn_f)],
        },
        fallbacks=[CommandHandler("start", start)])

    ban_conv = ConversationHandler(
        entry_points=[],
        states={
            BAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ban_id_olish)],
            BAN_ID + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, ban_sabab_olish)],
        },
        fallbacks=[CommandHandler("start", start)])

    unban_conv = ConversationHandler(
        entry_points=[],
        states={UNBAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, unban_id_olish)]},
        fallbacks=[CommandHandler("start", start)])

    majburiy_conv = ConversationHandler(
        entry_points=[],
        states={MAJBURIY_KANAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, majburiy_qosh)]},
        fallbacks=[CommandHandler("start", start)])

    staff_conv = ConversationHandler(
        entry_points=[],
        states={STAFF_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, staff_qosh)]},
        fallbacks=[CommandHandler("start", start)])

    qollanma_conv = ConversationHandler(
        entry_points=[],
        states={QOLLANMA_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, qollanma_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    reklama_conv = ConversationHandler(
        entry_points=[],
        states={REKLAMA_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reklama_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    vip_narx_conv = ConversationHandler(
        entry_points=[],
        states={VIP_NARX_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, vip_narx_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    xush_conv = ConversationHandler(
        entry_points=[],
        states={XUSH_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, xush_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    for conv in [izlash_conv, anime_conv, seriya_conv, tolov_conv, post_conv, alohida_conv, ban_conv, unban_conv, majburiy_conv, staff_conv, qollanma_conv, reklama_conv, vip_narx_conv, xush_conv]:
        app.add_handler(conv)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start_cb, "^start$"))
    app.add_handler(CallbackQueryHandler(obuna_tekshir, "^obuna_tekshir$"))
    app.add_handler(CallbackQueryHandler(barcha_anime, "^barcha_anime$"))
    app.add_handler(CallbackQueryHandler(top_anime, "^top_anime$"))
    app.add_handler(CallbackQueryHandler(yangi_anime, "^yangi_anime$"))
    app.add_handler(CallbackQueryHandler(anime_detail, "^anime_\\d+$"))
    app.add_handler(CallbackQueryHandler(seriya_detail, "^seriya_\\d+$"))
    app.add_handler(CallbackQueryHandler(seriya_anime_sel, "^sa_\\d+$"))
    app.add_handler(CallbackQueryHandler(vip_olish_cb, "^vip_olish_cb$"))
    app.add_handler(CallbackQueryHandler(vip_tolov, "^vip_tolov$"))
    app.add_handler(CallbackQueryHandler(vip_tasdiq, "^vip_tasdiq_\\d+$"))
    app.add_handler(CallbackQueryHandler(vip_rad, "^vip_rad_\\d+$"))
    app.add_handler(CallbackQueryHandler(anime_delete, "^del_\\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
