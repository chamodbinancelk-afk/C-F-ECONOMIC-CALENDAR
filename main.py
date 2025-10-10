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

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CAL_URL = "https://www.myfxbook.com/forex-economic-calendar"
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_SEC", 300))
LAST_EVENT_FILE = "last_event.txt"

bot = Bot(token=BOT_TOKEN)
translator = Translator()

logging.basicConfig(level=logging.INFO, filename="cal.log",
                    format='%(asctime)s %(levelname)s: %(message)s')

def read_last_event():
    if not os.path.exists(LAST_EVENT_FILE):
        return None
    with open(LAST_EVENT_FILE, 'r', encoding='utf-8') as f:
        return f.read().strip()

def write_last_event(ev):
    with open(LAST_EVENT_FILE, 'w', encoding='utf-8') as f:
        f.write(ev)

def fetch_calendar_release():
    last = read_last_event()
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(CAL_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    rows = soup.find_all("tr", class_="calendar-row")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 6:
            actual = cells[5].get_text(strip=True)
            if actual not in ("", "—", "-"):
                date = cells[0].get_text(strip=True)
                time_ = cells[1].get_text(strip=True)
                currency = cells[2].get_text(strip=True)
                event_name = cells[3].get_text(strip=True)
                identifier = f"{date} {time_} {event_name}"
                if identifier == last:
                    continue
                write_last_event(identifier)
                try:
                    event_si = translator.translate(event_name, dest='si').text
                except Exception as e:
                    event_si = "පරිවර්තනය අසාර්ථකයි"
                    logging.error(f"Translate error: {e}")

                sri = pytz.timezone("Asia/Colombo")
                now = datetime.now(sri)
                dt = now.strftime("%Y-%m-%d %I:%M %p")

                msg = f"""📊 Economic Release Event

🕒 Date & Time: {date} {time_}

💱 Currency: {currency}

📝 Event: {event_name}

🔥 සිංහල: {event_si}

⌚ Announcement Time (Local): {dt}
"""
                bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                logging.info(f"Sent event: {identifier}")
    return

if __name__ == "__main__":
    while True:
        try:
            fetch_calendar_release()
        except Exception as e:
            logging.error(f"Error in loop: {e}")
        time.sleep(FETCH_INTERVAL)
