import feedparser
import openai
import os
import asyncio
import re
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", 60))

bot = Bot(token=BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

FEEDS = [
    "https://www.animenewsnetwork.com/all/rss.xml",
    "https://www.crunchyroll.com/newsrss",
    "https://www.animenews24.com/feed/"
]

FILTER_KEYWORDS = [
    "spoiler", "review", "episode", "episodio", "ep.", "chapter", "recensione"
]

posted_links = []

def contains_filtered_words(text):
    text = text.lower()
    return any(keyword in text for keyword in FILTER_KEYWORDS)

def clean_telegram_html(text):
    # Rimuove tag HTML non supportati
    return re.sub(r'<(/?)(?!b|i|u|strong|a|code|pre|br)[^>]*>', '', text)

def get_news():
    news = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.link in posted_links:
                continue
            title = entry.title
            summary = entry.summary if "summary" in entry else ""
            if contains_filtered_words(title) or contains_filtered_words(summary):
                continue
            image = None
            if "media_content" in entry:
                for media in entry.media_content:
                    if "url" in media:
                        image = media["url"]
                        break
            news.append({
                "title": title,
                "summary": summary,
                "link": entry.link,
                "image": image
            })
    return news

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='it').translate(text)
    except Exception as e:
        print(f"Errore traduzione: {e}")
        return text

def rewrite(title, summary):
    prompt = f"""
🎌 Scrivi un post dettagliato in italiano per appassionati di anime e manga, basandoti sulle informazioni seguenti.

✅ Regole da seguire:
- Inserisci un TITOLO in grassetto (usa ** ... **)
- Massimo 1990 caratteri
- Usa molte emoji dove utile 🎉🔥❤️🎌✨
- Tono appassionato, coinvolgente, da fan per fan
- Spiega bene di cosa parla l’opera (trama, genere, data uscita se c’è)
- Aggiungi tanti hashtag anime/manga solo in fondo (#anime #news ecc.)
- Alla fine **inserisci sempre** questo blocco fisso (non modificarlo!):

🔹 Unisciti al nostro gruppo Telegram per restare aggiornato su tutte le novità anime! Link in bio! 🔹  
📺 Seguici su @animeitaliacomunitaotaku per aggiornamenti esclusivi! 🎌🔥

📝 Ecco i dati da cui partire:
Titolo originale: {title}
Descrizione ufficiale: {summary}

✍️ Scrivi ora il post:
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Errore rielaborazione: {e}")
        return f"**{title}**\n\n{summary}"

async def send_post(news_item):
    message = clean_telegram_html(news_item['text'])
    try:
        if news_item["image"]:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=news_item["image"], caption=message, parse_mode=ParseMode.HTML)
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode=ParseMode.HTML)
    except Exception as e:
        print("Errore invio su Telegram:", e)

async def main_loop():
    while True:
        print("🔄 Controllo nuovi articoli RSS...")
        news_list = get_news()
        for item in news_list:
            try:
                title_it = translate(item["title"])
                summary_it = translate(item["summary"])
                rewritten = rewrite(title_it, summary_it)
                post_data = {
                    "text": rewritten,
                    "link": item["link"],
                    "image": item["image"]
                }
                await send_post(post_data)
                posted_links.append(item["link"])
                await asyncio.sleep(5)  # evita flood su Telegram
            except Exception as e:
                print("❌ Errore nel processo:", e)
        await asyncio.sleep(INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    asyncio.run(main_loop())
