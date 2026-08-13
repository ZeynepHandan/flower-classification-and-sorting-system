import os
import csv
import json
import sqlite3
import threading
from datetime import datetime
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import math
import time
from tkinter import messagebox
from flask import current_app, logging

try:
    import qrcode
except ImportError:
    qrcode = None

# =============================================================================
# RENK SİSTEMİ — Koyu Botanik / Yeşil-Antrasit Tonal Paleti
# =============================================================================
BG_DEEP = "#0D0F0E"  # En derin siyah-yeşil arka plan
BG_PANEL = "#131714"  # Panel yüzeyi — derin orman
BG_CARD = "#1A1E1B"  # Kart/kutu yüzeyi
BG_INSET = "#0F1210"  # İçe gömülü alan (kamera ekranı)
BG_BORDER = "#2A3329"  # Yeşilimsi ince kenarlık

ACCENT_GREEN = "#4ADE80"  # Canlı neon yeşil vurgu (sinyal rengi)
ACCENT_TEAL = "#2DD4BF"  # Türkuaz ikincil vurgu
ACCENT_AMBER = "#FBBF24"  # Uyarı / manuel mod sarısı
ACCENT_RED = "#F87171"  # Durdur / hata kırmızısı
ACCENT_DIM = "#1F5C3A"  # Soluk yeşil — arkaplan aksan rengi

TEXT_PRIMARY = "#E8F0EB"  # Ana metin — soğuk beyaz
TEXT_SECONDARY = "#7A9B84"  # İkincil metin — soluk yaprak
TEXT_MUTED = "#3D5445"  # Arka plan metin

FONT_LOGO = ("Courier New", 13, "bold")
FONT_HEADING = ("Courier New", 11, "bold")
FONT_DATA = ("Courier New", 18, "bold")
FONT_LABEL = ("Courier New", 9)
FONT_BODY = ("Courier New", 10)
FONT_SMALL = ("Courier New", 8)

ESP32_IP = "**.**.**.**"


# =============================================================================
# YARDIMCI: Hover ToolTip Sınıfı
# =============================================================================
class ToolTip:
    def __init__(self, widget, text_func):
        self.widget = widget
        self.text_func = text_func
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        text = self.text_func()
        if not text or text == "—" or text.strip() == "Bilgi girilmedi":
            return
        if self.tip_window:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(
            tw,
            fg_color="#1A1E1B",  # BG_CARD
            border_width=1,
            border_color="#2DD4BF",  # ACCENT_TEAL
            corner_radius=6,
        )
        frame.pack()

        label = ctk.CTkLabel(
            frame,
            text=text,
            justify="left",
            font=("Courier New", 9),
            text_color="#E8F0EB",  # TEXT_PRIMARY
            wraplength=220,
            padx=8,
            pady=6,
        )
        label.pack()

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


# =============================================================================
# YARDIMCI: Halka Grafik Çizici (Tk Canvas üzerinde)
# =============================================================================


def halka_ciz(canvas, yuzde, w=100, h=100, kalinlik=8):
    canvas.delete("all")
    pad = kalinlik + 4
    # Arka plan halkası
    canvas.create_arc(
        pad,
        pad,
        w - pad,
        h - pad,
        start=0,
        extent=359.9,
        outline=BG_CARD,
        width=kalinlik,
        style="arc",
    )
    # Değer halkası
    if yuzde > 0:
        extent = -(360 * yuzde / 100)
        if yuzde >= 90:
            renk = ACCENT_GREEN
        elif yuzde >= 70:
            renk = ACCENT_TEAL
        elif yuzde >= 50:
            renk = ACCENT_AMBER
        else:
            renk = ACCENT_RED
        canvas.create_arc(
            pad,
            pad,
            w - pad,
            h - pad,
            start=90,
            extent=extent,
            outline=renk,
            width=kalinlik,
            style="arc",
        )
        # İnce parlama halkası
        canvas.create_arc(
            pad + 2,
            pad + 2,
            w - pad - 2,
            h - pad - 2,
            start=90,
            extent=extent * 0.3,
            outline=renk,
            width=2,
            style="arc",
        )
    # Merkez metin
    canvas.create_text(
        w // 2,
        h // 2 - 6,
        text=f"{round(yuzde, 1)}",
        fill=TEXT_PRIMARY,
        font=("Courier New", 13, "bold"),
    )
    canvas.create_text(
        w // 2, h // 2 + 9, text="%", fill=TEXT_SECONDARY, font=("Courier New", 8)
    )


# =============================================================================
# YARDIMCI: Ayırıcı çizgi
# =============================================================================
def ayirici(parent, renk=BG_BORDER):
    f = ctk.CTkFrame(parent, height=1, fg_color=renk)
    f.pack(fill="x", padx=15, pady=6)


# =============================================================================
# YARDIMCI: Etiket + Değer çifti kutusu
# =============================================================================
class StatKart(ctk.CTkFrame):
    def __init__(self, parent, baslik, deger="—", renk=TEXT_PRIMARY, **kw):
        super().__init__(
            parent,
            fg_color=BG_INSET,
            corner_radius=6,
            border_width=1,
            border_color=BG_BORDER,
            **kw,
        )
        ctk.CTkLabel(
            self, text=baslik.upper(), font=FONT_SMALL, text_color=TEXT_MUTED
        ).pack(anchor="w", padx=12, pady=(10, 2))
        self.deger_lbl = ctk.CTkLabel(
            self, text=deger, font=("Courier New", 12, "bold"), text_color=renk
        )
        self.deger_lbl.pack(anchor="w", padx=12, pady=(0, 10))

    def guncelle(self, metin, renk=None):
        self.deger_lbl.configure(text=metin)
        if renk:
            self.deger_lbl.configure(text_color=renk)


# =============================================================================
# SAĞ PANEL — Raporlama & Analitik
# =============================================================================
class SagKontrolPaneli(ctk.CTkFrame):
    def __init__(self, parent, db_path="cicek_projesi.db"):
        super().__init__(parent, fg_color="transparent")
        self.db_path = db_path
        self._gunluk_loop_id = None

        # Başlık
        baslik = ctk.CTkFrame(self, fg_color="transparent")
        baslik.pack(fill="x", padx=0, pady=(0, 12))
        ctk.CTkLabel(
            baslik, text="◈ ANALİTİK", font=FONT_HEADING, text_color=ACCENT_GREEN
        ).pack(side="left")
        self.canli_nokta = ctk.CTkLabel(
            baslik, text="●", font=("Courier New", 9), text_color=ACCENT_GREEN
        )
        self.canli_nokta.pack(side="right")

        ayirici(self, renk=BG_BORDER)

        # BUGÜNKÜ ADET (KPI KART VE SEÇİM ALANI)
        self.frame_gunluk_sayim = ctk.CTkFrame(
            self,
            fg_color=BG_INSET,
            corner_radius=8,
            border_width=1,
            border_color=BG_BORDER,
            height=100,
        )
        self.frame_gunluk_sayim.pack(fill="x", pady=(10, 10))
        self.frame_gunluk_sayim.pack_propagate(False)

        lbl_kpi_header = ctk.CTkLabel(
            self.frame_gunluk_sayim,
            text="BUGÜN GEÇEN ADET (SEÇİLİ TÜR)",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
        )
        lbl_kpi_header.pack(anchor="w", padx=12, pady=(8, 2))

        # KPI İçerik Alanı (Sayı ve Seçim yan yana)
        kpi_icerik = ctk.CTkFrame(self.frame_gunluk_sayim, fg_color="transparent")
        kpi_icerik.pack(fill="x", padx=12, pady=2)

        self.lbl_gunluk_adet = ctk.CTkLabel(
            kpi_icerik,
            text="0",
            font=("Courier New", 26, "bold"),
            text_color=ACCENT_TEAL,
        )
        self.lbl_gunluk_adet.pack(side="left", padx=(0, 10))

        self.cmb_cicek_sec = ctk.CTkComboBox(
            kpi_icerik,
            values=[
                "Alstromerya",
                "Anemon(Dağ Lalesi)",
                "Antoryum",
                "Yıldızpatı",
                "Kala",
                "Karanfil",
                "Krizantem(Kasımpatı)",
                "Nergis",
                "Papatya",
                "Okaliptüs",
                "Frezya",
                "Gerbera",
                "Glayöl",
                "Sümbül",
                "Ortanca",
                "İris (Susam)",
                "Zambak",
                "Lisyantus",
                "Manolya",
                "Şebboy",
                "Orkide",
                "Şakayık",
                "Protea",
                "Düğün Çiçeği",
                "Gül",
                "Sardunya",
                "Deniz Lavantası",
                "Ayçiçeği",
                "Lale",
                "Zinya",
            ],
            width=170,
        )
        self.cmb_cicek_sec.pack(side="right")
        self.cmb_cicek_sec.set("Gül")

        # Stat kartları
        self.kart_toplam = StatKart(self, "toplam geçen", "— adet", renk=ACCENT_GREEN)
        self.kart_toplam.pack(fill="x", pady=(0, 6))

        self.kart_bugun = StatKart(self, "bugün geçen", "— adet", renk=ACCENT_TEAL)
        self.kart_bugun.pack(fill="x", pady=(0, 6))

        # Aksiyon butonları (Her zaman görünmesi için en altta packlenir)
        self.btn_qr = ctk.CTkButton(
            self,
            text="📱 QR KOD İLE TELEFONDAN İZLE",
            font=FONT_HEADING,
            fg_color=BG_CARD,
            hover_color="#1A3040",
            border_width=1,
            border_color=ACCENT_TEAL,
            text_color=ACCENT_TEAL,
            corner_radius=4,
            height=36,
            command=self.telefona_gonder_api,
        )
        self.btn_qr.pack(fill="x", side="bottom", pady=4)

        self.btn_csv = ctk.CTkButton(
            self,
            text="⬇  CSV / EXCEL RAPORU",
            font=FONT_HEADING,
            fg_color=BG_CARD,
            hover_color=ACCENT_DIM,
            border_width=1,
            border_color=ACCENT_GREEN,
            text_color=ACCENT_GREEN,
            corner_radius=4,
            height=36,
            command=self.csv_disa_aktar,
        )
        self.btn_csv.pack(fill="x", side="bottom", pady=4)

        sep = ctk.CTkFrame(self, height=1, fg_color=BG_BORDER)
        sep.pack(fill="x", side="bottom", pady=6)

        # Tür bazlı liste — frame içinde scrollable (Kalan orta alanı kaplar)
        lbl_tur_baslik = ctk.CTkLabel(
            self, text="BUGÜN GEÇEN TÜRLER", font=FONT_SMALL, text_color=TEXT_MUTED
        )
        lbl_tur_baslik.pack(anchor="w", padx=12, pady=(8, 2))

        tur_frame = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=10,
            border_width=0,
        )
        tur_frame.pack(fill="both", expand=True, padx=0, pady=(0, 12))

        ctk.CTkLabel(
            tur_frame,
            text="BUGÜN GEÇEN TÜRLER",
            font=("Courier New", 11, "bold"),
            text_color=ACCENT_TEAL,
        ).pack(anchor="w", padx=12, pady=(8, 4))

        self.lbl_veri_yok = ctk.CTkLabel(
            tur_frame,
            text="Bugün henüz geçiş olmadı",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
        )
        self.lbl_veri_yok.pack(pady=20)

        # 5 adet şık satır oluşturuyoruz
        self.tur_satirlari = []
        for i in range(5):
            satir_frame = ctk.CTkFrame(tur_frame, fg_color="transparent")

            lbl_isim = ctk.CTkLabel(
                satir_frame,
                text="—",
                font=FONT_BODY,
                text_color=TEXT_PRIMARY,
            )
            lbl_isim.pack(side="left", padx=12)

            lbl_deger = ctk.CTkLabel(
                satir_frame,
                text="0 adet",
                font=("Courier New", 10, "bold"),
                text_color=ACCENT_TEAL,
            )
            lbl_deger.pack(side="right", padx=12)

            self.tur_satirlari.append((satir_frame, lbl_isim, lbl_deger))

        # Döngüleri başlat
        self.gunluk_sayim_goster()
        self.istatistikleri_guncelle()
        self._canli_animasyon()

    def _canli_animasyon(self):
        """Canlı yeşil nokta için titreşim efekti"""
        mevcut = self.canli_nokta.cget("text_color")
        yeni = TEXT_MUTED if mevcut == ACCENT_GREEN else ACCENT_GREEN
        self.canli_nokta.configure(text_color=yeni)
        self.after(900, self._canli_animasyon)

    def gunluk_sayim_goster(self):
        secilen_cicek = self.cmb_cicek_sec.get()

        if not secilen_cicek:
            self._gunluk_loop_id = self.after(1000, self.gunluk_sayim_goster)
            return

        bugun = datetime.now().strftime("%Y-%m-%d")
        try:
            conn = sqlite3.connect("cicek_projesi.db")
            cursor = conn.cursor()
            cursor.execute(
                """SELECT adet FROM GunlukSayim WHERE tarih=? AND cicek_turu=?""",
                (bugun, secilen_cicek),
            )
            sonuc = cursor.fetchone()
            conn.close()

            if sonuc:
                adet = sonuc[0]
            else:
                adet = 0

            self.lbl_gunluk_adet.configure(text=str(adet))
        except Exception as e:
            print(f"Error in gunluk_sayim_goster: {e}")

        self._gunluk_loop_id = self.after(1000, self.gunluk_sayim_goster)

    def istatistikleri_guncelle(self):
        try:
            if os.path.exists(self.db_path):
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()

                # Toplam
                cur.execute("SELECT COUNT(*) FROM Siniflandirma")
                toplam = cur.fetchone()[0]
                self.kart_toplam.guncelle(f"{toplam} adet", ACCENT_GREEN)

                # Bugün
                bugun = datetime.now().strftime("%Y-%m-%d")
                cur.execute(
                    "SELECT COUNT(*) FROM Siniflandirma WHERE tarih LIKE ?",
                    (f"{bugun}%",),
                )
                bugun_sayı = cur.fetchone()[0]
                self.kart_bugun.guncelle(f"{bugun_sayı} adet", ACCENT_TEAL)

                # Tür bazlı (bugün geçenler, top 5)
                cur.execute(
                    """
                    SELECT cicek_turu, COUNT(*) as c FROM Siniflandirma
                    WHERE tarih LIKE ?
                    GROUP BY cicek_turu ORDER BY c DESC LIMIT 5
                """,
                    (f"{bugun}%",),
                )
                turler = cur.fetchall()
                conn.close()

                if turler:
                    self.lbl_veri_yok.pack_forget()
                    for idx, (satir_frame, lbl_name, lbl_val) in enumerate(
                        self.tur_satirlari
                    ):
                        if idx < len(turler):
                            t_name = turler[idx][0].upper()
                            t_count = turler[idx][1]
                            lbl_name.configure(text=t_name)
                            lbl_val.configure(text=f"{t_count} adet")
                            satir_frame.pack(fill="x", padx=5, pady=4)
                        else:
                            satir_frame.pack_forget()
                else:
                    self.lbl_veri_yok.pack(pady=20)
                    for satir_frame, _, _ in self.tur_satirlari:
                        satir_frame.pack_forget()
        except Exception as e:
            print(f"Error in istatistikleri_guncelle: {e}")
        self.after(3000, self.istatistikleri_guncelle)

    def csv_disa_aktar(self):
        """Excel/CSV raporu — detaylı kayıtlar + tür bazlı istatistik"""
        try:
            if not os.path.exists(self.db_path):
                messagebox.showerror("Hata", "Veritabanı bulunamadı!")
                return
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            # Detaylı kayıtlar
            cur.execute("SELECT * FROM Siniflandirma ORDER BY rowid DESC")
            satirlar = cur.fetchall()

            # Tür bazlı istatistik
            cur.execute("""
                SELECT cicek_turu, COUNT(*) as c, ROUND(AVG(dogruluk_orani)*100, 2) as ort_dogr
                FROM Siniflandirma
                GROUP BY cicek_turu ORDER BY c DESC
            """)
            istatistik = cur.fetchall()
            conn.close()

            dosya = f"flor_eye_rapor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")

                # Bölüm 1: Detaylı kayıtlar
                w.writerow(["DETAYLI KAYITLAR"])
                w.writerow(
                    [
                        "ID",
                        "Cicek",
                        "Dogruluk",
                        "Sure_sn",
                        "Manuel",
                        "Ozellik_Vektoru",
                        "Tarih",
                    ]
                )
                w.writerows(satirlar)

                # Boş satır
                w.writerow([])

                # Bölüm 2: Tür istatistiği
                w.writerow(["TÜR BAZLI İSTATİSTİK"])
                w.writerow(["Cicek_Turu", "Toplam_Adet", "Ortalama_Dogruluk"])
                w.writerows(istatistik)

            messagebox.showinfo("Rapor Hazır", f"✅ Excel raporu kaydedildi:\n{dosya}")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def telefona_gonder_api(self):
        """Mobil uygulamaya QR kod ile bağlantı gönder — pencerede göster"""
        if not qrcode:
            messagebox.showerror(
                "Hata", "QR kod kütüphanesi yüklü değil.\npip install qrcode[pil]"
            )
            return

        try:
            # Get actual local IP dynamically (Robust method)
            import socket

            def get_local_ip():
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    ip = s.getsockname()[0]
                    s.close()
                    if ip != "127.0.0.1":
                        return ip
                except Exception:
                    pass

                try:
                    hostname = socket.gethostname()
                    ips = socket.gethostbyname_ex(hostname)[2]
                    for ip in ips:
                        if not ip.startswith("127."):
                            return ip
                except Exception:
                    pass
                return "127.0.0.1"

            local_ip = get_local_ip()
            api_url = f"http://{local_ip}:5000/api/cicek-veri"

            # QR kod oluştur
            qr = qrcode.QRCode(version=1, box_size=10, border=3)
            qr.add_data(api_url)
            qr.make(fit=True)
            # Convert to RGB to ensure compatibility with CTkImage / Tkinter
            qr_img = qr.make_image(fill_color="black", back_color="white").convert(
                "RGB"
            )

            # CTkImage ile dönüştür
            ctk_img = ctk.CTkImage(
                light_image=qr_img, dark_image=qr_img, size=(250, 250)
            )

            # Popup pencere aç
            popup = ctk.CTkToplevel(self)
            popup.title("Mobil Bağlantı — QR Kod")
            popup.geometry("380x480")
            popup.configure(fg_color=BG_DEEP)
            popup.transient(self)
            popup.grab_set()

            # Başlık
            baslik = ctk.CTkLabel(
                popup,
                text="📱 MOBİL VERİ PAYLAŞIMI",
                font=FONT_HEADING,
                text_color=ACCENT_GREEN,
            )
            baslik.pack(pady=15)

            # QR kod göster
            lbl_qr = ctk.CTkLabel(popup, image=ctk_img, text="")
            lbl_qr.image = ctk_img  # referans tut
            lbl_qr.pack(pady=5)

            # URL bilgisi
            ctk.CTkLabel(
                popup, text="API URL:", font=FONT_SMALL, text_color=TEXT_MUTED
            ).pack(anchor="w", padx=20, pady=(5, 2))

            entry_url = ctk.CTkEntry(
                popup,
                width=340,
                font=("Courier New", 9),
                text_color=ACCENT_TEAL,
                fg_color=BG_INSET,
                border_color=BG_BORDER,
            )
            entry_url.insert(0, api_url)
            entry_url.configure(state="readonly")
            entry_url.pack(padx=20, pady=(0, 8))

            # Uyarı Notu
            lbl_not = ctk.CTkLabel(
                popup,
                text="⚠️ Telefon ve PC aynı Wi-Fi ağına bağlı olmalı\nve server.py çalışıyor olmalıdır.",
                font=("Courier New", 8, "bold"),
                text_color=ACCENT_AMBER,
                justify="center",
            )
            lbl_not.pack(pady=(0, 5))

            # Kapat butonu
            btn_kapat = ctk.CTkButton(
                popup,
                text="Kapat",
                fg_color=BG_CARD,
                hover_color=ACCENT_DIM,
                border_width=1,
                border_color=ACCENT_RED,
                text_color=ACCENT_RED,
                corner_radius=4,
                height=32,
                command=popup.destroy,
            )
            btn_kapat.pack(fill="x", padx=20, pady=10)

        except Exception as e:
            messagebox.showerror("Hata", f"QR kod oluşturulamadı:\n{e}")


# =============================================================================
# ANA DASHBOARD
# =============================================================================
class FlorEyeDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=BG_DEEP)
        self.title("FLOR·EYE — Bitki Sınıflandırma Sistemi")
        self.geometry("1200x740")
        self.resizable(True, True)
        self.sistem_aktif = False
        self._loop_resim = None
        self._loop_veri = None

        # ── GENEL LAYOUT ────────────────────────────────────────────────────
        # Sol kolon: kamera + telemetri
        # Sağ kolon: kontrol + analitik
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self._sol_panel_olustur()
        self._sag_panel_olustur()

        # Başlatma
        self.veritabani_bagla()
        self.resmi_yenile()
        self.canli_verileri_guncelle()
        self.protocol("WM_DELETE_WINDOW", self.pencereyi_kapat)
        self.after(800, self._acilis_animasyonu)

    # ── SOL PANEL ──────────────────────────────────────────────────────────
    def _sol_panel_olustur(self):
        sol = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            corner_radius=10,
            border_width=1,
            border_color=BG_BORDER,
        )
        sol.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        sol.grid_rowconfigure(0, weight=1)  # kamera — küçük
        sol.grid_rowconfigure(1, weight=1)  # telemetri
        sol.grid_rowconfigure(2, weight=2)  # bakım bilgileri
        sol.grid_columnconfigure(0, weight=1)

        # ── KAMERA BÖLÜMÜ ───────────────────────────────────────────────
        kamera_alan = ctk.CTkFrame(sol, fg_color="transparent")
        kamera_alan.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 6))
        kamera_alan.grid_rowconfigure(1, weight=1)
        kamera_alan.grid_columnconfigure(0, weight=1)

        baslik_satir = ctk.CTkFrame(kamera_alan, fg_color="transparent")
        baslik_satir.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(
            baslik_satir,
            text="◈ VİZYON AKIŞI",
            font=FONT_HEADING,
            text_color=ACCENT_GREEN,
        ).pack(side="left")
        self.lbl_fps = ctk.CTkLabel(
            baslik_satir,
            text="FEED: BEKLENIYOR",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
        )
        self.lbl_fps.pack(side="right")

        self.kamera_cerceve = ctk.CTkFrame(
            kamera_alan,
            fg_color=BG_INSET,
            corner_radius=6,
            border_width=1,
            border_color=BG_BORDER,
        )
        self.kamera_cerceve.grid(row=1, column=0, sticky="nsew")
        self.kamera_cerceve.pack_propagate(
            False
        )  # İçindeki label'ın çerçeveyi şişirmesini engeller
        self.kamera_cerceve.configure(width=300, height=300)
        self.image_display = ctk.CTkLabel(
            self.kamera_cerceve,
            text="[ SINYAL BEKLENİYOR ]",
            font=FONT_LABEL,
            text_color=TEXT_MUTED,
            fg_color="transparent",
        )
        self.image_display.pack(fill="both", expand=True, padx=2, pady=2)

        # ── TELEMETRİ BLOĞU (Kompakt Satır + Halka Grafik) ────────────────
        tel_dis = ctk.CTkFrame(
            sol,
            fg_color=BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=BG_BORDER,
        )
        tel_dis.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        tel_dis.grid_columnconfigure(0, weight=3)  # kompakt satır
        tel_dis.grid_columnconfigure(1, weight=1)  # halka
        tel_dis.grid_rowconfigure(1, weight=1)

        # Başlık
        tel_baslik = ctk.CTkFrame(tel_dis, fg_color="transparent")
        tel_baslik.grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 4)
        )
        ctk.CTkLabel(
            tel_baslik,
            text="◈ CANLI VERİ",
            font=FONT_HEADING,
            text_color=TEXT_SECONDARY,
        ).pack(side="left")
        self.lbl_fps_tel = ctk.CTkLabel(
            tel_baslik, text="● CANLI", font=FONT_SMALL, text_color=ACCENT_GREEN
        )
        self.lbl_fps_tel.pack(side="right")

        # Ayırıcı
        ctk.CTkFrame(tel_dis, height=1, fg_color=BG_BORDER).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=0
        )

        # SOL: Kompakt satır
        veri_ic = ctk.CTkFrame(tel_dis, fg_color="transparent")
        veri_ic.grid(row=1, column=0, sticky="ew", padx=16, pady=10)

        self.lbl_telemetri_kompakt = ctk.CTkLabel(
            veri_ic,
            text="—  |  —%  |  —s  |  —  |  —",
            font=("Courier New", 15, "bold"),
            text_color=TEXT_PRIMARY,
            justify="left",
        )
        self.lbl_telemetri_kompakt.pack(side="left")

        # SAĞ: Halka Grafiği
        halka_ic = ctk.CTkFrame(tel_dis, fg_color="transparent")
        halka_ic.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)

        ctk.CTkLabel(
            halka_ic, text="DOĞRULUK", font=("Courier New", 7), text_color=TEXT_MUTED
        ).pack()

        self.halka_canvas = tk.Canvas(
            halka_ic, width=170, height=170, bg=BG_CARD, highlightthickness=0
        )
        self.halka_canvas.pack(pady=(2, 0))
        halka_ciz(self.halka_canvas, 0, 170, 170, 10)

        # ── BAKIM BİLGİLERİ BLOĞU ───────────────────────────────────────
        bakim_dis = ctk.CTkFrame(
            sol,
            fg_color=BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=BG_BORDER,
        )
        bakim_dis.grid(row=2, column=0, sticky="nsew", padx=16, pady=(6, 16))
        bakim_dis.grid_columnconfigure(0, weight=1)
        bakim_dis.grid_columnconfigure(1, weight=1)
        bakim_dis.grid_columnconfigure(2, weight=1)
        bakim_dis.grid_columnconfigure(3, weight=1)
        bakim_dis.grid_columnconfigure(4, weight=1)
        bakim_dis.grid_rowconfigure(1, weight=1)

        # Başlık
        bakim_baslik = ctk.CTkFrame(bakim_dis, fg_color="transparent")
        bakim_baslik.grid(
            row=0, column=0, columnspan=5, sticky="ew", padx=16, pady=(12, 4)
        )
        ctk.CTkLabel(
            bakim_baslik,
            text="◈ BAKIM REHBERİ",
            font=FONT_HEADING,
            text_color=TEXT_SECONDARY,
        ).pack(side="left")
        self.lbl_bakim_tur = ctk.CTkLabel(
            bakim_baslik,
            text="",
            font=("Courier New", 10, "bold"),
            text_color=ACCENT_TEAL,
        )
        self.lbl_bakim_tur.pack(side="right")
        ctk.CTkFrame(bakim_dis, height=1, fg_color=BG_BORDER).grid(
            row=0, column=0, columnspan=5, sticky="sew", padx=0, pady=(0, 0)
        )

        # 5 bakım kartı: sulama, ışık, sıcaklık, toprak, budama
        bakim_dis.grid_columnconfigure(4, weight=1)
        self.bakim_kartlari = {}
        KARTLAR = [
            ("sulama", "SULAMA", "💧", ACCENT_TEAL),
            ("isik_konum", "IŞIK", "☀", ACCENT_AMBER),
            ("ideal_sicaklik", "SICAKLIK", "🌡", ACCENT_RED),
            ("toprak_besin", "TOPRAK", "🌱", TEXT_PRIMARY),
            ("budama", "BUDAMA", "✂", TEXT_SECONDARY),
        ]

        for i, (json_alan, baslik, ikon, renk) in enumerate(KARTLAR):
            kart = ctk.CTkFrame(
                bakim_dis,
                fg_color=BG_INSET,
                corner_radius=6,
                border_width=1,
                border_color=BG_BORDER,
            )
            kart.grid(row=1, column=i, sticky="nsew", padx=6, pady=12)

            lbl_ikon = ctk.CTkLabel(
                kart, text=ikon, font=("Courier New", 18), text_color=renk
            )
            lbl_ikon.pack(pady=(16, 2))

            lbl_baslik = ctk.CTkLabel(
                kart, text=baslik, font=FONT_SMALL, text_color=TEXT_MUTED
            )
            lbl_baslik.pack(pady=(0, 16))

            deger_lbl = ctk.CTkLabel(
                kart,
                text="—",
                font=("Courier New", 8),
                text_color=renk,
                wraplength=95,
                justify="center",
            )
            # Not packing deger_lbl directly as requested by the user
            self.bakim_kartlari[baslik] = deger_lbl

            # Tooltip entegrasyonu
            def make_text_func(b=baslik):
                return self.bakim_kartlari[b].cget("text")

            tooltip = ToolTip(kart, make_text_func)
            for widget in (kart, lbl_ikon, lbl_baslik):
                widget.bind("<Enter>", tooltip.show_tip)
                widget.bind("<Leave>", tooltip.hide_tip)

    # ── SAĞ PANEL ──────────────────────────────────────────────────────────
    def _sag_panel_olustur(self):
        sag = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            corner_radius=10,
            border_width=1,
            border_color=BG_BORDER,
        )
        sag.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")

        # ── Logo / Kimlik ────────────────────────────────────────────────
        logo_alan = ctk.CTkFrame(
            sag, fg_color=BG_INSET, corner_radius=0, border_width=0
        )
        logo_alan.pack(fill="x")
        ctk.CTkFrame(logo_alan, height=1, fg_color=BG_BORDER).pack(
            fill="x", side="bottom"
        )

        logo_ic = ctk.CTkFrame(logo_alan, fg_color="transparent")
        logo_ic.pack(padx=16, pady=14)
        ctk.CTkLabel(
            logo_ic,
            text="✿ FLOR·EYE",
            font=("Courier New", 16, "bold"),
            text_color=ACCENT_GREEN,
        ).pack()
        ctk.CTkLabel(
            logo_ic,
            text="Industrial Classification v2.0",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
        ).pack()

        # ── Sistem Kontrol Butonu ────────────────────────────────────────
        kontrol_alan = ctk.CTkFrame(sag, fg_color="transparent")
        kontrol_alan.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            kontrol_alan, text="◈ SİSTEM", font=FONT_HEADING, text_color=TEXT_SECONDARY
        ).pack(anchor="w", pady=(0, 8))

        self.btn_kontrol = ctk.CTkButton(
            kontrol_alan,
            text="▶  SİSTEMİ BAŞLAT",
            font=("Courier New", 11, "bold"),
            fg_color=BG_CARD,
            hover_color=ACCENT_DIM,
            border_width=1,
            border_color=ACCENT_GREEN,
            text_color=ACCENT_GREEN,
            corner_radius=4,
            height=44,
            command=self.sistem_durumunu_yonet_thread,
        )
        self.btn_kontrol.pack(fill="x")

        # Durum çubuğu
        self.durum_serit = ctk.CTkFrame(
            kontrol_alan, height=3, fg_color=BG_BORDER, corner_radius=2
        )
        self.durum_serit.pack(fill="x", pady=(6, 0))
        self.durum_ici = ctk.CTkFrame(
            self.durum_serit, height=3, width=0, fg_color=ACCENT_GREEN, corner_radius=2
        )
        self.durum_ici.place(x=0, y=0, relheight=1, relwidth=0)

        # Ayırıcı
        ctk.CTkFrame(sag, height=1, fg_color=BG_BORDER).pack(fill="x", padx=16, pady=10)

        # ── Analitik Panel ───────────────────────────────────────────────
        analitik_alan = ctk.CTkFrame(sag, fg_color="transparent")
        analitik_alan.pack(fill="both", expand=True, padx=16)
        self.sag_panel = SagKontrolPaneli(analitik_alan)
        self.sag_panel.pack(fill="both", expand=True)

        # Alt imza
        ctk.CTkLabel(
            sag,
            text=f"FLOR·EYE  ©{datetime.now().year}  ESP32-CAM",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
        ).pack(pady=(10, 14))

    # ── AÇILIŞ ANİMASYONU ──────────────────────────────────────────────────
    def _acilis_animasyonu(self):
        """Durum şeridini kademeli olarak doldur"""
        self._animasyon_ilerleme(0)

    def _animasyon_ilerleme(self, adim):
        if adim <= 60:
            oran = adim / 60
            self.durum_ici.place(x=0, y=0, relheight=1, relwidth=oran * 0.2)
            self.after(16, lambda: self._animasyon_ilerleme(adim + 1))

    # ── KAMERA GÖRÜNTÜSÜ ───────────────────────────────────────────────────
    def resmi_yenile(self):
        resim_yolu = "son_cekilen_foto.jpg"
        if os.path.exists(resim_yolu):
            try:
                with Image.open(resim_yolu) as img:
                    img_klon = img.copy()
                # Boyutlandır
                w = self.kamera_cerceve.winfo_width() - 4
                h = self.kamera_cerceve.winfo_height() - 4
                if w > 10 and h > 10:
                    img_klon.thumbnail((w, h), Image.LANCZOS)
                my_img = ctk.CTkImage(
                    light_image=img_klon,
                    dark_image=img_klon,
                    size=(img_klon.width, img_klon.height),
                )
                self.image_display.configure(image=my_img, text="")
                self.image_display.image = my_img
                self.lbl_fps.configure(text="FEED: AKTİF", text_color=ACCENT_GREEN)
            except Exception:
                pass
        self._loop_resim = self.after(1000, self.resmi_yenile)

    # ── JSON BAKIM VERİTABANI ─────────────────────────────────────────────
    # Format: [ {"cicek_adi": "...", "ideal_sicaklik": "...", "isik_konum": "...",
    #             "sulama": "...", "toprak_besin": "...", "budama": "..."}, ... ]
    BAKIM_JSON_YOLU = "flower_information.json"

    def _turkce_temizle(self, metin: str) -> str:
        """Türkçe karakterleri İngilizce karşılıklarına çevirerek eşleşme güvenliği sağlar."""
        if not metin:
            return ""
        donusum = {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "i": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
            "Ç": "c",
            "Ğ": "g",
            "İ": "i",
            "I": "i",
            "Ö": "o",
            "Ş": "s",
            "Ü": "u",
        }
        temiz_metin = "".join(donusum.get(harf, harf) for harf in metin)
        return temiz_metin.lower().strip()

    def _json_oku(self) -> list:
        """JSON listesini oku; hata/yoksa boş liste döndür."""
        try:
            if os.path.exists(self.BAKIM_JSON_YOLU):
                with open(self.BAKIM_JSON_YOLU, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            print(f"❌ [Kritik] JSON Yazma Hatası! Detay: {e}")
        return []

    def _json_yaz(self, liste: list):
        """JSON listesini güvenli yaz (geçici dosya üzerinden)."""
        try:
            gecici = self.BAKIM_JSON_YOLU + ".tmp"
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump(liste, f, ensure_ascii=False, indent=4)
            os.replace(gecici, self.BAKIM_JSON_YOLU)
        except Exception:
            print(f"❌ [Kritik] JSON Yazma Hatası! Detay: {e}")

    def _json_ara(self, tur_adi: str) -> dict | None:
        """
        cicek_adi alanında tam veya kısmi eşleşme ara (büyük/küçük harf yok sayılır).
        Bulunan kaydı döndürür; bulamazsa None.
        """
        aranan = self._turkce_temizle(tur_adi)
        if not aranan:
            return None
        for kayit in self._json_oku():
            if self._turkce_temizle(kayit["cicek_adi"]) == aranan:
                return kayit
        return None

    def _json_tur_ekle(self, tur_adi: str):
        """
        Tür JSON'da yoksa boş iskeletle ekle.
        Varsa dokunma — kullanıcı verileri elle giriyor.
        """
        if self._json_ara(tur_adi):
            return  # zaten var
        liste = self._json_oku()
        liste.append(
            {
                "cicek_adi": tur_adi.capitalize(),
                "ideal_sicaklik": "",
                "isik_konum": "",
                "sulama": "",
                "toprak_besin": "",
                "budama": "",
                "_ilk_gorulme": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        self._json_yaz(liste)

    def _bakim_bilgisi_guncelle(self, tur_adi: str):
        """
        Tespit edilen türün bakım kartlarını JSON'dan doldur.
        Tür JSON'da yoksa arka planda boş iskeletle ekle.
        """
        # Bilinmeyen türse arka planda ekle
        threading.Thread(
            target=self._json_tur_ekle, args=(tur_adi,), daemon=True
        ).start()

        kayit = self._json_ara(tur_adi)

        if kayit:
            sicaklik = kayit.get("ideal_sicaklik", "").strip() or "Bilgi girilmedi"
            isik = kayit.get("isik_konum", "").strip() or "Bilgi girilmedi"
            sulama = kayit.get("sulama", "").strip() or "Bilgi girilmedi"
            toprak = kayit.get("toprak_besin", "").strip() or "Bilgi girilmedi"
            budama = kayit.get("budama", "").strip() or "Bilgi girilmedi"
        else:
            sicaklik = isik = sulama = toprak = "Yeni tür — JSON'a eklendi"

        self.bakim_kartlari["SULAMA"].configure(text=sulama, text_color=ACCENT_TEAL)
        self.bakim_kartlari["IŞIK"].configure(text=isik, text_color=ACCENT_AMBER)
        self.bakim_kartlari["TOPRAK"].configure(text=toprak, text_color=TEXT_PRIMARY)
        self.bakim_kartlari["SICAKLIK"].configure(text=sicaklik, text_color=ACCENT_RED)
        self.bakim_kartlari["BUDAMA"].configure(text=budama, text_color=ACCENT_AMBER)

        if hasattr(self, "lbl_bakim_tur"):
            ad = kayit.get("cicek_adi", tur_adi.upper()) if kayit else tur_adi.upper()
            self.lbl_bakim_tur.configure(text=f"→ {ad.upper()}")

    def sistem_durumunu_yonet_thread(self):
        if not self.sistem_aktif:
            self.btn_kontrol.configure(
                text="◌  BAĞLANILIYOR...",
                border_color=ACCENT_AMBER,
                text_color=ACCENT_AMBER,
            )
        else:
            self.btn_kontrol.configure(
                text="◌  DURDURULUYOR...",
                border_color=ACCENT_AMBER,
                text_color=ACCENT_AMBER,
            )
        threading.Thread(target=self._esp_ile_konus, daemon=True).start()

    def _esp_ile_konus(self):
        import requests

        headers = {"Connection": "close"}
        if not self.sistem_aktif:
            try:
                r = requests.get(f"http://{ESP32_IP}/start", timeout=3, headers=headers)
                if r.status_code == 200:
                    self.sistem_aktif = True
                    self.btn_kontrol.configure(
                        text="■  SİSTEMİ DURDUR",
                        border_color=ACCENT_RED,
                        text_color=ACCENT_RED,
                    )
                    self.durum_ici.place(x=0, y=0, relheight=1, relwidth=1.0)
            except Exception:
                self.btn_kontrol.configure(
                    text="▶  SİSTEMİ BAŞLAT",
                    border_color=ACCENT_GREEN,
                    text_color=ACCENT_GREEN,
                )
        else:
            try:
                r = requests.get(f"http://{ESP32_IP}/stop", timeout=3, headers=headers)
                if r.status_code == 200:
                    self.sistem_aktif = False
                    self.btn_kontrol.configure(
                        text="▶  SİSTEMİ BAŞLAT",
                        border_color=ACCENT_GREEN,
                        text_color=ACCENT_GREEN,
                    )
                    self.durum_ici.place(x=0, y=0, relheight=1, relwidth=0.0)
            except Exception:
                self.btn_kontrol.configure(
                    text="■  SİSTEMİ DURDUR",
                    border_color=ACCENT_RED,
                    text_color=ACCENT_RED,
                )

    # ── VERİTABANI ─────────────────────────────────────────────────────────
    def veritabani_bagla(self):
        try:
            self.conn = sqlite3.connect("cicek_projesi.db", check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()

            self._son_kaydi_goster()
        except Exception as e:
            print("❌ Veritabanı bağlanırken hata oluştu:", e)

    def _son_kaydi_goster(self):
        try:
            conn = sqlite3.connect("cicek_projesi.db", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Önce tablonun var olup olmadığını kontrol et
            cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='Siniflandirma'
        """)

            if not cur.fetchone():
                logging.warning(
                    "Siniflandirma tablosu bulunamadı. Tablo olusturuluyor."
                )
                conn.close()
                return

            cur.execute("""
                SELECT * FROM Siniflandirma ORDER BY rowid DESC LIMIT 1""")
            son = cur.fetchone()
            conn.close()

            if son:
                self._gui_guncelle(son)

            else:
                logging.info("Son kayıt bulunamadı.")

        except Exception as e:
            print(f"son kayıt hatası: {e}")

    def _gui_guncelle(self, son):
        try:
            print("TIP:", type(son))
            print("ICERIK:", son)

            # Eger Row veya sozlukse, isimle eriselim
            if hasattr(son, "keys") or isinstance(son, sqlite3.Row):
                ad = son["cicek_turu"]
                dogruluk = son["dogruluk_orani"]
                sure = son["islem_suresi"]
                manuel = son["manuel_kontrol"]
                tarih = son["tarih"]
            else:
                # Yedek/Fallback (Tuple ise)
                if len(son) == 7:
                    _, ad, dogruluk, sure, manuel, _, tarih = son
                elif len(son) == 6:
                    ad, dogruluk, sure, manuel, _, tarih = son
                else:
                    ad, dogruluk, sure, manuel, tarih = son

            ad = str(ad).upper()
            dogruluk = float(dogruluk)

            if dogruluk <= 1:
                dogr = round(dogruluk * 100, 1)
            else:
                dogr = round(dogruluk, 1)

            mod = "MANUEL" if manuel == 1 else "OTOMATİK"
            saat = str(tarih)[:16] if tarih else "—"

            satir = f"{ad}  |  {sure}s  |  {mod}  |  {saat}"
            self.lbl_telemetri_kompakt.configure(text=satir)

            halka_ciz(self.halka_canvas, dogr, 140, 140, 10)

            self._bakim_bilgisi_guncelle(ad)

        except Exception as e:
            print(f"[HATA] _gui_guncelle: {e}")

    def canli_verileri_guncelle(self):
        """
        Her 1 saniyede veritabanını polling ile kontrol eder.
        Sistem aktif olmasa bile son kaydı gösterir.
        Yeni kayıt varsa GUI'yi günceller.
        """
        try:
            conn = sqlite3.connect("cicek_projesi.db", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
            SELECT * FROM Siniflandirma
            ORDER BY rowid DESC
            LIMIT 1
            """)
            son = cur.fetchone()
            conn.close()

            if son:
                gelen_rowid = son["id"]
                print()

                # Sadece yeni kayıt geldiyse güncelle (gereksiz yeniden çizimi önler)
                if not hasattr(self, "_son_rowid") or self._son_rowid != gelen_rowid:
                    self._son_rowid = gelen_rowid
                    print(f"[BİLGİ] Yeni kayıt → rowid={gelen_rowid}")
                    self._gui_guncelle(son)
            else:
                print("Tablo boş, güncelleme yapılmadı.")

        except sqlite3.Error as e:
            print(f"Canlı Güncelleme DB Hatası: {e}")
        except Exception as e:
            print(f"Canlı Güncelleme Genel Hatası: {e}")

        # Kendini 1 saniye sonra tekrar çağır
        self._loop_veri = self.after(1000, self.canli_verileri_guncelle)

    # ── KAPAT ──────────────────────────────────────────────────────────────
    def pencereyi_kapat(self):
        if self._loop_resim:
            self.after_cancel(self._loop_resim)
        if self._loop_veri:
            self.after_cancel(self._loop_veri)
        try:
            self.conn.close()
        except Exception:
            pass
        self.destroy()


# =============================================================================
if __name__ == "__main__":
    app = FlorEyeDashboard()
    app.mainloop()
