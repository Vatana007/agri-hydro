# 🌱 NFT Hydroponics IoT System (Raspberry Pi & Python)

ប្រព័ន្ធកសិកម្មវៃឆ្លាតសម្រាប់ដាំដំណាំអុីដ្រូផូនិច (NFT Hydroponics) ដែលដំណើរការលើបន្ទះ **Raspberry Pi** សរសេរជាភាសា **Python**។ ប្រព័ន្ធនេះវាស់ស្ទង់ស្ថានភាពបរិស្ថាន រក្សាទុកទិន្នន័យទៅក្នុង Google Sheets ស្វ័យប្រវត្តិ និងអនុញ្ញាតឱ្យបញ្ជា ឬទទួលបានសារព្រមានតាមរយៈ Telegram Bot។

---

## 📊 គ្រឿងរឹង និងសេនស័រ (Hardware Components)

1. **Raspberry Pi:** បន្ទះកុំព្យូទ័រមេបញ្ជាការកូដ Python
2. **DHT11:** សេនស័រវាស់សីតុណ្ហភាពខ្យល់ និងសំណើម
3. **DS18B20:** សេនស័រវាស់សីតុណ្ហភាពទឹក (1-Wire Waterproof)
4. **Ultrasonic (HC-SR04):** សេនស័រវាស់ចម្ងាយផ្ទៃទឹកក្នុងធុង (កម្ពស់ទឹក)
5. **Relay 1:** បញ្ជាបើក/បិទ កង្ហារ (Fan)
6. **Relay 2:** បញ្ជាបើក/បិទ ម៉ូទ័រទឹក (Water Pump)

---

## 🔌 ការភ្ជាប់ខ្សែឧបករណ៍ (GPIO Pinout)

សូមភ្ជាប់ខ្សែទៅនឹងបន្ទះ Raspberry Pi តាមការកំណត់ជើង GPIO (BCM Numbering) ដូចខាងក្រោម៖

| ឧបករណ៍ (Device) | ជើងសេនស័រ (Sensor Pin) | ជើង Raspberry Pi (GPIO Pin BCM) |
| :--- | :--- | :--- |
| **DHT11** | Data Pin | `GPIO 4` (board.D4) |
| **Ultrasonic** | Trig Pin | `GPIO 14` |
| **Ultrasonic** | Echo Pin | `GPIO 12` |
| **Relay 1 (Fan)** | IN Pin | `GPIO 13` |
| **Relay 2 (Pump)** | IN Pin | `GPIO 15` |
| **DS18B20** | Data Pin | `GPIO 4` (ជើងលំនាំដើមរបស់ 1-Wire លើ RPi) |

---

## 🛠️ ការតំឡើង និងដំណើរការ (Setup & Installation)

### ១. បើកដំណើរការ 1-Wire សម្រាប់សេនស័រទឹក DS18B20
នៅលើ Raspberry Pi របស់អ្នក សូមបើក Terminal រួចវាយ៖
```bash
sudo raspi-config
```
* ជ្រើសរើសយក **Interface Options** -> **1-Wire** -> ជ្រើសរើសយក **Yes** ដើម្បី Enable។
* រួចចុច **Finish** ហើយធ្វើការ **Reboot** ម៉ាស៊ីនឡើងវិញ។

### ២. តំឡើងបណ្ណាល័យ Python (Libraries)
រត់កូដខាងក្រោមដើម្បីដំឡើងបណ្ណាល័យដែលត្រូវការ៖
```bash
pip install requests RPi.GPIO adafruit-circuitpython-dht
```

### ៣. រៀបចំ Google Sheet Backend
1. បង្កើត Google Sheet ថ្មីមួយ និងដាក់ឈ្មោះក្បាលតារាងនៅជួរដេកទី ១៖
   `Timestamp` | `Air Temperature` | `Humidity` | `Water Temperature` | `Water Level`
2. ចូលទៅ **Extensions** -> **Apps Script** រួចចម្លងកូដនៅក្នុងឯកសារ [appscript.js](appscript.js) ទៅដាក់ រួច Save។
3. ចុច **Deploy** -> **New deployment** -> ជ្រើសរើសប្រភេទ **Web app**។
4. កំណត់ **Execute as** ទៅជា **Me** និង **Who has access** ទៅជា **Anyone** រួចចុច **Deploy** និងផ្តល់សិទ្ធិ (Authorize)។
5. ចម្លងយក **Web app URL** ទៅជំនួសត្រង់អថេរ `GOOGLE_SCRIPT_URL` ក្នុងឯកសារ [app.py](app.py)។

### ៤. កំណត់តម្លៃ Telegram Bot
* បង្កើត Telegram Bot តាមរយៈ BotFather ដើម្បីទទួលបាន `BOT_TOKEN`។
* បង្កើត Group រួចទាញយក `CHAT_ID` នៃគ្រុបនោះ។
* យកទៅជំនួសក្នុងកូដ [app.py](app.py) ត្រង់អថេរ `BOT_TOKEN` និង `CHAT_ID`។

### ៥. បើកដំណើរការកម្មវិធី
រត់កម្មវិធីដោយប្រើបញ្ជា៖
```bash
python app.py
```

ចង់ឱ្យកម្មវិធីរត់ក្នុង Background ជាប់រហូត៖
```bash
nohup python app.py > hydroponics.log 2>&1 &
```

---

## 🤖 បញ្ជីពាក្យបញ្ជា Telegram (Telegram Commands)

* `/status` : ពិនិត្យទិន្នន័យសេនស័រ និងស្ថានភាពឧបករណ៍បច្ចុប្បន្ន
* `/auto` : បើកដំណើរការរបៀបស្វ័យប្រវត្តិ (Auto Mode)
* `/manual` : បើកដំណើរការរបៀបបញ្ជាដោយដៃ (Manual Mode)
* `/fanon` : បើកកង្ហារ (ដំណើរការតែក្នុង Manual Mode ឡើយ)
* `/fanoff` : បិទកង្ហារ
* `/pumpon` : បើកម៉ូទ័រទឹក
* `/pumpoff` : បិទម៉ូទ័រទឹក
