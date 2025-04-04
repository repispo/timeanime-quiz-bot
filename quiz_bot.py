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

# Configurazioni
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
current_anime = ""

# Funzione per selezionare un personaggio
def get_random_character():
    for _ in range(5):
        page = random.randint(1, 200)
        query = '''
        query {
          Page(page: %d, perPage: 1) {
            characters(sort: FAVOURITES_DESC) {
              name { full }
              image { large }
              media(perPage: 1) {
                nodes {
                  title { romaji }
                  startDate { year }
                }
              }
            }
          }
        }
        ''' % page

        response = requests.post("https://graphql.anilist.co", json={"query": query})
        try:
            data = response.json()
            char = data["data"]["Page"]["characters"][0]
            name = char["name"]["full"]
            image = char["image"]["large"]
            anime = char["media"]["nodes"][0]["title"]["romaji"]
            year = char["media"]["nodes"][0]["startDate"]["year"]
            if year and (year >= 2020 or random.random() < 0.1):
                return name, image, anime
        except:
            continue
    return None, None, None

# Comando per iniziare il quiz
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_answer, answered_users, correct_users, current_anime

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può avviare il quiz.")
        return

    name, image, anime = get_random_character()
    if not name:
        await update.message.reply_text("Errore nel recupero dei dati, riprova.")
        return

    current_answer = name.lower()
    current_anime = anime
    answered_users.clear()
    correct_users.clear()

    fake_names = ["Naruto", "Goku", "Asuka", "Levi", "Mikasa", "Rem", "Shinji", "Sasuke"]
    options = random.sample(fake_names, 4)
    options.append(name)
    random.shuffle(options)
    keyboard = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image,
        caption="🎮 *AIO QUIZ!*\nChi è questo personaggio? Hai 5 minuti per rispondere!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⏳ Aspetta 2 minuti per l'indizio..."
    )

    await context.application.create_task(provide_hint(context, update.effective_chat.id))
    await context.application.create_task(timeout_quiz(context, update.effective_chat.id))

# Indizio dopo 2 minuti
async def provide_hint(context, chat_id):
    await context.application.bot.send_message(
        chat_id=chat_id,
        text=f"💡 Indizio: il personaggio proviene da *{current_anime}*",
        parse_mode="Markdown",
        delay=120
    )

# Timeout dopo 5 minuti
async def timeout_quiz(context, chat_id):
    await context.application.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ Tempo scaduto! La risposta corretta era: *{current_answer.title()}*",
        parse_mode="Markdown",
        delay=300
    )

# Gestione delle risposte
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

# Mostrare la classifica
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

# Reset classifica
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Solo l'admin può resettare la classifica.")
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
