#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🌱 NFT Hydroponic Automation System
រត់បានទាំងលើ Raspberry Pi (សេនស័រពិត) និងលើ Windows PC (ការតេស្តសាកល្បង/Simulation)
អាប់ដេត៖ 
1. ញែក Telegram Polling ឱ្យរត់លើ Background Thread ដើម្បីកុំឱ្យស្ទះ (Block) Main Thread នាំឱ្យខូច Real-time
2. ផ្ញើកម្ពស់ទឹកពិតប្រាកដ (20 - water_level) ទៅ Google Sheet ដើម្បីឱ្យត្រូវគ្នានឹង Web UI ទាំងស្រុង
"""

import os
import time
import glob
import json
import random
import threading
import requests
from flask import Flask, jsonify, request

# ================== កំណត់តម្លៃទូទៅ (Configuration) ==================
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyUGmBiRx5rsVDoqlxBs99oBcN-QILD6LIuBlTo-J_ei1lkO19oaNsHWbTzfzNOuyfF/exec"

# Telegram Bot
BOT_TOKEN = "8683283536:AAGRIY4bn_6OybeVE4Qm2lo_M3FlfCTREGw"
CHAT_ID = "-5397107189"

# ដែនកំណត់សុវត្ថិភាពលំនាំដើម (Thresholds - អាចកែប្រែបានពី UI)
AIR_TEMP_THRESHOLD = 33.0     # សីតុណ្ហភាពខ្យល់ខ្ពស់បំផុត
WATER_TEMP_THRESHOLD = 35.0   # សីតុណ្ហភាពទឹកខ្ពស់បំផុត
WATER_LOW_THRESHOLD = 20      # កម្រិតចម្ងាយវាស់ពីសេនស័រទៅទឹក (កម្រិតទឹកទាប)

# ការកំណត់មុខងារផ្សេងៗ (អាចកែប្រែបានពី UI)
telegram_alerts_enabled = True
google_sheet_logging_enabled = True

# ប៉ារ៉ាម៉ែត្រកាលកំណត់ពេលវេលា
READ_INTERVAL = 2             # អានសេនស័ររាល់ ២ វិនាទីម្តង (Real-time)
UPLOAD_INTERVAL = 5          # ផ្ញើទៅ Google Sheet រាល់ ១៥ វិនាទីម្តង
# ===================================================================

# ពិនិត្យមើលថាតើឧបករណ៍មានបណ្ណាល័យ Raspberry Pi ដែរឬទេ
try:
    import RPi.GPIO as GPIO
    import adafruit_dht
    import board
    IS_SIMULATION = False
    print("🤖 Found Raspberry Pi libraries: Running in Real Hardware Mode")
except ImportError:
    IS_SIMULATION = True
    print("⚠️ No Raspberry Pi libraries found: Running in Simulation Mode")

# การកំណត់ជើង GPIO (លុះត្រាតែមិនមែនជា Simulation)
if not IS_SIMULATION:
    DHT_PIN = board.D4       # GPIO 4 (ជើងសេនស័រ DHT11)
    TRIG_PIN = 14            # GPIO 14 (ជើង Trig របស់ Ultrasonic)
    ECHO_PIN = 12            # GPIO 12 (ជើង Echo របស់ Ultrasonic)
    RELAY1 = 13              # GPIO 13 (រីឡេកង្ហារ - Active LOW)
    RELAY2 = 18              # GPIO 18 (រីឡេម៉ូទ័រទឹក - Active LOW)
else:
    # បង្កើតតម្លៃសិប្បនិម្មិតសម្រាប់ Simulation
    mock_relay_fan = "OFF"
    mock_relay_pump = "OFF"

# ស្ថានភាពបច្ចុប្បន្ន
air_temp = 28.5
humidity = 65.0
water_temp = 26.0
water_level = 10
auto_mode = True

# ស្ថានភាពនៃការផ្ញើសារព្រមាន
high_air_temp_alert_sent = False
high_water_temp_alert_sent = False
low_water_alert_sent = False
high_water_alert_sent = False

# អាយឌីសារចុងក្រោយដែលទទួលបានពី Telegram
last_update_id = 0

# ចាប់ផ្តើមសេនស័រ DHT (លុះត្រាតែមិនមែនជា Simulation)
dht_device = None
if not IS_SIMULATION:
    try:
        dht_device = adafruit_dht.DHT11(DHT_PIN)
    except Exception as e:
        print(f"❌ Failed to initialize DHT11: {e}")

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

@web_app.route('/api/status', methods=['GET'])
def get_status():
    """ផ្ញើទិន្នន័យសេនស័រ ស្ថានភាពឧបករណ៍ និងការកំណត់ទាំងអស់ទៅកាន់ Web UI"""
    if not IS_SIMULATION:
        fan_state = "ON" if GPIO.input(RELAY1) == GPIO.LOW else "OFF"
        pump_state = "ON" if GPIO.input(RELAY2) == GPIO.LOW else "OFF"
    else:
        fan_state = mock_relay_fan
        pump_state = mock_relay_pump
        
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
        "googleSheetLoggingEnabled": google_sheet_logging_enabled
    })

@web_app.route('/api/control', methods=['POST'])
def control_system():
    """ទទួលបញ្ជាពី Web UI សម្រាប់កែប្រែរាល់មុខងារទាំងអស់"""
    global auto_mode, mock_relay_fan, mock_relay_pump
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
        
    # ៣. កែប្រែកុងតាក់មុខងារ Alerts & Logging
    if "telegramAlertsEnabled" in data:
        telegram_alerts_enabled = bool(data["telegramAlertsEnabled"])
        send_telegram_message(f"🔔 *Telegram Alerts* {'Enabled' if telegram_alerts_enabled else 'Disabled'} via Web UI")
    if "googleSheetLoggingEnabled" in data:
        google_sheet_logging_enabled = bool(data["googleSheetLoggingEnabled"])
        print(f"⚙️ Google Sheet Logging is: {'Enabled' if google_sheet_logging_enabled else 'Disabled'}")
        
    # ៤. បញ្ជាឧបករណ៍ដោយដៃ (Manual Mode) តាមរយៈ Web UI
    if not auto_mode:
        if "fan" in data:
            state = data["fan"]
            if not IS_SIMULATION:
                if state in ["ON", True]:
                    GPIO.output(RELAY1, GPIO.LOW)
                else:
                    GPIO.output(RELAY1, GPIO.HIGH)
            else:
                mock_relay_fan = "ON" if state in ["ON", True] else "OFF"
            send_telegram_message(f"💨 កង្ហារ៖ *{state}* (តាមរយៈ Web UI)")
                
        if "pump" in data:
            state = data["pump"]
            if not IS_SIMULATION:
                if state in ["ON", True]:
                    GPIO.output(RELAY2, GPIO.LOW)
                else:
                    GPIO.output(RELAY2, GPIO.HIGH)
            else:
                mock_relay_pump = "ON" if state in ["ON", True] else "OFF"
            send_telegram_message(f"🔌 ម៉ូទ័រ៖ *{state}* (តាមរយៈ Web UI)")
                
    return jsonify({"success": True})


def setup_gpio():
    """កំណត់ជើងបញ្ជា GPIO ទាំងអស់ (សម្រាប់តែ Raspberry Pi)"""
    if IS_SIMULATION:
        print("[Simulation] Virtual GPIO setup complete.")
        return
        
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # កំណត់ជើង Ultrasonic
    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    
    # កំណត់ជើងរីឡេ (Active LOW) - កំណត់ដំបូងជា HIGH (បិទ)
    GPIO.setup(RELAY1, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(RELAY2, GPIO.OUT, initial=GPIO.HIGH)
    print("✅ GPIO setup complete!")


def get_water_level():
    """វាស់ចម្ងាយពីសេនស័រទៅផ្ទៃទឹក ( Ultrasonic )"""
    if IS_SIMULATION:
        return water_level
        
    try:
        GPIO.output(TRIG_PIN, GPIO.LOW)
        time.sleep(0.000002)
        GPIO.output(TRIG_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIG_PIN, GPIO.LOW)
        
        pulse_start = time.time()
        timeout_start = time.time()
        while GPIO.input(ECHO_PIN) == GPIO.LOW:
            pulse_start = time.time()
            if pulse_start - timeout_start > 0.05:
                return 999
                
        pulse_end = time.time()
        timeout_start = time.time()
        while GPIO.input(ECHO_PIN) == GPIO.HIGH:
            pulse_end = time.time()
            if pulse_end - timeout_start > 0.05:
                return 999
                
        duration = pulse_end - pulse_start
        distance = duration * 34300 / 2
        return int(distance)
    except Exception as e:
        print(f"❌ Error measuring water level: {e}")
        return 0


def read_water_temp():
    """អានសីតុណ្ហភាពទឹកពីសេនស័រ DS18B20 (1-Wire)"""
    if IS_SIMULATION:
        return water_temp
        
    try:
        base_dir = '/sys/bus/w1/devices/'
        device_folders = glob.glob(base_dir + '28-*')
        if not device_folders:
            return 0.0
            
        device_file = device_folders[0] + '/w1_slave'
        with open(device_file, 'r') as f:
            lines = f.readlines()
            
        if lines[0].strip().endswith('YES'):
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
                return round(temp_c, 2)
    except Exception as e:
        print(f"❌ Error reading DS18B20 water temperature: {e}")
    return 0.0


def read_sensors():
    """អានទិន្នន័យពីសេនស័រទាំងអស់"""
    global air_temp, humidity, water_temp, water_level
    
    if IS_SIMULATION:
        if mock_relay_fan == "ON":
            air_temp = max(25.0, air_temp - random.uniform(0.1, 0.4))
        else:
            air_temp = min(36.0, air_temp + random.uniform(0.1, 0.3))
            
        if mock_relay_pump == "ON":
            water_level = max(0, water_level - 1)
        else:
            water_level = min(20, water_level + 1)
            
        humidity = round(random.uniform(55.0, 75.0), 1)
        water_temp = round(air_temp - 2.0, 2)
        
        print("\n--- 📊 [Simulation] Sensor Data Mock ---")
        print(f"Air Temp: {air_temp:.2f}°C | Humidity: {humidity:.2f}%")
        print(f"Water Temp: {water_temp:.2f}°C | Water Level Distance: {water_level} cm")
        return

    # ករណីរត់លើ Raspberry Pi ពិតប្រាកដ
    if dht_device:
        try:
            air_temp = dht_device.temperature
            humidity = dht_device.humidity
            if air_temp is None: air_temp = 0.0
            if humidity is None: humidity = 0.0
        except RuntimeError as e:
            print(f"⚠️ DHT11 read failed: {e}")
        except Exception as e:
            print(f"❌ DHT11 error: {e}")
            
    water_temp = read_water_temp()
    water_level = get_water_level()
    
    print("\n--- 📊 Real Sensor Readings ---")
    print(f"Air Temp: {air_temp:.2f}°C | Humidity: {humidity:.2f}%")
    print(f"Water Temp: {water_temp:.2f}°C | Water Level Distance: {water_level} cm")


def send_to_google_sheet_worker():
    """កូដផ្ញើទិន្នន័យពិតប្រាកដដែលដំណើរការក្នុង Background Thread"""
    if not google_sheet_logging_enabled:
        print("🌐 [Background] Google Sheet logging is disabled.")
        return
        
    # គណនាកម្ពស់ទឹកពិតប្រាកដ (២០ ដកចម្ងាយទំនេរ) ដើម្បីផ្ញើទៅ Google Sheets ឱ្យត្រូវគ្នានឹង UI
    actual_water_height = max(0, 20 - water_level)
    
    payload = {
        "airTemp": air_temp,
        "humidity": humidity,
        "waterTemp": water_temp,
        "waterLevel": actual_water_height # បញ្ជូនកម្ពស់ទឹកពិតប្រាកដ
    }
    headers = {"Content-Type": "application/json"}
    print("🌐 [Background] Sending data to Google Sheet...")
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"✅ Google Sheet Response: {response.text}")
        else:
            print(f"❌ Failed to upload. Status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Google Sheet upload error (Timeout/Network): {e}")


def send_to_google_sheet():
    """ហៅមុខងារផ្ញើទៅ Google Sheet ដោយមិនធ្វើឱ្យគាំងកូដមេ (Asynchronous)"""
    thread = threading.Thread(target=send_to_google_sheet_worker, daemon=True)
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


def check_alerts():
    """ពិនិត្យនិងផ្ញើសារព្រមាន"""
    global high_air_temp_alert_sent, high_water_temp_alert_sent, low_water_alert_sent, high_water_alert_sent
    
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
        
    # កម្ពស់ទឹកក្នុងអាង (ទឹកទាប)
    if water_level >= WATER_LOW_THRESHOLD and not low_water_alert_sent:
        send_telegram_message(f"🚨 *កម្រិតទឹកក្នុងអាងទាបខ្លាំង!* {water_level} cm")
        low_water_alert_sent = True
    elif water_level < (WATER_LOW_THRESHOLD - 2):
        low_water_alert_sent = False
        
    # កម្ពស់ទឹកក្នុងអាង (ទឹកពេញ)
    if water_level <= 5 and not high_water_alert_sent:
        send_telegram_message(f"✅ *ទឹកពេញហើយ!* បិទម៉ូទ័រដើម្បីសុវត្ថិភាព។")
        high_water_alert_sent = True
        # បិទម៉ូទ័រទឹកភ្លាមៗ (ទោះជានៅក្នុង Auto ឬ Manual Mode ក៏ដោយ)
        global mock_relay_pump
        if not IS_SIMULATION:
            GPIO.output(RELAY2, GPIO.HIGH)
        else:
            mock_relay_pump = "OFF"
    elif water_level > 6:
        high_water_alert_sent = False


def auto_control():
    """បញ្ជាឧបករណ៍ស្វ័យប្រវត្តិ"""
    global mock_relay_fan, mock_relay_pump
    if not auto_mode:
        return
        
    # បញ្ជាកង្ហារ (Relay 1 - Active LOW)
    if air_temp >= AIR_TEMP_THRESHOLD:
        if not IS_SIMULATION:
            GPIO.output(RELAY1, GPIO.LOW)
        else:
            mock_relay_fan = "ON"
    else:
        if not IS_SIMULATION:
            GPIO.output(RELAY1, GPIO.HIGH)
        else:
            mock_relay_fan = "OFF"
        
    # បញ្ជាម៉ូទ័រទឹក (Relay 2 - Active LOW)
    # បើទឹកពេញ (ចម្ងាយវាស់បាន <= 5cm) -> បិទម៉ូទ័រទឹក (HIGH / OFF) ស្វ័យប្រវត្តិ
    if water_level <= 5:
        if not IS_SIMULATION:
            GPIO.output(RELAY2, GPIO.HIGH)
        else:
            mock_relay_pump = "OFF"
    # បើទឹកទាប (ចម្ងាយវាស់បាន >= WATER_LOW_THRESHOLD) -> បើកម៉ូទ័រទឹក (LOW / ON) ដើម្បីបញ្ចូលទឹក
    elif water_level >= WATER_LOW_THRESHOLD:
        if not IS_SIMULATION:
            GPIO.output(RELAY2, GPIO.LOW)
        else:
            mock_relay_pump = "ON"


def handle_new_messages(updates):
    """គ្រប់គ្រងពាក្យបញ្ជាពី Telegram Bot"""
    global auto_mode, mock_relay_fan, mock_relay_pump
    for update in updates:
        message = update.get("message")
        if not message:
            continue
            
        chat_id = str(message.get("chat", {}).get("id"))
        if chat_id != CHAT_ID:
            continue
            
        text = message.get("text", "")
        from_name = message.get("from", {}).get("first_name", "User")
        
        if text in ["/start", "/help"]:
            welcome = (
                f"🌱 ស្វាគមន៍មកកាន់ *NFT Hydroponic Bot*, {from_name}.\n\n"
                "📋 *ពាក្យបញ្ជាដែលមាន៖*\n"
                "🔷 /status : ពិនិត្យមើលទិន្នន័យទូទៅ\n"
                "🔷 /auto : បើកមុខងារស្វ័យប្រវត្ត (Auto)\n"
                "🔷 /manual : បើកមុខងារបញ្ជាដោយដៃ (Manual)\n"
                "🔷 /fanon : បើកកង្ហារ\n"
                "🔷 /fanoff : បិទកង្ហារ\n"
                "🔷 /pumpon : បើកម៉ូទ័រទឹក\n"
                "🔷 /pumpoff : បិទម៉ូទ័រទឹក\n"
            )
            send_telegram_message(welcome)
            
        elif text == "/status":
            if not IS_SIMULATION:
                fan_status = "🟢 ON" if GPIO.input(RELAY1) == GPIO.LOW else "🔴 OFF"
                pump_status = "🟢 ON" if GPIO.input(RELAY2) == GPIO.LOW else "🔴 OFF"
            else:
                fan_status = "🟢 ON" if mock_relay_fan == "ON" else "🔴 OFF"
                pump_status = "🟢 ON" if mock_relay_pump == "ON" else "🔴 OFF"
            
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
                if not IS_SIMULATION:
                    GPIO.output(RELAY1, GPIO.LOW)
                else:
                    mock_relay_fan = "ON"
                send_telegram_message("💨 កង្ហារ៖ *បើក*")
            else:
                send_telegram_message("⚠️ ចុច /manual មុនបញ្ជា!")
                
        elif text == "/fanoff":
            if not auto_mode:
                if not IS_SIMULATION:
                    GPIO.output(RELAY1, GPIO.HIGH)
                else:
                    mock_relay_fan = "OFF"
                send_telegram_message("💨 កង្ហារ៖ *បិទ*")
            else:
                send_telegram_message("⚠️ ចុច /manual មុនបញ្ជា!")
                
        elif text == "/pumpon":
            if not auto_mode:
                if not IS_SIMULATION:
                    GPIO.output(RELAY2, GPIO.LOW)
                else:
                    mock_relay_pump = "ON"
                send_telegram_message("🔌 ម៉ូទ័រ៖ *បើក*")
            else:
                send_telegram_message("⚠️ ចុច /manual មុនបញ្ជា!")
                
        elif text == "/pumpoff":
            if not auto_mode:
                if not IS_SIMULATION:
                    GPIO.output(RELAY2, GPIO.HIGH)
                else:
                    mock_relay_pump = "OFF"
                send_telegram_message("🔌 ម៉ូទ័រ៖ *បិទ*")
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
    """រត់ Telegram Polling ក្នុង Background Thread ដើម្បីកុំឱ្យរំខាន Main Thread"""
    print("🤖 Telegram polling thread started.")
    while True:
        poll_telegram()
        time.sleep(1)


def run_web_server():
    """បើកដំណើរការ Flask Web Server (រត់លើ Port 5000)"""
    print("🌐 Starting Web Server on Port 5000...")
    try:
        web_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Web Server execution error: {e}")


def main():
    setup_gpio()
    
    # បើកដំណើរការ Web Server
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # បើកដំណើរការ Telegram Polling លើ Thread ផ្សេងមួយទៀត
    telegram_thread = threading.Thread(target=telegram_polling_worker, daemon=True)
    telegram_thread.start()
    
    mode_text = "Simulation Mode" if IS_SIMULATION else "Real Hardware Mode"
    send_telegram_message(f"🌱 *ប្រព័ន្ធ Hydroponic IoT Online ក្នុងរបៀប {mode_text}!*")
    
    previous_millis_sensors = time.time()
    previous_millis_sheets = time.time()
    
    print("🚀 Main application running...")
    try:
        while True:
            try:
                current_time = time.time()
                
                # ១. អានសេនស័រ និងបញ្ជាស្វ័យប្រវត្តរាល់ ២ វិនាទីម្តង (Real-time)
                if current_time - previous_millis_sensors >= READ_INTERVAL:
                    previous_millis_sensors = current_time
                    read_sensors()
                    check_alerts()
                    auto_control()
                
                # ២. ផ្ញើទិន្នន័យកត់ត្រាទៅ Google Sheet រាល់ ១៥ វិនាទីម្តង
                if current_time - previous_millis_sheets >= UPLOAD_INTERVAL:
                    previous_millis_sheets = current_time
                    send_to_google_sheet()
            except Exception as loop_err:
                print(f"⚠️ Error in main loop iteration: {loop_err}")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n👋 Application stopped.")
    finally:
        if not IS_SIMULATION:
            GPIO.cleanup()
            if dht_device:
                dht_device.exit()


if __name__ == "__main__":
    main()
