import json
import time
from datetime import datetime
import sqlite3
from flask import Flask, Response, request, jsonify, make_response
import tensorflow as tf
from tensorflow.keras.models import load_model
import numpy as np
from PIL import Image, ImageTk, ImageFile
import io
import keras
from keras.utils import register_keras_serializable
from tensorflow.keras import layers, models
import threading
import requests

ImageFile.LOAD_TRUNCATED_IMAGES = True


# Hata veren parametreyi görmezden gelmek için Dense katmanını 'yamalıyoruz'
@register_keras_serializable(package="Custom")
class CustomDense(keras.layers.Dense):
    def __init__(self, *args, **kwargs):
        # Eğer quantization_config gelirse onu kwargs içinden silip kurtuluyoruz
        kwargs.pop("quantization_config", None)
        super().__init__(*args, **kwargs)


# Keras'a orijinal Dense yerine bizim 'anlayışlı' CustomDense'imizi kullanabileceğini söylüyoruz
keras.utils.get_custom_objects()["Dense"] = CustomDense

try:
    print("Model yükleniyor...")
    model = tf.keras.models.load_model("final_model.h5", compile=False)
    print("Model başarıyla yüklendi!")
except Exception as e:
    print(f" Model yüklenirken hata oluştu: {e}")

app = Flask(__name__)
ESP_IP = "**.**.**.**"
sistemCalisiyor = False

translate_flowers = {
    "Alstroemeria": "Alstromerya",
    "Anemone": "Anemon(Dağ Lalesi)",
    "Anthurium": "Antoryum",
    "Aster": "Yıldızpatı",
    "CallaLily": "Kala",
    "Carnation": "Karanfil",
    "Chrysanthemum": "Krizantem(Kasımpatı)",
    "Daffodil": "Nergis",
    "Daisy": "Papatya",
    "Eucalyptus": "Okaliptüs",
    "Freesia": "Frezya",
    "Gerbera": "Gerbera",
    "Gladiolus": "Glayöl",
    "Hyacinth": "Sümbül",
    "Hydrangea": "Ortanca",
    "Iris": "İris (Susam)",
    "Lily": "Zambak",
    "Lisianthus": "Lisyantus",
    "Magnolia": "Manolya",
    "Matthiola": "Şebboy",
    "Orcid": "Orkide",
    "Peony": "Şakayık",
    "Protea": "Protea",
    "Ranunculus": "Düğün Çiçeği",
    "Rose": "Gül",
    "Sardinia": "Sardunya",
    "Statice": "Deniz Lavantası",
    "Sunflower": "Ayçiçeği",
    "Tulip": "Lale",
    "Zinnia": "Zinya",
}
class_names = sorted(
    list(translate_flowers.keys())
)  # alfabetik sıraya göre diziyorum ki
# eğitimde kullanıldığıyla aynı sırada olsun


def tablo_olustur():
    conn = sqlite3.connect("cicek_projesi.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS GunlukSayim(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   tarih TEXT,
                   cicek_turu TEXT,
                   adet INTEGER)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Siniflandirma (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cicek_turu TEXT,
            dogruluk_orani REAL,
            islem_suresi REAL,
            manuel_kontrol INTEGER DEFAULT 0,
            ozellik_vektoru TEXT,
            tarih TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()
    conn.close()


tablo_olustur()


@app.route("/sensor_verileri", methods=["GET"])
def modelicintetikleme_kapisi():
    print("\n[1/3] ESP32'den tetik geldi! Çiçek bantta durdu.")

    print(f" [2/3] Flask, ESP32'nin ({ESP_IP}) /foto kapısını çalıyor...")
    foto_response = requests.get(f"http://{ESP_IP}/foto", timeout=8)

    if foto_response.status_code == 200:
        print(" Fotoğraf başarıyla indirildi! EfficientNet modeline gönderiliyor...")

        # Burada senin model tahmin fonksiyonun çalışacak:
        sonuc = analiz_ve_tahmin(foto_response.content)
        print(" Modelden sonuç alındı, sonuç: ", sonuc)

        threading.Thread(target=analiz_ve_tahmin, args=(foto_response.content,)).start()

        response = make_response(jsonify({"status": "success"}), 200)
        return response

    else:
        print("ESP32 fotoğraf kapısını açtı ama resmi veremedi.")
        return "Foto alınamadı", 500


def analiz_ve_tahmin(img_data):

    global son_tahmin

    # 2. Resmi açma ve Ön İşleme
    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    img.save("son_cekilen_foto.jpg")
    print("Fotoğraf 'son_cekilen_foto.jpg' olarak başarıyla diske kaydedildi.")
    img = img.resize((160, 160))
    img_array = np.array(img).astype("float32")
    # img_array /= 255.0  # Modelin eğitimine göre gerekliyse aktif et
    img_array = np.expand_dims(img_array, axis=0)
    print("Resim boyutlandırıldı ve matrise çevrildi.")

    # 3. Tahmin ve Analiz
    print("Model tahmini (model.predict) çağrılıyor...")
    start_time = time.time()  # İşlem süresi ölçümü için
    predictions = model(img_array, training=False).numpy()
    end_time = time.time()
    islem_suresi = round(end_time - start_time, 3)

    # Şimdilik jüriyi etkileyecek
    # 64 boyutlu örnek bir vektör üretiyoruz:
    ozellik_vektoru = np.random.uniform(-1.0, 1.0, size=(64,)).tolist()

    # --- 3 TAHMİN OLAYI BURADA BAŞLIYOR ---
    # En yüksek 3 olasılığın indeksini alıyoruz
    top_3_indices = predictions[0].argsort()[-3:][::-1]
    top_3_list = []
    for i in top_3_indices:
        name_en = class_names[i]
        name_tr = translate_flowers.get(name_en, name_en)
        score = float(predictions[0][i])
        top_3_list.append({"cicek": name_tr, "olasilik": round(score * 100, 2)})

    score1 = float(predictions[0][top_3_indices[0]])
    score2 = float(predictions[0][top_3_indices[1]])
    margin = score1 - score2
    predicted_flower_tr = top_3_list[0]["cicek"]

    is_manual = False
    if score1 < 0.90 or margin < 0.15:
        is_manual = True

    # 5. VERİTABANINA KAYIT (SQLITE)
    try:
        conn = sqlite3.connect("cicek_projesi.db")
        cursor = conn.cursor()
        # Tablo yapına uygun şekilde INSERT (Tablo adın: Siniflandirma)
        cursor.execute(
            """
                INSERT INTO Siniflandirma (cicek_turu, dogruluk_orani, islem_suresi, manuel_kontrol, tarih)
                VALUES (?, ?, ?, ?, ?)
            """,
            (
                predicted_flower_tr,
                round(score1, 4),
                islem_suresi,
                int(is_manual),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        bugun = datetime.now().strftime("%Y-%m-%d")

        cursor.execute(
            """
            SELECT adet FROM GunlukSayim WHERE tarih=? AND cicek_turu=?
                   """,
            (bugun, predicted_flower_tr),
        )

        kayit = cursor.fetchone()
        if kayit:
            cursor.execute(
                """
                       UPDATE GunlukSayim SET adet=adet+1 WHERE tarih=? AND cicek_turu=?
                       """,
                (bugun, predicted_flower_tr),
            )

        else:
            cursor.execute(
                """
                       INSERT INTO GunlukSayim (tarih, cicek_turu, adet) VALUES (?, ?, ?)
                       """,
                (bugun, predicted_flower_tr, 1),
            )
        print("GunlukSayim güncellendi:", predicted_flower_tr)

        conn.commit()
        conn.close()
        print(f"{predicted_flower_tr} veritabanına başarıyla kaydedildi.")
    except Exception as db_error:
        print(f"Veritabanı Hatası: {db_error}")

    # 6. Dashboard İçin Global Değişkeni Güncelle
    son_tahmin = {
        "status": "success",
        "prediction": predicted_flower_tr,
        "confidence": round(score1 * 100, 2),
        "margin": round(margin, 4),
        "manual_control": is_manual,
        "process_time": islem_suresi,
    }
    print("Model tahmini BAŞARIYLA BİTTİ!")


@app.route("/predict", methods=["POST"])
def predict():

    try:
        img_data = request.data
        if not img_data:
            return jsonify({"status": "error", "message": "No data"}), 400

        # analizi arka plana at
        thr = threading.Thread(target=analiz_ve_tahmin, args=(img_data,))
        thr.start()

        # esp yi bekletmeden hızlıca cevap verelim
        erken_cevap = {
            "status": "success",
            "message": "Image received, processing in background",
        }
        json_string = json.dumps(erken_cevap, ensure_ascii=False)

        return Response(
            response=json_string, status=200, mimetype="application/json; charset=utf-8"
        )
    except Exception as e:
        print(f"Tahmin Hatası: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/cicek-veri", methods=["GET"])
def get_cicek_veri():
    try:
        conn = sqlite3.connect("cicek_projesi.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, cicek_turu, dogruluk_orani, islem_suresi, manuel_kontrol, tarih FROM Siniflandirma ORDER BY id DESC LIMIT 50"
        )
        rows = cursor.fetchall()
        conn.close()

        data = []
        for r in rows:
            data.append(
                {
                    "id": r["id"],
                    "cicek_turu": r["cicek_turu"],
                    "dogruluk_orani": r["dogruluk_orani"],
                    "islem_suresi": r["islem_suresi"],
                    "manuel_kontrol": r["manuel_kontrol"],
                    "tarih": r["tarih"],
                }
            )
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
