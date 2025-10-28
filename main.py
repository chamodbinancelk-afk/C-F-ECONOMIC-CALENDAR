import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime
import pytz
import time
import os
from flask import Flask
from threading import Thread

# ----------------------------------------------------
# 1. Configuration (සැකසීම්)
# ----------------------------------------------------

# Environment variables වලින් Token සහ Chat ID ලබා ගනී
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://www.forexfactory.com/calendar"

# Bot object එක නිර්මාණය කිරීම
if not BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
    exit()

bot = Bot(token=BOT_TOKEN)
# දැනටමත් යවා ඇති event IDs ගබඩා කිරීම සඳහා set එක
sent_event_ids = set()

app = Flask(__name__) 

# ----------------------------------------------------
# 2. Helper Functions (උපකාරක ශ්‍රිත)
# ----------------------------------------------------

def analyze_comparison(actual, previous):
    """
    පෙර දත්ත සහ වත්මන් දත්ත සංසන්දනය කර වෙළඳපොළ ප්‍රතිචාරය අනාවැකි පළ කරයි.
    """
    try:
        # ප්‍රතිශත ලකුණු ඉවත් කර float අගයක් බවට පත් කිරීම
        a = float(actual.replace('%','').strip())
        p = float(previous.replace('%','').strip())
        
        # සාමාන්‍යයෙන්, Actual > Previous යනු මුදල් ඒකකයට ධනාත්මක බලපෑමකි.
        if a > p:
            # නිවැරදි කළ අනාවැකිය: ඉහළ අගයක් මුදල් ඒකකය ශක්තිමත් කිරීමට හේතු විය හැක.
            return f"පෙර දත්තවලට වඩා ඉහළයි (Actual: {actual})", "📈 ධනාත්මක බලපෑමක්, වෙළඳපොළ ඉහළට යා හැකියි"
        elif a < p:
            # නිවැරදි කළ අනාවැකිය: පහළ අගයක් මුදල් ඒකකය දුර්වල කිරීමට හේතු විය හැක.
            return f"පෙර දත්තවලට වඩා පහළයි (Actual: {actual})", "📉 සෘණාත්මක බලපෑමක්, වෙළඳපොළ පහළට යා හැකියි"
        else:
            return f"පෙර දත්තවලට සමානයි (Actual: {actual})", "⚖️ වෙළඳපොළ ප්‍රතිචාරය ස්ථාවරයෙහි පවතී"
    except ValueError:
        # float බවට හැරවිය නොහැකි දත්ත සඳහා
        return f"Actual: {actual}", "🔍 දත්ත සංසන්දනය කළ නොහැක, වෙළඳපොළ ප්‍රතිචාර අනාවැකි පළ නොවේ"
    except Exception as e:
        print(f"Error in analyze_comparison: {e}")
        return f"Actual: {actual}", "❌ අනාවැකි දෝෂයක්"


def get_impact(row):
    """
    Forex Factory calendar row එකකින් impact level එක ලබා ගනී.
    """
    impact_td = row.find('td', class_='calendar__impact')
    
    if not impact_td:
        return "Unknown"

    # 'title' attribute එක හරහා impact එක ලබා ගැනීමට ප්‍රමුඛත්වය දීම
    impact_span = impact_td.find('span', title=True)
    
    if impact_span and impact_span['title'].strip():
        impact = impact_span['title'].strip()
        return impact

    # class attribute හරහා fallback
    impact_span_fallback = impact_td.find('span')
    
    if impact_span_fallback:
        class_attr = impact_span_fallback.get('class', [])
        
        # High Impact (රතු)
        if any('ff-impact-red' in c for c in class_attr):
            return "High Impact Expected"
        # Medium Impact (තැඹිලි)
        elif any('ff-impact-ora' in c for c in class_attr):
            return "Medium Impact Expected"
        # Low Impact (කහ)
        elif any('ff-impact-yel' in c for c in class_attr):
            return "Low Impact Expected"

    return "Unknown"

# ----------------------------------------------------
# 3. Main Scraping and Sending Functions (ප්‍රධාන ශ්‍රිත)
# ----------------------------------------------------

def get_latest_event():
    """Forex Factory වෙතින් නවතම සම්පූර්ණ වූ (Actual අගය සහිත) event එක ලබා ගනී."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        resp = requests.get(URL, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    # 'calendar__row--is-past' සහිත පේළි පමණක් සලකා බැලීම
    rows = soup.find_all("tr", class_="calendar__row")

    # අලුත්ම event එක සොයා ගැනීම සඳහා ආපසු හැරවීම
    for row in rows[::-1]:
        event_id = row.get("data-event-id")
        
        # මේක අනාගත event එකක් නම්, සලකා බලන්නේ නැත
        if 'calendar__row--is-future' in row.get('class', []):
            continue

        currency_td = row.find("td", class_="calendar__currency")
        time_td = row.find("td", class_="calendar__time")
        title_td = row.find("td", class_="calendar__event")
        actual_td = row.find("td", class_="calendar__actual")
        previous_td = row.find("td", class_="calendar__previous")
        
        if not all([event_id, currency_td, title_td, time_td, actual_td, previous_td]):
            continue

        actual = actual_td.text.strip()
        previous = previous_td.text.strip() if previous_td else "-"
        
        # Actual අගය නොමැති නම් (තවමත් නිවේදනය කර නොමැති නම්), මඟ හරින්න
        if not actual or actual == "-" or actual == "":
            continue

        impact_text = get_impact(row)
        time_text = time_td.text.strip()
        
        # Time එකේ 'Tentative' තිබේ නම් එය 'Time' නොවේ. එය date cell එකක්.
        if 'Tentative' in time_text:
             continue


        return {
            "id": event_id,
            "currency": currency_td.text.strip(),
            "title": title_td.text.strip(),
            "time": time_text,
            "actual": actual,
            "previous": previous,
            "impact": impact_text
        }
    return None

def send_event(event):
    """Telegram වෙත event details යවයි."""
    if not CHAT_ID:
        print("Error: TELEGRAM_CHAT_ID environment variable not set. Cannot send message.")
        return

    # ශ්‍රී ලංකා වේලාව (Colombo)
    now = datetime.now(pytz.timezone('Asia/Colombo')).strftime('%Y-%m-%d %H:%M:%S %Z')
    
    impact = event['impact']
    if "High" in impact:
        impact_level = "🔴 High"
    elif "Medium" in impact:
        impact_level = "🟠 Medium"
    elif "Low" in impact:
        impact_level = "🟢 Low"
    else:
        impact_level = "⚪ Unknown"
    
    comparison, reaction = analyze_comparison(event['actual'], event['previous'])

    msg = f"""🛑 *Breaking News* 📰

⏰ *Colombo Time:* {now}

🌍 *Currency:* {event['currency']}

📌 *Headline:* {event['title']}

🔥 *Impact:* {impact_level}

📊 *Data Comparison:* {comparison}

📈 *Actual:* {event['actual']}
📉 *Previous:* {event['previous']}

🔮 *Market Forecast:* {reaction}

🚀 *Dev: Mr Chamo 🇱🇰*
"""
    try:
        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# ----------------------------------------------------
# 4. Threaded Bot Loop (නොනවත්වා ක්‍රියාත්මක වන Bot කොටස)
# ----------------------------------------------------

def run_bot_loop():
    """Bot Loop එක වෙනම Thread එකක ක්‍රියාත්මක කිරීමට."""
    print("Forex Bot Loop Started. Checking every 60 seconds...")
    # ආරම්භයේදී, දැනටමත් සම්පූර්ණ කර ඇති event id ටික ලබා ගනී.
    # මේක නැවත යැවීම වැලැක්වීමට උපකාරී වේ.
    initial_event = get_latest_event()
    if initial_event:
        sent_event_ids.add(initial_event['id'])
        print(f"Initial event ID collected: {initial_event['id']}")
        
    while True:
        try:
            event = get_latest_event()
            # event එකක් ලැබී ඇත්නම් සහ එය දැනටමත් යවා නොමැති නම්
            if event and event['id'] not in sent_event_ids:
                send_event(event)
                sent_event_ids.add(event['id'])
                print(f"Sent New Event ID: {event['id']} - {event['title']}")
            # event එකක් ලැබී නොමැති නම්, බොහෝ විට දත්ත නැවත ලබා ගැනීමට ප්‍රමාද වැඩි නිසා
            elif event:
                # දැනටමත් යවා ඇති event එක නැවත log කරන්න
                pass

        except Exception as e:
            print(f"General Error in Bot Loop: {e}")
        
        # 60 තත්පර පොරොත්තු කාලය (Scraping rate අඩු කිරීම සඳහා)
        time.sleep(10)

# ----------------------------------------------------
# 5. Flask Routes (Web Server එක)
# ----------------------------------------------------

@app.route('/')
def hello():
    """Bot status පෙන්වන්න සහ uptime monitoring සඳහා."""
    return "Forex Bot is Running 24/7! (Checked last at: {}) 🚀".format(
        datetime.now(pytz.timezone('Asia/Colombo')).strftime('%Y-%m-%d %H:%M:%S %Z')
    ), 200

@app.route('/status')
def status():
    """Bot status details."""
    return {
        "status": "running",
        "events_sent": len(sent_event_ids),
        "bot_name": "ForexNewsBot",
        "last_checked": datetime.now(pytz.timezone('Asia/Colombo')).strftime('%Y-%m-%d %H:%M:%S %Z')
    }, 200

# ----------------------------------------------------
# 6. Execution Block (ක්‍රියාත්මක කිරීම)
# ----------------------------------------------------

if __name__ == "__main__":
    # Bot loop එක වෙනම thread එකක ආරම්භ කිරීම
    t = Thread(target=run_bot_loop)
    t.daemon = True
    t.start()
    
    print("Web Server Starting on port 5000...")
    # Flask web server එක ආරම්භ කිරීම
    app.run(host="0.0.0.0", port=5000)
