"""Donanim katmani: tum sensorler ve cikislar.

Her bilesen, donanim bagli degilse sistemin geri kalanini kilitlemeden
None/sahte deger dondurecek sekilde hata toleransli yazildi.
"""
import io
import os
import threading
import time
from datetime import datetime

import config


# --- Cikislar: buzzer + LED ---
from gpiozero import Buzzer, LED, MotionSensor

buzzer = Buzzer(config.PIN_BUZZER)
led = LED(config.PIN_LED)
pir = MotionSensor(config.PIN_PIR)


# --- MQ-2 gaz sensoru (DIJITAL DO cikisi, GPIO) ---
# MCP3008 yok; MQ-2'nin dijital DO pini kullaniliyor. Esik modulun
# uzerindeki potansiyometreyle ayarlanir. Cogu modulde gaz algilaninca
# DO LOW olur (active-low); config.MQ2_ACTIVE_LOW ile ayarlanabilir.
try:
    from gpiozero import DigitalInputDevice
    _mq2 = DigitalInputDevice(config.PIN_MQ2_DO, pull_up=None, active_state=False)
except Exception as e:
    print(f"[hardware] MQ-2 DO baslatilamadi: {e}")
    _mq2 = None


def gas_detected():
    """Gaz esigi asildi mi? True/False, hata durumunda None.
    Dijital DO okur; ham pini config.MQ2_ACTIVE_LOW'a gore yorumlar."""
    if _mq2 is None:
        return None
    try:
        high = bool(_mq2.value)  # pinin ham mantik seviyesi (True=HIGH)
        return (not high) if config.MQ2_ACTIVE_LOW else high
    except Exception:
        return None


# --- AM2301 sicaklik + nem (dijital, GPIO4) ---
# AM2301 = DHT22/AM2302 protokolu (kablolu versiyon). Dogrudan GPIO'ya
# baglanir, ADC gerekmez. DHT11'den hassas: ±0.5°C, ±3% nem, ondalikli.
# Cipli karti olmadigi icin DATA-VCC arasi harici 10k pull-up gerekir.
try:
    import board
    import adafruit_dht
    # use_pulseio=False: libgpiod_pulsein helper surecini kullanmaz (saf Python
    # bit-bang). Bu sistemde pulseio yolu surekli OverflowError veriyordu;
    # bit-bang daha kararli ve GPIO4'u kilitleyen yardimci surec olmuyor.
    _dht = adafruit_dht.DHT22(getattr(board, f"D{config.PIN_AM2301}"), use_pulseio=False)
except Exception as e:
    print(f"[hardware] AM2301 baslatilamadi: {e}")
    _dht = None


def read_dht():
    """(sicaklik_C, nem_yuzde) veya (None, None). AM2301 zaman zaman
    okuma hatasi verir; bu normaldir, cagiran taraf son gecerli degeri tutar."""
    if _dht is None:
        return None, None
    try:
        return _dht.temperature, _dht.humidity
    except RuntimeError:
        return None, None
    except Exception:
        return None, None


# --- Kamera (Pi Camera v1.3 / OV5647) - canli MJPEG yayini ---
# Kamera surekli MJPEG yayini yapar. Hem canli izleme (/video_feed) hem
# alarm fotosu hem kullanici snapshot'i ayni akistan beslenir; tek kamera,
# mod degistirmeden, cakisma olmadan.
class _StreamingOutput(io.BufferedIOBase):
    """picamera2 encoder'in yazdigi son JPEG karesini tutar."""
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def writable(self):
        return True

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()
        return len(buf)


stream_output = None
_clip_lock = threading.Lock()
try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder, H264Encoder
    from picamera2.outputs import FileOutput, FfmpegOutput

    _cam = Picamera2()
    # main: canli MJPEG yayini icin; lores (YUV420): donanim H264 klip kaydi icin
    _cfg = _cam.create_video_configuration(
        main={"size": tuple(config.CAM_STREAM_SIZE)},
        lores={"size": tuple(config.CLIP_SIZE), "format": "YUV420"})
    _cam.configure(_cfg)
    stream_output = _StreamingOutput()
    _cam.start_recording(MJPEGEncoder(), FileOutput(stream_output))  # main akis
    time.sleep(1)  # otomatik pozlama otursun
except Exception as e:
    print(f"[hardware] Kamera baslatilamadi: {e}")
    _cam = None


def record_clip(prefix="alarm", seconds=None):
    """Hareket aninda kisa mp4 klip kaydeder (lores akistan donanim H264).
    Canli yayini bozmaz. Dosya adini dondurur, kamera yoksa/zaten kayittaysa None."""
    if _cam is None:
        return None
    if seconds is None:
        seconds = config.CLIP_SECONDS
    if not _clip_lock.acquire(blocking=False):
        return None  # zaten bir klip kaydediliyor
    try:
        filename = datetime.now().strftime(f"{prefix}_%Y%m%d_%H%M%S.mp4")
        path = os.path.join(config.PHOTO_DIR, filename)
        encoder = H264Encoder()
        _cam.start_encoder(encoder, FfmpegOutput(path), name="lores")
        time.sleep(seconds)
        _cam.stop_encoder(encoder)
        return filename
    except Exception as e:
        print(f"[hardware] Klip kaydedilemedi: {e}")
        return None
    finally:
        _clip_lock.release()


def latest_frame(timeout=2.0):
    """Yayindan en guncel JPEG karesini (bytes) dondurur, yoksa None."""
    if stream_output is None:
        return None
    with stream_output.condition:
        if stream_output.frame is None:
            stream_output.condition.wait(timeout=timeout)
        return stream_output.frame


def take_photo(prefix="alarm"):
    """Yayindan anlik kareyi dosyaya yazar, dosya adini dondurur. Kamera yoksa None.
    prefix: 'alarm' (otomatik) veya 'snapshot' (kullanici talebi)."""
    frame = latest_frame()
    if frame is None:
        return None
    filename = datetime.now().strftime(f"{prefix}_%Y%m%d_%H%M%S.jpg")
    path = os.path.join(config.PHOTO_DIR, filename)
    try:
        with open(path, "wb") as f:
            f.write(frame)
        return filename
    except Exception as e:
        print(f"[hardware] Fotograf yazilamadi: {e}")
        return None


def mjpeg_generator():
    """Flask icin multipart MJPEG akisi uretir."""
    if stream_output is None:
        return
    while True:
        with stream_output.condition:
            stream_output.condition.wait()
            frame = stream_output.frame
        if frame is None:
            continue
        yield (b"--FRAME\r\nContent-Type: image/jpeg\r\n"
               b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
               + frame + b"\r\n")


# --- RC522 RFID (SPI CE0, RST=GPIO25) ---
try:
    from mfrc522 import SimpleMFRC522
    _rfid = SimpleMFRC522()
except Exception as e:
    print(f"[hardware] RC522 baslatilamadi (SPI acik mi?): {e}")
    _rfid = None


def read_rfid():
    """Bloklamadan kart okur: kart varsa UID dondurur, yoksa None."""
    if _rfid is None:
        return None
    try:
        uid, _ = _rfid.read_no_block()
        return uid
    except Exception:
        return None
