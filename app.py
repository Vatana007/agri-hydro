#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🌱 NFT Hydroponic Automation System - Cloud API Server
រចនាឡើងសម្រាប់ដំណើរការនៅលើ Cloud (Render.com) ដោយឥតគិតថ្លៃរហូត
និងទំនាក់ទំនងជាមួយបន្ទះ ESP8266 តាមរយៈ WiFi
"""

import os
import time
import json
import threading
import requests
from flask import Flask, jsonify, request, send_from_directory

# ================== កំណត់តម្លៃទូទៅ (Configuration) ==================
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyUGmBiRx5rsVDoqlxBs99oBcN-QILD6LIuBlTo-J_ei1lkO19oaNsHWbTzfzNOuyfF/exec"

# Telegram Bot
BOT_TOKEN = "8683283536:AAGRIY4bn_6OybeVE4Qm2lo_M3FlfCTREGw"
CHAT_ID = "-5397107189"
OWNER_ID = "1807322375" # ជំនួសដោយ ID តេឡេក្រាមរបស់អ្នកដើម្បីការពារកុំឱ្យអ្នកផ្សេងបញ្ជាបាន

# ដែនកំណត់សុវត្ថិភាពលំនាំដើម (Thresholds - អាចកែប្រែបានពី UI)
AIR_TEMP_THRESHOLD = 33.0     # សីតុណ្ហភាពខ្យល់ខ្ពស់បំផុត
WATER_TEMP_THRESHOLD = 35.0   # សីតុណ្ហភាពទឹកខ្ពស់បំផុត
WATER_LOW_THRESHOLD = 28      # កម្រិតចម្ងាយវាស់ពីសេនស័រទៅទឹក (កម្រិតទឹកទាប - កម្ពស់ទឹក 2cm)
TANK_HEIGHT = 30              # កម្ពស់ធុងទឹកសរុប (30cm)

# ការកំណត់មុខងារផ្សេងៗ (អាចកែប្រែបានពី UI)
telegram_alerts_enabled = True
google_sheet_logging_enabled = True

# ប៉ារ៉ាម៉ែត្រកាលកំណត់ពេលវេលា
UPLOAD_INTERVAL = 15          # ផ្ញើទៅ Google Sheet យ៉ាងតិចរាល់ ១៥ វិនាទីម្តង
# ===================================================================

# ស្ថានភាពបច្ចុប្បន្ន
air_temp = 28.5
humidity = 65.0
water_temp = 26.0
water_level = 10
auto_mode = True
use_simulation = True # បើក/បិទ របៀបសាកល្បង ឬទិន្នន័យពិតពីបន្ទះឈីប

# Actuator states (commands sent to ESP8266)
fan_state = "OFF"
pump_state = "OFF"

# ស្ថានភាពនៃការផ្ញើសារព្រមាន
high_air_temp_alert_sent = False
high_water_temp_alert_sent = False
low_water_alert_sent = False
high_water_alert_sent = False

# អាយឌីសារចុងក្រោយដែលទទួលបានពី Telegram
last_update_id = 0
last_sheet_upload_time = 0

# ចាប់ផ្តើម Flask App
web_app = Flask(__name__)

@web_app.route('/')
def index():
    """បង្ហាញទំព័រ Web UI Dashboard (Vue.js)"""
    try:
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'index.html')
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Failed to read index.html: {str(e)}")
        return f"❌ Error loading index.html: {str(e)}", 500

@web_app.route('/manifest.json')
def serve_manifest():
    """Serve Manifest for PWA"""
    return send_from_directory('static', 'manifest.json')

@web_app.route('/api/status', methods=['GET'])
def get_status():
    """ផ្ញើទិន្នន័យសេនស័រ ស្ថានភាពឧបករណ៍ និងការកំណត់ទាំងអស់ទៅកាន់ Web UI"""
    global air_temp, humidity, water_temp, water_level
    global fan_state, pump_state
    
    if use_simulation:
        import random
        # របៀបសាកល្បង៖ បង្កើតទិន្នន័យសិប្បនិម្មិត
        if fan_state == "ON":
            air_temp = max(25.0, air_temp - random.uniform(0.1, 0.4))
        else:
            air_temp = min(36.0, air_temp + random.uniform(0.1, 0.3))
            
        if pump_state == "ON":
            water_level = max(0, water_level - 1)
        else:
            water_level = min(TANK_HEIGHT, water_level + 1)
            
        humidity = round(random.uniform(55.0, 75.0), 1)
        water_temp = round(air_temp - 2.0, 2)
        
        # ដំណើរការស្វ័យប្រវត្ត និងឆែកការព្រមានសម្រាប់ Simulation
        auto_control()
        check_alerts()
        
        # ផ្ញើទិន្នន័យទៅ Google Sheets (Asynchronous) ទៅកាន់សន្លឹក DataSim
        send_to_google_sheet(is_sim=True)
        
    return jsonify({
        "airTemp": air_temp,
        "humidity": humidity,
        "waterTemp": water_temp,
        "waterLevel": water_level,
        "autoMode": auto_mode,
        "fan": fan_state,
        "pump": pump_state,
        "airTempThreshold": AIR_TEMP_THRESHOLD,
        "waterTempThreshold": WATER_TEMP_THRESHOLD,
        "waterLevelThreshold": WATER_LOW_THRESHOLD,
        "telegramAlertsEnabled": telegram_alerts_enabled,
        "googleSheetLoggingEnabled": google_sheet_logging_enabled,
        "useSimulation": use_simulation
    })

@web_app.route('/api/control', methods=['POST'])
def control_system():
    """ទទួលបញ្ជាពី Web UI សម្រាប់កែប្រែរាល់មុខងារទាំងអស់"""
    global auto_mode, fan_state, pump_state, use_simulation
    global AIR_TEMP_THRESHOLD, WATER_TEMP_THRESHOLD, WATER_LOW_THRESHOLD
    global telegram_alerts_enabled, google_sheet_logging_enabled
    
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    # ១. កែប្រែរបៀបស្វ័យប្រវត្ត
    if "autoMode" in data:
        auto_mode = bool(data["autoMode"])
        send_telegram_message(f"🔄 *Auto Mode* {'Activated' if auto_mode else 'Deactivated'} via Web UI")
        
    # ២. កែប្រែដែនកំណត់ (Thresholds)
    if "airTempThreshold" in data:
        AIR_TEMP_THRESHOLD = float(data["airTempThreshold"])
        print(f"⚙️ Updated Air Temp Threshold to: {AIR_TEMP_THRESHOLD}°C")
    if "waterTempThreshold" in data:
        WATER_TEMP_THRESHOLD = float(data["waterTempThreshold"])
        print(f"⚙️ Updated Water Temp Threshold to: {WATER_TEMP_THRESHOLD}°C")
    if "waterLevelThreshold" in data:
        WATER_LOW_THRESHOLD = int(data["waterLevelThreshold"])
        print(f"⚙️ Updated Water Level Threshold to: {WATER_LOW_THRESHOLD} cm")
        
    # ៣. កែប្រែកុងតាក់មុខងារ Alerts & Logging & Simulation
    if "telegramAlertsEnabled" in data:
        telegram_alerts_enabled = bool(data["telegramAlertsEnabled"])
        send_telegram_message(f"🔔 *Telegram Alerts* {'Enabled' if telegram_alerts_enabled else 'Disabled'} via Web UI")
    if "googleSheetLoggingEnabled" in data:
        google_sheet_logging_enabled = bool(data["googleSheetLoggingEnabled"])
        print(f"⚙️ Google Sheet Logging is: {'Enabled' if google_sheet_logging_enabled else 'Disabled'}")
    if "useSimulation" in data:
        use_simulation = bool(data["useSimulation"])
        print(f"⚙️ Simulation mode updated to: {use_simulation}")
        
    # ៤. បញ្ជាឧបករណ៍ដោយដៃ (Manual Mode) តាមរយៈ Web UI
    if not auto_mode:
        if "fan" in data:
            state = data["fan"]
            fan_state = "ON" if state in ["ON", True] else "OFF"
            send_telegram_message(f"💨 កង្ហារ៖ *{fan_state}* (តាមរយៈ Web UI)")
                
        if "pump" in data:
            state = data["pump"]
            target_state = "ON" if state in ["ON", True] else "OFF"
            change_pump_state(target_state, reason="តាមរយៈ Web UI")
                
    return jsonify({"success": True})

@web_app.route('/api/esp', methods=['POST'])
def handle_esp():
    """ទទួលទិន្នន័យពី ESP8266 និងបញ្ជូនទិន្នន័យបញ្ជាត្រលប់ទៅវិញ"""
    global air_temp, humidity, water_temp, water_level
    
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    # ទទួលទិន្នន័យសេនស័រ (លុះត្រាតែមិនមែនជា Simulation)
    if not use_simulation:
        air_temp = float(data.get("airTemp", air_temp))
        humidity = float(data.get("humidity", humidity))
        water_temp = float(data.get("waterTemp", water_temp))
        water_level = int(data.get("waterLevel", water_level))
        
        # ដំណើរការស្វ័យប្រវត្ត និងពិនិត្យការព្រមាន
        auto_control()
        check_alerts()
        
        # ផ្ញើទិន្នន័យទៅ Google Sheets (Asynchronous)
        send_to_google_sheet()
    
    return jsonify({
        "success": True,
        "fan": fan_state,
        "pump": pump_state
    })


def send_to_google_sheet_worker(is_sim):
    """កូដផ្ញើទិន្នន័យពិតប្រាកដដែលដំណើរការក្នុង Background Thread"""
    if not google_sheet_logging_enabled:
        return
        
    actual_water_height = max(0, TANK_HEIGHT - water_level)
    
    payload = {
        "airTemp": air_temp,
        "humidity": humidity,
        "waterTemp": water_temp,
        "waterLevel": actual_water_height,
        "sheetName": "DataSim" if is_sim else "DataLive"
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"✅ Google Sheet Response: {response.text}")
    except Exception as e:
        print(f"❌ Google Sheet upload error: {e}")


def send_to_google_sheet(is_sim=False):
    """ហៅមុខងារផ្ញើទៅ Google Sheet ដោយមិនធ្វើឱ្យគាំងកូដមេ (Asynchronous)"""
    global last_sheet_upload_time
    current_time = time.time()
    if current_time - last_sheet_upload_time >= UPLOAD_INTERVAL:
        last_sheet_upload_time = current_time
        thread = threading.Thread(target=send_to_google_sheet_worker, args=(is_sim,), daemon=True)
        thread.start()


def send_telegram_message(message):
    """ផ្ញើសារទៅកាន់ Telegram Chat"""
    if not telegram_alerts_enabled:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")


def change_pump_state(new_state, reason=None):
    """គ្រប់គ្រងការផ្លាស់ប្តូរស្ថានភាពម៉ូទ័រទឹក និងផ្ញើសារព្រមានទៅ Telegram"""
    global pump_state
    if pump_state != new_state:
        pump_state = new_state
        action = "បើក" if new_state == "ON" else "បិទ"
        msg = f"🔌 ម៉ូទ័រទឹក៖ *{action}*"
        if reason:
            msg += f" ({reason})"
        send_telegram_message(msg)


def check_alerts():
    """ពិនិត្យនិងផ្ញើសារព្រមាន"""
    global high_air_temp_alert_sent, high_water_temp_alert_sent, low_water_alert_sent, high_water_alert_sent
    global pump_state
    
    # សីតុណ្ហភាពខ្យល់
    if air_temp >= AIR_TEMP_THRESHOLD and not high_air_temp_alert_sent:
        send_telegram_message(f"⚠️ *សីតុណ្ហភាពខ្យល់ឡើងខ្ពស់៖* {air_temp:.2f}°C!")
        high_air_temp_alert_sent = True
    elif air_temp < (AIR_TEMP_THRESHOLD - 1.0):
        high_air_temp_alert_sent = False
        
    # សីតុណ្ហភាពទឹក
    if water_temp >= WATER_TEMP_THRESHOLD and not high_water_temp_alert_sent:
        send_telegram_message(f"⚠️ *សីតុណ្ហភាពទឹកឡើងខ្ពស់៖* {water_temp:.2f}°C!")
        high_water_temp_alert_sent = True
    elif water_temp < (WATER_TEMP_THRESHOLD - 1.0):
        high_water_temp_alert_sent = False
        
    # កម្ពស់ទឹកក្នុងអាង (ទឹកទាប) - កម្ពស់ទឹក < 2cm
    water_height = TANK_HEIGHT - water_level
    if water_height < 2 and not low_water_alert_sent:
        send_telegram_message(f"🚨 *កម្រិតទឹកក្នុងអាងទាបខ្លាំង (ក្រោម 2cm)!*")
        low_water_alert_sent = True
    elif water_height >= 4:
        low_water_alert_sent = False
        
    # កម្ពស់ទឹកក្នុងអាង (ទឹកពេញ) - កម្ពស់ទឹក >= 30cm
    if water_height >= 30 and not high_water_alert_sent:
        send_telegram_message(f"✅ *ទឹកពេញហើយ (30cm)!*")
        high_water_alert_sent = True
        change_pump_state("OFF", reason="ទឹកពេញ 30cm")
    elif water_height < 28:
        high_water_alert_sent = False


def auto_control():
    """បញ្ជាឧបករណ៍ស្វ័យប្រវត្តិ"""
    global fan_state, pump_state
    if not auto_mode:
        return
        
    # បញ្ជាកង្ហារ
    if air_temp >= AIR_TEMP_THRESHOLD:
        fan_state = "ON"
    else:
        fan_state = "OFF"
        
    # បញ្ជាម៉ូទ័រទឹក
    water_height = TANK_HEIGHT - water_level
    if water_height >= 30:
        change_pump_state("OFF", reason="ស្វ័យប្រវត្តិ - ទឹកពេញ 30cm")
    elif water_height < 2:
        change_pump_state("ON", reason="ស្វ័យប្រវត្តិ - ទឹកទាបក្រោម 2cm")


def handle_new_messages(updates):
    """គ្រប់គ្រងពាក្យបញ្ជាពី Telegram Bot"""
    global auto_mode, fan_state, pump_state
    for update in updates:
        message = update.get("message")
        if not message:
            continue
            
        chat_id = str(message.get("chat", {}).get("id"))
        if chat_id != CHAT_ID:
            continue
            
        # ពិនិត្យមើលសមាជិកថ្មីចូលរួមក្រុម (Check for new members joining the group)
        new_members = message.get("new_chat_members")
        if new_members:
            for member in new_members:
                # មិនបាច់ស្វាគមន៍ Bot ផ្សេងទៀត ឬខ្លួនឯងទេ (Skip other bots)
                if member.get("is_bot"):
                    continue
                first_name = member.get("first_name", "សមាជិកថ្មី")
                welcome = (
                    f"👋 *សួស្តី {first_name}!* ស្វាគមន៍មកកាន់ក្រុមរបស់ពួកយើង។\n\n"
                    "🌱 នេះជាបញ្ជីពាក្យបញ្ជារបស់ *NFT Hydroponic Bot* ដែលអ្នកអាចប្រើប្រាស់បាន៖\n\n"
                    "📋 *ពាក្យបញ្ជាដែលមាន៖*\n"
                    "🔷 /status : ពិនិត្យមើលទិន្នន័យទូទៅ (សាធារណៈ)\n"
                    "🔷 /auto : បើកមុខងារស្វ័យប្រវត្ត (ការពារ)\n"
                    "🔷 /manual : បើកមុខងារបញ្ជាដោយដៃ (ការពារ)\n"
                    "🔷 /fanon : បើកកង្ហារ (ការពារ)\n"
                    "🔷 /fanoff : បិទកង្ហារ (ការពារ)\n"
                    "🔷 /pumpon : បើកម៉ូទ័រទឹក (ការពារ)\n"
                    "🔷 /pumpoff : បិទម៉ូទ័រទឹក (ការពារ)\n"
                )
                send_telegram_message(welcome)
            continue
            
        text = message.get("text", "")
        # ដកឈ្មោះ Bot ចេញ ប្រសិនបើរត់ក្នុង Group (ឧទាហរណ៍៖ "/status@agri_hydro_bot" -> "/status")
        if "@" in text:
            text = text.split("@")[0]
            
        from_name = message.get("from", {}).get("first_name", "User")
        user_id = str(message.get("from", {}).get("id", ""))
        
        # បញ្ជីពាក្យបញ្ជាដែលត្រូវការពារ (ទាមទារសិទ្ធិជាម្ចាស់)
        restricted_commands = ["/auto", "/manual", "/fanon", "/fanoff", "/pumpon", "/pumpoff"]
        
        if text in restricted_commands:
            # ពិនិត្យសិទ្ធិអ្នកបញ្ជា (មានតែម្ចាស់ប្រព័ន្ធទើបអាចបញ្ជាបាន)
            if OWNER_ID and OWNER_ID != "YOUR_TELEGRAM_USER_ID" and user_id != OWNER_ID:
                send_telegram_message(f"❌ គ្មានសិទ្ធិបញ្ជាឧបករណ៍ឡើយ! គណនីរបស់អ្នកមាន ID: `{user_id}`។")
                continue
        
        if text in ["/start", "/help"]:
            welcome = (
                f"🌱 ស្វាគមន៍មកកាន់ *NFT Hydroponic Bot*, {from_name}.\n\n"
                "📋 *ពាក្យបញ្ជាដែលមាន៖*\n"
                "🔷 /status : ពិនិត្យមើលទិន្នន័យទូទៅ (សាធារណៈ)\n"
                "🔷 /auto : បើកមុខងារស្វ័យប្រវត្ត (ការពារ)\n"
                "🔷 /manual : បើកមុខងារបញ្ជាដោយដៃ (ការពារ)\n"
                "🔷 /fanon : បើកកង្ហារ (ការពារ)\n"
                "🔷 /fanoff : បិទកង្ហារ (ការពារ)\n"
                "🔷 /pumpon : បើកម៉ូទ័រទឹក (ការពារ)\n"
                "🔷 /pumpoff : បិទម៉ូទ័រទឹក (ការពារ)\n"
            )
            send_telegram_message(welcome)
            
        elif text == "/status":
            fan_status = "🟢 ON" if fan_state == "ON" else "🔴 OFF"
            pump_status = "🟢 ON" if pump_state == "ON" else "🔴 OFF"
            
            msg = (
                "📊 *របាយការណ៍បច្ចុប្បន្ន៖*\n"
                f"🌡️ សីតុណ្ហភាពខ្យល់៖ {air_temp:.2f} °C\n"
                f"💧 សំណើមខ្យល់៖ {humidity:.2f} %\n"
                f"🧪 សីតុណ្ហភាពទឹក៖ {water_temp:.2f} °C\n"
                f"📏 កម្ពស់ទឹក៖ {water_level} cm\n"
                f"🤖 របៀបដំណើរការ៖ {'⚙️ Auto' if auto_mode else '🕹️ Manual'}\n"
                f"💨 កង្ហារ៖ {fan_status}\n"
                f"🔌 ម៉ូទ័រ៖ {pump_status}\n"
            )
            send_telegram_message(msg)
            
        elif text == "/auto":
            auto_mode = True
            send_telegram_message("🔄 *Auto Mode* Activated")
            
        elif text == "/manual":
            auto_mode = False
            send_telegram_message("🕹️ *Manual Mode* Activated")
            
        elif text == "/fanon":
            if not auto_mode:
                fan_state = "ON"
                send_telegram_message("💨 កង្ហារ៖ *បើក*")
            else:
                send_telegram_message("⚠️ ចុច /manual មុនបញ្ជា!")
                
        elif text == "/fanoff":
            if not auto_mode:
                fan_state = "OFF"
                send_telegram_message("💨 កង្ហារ៖ *បិទ*")
            else:
                send_telegram_message("⚠️ ចុច /manual មុនបញ្ជា!")
                
        elif text == "/pumpon":
            if not auto_mode:
                change_pump_state("ON", reason=f"បញ្ជាដោយ {from_name}")
            else:
                send_telegram_message("⚠️ ចុច /manual មុនបញ្ជា!")
                
        elif text == "/pumpoff":
            if not auto_mode:
                change_pump_state("OFF", reason=f"បញ្ជាដោយ {from_name}")
            else:
                send_telegram_message("⚠️ ចុច /manual មុនបញ្ជា!")


def poll_telegram():
    """អានពាក្យបញ្ជាពី Telegram Bot"""
    global last_update_id
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 2}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            result = response.json().get("result", [])
            if result:
                last_update_id = result[-1]["update_id"]
                handle_new_messages(result)
    except Exception as e:
        print(f"⚠️ Telegram Polling Error: {e}")


def telegram_polling_worker():
    """រត់ Telegram Polling ក្នុង Background Thread"""
    print("🤖 Telegram polling thread started.")
    while True:
        poll_telegram()
        time.sleep(1)


# បើកដំណើរការ Telegram Polling នៅក្នុង Background Thread
telegram_thread = threading.Thread(target=telegram_polling_worker, daemon=True)
telegram_thread.start()

# សម្រាប់ឱ្យ Render ដំណើរការ Flask
# Render នឹងហៅ 'app:web_app' តាមរយៈ Gunicorn
# ដូច្នេះ Flask Web Server នឹងដំណើរការពីទីនេះ

if __name__ == "__main__":
    # បើកដំណើរការ Flask Web Server សម្រាប់ការតេស្តក្នុងកុំព្យូទ័រផ្ទាល់ខ្លួន (Local)
    print("🌐 Starting Web Server on Port 5000 locally...")
    try:
        web_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Web Server execution error: {e}")
