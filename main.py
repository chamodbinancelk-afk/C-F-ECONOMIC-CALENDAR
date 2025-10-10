import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime
import pytz
import time
import os

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://www.forexfactory.com/calendar"

bot = Bot(token=BOT_TOKEN)
sent_event_ids = set()

def get_latest_event():
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(URL, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.find_all("tr", class_="calendar__row")

    for row in rows[::-1]:  # Check latest first
        event_id = row.get("data-event-id")
        currency_td = row.find("td", class_="calendar__currency")
        time_td = row.find("td", class_="calendar__time")
        title_td = row.find("td", class_="calendar__event")
        actual_td = row.find("td", class_="calendar__actual")
        
        if not time_td or not title_td or not actual_td or not currency_td:
            continue
            
        time_str = time_td.text.strip()
        title = title_td.text.strip()
        actual = actual_td.text.strip()
        currency = currency_td.text.strip()

        if event_id and actual and actual != "-":
            return {
                "id": event_id,
                "country": country,
                "time": time_str,
                "title": title,
                "actual": actual
            }
    return None

def send_event(event):
    tz = pytz.timezone('Asia/Colombo')
    now = datetime.now(tz).strftime('%Y-%m-%d %I:%M %p')
    msg = f"""📊 Economic Event Alert!

🕒 Date & Time: {now}

🌍 Country: {event['country']}

📌 Event: {event['title']}

📈 Actual: {event['actual']}

🚀 Dev: Mr Chamo 🇱🇰
"""
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

if __name__ == "__main__":
    print("Bot started...")
    latest = get_latest_event()
    if latest:
        send_event(latest)
        sent_event_ids.add(latest['id'])

    while True:
        try:
            event = get_latest_event()
            if event and event['id'] not in sent_event_ids:
                send_event(event)
                sent_event_ids.add(event['id'])
        except Exception as e:
            print("Error:", e)
        time.sleep(1)
