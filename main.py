import requests
from bs4 import BeautifulSoup
from googletrans import Translator
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv
import pytz
import os
import time
import logging

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FF_URL = os.getenv("FOREXFACTORY_NEWS_URL", "https://www.forexfactory.com/news")
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_SEC", 1))
LAST_HEADLINE_FILE = "last_headline.txt"

bot = Bot(token=BOT_TOKEN)
translator = Translator()

# Setup logging
logging.basicConfig(level=logging.INFO, filename="bot.log",
                    format='%(asctime)s %(levelname)s: %(message)s')


def read_last_headline():
    if not os.path.exists(LAST_HEADLINE_FILE):
        return None
    with open(LAST_HEADLINE_FILE, 'r', encoding='utf-8') as f:
        return f.read().strip()


def write_last_headline(headline):
    with open(LAST_HEADLINE_FILE, 'w', encoding='utf-8') as f:
        f.write(headline)


def fetch_latest_news():
    last = read_last_headline()
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(FF_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    news_link = soup.find('a', href=lambda href: isinstance(href, str) and href.startswith('/news/') and not href.endswith('/hit'))
    if not news_link:
        logging.warning("News element not found!")
        return

    headline = news_link.get_text(strip=True)
    news_url = "https://www.forexfactory.com" + news_link['href']

    if headline == last:
        return

    write_last_headline(headline)

    # Translate
    try:
        translation = translator.translate(headline, dest='si').text
    except Exception as e:
        translation = "Translation failed"
        logging.error(f"Translation error: {e}")

    # Step 2: Go to article page and extract image
    img_url = None
    try:
        article_resp = requests.get(news_url, headers=headers, timeout=10)
        article_resp.raise_for_status()
        article_soup = BeautifulSoup(article_resp.content, 'html.parser')
        meta_img = article_soup.find("meta", property="og:image")
        if meta_img:
            img_url = meta_img.get("content")
        else:
            img_tag = article_soup.find("img")
            if img_tag:
                img_url = img_tag.get("src")

        # Make sure it's a full URL
        if img_url and img_url.startswith('/'):
            img_url = "https://www.forexfactory.com" + img_url

    except Exception as e:
        logging.error(f"Image extraction failed: {e}")
        img_url = None

    # Time
    sri_lanka_tz = pytz.timezone('Asia/Colombo')
    now = datetime.now(sri_lanka_tz)
    date_time = now.strftime('%Y-%m-%d %I:%M %p')

    message = f"""📰 *Fundamental News (සිංහල)*


⏰ *Date & Time:* {date_time}
                

🌎 *English:* {headline}


🔥 *සිංහල:* {translation}


🚀 *Dev :* Mr Chamo 🇱🇰
"""

    try:
        if img_url:
            bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=message, parse_mode='Markdown')
        else:
            bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')

        logging.info(f"Posted: {headline}")
    except Exception as e:
        logging.error(f"Telegram error: {e}")


if __name__ == '__main__':
    while True:
        try:
            fetch_latest_news()
        except Exception as e:
            logging.error(f"Error in loop: {e}")
        time.sleep(FETCH_INTERVAL)

