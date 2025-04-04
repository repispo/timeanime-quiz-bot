import os
import logging
import random
import requests
import asyncio
from datetime import datetime
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIO_QUIZ")

# Variabili globali
scores = defaultdict(int)
answered_users = set()
current_answer = ""
correct_users = []
reveal_timer = None
end_timer = None
message_context = None
anime_title = ""

# --- Funzione per avviare il quiz ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, correct_users, reveal_timer, end_timer, message_context, anime_title

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può avviare AIO QUIZ.")
        return

    answered_users.clear()
    correct_users.clear()
    message_context = context

    use_old_anime = random.randint(1, 10) == 1
    year_filter = "1990" if use_old_anime else "2020"
    page = random.randint(1, 100)

    query = f'''
    query {{
      Page(page: {page}, perPage: 1) {{
        characters(sort: FAVOURITES_DESC) {{
          name {{ full }}
          image {{ large }}
          media(perPage: 1, sort: POPULARITY_DESC) {{
            nodes {{ title {{ romaji }} startDate {{ year }} }}
          }}
        }}
      }}
    }}
    '''

    try:
        response = requests.post("https://graphql.anilist.co", json={"query": query})
        data = response.json()
        char = data["data"]["Page"]["characters"][0]
        name = char["name"]["full"]
        image = char["image"]["large"]
        anime = char["media"]["nodes"][0]["title"]["romaji"]
        year = char["media"]["nodes"][0]["startDate"]["year"]
        if not use_old_anime and year < 2020:
            await update.message.reply_text("Sto cercando un personaggio più recente, riprova...")
            return await start_quiz(update, context)
    except:
        await update.message.reply_text("Errore nel recupero dei dati, riprova.")
        return

    current_answer = name.lower()
    anime_title = anime
    options = [name, "Naruto", "Rem", "Mikasa", "Gojo", "Levi", "Chizuru"]
    options = random.sample(set(options), 5)
    if name not in options:
        options[random.randint(0, 4)] = name
    random.shuffle(options)

    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]
    sent_message = await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image,
        caption="🎮 *AIO QUIZ!*
Chi è questo personaggio? Hai 5 minuti per rispondere!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    reveal_timer = context.job_queue.run_once(reveal_hint, 120, data=sent_message)
    end_timer = context.job_queue.run_once(end_quiz, 300, data=sent_message)


# --- Suggerimento dopo 2 minuti ---
async def reveal_hint(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"🚡 *Suggerimento:* Il personaggio viene da *{anime_title}*.",
        parse_mode="Markdown",
    )


# --- Fine quiz dopo 5 minuti ---
async def end_quiz(context: ContextTypes.DEFAULT_TYPE):
    if not correct_users:
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=f"Nessuno ha indovinato. La risposta era: *{current_answer.title()}*",
            parse_mode="Markdown",
        )


# --- Risposte utenti ---
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
        correct_users.append(user_id)
        await query.message.reply_text(f"✅ Corretto, {user_name}!")
    else:
        await query.message.reply_text(f"❌ Sbagliato, {user_name}!")


# --- Classifica ---
async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Nessun punteggio ancora.")
        return

    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 *Classifica AIO QUIZ:*
"
    for i, (uid, pts) in enumerate(ranking, 1):
        user = await context.bot.get_chat(uid)
        text += f"{i}. {user.first_name}: {pts} punti\n"
    await update.message.reply_text(text, parse_mode="Markdown")


# --- Reset classifica ---
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può resettare la classifica.")
        return
    scores.clear()
    await update.message.reply_text("✅ Classifica resettata.")


# --- Avvio Bot ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))

    print("Bot AIO QUIZ avviato...")
    app.run_polling()
