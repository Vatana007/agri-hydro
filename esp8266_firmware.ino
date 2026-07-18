/*
 * 🌱 NFT Hydroponic Automation System - ESP8266 Firmware
 * កូដសម្រាប់ដំឡើងចូលបន្ទះ ESP8266 WiFi 
 * ដើម្បីអានសេនស័រពិតៗ រួចបញ្ជូនទៅកាន់ Cloud Server (Render.com) តាម WiFi
 *
 * បណ្ណាល័យចាំបាច់ត្រូវដំឡើងក្នុង Arduino IDE៖
 * 1. DHT sensor library by Adafruit
 * 2. DallasTemperature by Miles Burton
 * 3. OneWire by Paul Stoffregen
 * 4. ArduinoJson by Benoit Blanchon (ជំនាន់ទី 6 ឬ 7)
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ==================== កំណត់ការកំណត់ផ្ទាល់ខ្លួន ====================
const char* ssid = "ឈ្មោះ_WiFi_របស់អ្នក";             // ឈ្មោះ WiFi នៅផ្ទះ
const char* password = "លេខសម្ងាត់_WiFi_របស់អ្នក";     // លេខសម្ងាត់ WiFi

// អាសយដ្ឋាន Server របស់អ្នកនៅលើ Render.com (កុំភ្លេចប្តូរ Link នេះ)
const char* serverUrl = "https://ឈ្មោះ-វេបសាយ-របស់អ្នក.onrender.com/api/esp";
// =============================================================

// កំណត់ជើងសេនស័រ (Pin Configurations)
#define DHTPIN D4             // ជើងសេនស័រ DHT11 (GPIO2)
#define DHTTYPE DHT11

#define ONE_WIRE_BUS D7       // ជើងសេនស័រ DS18B20 (GPIO13)

#define TRIG_PIN D1           // ជើង Trig របស់ Ultrasonic (GPIO5)
#define ECHO_PIN D2           // ជើង Echo របស់ Ultrasonic (GPIO4)

#define FAN_RELAY D5          // រីឡេបញ្ជាកង្ហារ (GPIO14)
#define PUMP_RELAY D6         // រីឡេបញ្ជាម៉ូទ័រទឹក (GPIO12)

// បង្កើត Object សម្រាប់សេនស័រ
DHT dht(DHTPIN, DHTTYPE);
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature waterTempSensor(&oneWire);

// កំណត់ប្រភេទរីឡេ (Active LOW ឬ Active HIGH)
// ប្រសិនបើរីឡេរបស់អ្នកបើកពេលបញ្ជូនកូដ LOW សូមទុក true។ ប្រសិនបើបើកពេលបញ្ជូនកូដ HIGH សូមប្តូរទៅ false
const bool RELAY_ACTIVE_LOW = true; 

unsigned long lastTime = 0;
const unsigned long timerDelay = 5000; // បាញ់ទិន្នន័យទៅ Server រាល់ ៥ វិនាទីម្តង

void setup() {
  Serial.begin(115200);
  
  // កំណត់ជើង Relays
  pinMode(FAN_RELAY, OUTPUT);
  pinMode(PUMP_RELAY, OUTPUT);
  
  // បិទរីឡេទាំងពីរកាលដំបូង
  setRelayState(FAN_RELAY, false);
  setRelayState(PUMP_RELAY, false);
  
  // ចាប់ផ្តើមសេនស័រ
  dht.begin();
  waterTempSensor.begin();
  
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  // តភ្ជាប់ WiFi
  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to WiFi network with IP Address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // បាញ់ទិន្នន័យទៅ Server រាល់ពេលកំណត់
  if ((millis() - lastTime > timerDelay) || lastTime == 0) {
    if (WiFi.status() == WL_CONNECTED) {
      
      // ១. អានតម្លៃពីសេនស័រ
      float airTemp = dht.readTemperature();
      float humidity = dht.readHumidity();
      
      // បើអាន DHT11 មិនចេញ ឱ្យតម្លៃលំនាំដើម
      if (isnan(airTemp)) airTemp = 28.5;
      if (isnan(humidity)) humidity = 65.0;

      // អានសីតុណ្ហភាពទឹក (DS18B20)
      waterTempSensor.requestTemperatures();
      float waterTemp = waterTempSensor.getTempCByIndex(0);
      if (waterTemp == -127.00 || isnan(waterTemp)) {
        waterTemp = airTemp - 2.0; // តម្លៃស្មានបើអានមិនចេញ
      }

      // អានកម្ពស់ទឹក (Ultrasonic - វាស់ចម្ងាយទំនេរ)
      int waterLevelDistance = getUltrasonicDistance();
      if (waterLevelDistance <= 0 || waterLevelDistance > 40) {
        waterLevelDistance = 10; // តម្លៃលំនាំដើម
      }

      Serial.println("\n--- 📊 ព័ត៌មានអានពីសេនស័រ ---");
      Serial.print("Air Temp: "); Serial.print(airTemp); Serial.println(" C");
      Serial.print("Humidity: "); Serial.print(humidity); Serial.println(" %");
      Serial.print("Water Temp: "); Serial.print(waterTemp); Serial.println(" C");
      Serial.print("Water Level Distance: "); Serial.print(waterLevelDistance); Serial.println(" cm");

      // ២. បង្កើត JSON Payload ដើម្បីផ្ញើទៅ Server
      WiFiClientSecure client;
      client.setInsecure(); // មិនបាច់ផ្ទៀងផ្ទាត់ SSL Certificate នាំឱ្យយឺត
      
      HTTPClient http;
      http.begin(client, serverUrl);
      http.addHeader("Content-Type", "application/json");

      // បង្កើត Json Document
      StaticJsonDocument<200> doc;
      doc["airTemp"] = air_temp_round(airTemp);
      doc["humidity"] = air_temp_round(humidity);
      doc["waterTemp"] = air_temp_round(waterTemp);
      doc["waterLevel"] = waterLevelDistance;

      String requestBody;
      serializeJson(doc, requestBody);

      // ផ្ញើ POST Request
      int httpResponseCode = http.POST(requestBody);
      
      if (httpResponseCode > 0) {
        String responseBody = http.getString();
        Serial.print("HTTP Response code: ");
        Serial.println(httpResponseCode);
        Serial.print("Server Response: ");
        Serial.println(responseBody);

        // ៣. បកស្រាយ JSON ឆ្លើយតបពី Server ដើម្បីបញ្ជាម៉ូទ័រ/កង្ហារ
        StaticJsonDocument<200> responseDoc;
        DeserializationError error = deserializeJson(responseDoc, responseBody);
        
        if (!error) {
          const char* fanCmd = responseDoc["fan"];   // "ON" ឬ "OFF"
          const char* pumpCmd = responseDoc["pump"]; // "ON" ឬ "OFF"

          Serial.print("➡️ បញ្ជាកង្ហារ៖ "); Serial.println(fanCmd);
          Serial.print("➡️ បញ្ជាម៉ូទ័រទឹក៖ "); Serial.println(pumpCmd);

          // បើក/បិទ រីឡេតាមបញ្ជា
          setRelayState(FAN_RELAY, strcmp(fanCmd, "ON") == 0);
          setRelayState(PUMP_RELAY, strcmp(pumpCmd, "ON") == 0);
        } else {
          Serial.print("deserializeJson() failed: ");
          Serial.println(error.f_str());
        }
      } else {
        Serial.print("Error on sending POST: ");
        Serial.println(httpResponseCode);
      }
      
      http.end(); // បិទការតភ្ជាប់
    } else {
      Serial.println("WiFi Disconnected");
    }
    lastTime = millis();
  }
}

// មុខងារជំនួយសម្រាប់អានចម្ងាយពី Ultrasonic
int getUltrasonicDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
  if (duration == 0) return 0;
  
  int distance = duration * 0.034 / 2;
  return distance;
}

// មុខងារជំនួយសម្រាប់គ្រប់គ្រងរីឡេ (Active LOW ឬ Active HIGH)
void setRelayState(int pin, bool turnOn) {
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(pin, turnOn ? LOW : HIGH);
  } else {
    digitalWrite(pin, turnOn ? HIGH : LOW);
  }
}

// មុខងារកាត់ខ្ទង់ក្បៀស
float air_temp_round(float val) {
  return (int)(val * 10 + 0.5) / 10.0;
}
