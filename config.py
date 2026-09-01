# Akilli Guvenlik Sistemi - Yapilandirma

# --- GPIO Pinleri (BCM numaralandirma) ---
PIN_PIR = 17        # HC-SR501 hareket sensoru
PIN_BUZZER = 27     # Aktif buzzer
PIN_LED = 22        # Kirmizi LED
PIN_AM2301 = 4      # AM2301 sicaklik/nem (DHT22 protokolu, dijital, GPIO4)
PIN_MQ2_DO = 23     # MQ-2 gaz sensoru dijital cikis (DO, GPIO23)

# --- SPI cihazlari ---
# RC522: SPI0, CS = CE0 (GPIO8), RST = GPIO25 (mfrc522 varsayilani).
# (MCP3008 KULLANILMIYOR: AM2301 ve MQ-2 dijital oldugu icin ADC gerekmiyor.)

# --- MQ-2 dijital cikis ayari ---
# Cogu MQ-2 modulunde gaz esigi asilinca DO pini LOW olur (active-low).
# Ters davranan modul olursa bunu False yap.
MQ2_ACTIVE_LOW = True

# Histerezis / titreme onleme (yazilim ince ayari):
# DO tam esik kenarinda titreyebilir. Anlik parazitin alarm vermesini onlemek
# icin ust uste belli sayida ayni okuma gerekir. MQ2_READ_INTERVAL=1sn ile:
GAS_ON_COUNT = 3    # ust uste 3 'gaz' okumasi -> uyari ver (~3 sn dogrulama)
GAS_OFF_COUNT = 6   # ust uste 6 'normal' okumasi -> uyariyi kaldir (~6 sn)

# --- Kamera ---
# Canli yayin + snapshot icin MJPEG cozunurlugu. Pi 3B+ ve hotspot agi icin
# 1296x972 dengeli; ag yavassa (640,480) yap, daha akici olur.
CAM_STREAM_SIZE = (1296, 972)

# Hareket aninda kaydedilen kisa video klip (donanim H264 -> mp4).
CLIP_ON_MOTION = True       # alarm aninda foto yerine kisa video kaydet
CLIP_SECONDS = 8            # klip suresi (saniye)
CLIP_SIZE = (640, 480)      # klip cozunurlugu (lores YUV420 akisi; 64'un kati olmali)

# --- Esik / okuma araliklari ---
TEMP_READ_INTERVAL = 3.0  # saniye (AM2301 okuma araligi)
MQ2_READ_INTERVAL = 1.0
RFID_POLL_INTERVAL = 0.3
ALARM_REARM_DELAY = 10.0 # alarm susturulduktan sonra PIR'in tekrar tetikleyebilmesi icin bekleme
READING_LOG_INTERVAL = 30.0  # saniye - sensor verisini SQLite gecmisine yazma araligi

# --- Yangin / asiri isi algilama (AM2301 sicakligi uzerinden) ---
# Iki tetikleyici: mutlak esik VE ani artis (rate-of-rise). Ikincisi daha akilli;
# oda serin olsa bile sicaklik hizla artiyorsa yangin isaretidir (ates testi bunu tetikler).
FIRE_DETECTION = True
FIRE_TEMP_THRESHOLD = 50.0   # mutlak sicaklik (°C) ustu = yangin
FIRE_RISE_THRESHOLD = 4.0    # FIRE_RISE_WINDOW icinde bu kadar ani artis (°C) = yangin
FIRE_RISE_WINDOW = 20.0      # saniye - artis penceresi
FIRE_CLEAR_TEMP = 38.0       # bu sicakligin altina inince yangin durumu temizlenir (histerezis)

# --- Dosya yollari ---
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "security.db")
PHOTO_DIR = os.path.join(BASE_DIR, "photos")

# --- Web ---
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
