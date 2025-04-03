import logging
import random
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# CONFIG DA VARIABILI ENVIRONMENT (Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(os.getenv("ADMIN_ID"))]

# DOMANDE E IMMAGINI (puoi aggiungerne quante vuoi)
quiz_questions = [
    {
        "question": "Chi è questo personaggio?",
        "image": "https://i.imgur.com/VqgYwFq.jpeg",
        "options": ["Naruto", "Goku", "Eren", "Ichigo", "Deku"],
        "correct": "Ichigo"
    },
    {
        "question": "Da quale anime proviene questa scena?",
        "image": "https://i.imgur.com/1XKfH6q.jpeg",
        "options": ["Attack on Titan", "Demon Slayer", "Bleach", "One Piece", "Death Note"],
        "correct": "Attack on Titan"
    }
]

# VARIABILI GLOBALI
current_question = None
current_participants = {}
scores = {}

# LOGGING
logging.basicConfig(level=logging.INFO)

# COMANDO /startquiz
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo gli admin possono avviare il quiz.")
        return

    global current_question, current_participants
    current_participants = {}

    question_data = random.choice(quiz_questions)
    current_question = question_data

    keyboard = [
        [InlineKeyboardButton(opt, callback_data=opt)]
        for opt in question_data["options"]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=question_data["image"],
        caption=f"🧠 *QUIZ TIME!*\n\n{question_data['question']}\nHai *5 minuti* per rispondere!",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

    await asyncio.sleep(300)
    await end_quiz(context, update.effective_chat.id)

# GESTIONE RISPOSTE
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_participants, current_question, scores

    query = update.callback_query
    user = query.from_user
    await query.answer()

    if not current_question:
        await query.message.reply_text("Nessun quiz attivo.")
        return

    user_responses = current_participants.get(user.id, [])

    if len(user_responses) >= 3:
        await query.message.reply_text(f"{user.first_name}, hai già risposto 3 volte!")
        return

    user_responses.append(query.data)
    current_participants[user.id] = user_responses

    if query.data == current_question["correct"]:
        if user.id not in scores:
            scores[user.id] = 0
        scores[user.id] += 1
        await query.message.reply_text(f"✅ {user.first_name} ha risposto correttamente!")
    else:
        await query.message.reply_text(f"❌ {user.first_name} ha sbagliato!")

# FINE QUIZ DOPO 5 MINUTI
async def end_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id):
    global current_question
    if not current_question:
        return

    correct = current_question["correct"]
    await context.bot.send_message(chat_id=chat_id, text=f"⏱ Tempo scaduto!\n✅ La risposta corretta era: *{correct}*", parse_mode="Markdown")
    current_question = None

# CLASSIFICA
async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Nessuno ha ancora punti!")
        return

    leaderboard = "🏆 *Classifica:*\n\n"
    for user_id, pts in scores.items():
        user = await context.bot.get_chat(user_id)
        leaderboard += f"{user.first_name}: {pts} punti\n"

    await update.message.reply_text(leaderboard, parse_mode="Markdown")

# RESET
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo gli admin possono resettare i punteggi.")
        return

    scores.clear()
    await update.message.reply_text("✅ Classifica resettata!")

# AVVIO BOT
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CallbackQueryHandler(handle_answer))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))

    print("Bot avviato...")
    app.run_polling()
