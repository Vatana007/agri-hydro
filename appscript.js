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

    // បើកសន្លឹកបៀរជាក់លាក់ឈ្មោះ "DataLive"
    var sheet = ss.getSheetByName("DataLive");
    if (!sheet) {
      sheet = ss.getActiveSheet();
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

    return ContentService.createTextOutput("✅ Data saved to DataLive successfully!")
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
