import requests
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime
import pytz
import time
import os
import json
from flask import Flask
from threading import Thread

# ----------------------------------------------------
# 1. Configuration (සැකසීම්)
# ----------------------------------------------------

# Environment variables වලින් Tokens සහ IDs ලබා ගනී
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# Gemini API Key එක environment variable වෙතින් ලබා ගනී
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") 
# Stable model එක භාවිතා කිරීමට යාවත්කාලීන කරන ලදී
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
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

def get_ai_market_analysis(event):
    """
    සිදු වූ ආර්ථික ප්‍රකාශනය Gemini AI වෙත යවා වෙළඳපොළ විශ්ලේෂණයක් සිංහලෙන් ලබා ගනී.
    """
    if not GEMINI_API_KEY:
        return "❌ *Gemini API Key* නොමැත. AI විශ්ලේෂණය කළ නොහැක."
        
    # AI වෙත යැවීමට අවශ්‍ය දත්ත
    data_points = {
        "Headline": event['title'],
        "Currency": event['currency'],
        "Impact Level": event['impact'],
        "Actual Value": event['actual'],
        "Forecast Value": event['forecast'],
        "Previous Value": event['previous']
    }
    
    # සිංහලෙන් විශ්ලේෂණයක් ලබා ගැනීමට ප්‍රධාන Prompt එක සකස් කිරීම
    prompt_text = f"""
    You are a highly experienced and objective Financial Market Analyst. Your task is to analyze the following economic data release and provide a clear, concise, and structured market impact analysis in a **mix of Sinhala and English (Singlish)**.

    **Instructions:**
    1. Focus on the *Fundamental Interpretation* of the data (e.g., Is the news Hawkish/Dovish for the USD? Is the data inflationary/deflationary?).
    2. Analyze the potential immediate impact on the relevant currency (Forex) and broader market sentiment (Crypto) using the following principles:
        - Strong USD (Hawkish Policy/Good data) generally leads to a *downward* movement in major non-USD Forex pairs (like EUR/USD) and puts *downward* pressure on Crypto (Risk-off).
        - Weak USD (Dovish Policy/Bad data, like a rate cut) generally leads to an *upward* movement in non-USD Forex pairs and *upward* pressure on Crypto (Risk-on).
    3. The response must be a single, detailed paragraph (maximum 100 words) in a **mix of Sinhala and English (Singlish)**, using English for technical terms like 'Hawkish', 'Dovish', 'Risk-on', 'Inflation', etc.
    4. Start the analysis with a clear summary sentence.

    **Economic Data for Analysis:**
    {json.dumps(data_points, indent=2)}
    """
    
    # API Payload එක
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        # Google Search Tool එක භාවිතයෙන් සත්‍ය වෙළඳපොළ ප්‍රතිචාර පිළිබඳව දැනුම ලබා ගැනීමට
        "tools": [{"google_search": {} }], 
        "systemInstruction": {
            "parts": [{"text": "You are an expert market analyst providing fundamental analysis in a mix of Sinhala and English (Singlish). Keep the response professional and objective."}]
        },
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    # API Call එක
    for attempt in range(3): # Exponential backoff for robustness
        try:
            # Timeout එක 30s දක්වා වැඩි කරන ලදී
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=30)
            response.raise_for_status() # HTTP errors raise exception
            
            result = response.json()
            
            if result.get('candidates') and result['candidates'][0].get('content'):
                ai_text = result['candidates'][0]['content']['parts'][0]['text']
                return ai_text
            
            return "❌ AI විශ්ලේෂණය ලබා දීමට අපොහොසත් විය (Empty response)."

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred on AI analysis: {http_err} (Status Code: {response.status_code})")
            if response.status_code in [429, 503] and attempt < 2:
                # Retry on rate limit or server error
                sleep_time = 2 ** attempt
                print(f"Retrying AI call in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                return f"❌ AI විශ්ලේෂණය දෝෂ සහිතයි. (HTTP {response.status_code})"
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred on AI analysis: {req_err}")
            return "❌ AI විශ්ලේෂණය සම්බන්ධතා දෝෂයකින් අසාර්ථක විය."
        except Exception as e:
            print(f"Unknown error in AI analysis: {e}")
            return "❌ AI විශ්ලේෂණය ලබා දීමට අපොහොසත් විය."

    return "❌ AI විශ්ලේෂණය ලබා දීමට නැවත උත්සාහයන් තුනම අසාර්ථක විය."


def get_impact(row):
    """
    Forex Factory calendar row එකකින් impact level එක ලබා ගනී.
    """
    impact_td = row.find('td', class_='calendar__impact')
    
    if not impact_td:
        return "Unknown"

    impact_span = impact_td.find('span', title=True)
    
    if impact_span and impact_span['title'].strip():
        impact = impact_span['title'].strip()
        return impact

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
        forecast_td = row.find("td", class_="calendar__forecast") 
        
        if not all([event_id, currency_td, title_td, time_td, actual_td, previous_td, forecast_td]):
            continue

        actual = actual_td.text.strip()
        previous = previous_td.text.strip() if previous_td else "-"
        forecast = forecast_td.text.strip() if forecast_td else "-"
        
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
            "forecast": forecast, 
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
    
    # --- NEW: Gemini AI Analysis ලබා ගැනීම ---
    ai_analysis_text = get_ai_market_analysis(event)
    # ------------------------------------------

    msg = f"""🛑 *Breaking News* 📰

⏰ *Colombo Time:* {now}

🌍 *Currency:* {event['currency']}

📌 *Headline:* {event['title']}

🔥 *Impact:* {impact_level}

📈 *Actual:* {event['actual']}
📊 *Forecast:* {event['forecast']}
📉 *Previous:* {event['previous']}

---
🧠 *AI Market Analysis (සිංහල/English):*
{ai_analysis_text}
---

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
    print("Forex Bot Loop Started. Checking every 10 seconds...")
    # ආරම්භයේදී, දැනටමත් සම්පූර්ණ කර ඇති event id ටික ලබා ගනී.
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
        
        # 10 තත්පර පොරොත්තු කාලය: ඉක්මන් ප්‍රතිචාර සඳහා 10s යනු වඩාත් සුදුසුයි.
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

@app.route('/test')
def test():
    """Test route to send the latest event regardless of sent_event_ids."""
    event = get_latest_event()
    if event:
        send_event(event)
        return {
            "status": "success",
            "message": f"Test message sent for event: {event['title']}",
            "event_id": event['id']
        }, 200
    else:
        return {
            "status": "error",
            "message": "No event found to send"
        }, 404

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
