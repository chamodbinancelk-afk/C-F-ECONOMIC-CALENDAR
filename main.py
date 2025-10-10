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
CAL_URL = "https://www.forexfactory.com/calendar"
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_SEC", 1))  # check often
LAST_EVENT_FILE = "last_event.txt"

bot = Bot(token=BOT_TOKEN)
translator = Translator()

logging.basicConfig(level=logging.INFO, filename="ffcal.log",
                    format="%(asctime)s %(levelname)s: %(message)s")

def read_last_event():
    if not os.path.exists(LAST_EVENT_FILE):
        return None
    with open(LAST_EVENT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def write_last_event(ev):
    with open(LAST_EVENT_FILE, "w", encoding="utf-8") as f:
        f.write(ev)

def fetch_calendar_release():
    last = read_last_event()
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(CAL_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    rows = soup.find_all("tr", class_="calendar__row")
    for row in rows:
        actual_td = row.find("td", class_="calendar_cell calendar_actual")
        if actual_td:
            actual = actual_td.get_text(strip=True)
            if actual and actual not in ("", "-", "—"):
                time_td = row.find("td", class_="calendar_cell calendar_time")
                time_str = time_td.get_text(strip=True) if time_td else "Unknown Time"
                currency_td = row.find("td", class_="calendar_cell calendar_currency")
                currency = currency_td.get_text(strip=True) if currency_td else "Unknown Currency"
                event_td = row.find("td", class_="calendar_cell calendar_event")
                event = event_td.get_text(strip=True) if event_td else "Unknown Event"
                identifier = f"{currency}-{event}-{actual}"
                if identifier == last:
                    continue
                write_last_event(identifier)

                event_si = translator.translate(event, dest="si").text
                sri_time = datetime.now(pytz.timezone("Asia/Colombo")).strftime("%Y-%m-%d %I:%M %p")

                msg = f"""📢 Economic News Released!

🕒 Local Time: {sri_time}
💱 Country: {currency}
📝 Event: {event}
🌐 සිංහල: {event_si}
📊 Actual: {actual}
⏰ News Time: {time_str}
"""
                bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                logging.info(f"Sent: {identifier}")

if __name__ == "__main__":
    while True:
        try:
            fetch_calendar_release()
        except Exception as e:
            logging.error(f"Error fetching calendar: {e}")
        time.sleep(FETCH_INTERVAL)
