import os
import logging
import random
import asyncio
import requests
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = [608950288, 123456789]  # Aggiungi qui gli ID admin che possono usare /startquiz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scores = defaultdict(int)
answered_users = set()
current_answer = ""
current_anime = ""
correct_users = []

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, correct_users, current_anime

    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo l'admin può avviare il quiz.")
        return

    answered_users.clear()
    correct_users.clear()

    for _ in range(10):
        try:
            year = random.choice(range(2000, 2024)) if random.randint(1, 10) == 1 else random.choice(range(2020, 2024))
            page = random.randint(1, 20)
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
            response = requests.post("https://graphql.anilist.co", json={"query": query})
            data = response.json()
            char = data["data"]["Page"]["characters"][0]
            anime_year = char["media"]["nodes"][0]["startDate"]["year"]
            if anime_year and ((year >= 2020 and anime_year >= 2020) or (year < 2020 and anime_year < 2020)):
                name = char["name"]["full"]
                image = char["image"]["large"]
                current_anime = char["media"]["nodes"][0]["title"]["romaji"]
                break
        except Exception:
            continue
    else:
        await update.message.reply_text("Sto cercando un personaggio più recente, riprova...")
        return

    current_answer = name.lower()

    fake_names = ["Naruto", "Goku", "Asuka", "Levi", "Mikasa", "Rem", "Sasuke", "Ichigo"]
    options = random.sample(fake_names, 4)
    options.append(name)
    random.shuffle(options)
    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image,
        caption="""🎮 *AIO QUIZ!*
Chi è questo personaggio? Hai 5 minuti per rispondere!""",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ Aspetta 2 minuti per l'indizio...")
    context.application.create_task(provide_hint(context, update.effective_chat.id))
    context.application.create_task(end_quiz(context, update.effective_chat.id))

async def provide_hint(context: ContextTypes.DEFAULT_TYPE, chat_id):
    await asyncio.sleep(120)
    await context.bot.send_message(chat_id=chat_id, text=f"💡 Indizio: il personaggio proviene da *{current_anime}*", parse_mode="Markdown")

async def end_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id):
    await asyncio.sleep(300)
    await context.bot.send_message(chat_id=chat_id, text=f"⏰ Tempo scaduto! La risposta corretta era: *{current_answer.title()}*", parse_mode="Markdown")

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
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo l'admin può resettare la classifica.")
        return

    scores.clear()
    await update.message.reply_text("✅ Classifica resettata.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("reset", reset))
    print("Bot avviato...")
    app.run_polling()
