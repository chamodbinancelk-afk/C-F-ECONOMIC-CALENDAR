# Forex News Telegram Bot

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

def analyze_comparison(actual, previous):
    try:
        a = float(actual.replace('%','').strip())
        p = float(previous.replace('%','').strip())
        if a > p:
            return f"පෙර දත්තවලට වඩා ඉහළයි ({actual}%)", "📉 Forex සහ Crypto වෙළඳපොළ පහළට යා හැකියි"
        elif a < p:
            return f"පෙර දත්තවලට වඩා පහළයි ({actual}%)", "📈 Forex සහ Crypto වෙළඳපොළ ඉහළට යා හැකියි"
        else:
            return f"පෙර දත්තවලට සමානයි ({actual}%)", "⚖ Forex සහ Crypto වෙළඳපොළ ස්ථාවරයෙහි පවතී"
    except:
        return f"Actual: {actual}", "🔍 වෙළඳපොළ ප්‍රතිචාර අනාවැකි කළ නොහැක"

def get_latest_event():
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(URL, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.find_all("tr", class_="calendar__row")

    for row in rows[::-1]:
        event_id = row.get("data-event-id")
        currency_td = row.find("td", class_="calendar__currency")
        time_td = row.find("td", class_="calendar__time")
        title_td = row.find("td", class_="calendar__event")
        actual_td = row.find("td", class_="calendar__actual")
        previous_td = row.find("td", class_="calendar__previous")

        if not all([event_id, currency_td, title_td, time_td, actual_td, previous_td, impact_td]):
            continue

        actual = actual_td.text.strip()
        previous = previous_td.text.strip() if previous_td else "0"
        if not actual or actual == "-":
            continue

       impact_td = row.find('td', class_='calendar_cell calendar_impact')
       impact_span = impact_td.find('span', title=True)

if impact_span:
    impact_text = impact_span['title']  # e.g. "High Impact Expected"
else:
    impact_text = "Unknown"

        return {
            "id": event_id,
            "currency": currency_td.text.strip(),
            "title": title_td.text.strip(),
            "time": time_td.text.strip(),
            "actual": actual,
            "previous": previous,
            "impact": impact
        }
    return None

def send_event(event):
    now = datetime.now(pytz.timezone('Asia/Colombo')).strftime('%Y-%m-%d %H:%M:%S')
    
    impact = event['impact']
    if impact_text == "High Impact Expected":
        impact_level = "🔴 High"
    elif impact_text == "Medium Impact Expected":
        impact_level = "🟠 Medium"
    elif impact_text == "Low Impact Expected":
        impact_level = "🟢 Low"
    else:
        impact_level = "⚪ Unknown"
    
    comparison, reaction = analyze_comparison(event['actual'], event['previous'])

    msg = f"""🛑 *Breaking News* 📰
    

⏰ *Date & Time:* {now}

🌍 *Currency:* {event['currency']}

📌 *Headline:* {event['title']}

🔥 *Impact:* {impact_level}

📈 *Actual:* {event['actual']}
📉 *Previous:* {event['previous']}

🔍 *Details:* {comparison}

📈 *Market Reaction Forecast:* {reaction}

🚀 *Dev : Mr Chamo 🇱🇰*
"""
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

if __name__ == "__main__":
    print("Bot started...")
    while True:
        try:
            event = get_latest_event()
            if event and event['id'] not in sent_event_ids:
                send_event(event)
                sent_event_ids.add(event['id'])
        except Exception as e:
            print("Error:", e)
        time.sleep(1)
