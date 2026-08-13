#include <Arduino.h>
#include <esp_camera.h>
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <ESPAsyncWebServer.h>

// --- PIN TANIMLAMALARI ---
const int sensorPin = 13;
const int motor1 = 12;    // L298N IN1
const int motor2 = 15;    // L298N IN2
const int buyukLed = 14;  // Üst Aydınlatma
const int kirmiziLed = 2; // İşlem Yapılıyor LED
const int yesilLed = 4;   // Sistem Aktif/Yolunda LED

const char *ssid = "*************";
const char *password = "*************";
const char *serverIP = "**.**.**.**";
const char *predictUrl = "http://**.**.**.**:5000/foto";
const char *modelicintetikleme = "http://**.**.**.**:5000/sensor_verileri";
AsyncWebServer server(80);

bool sistemCalisiyor = false;
bool analizYapiliyor = false;
String sensorDurumu = "0";
bool currentCom = false;
// Zamanlama kontrolleri için global değişkenler
unsigned long sensorBeklemeZamani = 0;
unsigned long analizBeklemeZamani = 0;
int analizAsamasi = 0; // 0: Beklemede, 1: Motor durdu 6sn bekleme süreci, 2: Sinyal gönderildi 3sn analiz süreci
bool is_processing = false;

void motoruDurdur()
{
  digitalWrite(motor1, LOW);
  digitalWrite(motor2, LOW);
}

void motoruCalistir()
{
  digitalWrite(motor1, HIGH);
  digitalWrite(motor2, LOW);
}

void sistemiDurdur()
{
  sistemCalisiyor = false;
  analizYapiliyor = false;
  analizAsamasi = 0;
  motoruDurdur();
  digitalWrite(kirmiziLed, LOW);
  digitalWrite(yesilLed, LOW);
  digitalWrite(buyukLed, LOW);
}

// AI THINKER Pin Ayarları
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

void setup()
{
  Serial.begin(115200);

  // Pin Modları
  pinMode(sensorPin, INPUT_PULLUP);
  pinMode(motor1, OUTPUT);
  pinMode(motor2, OUTPUT);
  pinMode(buyukLed, OUTPUT);
  pinMode(kirmiziLed, OUTPUT);
  pinMode(yesilLed, OUTPUT);

  pinMode(4, OUTPUT);
  digitalWrite(4, LOW);

  // Başlangıç Durumu
  sistemiDurdur();

  // Kamera Ayarları
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 5000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  esp_err_t camera_err = esp_camera_init(&config);
  if (camera_err != ESP_OK)
  {
    Serial.printf("Kamera Hatası: 0x%x", camera_err);
    return;
  }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Baglandi!");
  Serial.print("ESP32 IP Adresi: ");
  Serial.println(WiFi.localIP()); //

  server.on("/sensor_verileri", HTTP_GET, [](AsyncWebServerRequest *request)
            { request->send(200, "text/plain", sensorDurumu); });
  server.on("/foto", HTTP_GET, [](AsyncWebServerRequest *request)
            {
    camera_fb_t * fb = esp_camera_fb_get();
    if(!fb) {
      request->send(500, "text/plain", "Kamera Goruntusu Alinamadi");
      return;
    }
  AsyncWebServerResponse *response = request->beginResponse(200, "image/jpeg", fb->buf, fb->len);
  request->send(response);
  esp_camera_fb_return(fb);
  Serial.println("Foto sunucuya gonderildi!"); });

  // 3. CustomTkinter "Sistemi Başlat" dediğinde (Hem büyük hem küçük harf uyumlu)
  auto startHandler = [](AsyncWebServerRequest *request)
  {
    currentCom = true; // Döngüyü tetikle
    request->send(200, "text/plain", "Bant Baslatma Komutu Alindi");
  };
  server.on("/START", HTTP_GET, startHandler);
  server.on("/start", HTTP_GET, startHandler);

  // 4. CustomTkinter "Sistemi Durdur" dediğinde
  auto stopHandler = [](AsyncWebServerRequest *request)
  {
    currentCom = false; // Döngüyü kapat
    request->send(200, "text/plain", "Bant Durdurma Komutu Alindi");
  };
  server.on("/STOP", HTTP_GET, stopHandler);
  server.on("/stop", HTTP_GET, stopHandler);
  server.begin();
}

void loop()
{

  // Arayüz "START" (true) dediğinde ve sistem henüz çalışmıyorsa:
  if (currentCom == true && !sistemCalisiyor && !analizYapiliyor)
  {
    Serial.println("==> Arayüz emri algılandı: Motor çalıştırılıyor...");
    sistemCalisiyor = true;
    digitalWrite(yesilLed, HIGH);
    digitalWrite(kirmiziLed, LOW);
    digitalWrite(buyukLed, LOW);
    motoruCalistir();

    delay(200); // Motorun kalkış anında sensörü yanlış tetiklememesi için küçük bir nefes

    sensor_t *s = esp_camera_sensor_get();
    if (s)
    {
      s->set_aec_value(s, 0);
    }
    /*pinMode(4, OUTPUT);
    digitalWrite(4, LOW);
    Serial.println("Kamera kütüphanesi sonrası flaş zorla söndürüldü.");*/
  }

  // Arayüz "STOP" (false) dediğinde VEYA sistem açıkken STOP emri geldiyse:
  else if (currentCom == false && (sistemCalisiyor || analizYapiliyor))
  {
    Serial.println("==> Arayüz emri algılandı: Sistem Kapatılıyor...");
    sistemiDurdur(); // Motoru ve tüm süreçleri sıfırlayan fonksiyonunuz
  }

  // ================================================================
  // 🎯 SENSÖR TETİKLENME KONTROLÜ (Döngünün Dışında - Bağımsız)
  // ================================================================
  if (sistemCalisiyor && !analizYapiliyor)
  {
    int isSensor = digitalRead(sensorPin);
    if (isSensor == HIGH)
    {
      Serial.println("Sensör tetiklendi. Bant durduruluyor, 6sn bekleme başladı...");
      motoruDurdur();
      sistemCalisiyor = false;
      analizYapiliyor = true;
      analizAsamasi = 1;              // 1. Aşamayı (6 saniyelik beklemeyi) aktif et
      sensorBeklemeZamani = millis(); // Kronometreyi başlat

      digitalWrite(yesilLed, LOW);
      digitalWrite(kirmiziLed, LOW);
      digitalWrite(buyukLed, HIGH);
    }
  }

  // AŞAMA 1: Motor durduktan sonra çiçeğin tam oturması için 6 saniye bekleme
  if (analizYapiliyor && analizAsamasi == 1)
  {
    if (millis() - sensorBeklemeZamani >= 6000)
    {
      digitalWrite(kirmiziLed, HIGH);
      Serial.println("-> Kamera hazir. Bilgisayara (CustomTkinter) 'gel resmi al' sinyali gönderiliyor...");

      camera_fb_t *fb = NULL;
      fb = esp_camera_fb_get();
      if (fb)
      {
        esp_camera_fb_return(fb); // Eski kareyi hemen geri iade et, hafızayı temizle
        delay(50);
      }
      fb = esp_camera_fb_get();
      if (!fb)
      {
        Serial.println("Camera capture failed");
        analizAsamasi = 2;
        analizBeklemeZamani = millis();
        return;
      }
      else
      {
        Serial.println("📸 Fotoğraf başarıyla hafızaya alındı! Şimdi Flask tetikleniyor...");
      }
      delay(200);
      // Bilgisayar bu sinyali aldığı an /capture rotasına gelip resmi çekecek.
      sensorDurumu = "1";
      HTTPClient http;
      http.begin(modelicintetikleme);
      http.setTimeout(3000);
      int responseCode = http.GET();
      Serial.print("HTTP Response code: ");
      Serial.println(responseCode);
      http.end();

      if (fb)
      {
        esp_camera_fb_return(fb);
        fb = NULL;
        Serial.println("Hafıza temizlendi, yeni döngüye hazır.");
      }
      analizAsamasi = 2;              // 2. Aşamayı (3 saniyelik analiz bekleme süresini) başlat
      analizBeklemeZamani = millis(); // Kronometreyi sıfırla
    }
  }

  // AŞAMA 2: Fotoğrafın çekilmesi ve yapay zeka tahmini için 3 saniye bekleme
  if (analizYapiliyor && analizAsamasi == 2)
  {
    if (millis() - analizBeklemeZamani >= 3000)
    {
      Serial.println("-> Analiz bitti! Bant sonraki cicek icin yeniden baslatiliyor...");
      digitalWrite(buyukLed, LOW);
      digitalWrite(kirmiziLed, LOW);
      digitalWrite(yesilLed, HIGH);

      sensorDurumu = "0";

      // Eğer arayüz bu süreçte sistemi tamamen kapatmadıysa (hala true ise) motoru yeniden başlat
      if (currentCom == true)
      {
        motoruCalistir();
        sistemCalisiyor = true;

        Serial.println("Sensör okuması geciktiriliyor, çiçeğin geçmesi bekleniyor...");
        delay(2500);
      }

      analizYapiliyor = false;
      analizAsamasi = 3; // Süreci tamamen sıfırla, yeni çiçek bekle
    }
  }
  if (analizAsamasi == 3)
  {
    int isSensor = digitalRead(sensorPin);
    if (isSensor == LOW)
    {
      Serial.println("Nesne alanı terk etti.");
      analizAsamasi = 0;
    }
  }

  delay(50); // İşlemciyi kilitlemeyen, sunucunun nefes almasını sağlayan küçük pay
}