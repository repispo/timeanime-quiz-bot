import os
import logging
import random
import requests
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Legge token e ID admin dalle variabili ambiente
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))  # fallback se ADMIN_ID non è settato

# Abilita il logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variabili globali
scores = defaultdict(int)
answered_users = set()
current_answer = ""
correct_users = []

# Funzione principale per il quiz
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, correct_users

    # Solo admin può avviare il quiz
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può avviare il quiz.")
        return

    answered_users.clear()
    correct_users.clear()

    # Richiesta ad AniList API per personaggio casuale
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
          media(perPage: 1) {
            nodes {
              title {
                romaji
              }
            }
          }
        }
      }
    }
    ''' % random.randint(1, 150)

    try:
        response = requests.post("https://graphql.anilist.co", json={"query": query})
        data = response.json()
        char = data["data"]["Page"]["characters"][0]
        name = char["name"]["full"]
        image = char["image"]["large"]
        anime = char["media"]["nodes"][0]["title"]["romaji"]
    except Exception as e:
        await update.message.reply_text("Errore nel recupero dei dati.")
        return

    current_answer = name.lower()

    # Opzioni
    fake_names = ["Naruto", "Goku", "Asuka", "Levi", "Mikasa", "Rem"]
    options = random.sample(fake_names, 4)
    options.append(name)
    random.shuffle(options)

    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image,
        caption=f"Chi è questo personaggio?\nAnime: *{anime}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# Risposte degli utenti
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer

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

# Classifica
async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Nessun punteggio ancora.")
        return

    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 Classifica:\n"
    for i, (user_id, pts) in enumerate(ranking, 1):
        user = await context.bot.get_chat(user_id)
        text += f"{i}. {user.first_name}: {pts} punti\n"
    await update.message.reply_text(text)

# Reset classifica
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può resettare la classifica.")
        return

    scores.clear()
    await update.message.reply_text("✅ Classifica resettata.")

# Main
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))

    print("Bot avviato...")
    app.run_polling()
