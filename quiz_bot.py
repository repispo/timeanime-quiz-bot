import logging
import random
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from collections import defaultdict

BOT_TOKEN = "INSERISCI_IL_TUO_TOKEN"
ADMIN_ID = 608950288  # ID di Repispo

# Punteggi utenti
scores = defaultdict(int)
# Utenti che hanno già risposto a questa domanda
answered_users = set()
# Risposta corretta corrente
current_answer = ""
# Utenti che hanno indovinato
correct_users = []

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, correct_users
    if update.effective_user.id != ADMIN_ID:
        return

    answered_users = set()
    correct_users = []

    characters = [
        {"name": "Kaguya Shinomiya", "image": "https://s4.anilist.co/file/anilistcdn/character/large/b126419-3a9kIXuCAiwA.png"},
        {"name": "Tomo Aizawa", "image": "https://s4.anilist.co/file/anilistcdn/character/large/b126420-cGBzLhf8bHoF.png"},
        {"name": "Asuna Yuuki", "image": "https://s4.anilist.co/file/anilistcdn/character/large/b36821-zzSHv0BoNvOT.png"},
        {"name": "Shinobu Oshino", "image": "https://s4.anilist.co/file/anilistcdn/character/large/b24034-fFEnNi05tM5Z.png"},
        {"name": "Mai Sakurajima", "image": "https://s4.anilist.co/file/anilistcdn/character/large/b120763-Bp9CybJ8lhqz.png"}
    ]
    options = random.sample(characters, 5)
    correct = random.choice(options)
    current_answer = correct["name"]

    buttons = [
        [InlineKeyboardButton(c["name"], callback_data=c["name"])]
        for c in options
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=correct["image"],
        caption="**QUIZ TIME!**\n\nChi è questo personaggio?\nHai 30 secondi per rispondere!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    context.job_queue.run_once(end_quiz, 30, chat_id=update.effective_chat.id)

async def answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer
    query = update.callback_query
    user = query.from_user

    if user.id in answered_users:
        await query.answer("Hai già risposto!")
        return

    answered_users.add(user.id)
    answer = query.data

    if answer == current_answer:
        scores[user.id] += 1
        correct_users.append(user)
        await query.answer("Giusto!")
    else:
        await query.answer("Sbagliato!")

async def end_quiz(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    if correct_users:
        winners = "\n".join([f"– <a href='tg://user?id={u.id}'>{u.first_name}</a>" for u in correct_users])
    else:
        winners = "Nessuno ha indovinato questa volta!"

    if scores:
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        text_ranking = "\n".join(
            [f"{i+1}. <a href='tg://user?id={uid}'>{uid}</a> – {pts} punti" for i, (uid, pts) in enumerate(ranking)]
        )
    else:
        text_ranking = "Nessun punto assegnato ancora."

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ Risposta corretta: <b>{current_answer}</b>\n\n"
             f"{winners}\n\n"
             f"<b>🏆 Classifica attuale:</b>\n{text_ranking}",
        parse_mode="HTML"
    )

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if scores:
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        text_ranking = "\n".join(
            [f"{i+1}. <a href='tg://user?id={uid}'>{uid}</a> – {pts} punti" for i, (uid, pts) in enumerate(ranking)]
        )
    else:
        text_ranking = "Nessun punto ancora."

    await update.message.reply_text(
        f"<b>🏆 Classifica:</b>\n{text_ranking}",
        parse_mode="HTML"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        scores.clear()
        await update.message.reply_text("Classifica resettata.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(answer_callback))
    app.run_polling()
