#!/usr/bin/env python3
"""Tek tek bilesen testi.

Kullanim:
    python test_donanim.py led       # LED 3 kez yakip sondurur
    python test_donanim.py buzzer    # Buzzer 2 kez kisa oter
    python test_donanim.py pir       # 15 sn hareket bekler
    python test_donanim.py sicaklik  # AM2301 sicaklik/nem okur (GPIO4)
    python test_donanim.py gaz       # MQ-2 gaz seviyesi (5 okuma)
    python test_donanim.py rfid      # 15 sn kart bekler
    python test_donanim.py kamera    # Tek foto ceker
    python test_donanim.py hepsi     # Sirayla ozet
"""
import sys
import time


def test_led():
    from gpiozero import LED
    import config
    led = LED(config.PIN_LED)
    print(f"LED (GPIO{config.PIN_LED}) 3 kez yanip sonecek...")
    for i in range(3):
        led.on(); print(f"  {i+1}: ACIK"); time.sleep(0.5)
        led.off(); time.sleep(0.5)
    print("OK -> LED yandiysa baglanti dogru.")


def test_buzzer():
    from gpiozero import Buzzer
    import config
    bz = Buzzer(config.PIN_BUZZER)
    print(f"Buzzer (GPIO{config.PIN_BUZZER}) 2 kez otecek...")
    for i in range(2):
        bz.on(); print(f"  {i+1}: bip"); time.sleep(0.3)
        bz.off(); time.sleep(0.3)
    print("OK -> Ses duyduysan baglanti dogru.")


def test_pir():
    from gpiozero import MotionSensor
    import config
    pir = MotionSensor(config.PIN_PIR)
    print(f"PIR (GPIO{config.PIN_PIR}) - 15 sn icinde elini sallayarak hareket olustur...")
    t0 = time.time()
    while time.time() - t0 < 15:
        if pir.motion_detected:
            print("  >>> HAREKET ALGILANDI! OK")
            return
        time.sleep(0.1)
    print("  Hareket algilanmadi. (Kablo/potansiyometre/gecikme kontrol et)")


def test_sicaklik():
    import board, adafruit_dht, config
    dht = adafruit_dht.DHT22(getattr(board, f"D{config.PIN_AM2301}"))
    print(f"AM2301 (GPIO{config.PIN_AM2301}) okunuyor (birkac deneme)...")
    for i in range(6):
        try:
            t = dht.temperature; h = dht.humidity
            if t is not None and h is not None:
                print(f"  OK -> Sicaklik: {t:.1f} C, Nem: {h:.1f} %")
                return
        except RuntimeError as e:
            print(f"  deneme {i+1}: gecici okuma hatasi ({e}) - normal, tekrar deniyorum")
        time.sleep(2)
    print("  Okuma basarisiz. (VCC=3.3V, DATA->GPIO4, 10k pull-up kontrol et)")


def test_gaz():
    from gpiozero import DigitalInputDevice
    import config
    mq2 = DigitalInputDevice(config.PIN_MQ2_DO, pull_up=None, active_state=False)
    print(f"MQ-2 DO (GPIO{config.PIN_MQ2_DO}) - 10 okuma (active_low={config.MQ2_ACTIVE_LOW}):")
    for i in range(10):
        high = bool(mq2.value)
        alert = (not high) if config.MQ2_ACTIVE_LOW else high
        print(f"  {i+1}: ham_pin={'HIGH' if high else 'LOW'}  ->  {'>>> GAZ!' if alert else 'normal'}")
        time.sleep(1)
    print("OK -> Cakmak gazi/duman yaklastirinca durum 'GAZ!'a donmeli.")
    print("     Donmuyorsa modulun potansiyometresini ayarla; ters calisiyorsa")
    print("     config.MQ2_ACTIVE_LOW degerini degistiririz.")


def test_rfid():
    from mfrc522 import SimpleMFRC522
    rfid = SimpleMFRC522()
    print("RC522 - 15 sn icinde karti okuyucuya yaklastir...")
    t0 = time.time()
    while time.time() - t0 < 15:
        uid, _ = rfid.read_no_block()
        if uid:
            print(f"  >>> KART OKUNDU! UID: {uid}  OK")
            return
        time.sleep(0.2)
    print("  Kart okunamadi. (3.3V mi? SDA->CE0, RST->GPIO25 kontrol et)")


def test_kamera():
    from picamera2 import Picamera2
    import config, os
    from datetime import datetime
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1296, 972)}))
    cam.start(); time.sleep(1)
    fn = datetime.now().strftime("test_%Y%m%d_%H%M%S.jpg")
    path = os.path.join(config.PHOTO_DIR, fn)
    cam.capture_file(path)
    print(f"OK -> Foto cekildi: {path}")


TESTS = {
    "led": test_led, "buzzer": test_buzzer, "pir": test_pir,
    "sicaklik": test_sicaklik, "gaz": test_gaz, "rfid": test_rfid, "kamera": test_kamera,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in (*TESTS, "hepsi"):
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    targets = TESTS.keys() if arg == "hepsi" else [arg]
    for name in targets:
        print(f"\n--- {name.upper()} ---")
        try:
            TESTS[name]()
        except Exception as e:
            print(f"  HATA: {e}")


if __name__ == "__main__":
    main()
