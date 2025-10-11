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

    for row in rows[::-1]:  # Latest first
        event_id = row.get("data-event-id")
        currency_td = row.find("td", class_="calendar__currency")
        time_td = row.find("td", class_="calendar__time")
        title_td = row.find("td", class_="calendar__event")
        actual_td = row.find("td", class_="calendar__actual")
        previous_td = row.find("td", class_="calendar__previous")

        if not time_td or not title_td or not actual_td or not currency_td:
            continue

        time_str = time_td.text.strip()
        title = title_td.text.strip()
        actual = actual_td.text.strip()
        previous = previous_td.text.strip() if previous_td else "N/A"
        comparison = ""
        currency = currency_td.text.strip()

        if event_id and actual and actual != "-":
            try:
                actual_float = float(actual.replace(',', ''))
                previous_float = float(previous.replace(',', '')) if previous != "N/A" else None
                if previous_float is not None:
                    if actual_float < previous_float:
                        comparison = f"පෙර නිකුත්ව තිබු දත්ත වලට වඩා පහත වැටේ {actual}"
                    elif actual_float > previous_float:
                        comparison = f"පෙර නිකුත්ව තිබු දත්ත වලට වඩා ඉහළ යයි {actual}"
                    else:
                        comparison = f"පෙර නිකුත්ව තිබු දත්ත වලට සමානයි {actual}"
                else:
                    comparison = f"Actual: {actual}"
            except ValueError:
                comparison = f"Actual: {actual}"

            return {
                "id": event_id,
                "country": currency,
                "time": time_str,
                "title": title,
                "actual": actual,
                "previous": previous,
                "comparison": comparison
            }
    return None

def get_market_reaction(comparison_text):
    reaction = ""
    if "පහත" in comparison_text:
        reaction = "💡 බලාපොරොත්තුවට වඩා අඩු දත්ත, වෙළඳපොළට බරපතල හෝ සාමාන්‍ය ආකාරයක බලපෑමක් ඇති විය හැක."
    elif "ඉහළ" in comparison_text:
        reaction = "📈 බලාපොරොත්තුවට වඩා ඉහළ දත්ත, වෙළඳපොළට දැඩි ධනාත්මක බලපෑමක් ඇති විය හැක."
    elif "සමානයි" in comparison_text:
        reaction = "⚖ දත්ත සමාන වූ නිසා වෙළඳපොළට විශේෂ බලපෑමක් නොවිය හැක."
    else:
        reaction = ""
    return reaction

def send_event(event):
    tz = pytz.timezone('Asia/Colombo')
    now = datetime.now(tz).strftime('%Y-%m-%d %I:%M %p')

    reaction = get_market_reaction(event['comparison'])

    msg = f"""🛑 *Breaking News* 📰
    

🕒 *Date & Time:* {now}

🌍 *Country :* {event['country']}

📌 *Headline :* {event['title']}

📈 *Actual :* {event['actual']}
📉 *Previous :* {event.get('previous', 'N/A')}

🔎 *Details :* {event['comparison']}

📈 *Market Reaction :* {reaction}

🚀 *Dev : Mr Chamo 🇱🇰*
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
