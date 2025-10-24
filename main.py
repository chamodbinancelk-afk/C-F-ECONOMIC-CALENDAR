# Forex News Telegram Bot (Full Code with Robust Impact Detection)

import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime
import pytz
import time
import os

# ----------------------------------------------------
# 1. Configuration (සැකසීම්)
# ----------------------------------------------------

# Environment variables must be set for security and proper function.
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://www.forexfactory.com/calendar"

# Initialize Bot and track sent events
bot = Bot(token=BOT_TOKEN)
sent_event_ids = set()

# ----------------------------------------------------
# 2. Helper Functions (උපකාරක ශ්‍රිත)
# ----------------------------------------------------

def analyze_comparison(actual, previous):
    """
    ප්‍රකාශයට පත් කළ Actual අගය Previous අගය සමඟ සන්සන්දනය කර වෙළඳපොළ ප්‍රතිචාරය අනාවැකි කරයි.
    """
    try:
        # '%' සලකුණු ඉවත් කර දත්ත float ලෙස පරිවර්තනය කරයි
        a = float(actual.replace('%','').strip())
        p = float(previous.replace('%','').strip())
        
        if a > p:
            return f"පෙර දත්තවලට වඩා ඉහළයි ({actual}%)", "📉 Forex සහ Crypto වෙළඳපොළ පහළට යා හැකියි"
        elif a < p:
            return f"පෙර දත්තවලට වඩා පහළයි ({actual}%)", "📈 Forex සහ Crypto වෙළඳපොළ ඉහළට යා හැකියි"
        else:
            return f"පෙර දත්තවලට සමානයි ({actual}%)", "⚖ Forex සහ Crypto වෙළඳපොළ ස්ථාවරයෙහි පවතී"
    except:
        # දත්ත කියවීමේ දෝෂයක් ඇත්නම්
        return f"Actual: {actual}", "🔍 වෙළඳපොළ ප්‍රතිචාර අනාවැකි කළ නොහැක"

def get_impact(row):
    """
    Forex Factory calendar row එකකින් impact level එක ලබා ගනී.
    'title' attribute එක හෝ CSS class එක පරීක්ෂා කරයි.
    """
    impact_td = row.find('td', class_='calendar__impact')
    
    if not impact_td:
        return "Unknown"

    # 1. 'title' attribute එක සහිත span element එක සොයා බලයි
    impact_span = impact_td.find('span', title=True)
    
    if impact_span:
        impact = impact_span['title'].strip()
        if impact:
            return impact

    # 2. Fallback: CSS class එකෙන් color එක පරීක්ෂා කරයි
    impact_span_fallback = impact_td.find('span')
    
    if impact_span_fallback:
        class_attr = impact_span_fallback.get('class', [])
        
        if 'ff-impact-red' in class_attr:
            return "High Impact Expected"
        elif 'ff-impact-ora' in class_attr:
            return "Medium Impact Expected"
        elif 'ff-impact-yel' in class_attr:
            return "Low Impact Expected"

    return "Unknown"

# ----------------------------------------------------
# 3. Main Scraping and Sending Functions (ප්‍රධාන ශ්‍රිත)
# ----------------------------------------------------

def get_latest_event():
    """
    Forex Factory වෙතින් නවතම සම්පූර්ණ කරන ලද ප්‍රවෘත්ති Event එක ලබා ගනී.
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(URL, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.find_all("tr", class_="calendar__row")

    # අලුත්ම Events (පහළ සිට ඉහළට) පරීක්ෂා කරයි.
    for row in rows[::-1]:
        event_id = row.get("data-event-id")
        currency_td = row.find("td", class_="calendar__currency")
        time_td = row.find("td", class_="calendar__time")
        title_td = row.find("td", class_="calendar__event")
        actual_td = row.find("td", class_="calendar__actual")
        previous_td = row.find("td", class_="calendar__previous")
        impact_td = row.find('td', class_='calendar__impact')

        # සියලුම අවශ්‍ය දත්ත තිබේදැයි පරීක්ෂා කරයි
        if not all([event_id, currency_td, title_td, time_td, actual_td, previous_td, impact_td]):
            continue

        actual = actual_td.text.strip()
        previous = previous_td.text.strip() if previous_td else "0"
        
        # Actual අගය තිබේදැයි සහ හිස් නොවේදැයි පරීක්ෂා කරයි (Event එක අවසන් වී ඇති බවට සහතික වීමට)
        if not actual or actual == "-":
            continue

        # නව get_impact ශ්‍රිතය භාවිත කරයි
        impact_text = get_impact(row)

        return {
            "id": event_id,
            "currency": currency_td.text.strip(),
            "title": title_td.text.strip(),
            "time": time_td.text.strip(),
            "actual": actual,
            "previous": previous,
            "impact": impact_text
        }
    return None

def send_event(event):
    """
    සකස් කරන ලද පණිවිඩය Telegram වෙත යවයි.
    """
    # ශ්‍රී ලංකාවේ වේලාව
    now = datetime.now(pytz.timezone('Asia/Colombo')).strftime('%Y-%m-%d %H:%M:%S')
    
    impact = event['impact']
    if impact == "High Impact Expected":
        impact_level = "🔴 High"
    elif impact == "Medium Impact Expected":
        impact_level = "🟠 Medium"
    elif impact == "Low Impact Expected":
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

# ----------------------------------------------------
# 4. Execution Block (ක්‍රියාත්මක කිරීම)
# ----------------------------------------------------

if __name__ == "__main__":
    print("Bot started...")
    while True:
        try:
            event = get_latest_event()
            # නවතම Event එකක් තිබේ නම් සහ එය දැනටමත් යවා නොමැති නම්
            if event and event['id'] not in sent_event_ids:
                send_event(event)
                sent_event_ids.add(event['id'])
                print(f"Sent Event ID: {event['id']} ({event['title']})")
        except Exception as e:
            print("Error:", e)
        
        # සර්වර් බර අඩු කිරීමට සහ Forex Factory හි නීති රීතිවලට අනුකූල වීමට කාලය වැඩි කරයි.
        time.sleep(10)
