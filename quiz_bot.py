import os
import logging
import random
import requests
import asyncio
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Configurazione
BOT_TOKEN = os.environ.get("BOT_TOKEN")
admin_ids_str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_ids_str.split(",") if x.strip().isdigit()]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variabili globali
scores = defaultdict(int)
answered_users = set()
current_answer = ""
hint_given = False
quiz_active = False
anime_hint = ""

# Avvio quiz
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, hint_given, quiz_active, anime_hint

    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo gli admin possono avviare il quiz.")
        return

    if quiz_active:
        await update.message.reply_text("Un quiz è già in corso!")
        return

    answered_users.clear()
    hint_given = False
    quiz_active = True

    # Tentativi per trovare un personaggio recente
    for _ in range(10):
        page = random.randint(1, 200)
        query = '''
        query {
          Page(page: %d, perPage: 1) {
            characters {
              name {
                full
              }
              image {
                large
              }
              media(perPage: 1, sort: START_DATE_DESC) {
                nodes {
                  title {
                    romaji
                  }
                  startDate {
                    year
                  }
                }
              }
            }
          }
        }
        ''' % page

        try:
            response = requests.post("https://graphql.anilist.co", json={"query": query})
            char = response.json()["data"]["Page"]["characters"][0]
            name = char["name"]["full"]
            image = char["image"]["large"]
            anime = char["media"]["nodes"][0]["title"]["romaji"]
            year = char["media"]["nodes"][0]["startDate"]["year"]
            if year and year >= 2020 or random.random() < 0.1:
                current_answer = name.lower()
                anime_hint = anime
                break
        except Exception:
            continue
    else:
        await update.message.reply_text("Sto cercando un personaggio più recente, riprova...")
        quiz_active = False
        return

    # Opzioni di risposta
    options = [current_answer.title()] + [fake_name() for _ in range(4)]
    random.shuffle(options)
    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image,
        caption="🎮 *AIO QUIZ!*\nChi è questo personaggio? Hai 5 minuti per rispondere!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    await context.bot.send_message(update.effective_chat.id, "⌛ Aspetta 2 minuti per l'indizio...")
    asyncio.create_task(provide_hint(context, update.effective_chat.id))
    asyncio.create_task(end_quiz(context, update.effective_chat.id))

# Generatore nomi fittizi
fake_names_pool = [
    "Naruto Uzumaki", "Goku Son", "Asuka Langley", "Levi Ackerman",
    "Mikasa Ackerman", "Rem Re:Zero", "Shinji Ikari", "Light Yagami",
    "Rukia Kuchiki", "Edward Elric", "Sasuke Uchiha", "Eren Yeager"
]
def fake_name():
    return random.choice(fake_names_pool)

# Indizio dopo 2 minuti
async def provide_hint(context, chat_id):
    await asyncio.sleep(120)
    global hint_given
    if quiz_active:
        await context.bot.send_message(chat_id=chat_id, text=f"🔎 Indizio: il personaggio proviene da *{anime_hint}*", parse_mode="Markdown")
        hint_given = True

# Fine quiz dopo 5 minuti
async def end_quiz(context, chat_id):
    await asyncio.sleep(300)
    global quiz_active
    if quiz_active:
        await context.bot.send_message(chat_id=chat_id, text=f"⏰ Tempo scaduto! La risposta corretta era: *{current_answer.title()}*", parse_mode="Markdown")
        quiz_active = False
        await show_score(context, chat_id)

# Gestione risposte
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global quiz_active
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_name = query.from_user.first_name

    if user_id in answered_users:
        await query.message.reply_text("Hai già risposto!")
        return

    answered_users.add(user_id)
    chosen = query.data.lower()

    if chosen == current_answer:
        scores[user_id] += 1
        await query.message.reply_text(f"✅ Giusto, {user_name}!")
    else:
        await query.message.reply_text(f"❌ Sbagliato, {user_name}!")

# Mostra classifica
async def show_score(context, chat_id):
    if not scores:
        await context.bot.send_message(chat_id, "Nessun punteggio ancora.")
        return

    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 *Classifica AIO QUIZ:*\n"
    for i, (user_id, pts) in enumerate(ranking, 1):
        try:
            user = await context.bot.get_chat(user_id)
            text += f"{i}. {user.first_name}: {pts} punti\n"
        except Exception:
            continue
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")

# Comando /score
async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_score(context, update.effective_chat.id)

# Comando /reset
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo un admin può resettare la classifica.")
        return
    scores.clear()
    await update.message.reply_text("✅ Classifica resettata.")

# Avvio bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))
    print("Bot avviato...")
    app.run_polling()
