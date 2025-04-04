import logging
import os
import random
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID"))]

logging.basicConfig(level=logging.INFO)

API_URL = "https://graphql.anilist.co"

async def get_random_character():
    page = random.randint(1, 100)
    per_page = 25
    query = """
    query ($page: Int, $perPage: Int) {
      Page(page: $page, perPage: $perPage) {
        characters {
          id
          name {
            full
          }
          image {
            large
          }
        }
      }
    }
    """
    variables = {
        "page": page,
        "perPage": per_page
    }

    response = requests.post(API_URL, json={'query': query, 'variables': variables})
    characters = response.json().get("data", {}).get("Page", {}).get("characters", [])

    valid = [c for c in characters if c["name"]["full"] and c["image"]["large"]]
    if len(valid) < 5:
        return await get_random_character()

    correct = random.choice(valid)
    wrong = random.sample([c for c in valid if c["id"] != correct["id"]], 4)

    options = [correct["name"]["full"]] + [c["name"]["full"] for c in wrong]
    random.shuffle(options)

    return {
        "image": correct["image"]["large"],
        "correct": correct["name"]["full"],
        "options": options
    }

current_question = None
participants = {}
scores = {}

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo gli admin possono avviare il quiz.")
        return

    global current_question, participants
    participants = {}

    char_data = await get_random_character()
    current_question = char_data

    keyboard = [
        [InlineKeyboardButton(opt, callback_data=opt)]
        for opt in char_data["options"]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=char_data["image"],
        caption=f"🧠 *INDOVINA IL PERSONAGGIO!*\nChi è questo personaggio?\nHai *5 minuti* per rispondere!",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

    await asyncio.sleep(300)
    await end_quiz(context, update.effective_chat.id)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global participants, current_question, scores

    query = update.callback_query
    user = query.from_user
    await query.answer()

    if not current_question:
        return

    if user.id in participants:
        await query.message.reply_text(f"{user.first_name}, hai già risposto!")
        return

    participants[user.id] = query.data

    if query.data == current_question["correct"]:
        scores[user.id] = scores.get(user.id, 0) + 1
        await query.message.reply_text(f"✅ {user.first_name} ha indovinato!")
    else:
        await query.message.reply_text(f"❌ {user.first_name} ha sbagliato!")

async def end_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id):
    global current_question
    if not current_question:
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏱ Tempo scaduto!\nLa risposta corretta era: *{current_question['correct']}*",
        parse_mode="Markdown"
    )
    current_question = None

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Nessuno ha ancora punti!")
        return

    leaderboard = "🏆 *Classifica attuale:*\n\n"
    for user_id, pts in scores.items():
        user = await context.bot.get_chat(user_id)
        leaderboard += f"{user.first_name}: {pts} punti\n"

    await update.message.reply_text(leaderboard, parse_mode="Markdown")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo l'admin può resettare i punteggi.")
        return

    scores.clear()
    await update.message.reply_text("✅ Classifica resettata!")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CallbackQueryHandler(handle_answer))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))

    print("Bot avviato...")
    app.run_polling()
