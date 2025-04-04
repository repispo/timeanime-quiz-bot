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
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variabili globali
scores = defaultdict(int)
answered_users = set()
current_answer = ""
correct_users = []
hint_job = None
end_job = None

# Funzione per ottenere personaggio da AniList
def get_character():
    attempts = 0
    while attempts < 10:
        page = random.randint(1, 100)
        year = random.choices(
            population=[2024, 2023, 2022, 2021, 2020, 2019, 2018],
            weights=[30, 25, 20, 10, 8, 5, 2],
            k=1
        )[0]

        query = f'''
        query {{
          Page(page: {page}, perPage: 1) {{
            characters(sort: FAVOURITES_DESC) {{
              name {{ full }}
              image {{ large }}
              media(perPage: 1) {{
                nodes {{
                  title {{ romaji }}
                  startDate {{ year }}
                }}
              }}
            }}
          }}
        }}
        '''
        try:
            response = requests.post("https://graphql.anilist.co", json={"query": query})
            data = response.json()
            char = data["data"]["Page"]["characters"][0]
            anime_data = char["media"]["nodes"][0]

            anime_year = anime_data["startDate"]["year"] or 2000
            if anime_year < 2015 and random.random() > 0.1:
                raise ValueError("Troppo vecchio")

            return {
                "name": char["name"]["full"],
                "image": char["image"]["large"],
                "anime": anime_data["title"]["romaji"]
            }
        except Exception as e:
            attempts += 1

    return None

# Avvia quiz
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, correct_users, hint_job, end_job

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può avviare il quiz.")
        return

    character = get_character()
    if not character:
        await update.message.reply_text("Errore nel recupero dei dati, riprova.")
        return

    current_answer = character["name"].lower()
    answered_users.clear()
    correct_users.clear()

    fake_names = ["Naruto", "Goku", "Asuka", "Levi", "Mikasa", "Rem"]
    options = random.sample(fake_names, 4)
    options.append(character["name"])
    random.shuffle(options)

    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=character["image"],
        caption="🎮 *AIO QUIZ!*
Chi è questo personaggio? Hai 5 minuti per rispondere!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Suggerimento dopo 2 minuti
    hint_job = context.job_queue.run_once(send_hint, 120, data={
        "chat_id": update.effective_chat.id,
        "anime": character["anime"]
    })

    # Fine quiz dopo 5 minuti
    end_job = context.job_queue.run_once(end_quiz, 300, data={
        "chat_id": update.effective_chat.id
    })

async def send_hint(context):
    await context.bot.send_message(
        chat_id=context.job.data["chat_id"],
        text=f"✨ Suggerimento: l'anime è *{context.job.data['anime']}*",
        parse_mode="Markdown"
    )

async def end_quiz(context):
    global current_answer
    await context.bot.send_message(
        chat_id=context.job.data["chat_id"],
        text=f"Tempo scaduto! La risposta corretta era: *{current_answer.title()}*",
        parse_mode="Markdown"
    )
    current_answer = ""

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

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Nessun punteggio ancora.")
        return

    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 *Classifica AIO QUIZ:*\n"
    for i, (user_id, pts) in enumerate(ranking, 1):
        user = await context.bot.get_chat(user_id)
        text += f"{i}. {user.first_name}: {pts} punti\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può resettare la classifica.")
        return

    scores.clear()
    await update.message.reply_text("✅ Classifica resettata.")

# Avvio
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))

    print("Bot avviato...")
    app.run_polling()
