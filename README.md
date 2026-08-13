TR



\#Otonom Kesme Çiçek Sınıflandırma ve Sayma Sistemi



Bu proje, konveyör bant üzerinden geçen çiçeklerin otonom olarak görüntülenmesi, derin öğrenme (EfficientNet) modeliyle sınıflandırılması, verilerin işlenmesi ve masaüstü kullanıcı arayüzü üzerinden takibini sağlayan \*\*uçtan uca bir gömülü IoT ve yapay zeka otomasyon sistemidir.\*\*



\---



\## Sistem Mimarisi \& Çalışma Mantığı



Proje 4 temel katmandan oluşmaktadır:



1-Donanım Katmanı:Kızılötesi (IR) sensör konveyördeki çiçeği algıladığında motor durur. ESP32-CAM çiçeğin fotoğrafını çekerek Wi-Fi üzerinden yerel HTTP POST isteği ile backend sunucusuna gönderir.

2-Arka Plan Katmanı:Flask mimarisi üzerine kurulu REST API, gelen görüntüyü ön işlemeden geçirir ve eğitilmiş derin öğrenme modeline iletir.

3-Yapay Zeka Katmanı(AI):Transfer Learning (EfficientNetB0) mimarisi ile eğitilmiş model, çiçek türünü ve doğruluk (confidence) oranını tahmin eder. Sonuçlar SQLite veritabanına loglanır.

4-Ön Yüz Katmanı:CustomTkinter ile geliştirilmiş masaüstü arayüzü, gelen tahmin sonuçlarını, canlı durumu ve çiçek bakım kataloğunu kullanıcıya sunar.





PROJE KLASÖR YAPISI



flower-counting-and-classification/

├── software/

│   ├── backend/          # Flask REST API, SQLite Veritabanı Mantığı

│   │   ├── server.py

│   │   ├── final\_model.h5

│   │   └── requirements.txt

│   ├── frontend/         # CustomTkinter Masaüstü Arayüzü

│   │   ├── gui.py

│   │   ├── flower\_information.json

│   │   └── requirements.txt

│   └── ai\_model/         # Model Eğitim Defteri (Jupyter Notebook)

│       └── final-CNN-model.ipynb

├── hardware/

│   └── esp32/            # ESP32-CAM PlatformIO C++ Kodları

│       ├── platformio.ini

│       └── src/

│           └── main.cpp

├── docs/                 # Ekran Görüntüleri ve Sistem Görselleri

└── README.md             # Proje Dokümantasyonu



KURULUM VE ÇALIŞTIRMA



1.Arka Plan Sunucusunu Başlatma

cd software/backend

pip install -r requirements.txt

python server.py



Backend varsayılan olarak http://localhost:5000 veya yerel ağ IP'niz üzerinden dinlemeye başlar. SQLite veritabanı ilk çalıştırmada otomatik oluşturulur.



2.Kullanıcı Arayüzünü Çalıştırma

cd software/frontend

pip install -r requirements.txt

python gui.py



3.Donanım Yüklemesi

hardware/esp32 klasörünü VS Code + PlatformIO ile açın.



main.cpp içindeki Wi-Fi SSID, Parola ve Flask Sunucu IP adresini kendi ağınıza göre güncelleyin.



Kodu ESP32-CAM kartınıza yükleyin (Upload). Gerekli tüm C++ kütüphaneleri platformio.ini dosyasından otomatik indirilecektir.



KULLANILAN TEKNOLOJİLER



Gömülü Sistemler: ESP32-CAM, C++, PlatformIO, Arduino Framework



Yapay Zeka \& Derin Öğrenme: TensorFlow / Keras, EfficientNetB0, NumPy, Pillow



Arka Plan \& Veritabanı: Python, Flask (REST API), SQLite



Masaüstü Arayüzü: CustomTkinter, Tkinter



YAZAR

Zeynep Handan Çakır-Bilgisayar Mühendisi



ENG



\#Autonomous Flower Classification and Sorting System

> \\\\\\\\\\\\\\\*\\\\\\\\\\\\\\\*End-to-End Embedded IoT \\\\\\\\\\\\\\\& Deep Learning Conveyor Automation System\\\\\\\\\\\\\\\*\\\\\\\\\\\\\\\*



\---



This project is an \*\*end-to-end embedded IoT and deep learning automation system\*\* designed to capture images of flowers moving along a conveyor belt, classify them autonomously using an EfficientNet model, log classification metrics, and monitor real-time operations via a desktop GUI.



\## System Architecture \& Workflow



The system consists of 4 main layers:



Hardware Layer: When the Infrared (IR) sensor detects a flower on the conveyor belt, the motor stops. The ESP32-CAM captures an image and transmits it to the backend server via a local HTTP POST request over Wi-Fi.



Backend Layer: The Flask REST API preprocesses the incoming image and forwards it to the trained deep learning model.



AI Layer: Built using Transfer Learning (EfficientNetB0), the model predicts the flower species and output confidence score. Classification logs are automatically stored in an SQLite database.



Frontend Layer: The desktop interface built with CustomTkinter displays live classification results, system logs, and a flower care guide for operators.



PROJECT DIRECTORY STRUCTURE



flower-classification-and-sorting-system/

├── software/

│   ├── backend/          # Flask REST API, SQLite Database Logic

│   │   ├── server.py

│   │   ├── final\_model.h5

│   │   └── requirements.txt

│   ├── frontend/         # CustomTkinter Desktop Application

│   │   ├── gui.py

│   │   ├── flower\_information.json

│   │   └── requirements.txt

│   └── ai\_model/         # Model Training Notebook

│       └── final-CNN-model.ipynb

├── hardware/

│   └── esp32/            # ESP32-CAM PlatformIO C++ Source Code

│       ├── platformio.ini

│       └── src/

│           └── main.cpp

├── docs/                 # Screenshots and Project Visuals

└── README.md             # Project Documentation



SETUP AND EXECUTION



1.Starting the Backend Server



cd software/backend

pip install -r requirements.txt

python server.py



The Flask server listens on http://localhost:5000 or your local network IP by default. The SQLite database is automatically initialized on the first run.



2\. Running the Desktop Application (Frontend)



cd software/frontend

pip install -r requirements.txt

python gui.py



3\. ESP32-CAM Firmware Upload



Open the hardware/esp32 directory in VS Code with PlatformIO.



Update the Wi-Fi credentials (SSID/Password) and Flask server IP address in src/main.cpp.



Upload the firmware to your ESP32-CAM board. Required C++ libraries will be resolved automatically via platformio.ini.



TECH STACK



Embedded Systems: ESP32-CAM, C++, PlatformIO, Arduino Framework



AI \& Deep Learning: TensorFlow / Keras, EfficientNetB0, NumPy, Pillow



Backend \& Database: Python, Flask (REST API), SQLite



Frontend: CustomTkinter, Tkinter



AUTHOR

Zeynep Handan Çakır-Computer Engineer

