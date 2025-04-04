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

# Legge token e ID admin da variabili ambiente (compatibile con Railway)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 608950288))  # Fall-back all'ID di Repispo

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Punteggi utenti
scores = defaultdict(int)
answered_users = set()
current_answer = ""
correct_users = []

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, correct_users

    # Resetta dati
    answered_users.clear()
    correct_users.clear()

    # Ottieni dati random da Anilist (GraphQL API)
    query = '''
    query {
      Page(perPage: 1) {
        characters(sort: FAVOURITES_DESC) {
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
    '''
    response = requests.post(
        "https://graphql.anilist.co",
        json={"query": query}
    )
    data = response.json()
    character = data["data"]["Page"]["characters"][0]
    name = character["name"]["full"]
    image_url = character["image"]["large"]
    anime_title = character["media"]["nodes"][0]["title"]["romaji"]

    current_answer = name.lower()

    # Opzioni sbagliate (placeholder)
    fake_names = ["Naruto", "Mikasa", "Light Yagami", "Shinji", "Rem"]
    options = random.sample(fake_names, 4)
    options.append(name)
    random.shuffle(options)

    keyboard = [
        [InlineKeyboardButton(opt, callback_data=opt)] for opt in options
    ]

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image_url,
        caption=f"🎌 QUIZ TIME!\nChi è questo personaggio?\nAnime: *{anime_title}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_name = query.from_user.first_name

    if user_id in answered_users:
        await query.reply_text("Hai già risposto!")
        return

    answered_users.add(user_id)
    chosen = query.data.lower()

    if chosen == current_answer:
        scores[user_id] += 1
        correct_users.append(user_name)
        await query.edit_message_caption(
            caption=f"✅ Corretto! Era *{current_answer.title()}*!\n\n+1 punto per {user_name}",
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_caption(
            caption=f"❌ Sbagliato! Era *{current_answer.title()}*.",
            parse_mode="Markdown",
        )

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Nessun punteggio disponibile.")
        return

    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 Classifica:\n\n"
    for i, (user_id, score_value) in enumerate(ranking, 1):
        user = await context.bot.get_chat(user_id)
        text += f"{i}. {user.first_name}: {score_value} punti\n"
    await update.message.reply_text(text)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può usare questo comando.")
        return
    scores.clear()
    await update.message.reply_text("✅ Classifica azzerata.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot in esecuzione...")
    app.run_polling()

