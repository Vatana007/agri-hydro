/**
 * 🌐 Google Apps Script Backend for NFT Hydroponics IoT System (Optimized Version)
 * 
 * របៀបប្រើប្រាស់៖
 * ១. ចូលទៅ Extensions -> Apps Script
 * ២. លុបកូដចាស់ចោលទាំងអស់ រួចចម្លងកូដខាងក្រោមនេះទៅដាក់ជំនួស
 * ៣. ចុច Deploy -> New deployment -> Web app -> Deploy ឡើងវិញ
 */

function doPost(e) {
  try {
    // ទទួលបានទិន្នន័យ JSON ដែលផ្ញើមកពី Python app.py
    var jsonString = e.postData.contents;
    var data = JSON.parse(jsonString);

    // បើក Google Sheet សកម្មបច្ចុប្បន្ន (មិនចាំបាច់ប្រើ ID)
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    // ជ្រើសរើសសន្លឹកបៀរតាមឈ្មោះដែលផ្ញើមក ឬប្រើ "DataLive" ជាលំនាំដើម
    var sheetName = data.sheetName || "DataLive";
    var sheet = ss.getSheetByName(sheetName);
    
    // បើសន្លឹកបៀរនោះមិនទាន់មាន គឺវានឹងបង្កើតថ្មីមួយដោយស្វ័យប្រវត្ត
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
      // បញ្ចូលក្បាលតារាង (Header Columns)
      sheet.appendRow(["កាលបរិច្ឆេទ (Timestamp)", "សីតុណ្ហភាពខ្យល់ (Air Temp)", "សំណើមខ្យល់ (Humidity)", "សីតុណ្ហភាពទឹក (Water Temp)", "កម្ពស់ទឹក (Water Level)"]);
    }

    // បង្កើតទិន្នន័យពេលវេលាបច្ចុប្បន្ន (Timestamp)
    var timestamp = new Date();

    // ទាញយកតម្លៃចេញពី JSON Payload
    var airTemp = data.airTemp;
    var humidity = data.humidity;
    var waterTemp = data.waterTemp;
    var waterLevel = data.waterLevel;

    // បញ្ចូលទិន្នន័យទាំងអស់ទៅក្នុងជួរដេកថ្មី (Row ថ្មី)
    sheet.appendRow([timestamp, airTemp, humidity, waterTemp, waterLevel]);

    return ContentService.createTextOutput("✅ Data saved to " + sheetName + " successfully!")
      .setMimeType(ContentService.MimeType.TEXT);

  } catch (error) {
    return ContentService.createTextOutput("❌ Error: " + error.toString())
      .setMimeType(ContentService.MimeType.TEXT);
  }
}

// មុខងារ doGet សម្រាប់តេស្ត
function doGet(e) {
  return ContentService.createTextOutput("🌱 Web App for Hydroponic IoT (Tab: DataLive) is Online!")
    .setMimeType(ContentService.MimeType.TEXT);
}
