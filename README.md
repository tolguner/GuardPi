<div align="center">

# GuardPi

**Raspberry Pi 3B+ üzerinde çalışan, çok sensörlü akıllı güvenlik ve erken uyarı sistemi.**

Hareket algılama · Yangın/gaz erken uyarı · RFID ile alarm susturma · Canlı kamera akışı · Web kontrol paneli

![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3B%2B-C51A4A?logo=raspberrypi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![systemd](https://img.shields.io/badge/systemd-FCC624?logo=linux&logoColor=black)

</div>

---

## Ne yapıyor

GuardPi, bir odayı veya küçük bir mekânı sürekli izleyen gömülü bir güvenlik düğümüdür.
Beş sensörü tek bir olay döngüsünde birleştirir, kararı yerel olarak verir ve sonucu
hem fiziksel uyarıya (buzzer + LED) hem de bir web paneline yansıtır.

- **Hareket** — PIR sensörü tetiklendiğinde buzzer ve LED devreye girer, kamera olay anını
  kısa bir video klip olarak kaydeder, panel kırmızı alarm durumuna geçer.
- **Yangın** — sıcaklık mutlak eşiği (50 °C) aşarsa **veya** 20 saniyelik pencerede 4 °C'den
  hızlı yükselirse yangın uyarısı verir. Histerezisle (38 °C) titreşim engellenir.
- **Gaz** — MQ-2 okuması üst üste 3 kez pozitif gelirse uyarı verir, 6 kez normal gelirse kaldırır.
  Tek örneklik gürültü alarm üretmez.
- **Yetkilendirme** — alarm yalnızca kayıtlı bir RFID kartla veya paneldeki butonla susturulur.
  Susturma sonrası 10 saniyelik yeniden kurulma gecikmesi vardır.
- **Kayıt** — tüm olaylar (`motion`, `photo`, `silence`, `gas`, `rfid`, `system`) zaman
  damgasıyla SQLite'a yazılır; sensör geçmişi 30 saniyede bir loglanır.

## Donanım

| Bileşen | Model | Bağlantı |
|---------|-------|----------|
| Kart | Raspberry Pi 3B+ | — |
| Hareket sensörü | HC-SR501 (PIR) | GPIO17 |
| Sıcaklık/nem | AM2301 (DHT22 protokolü) | GPIO4 |
| Gaz sensörü | MQ-2 | GPIO23 (dijital çıkış) |
| RFID okuyucu | MFRC522 | SPI (CE0) |
| Kamera | Pi Camera | CSI |
| Uyarı | Aktif buzzer + LED | GPIO27 / GPIO22 |

Pin bağlantılarının tam şeması ve breadboard yerleşimi: **[KABLOLAMA.md](KABLOLAMA.md)**

## Mimari

```
                 ┌──────────────┐
   PIR ─────────►│              │
   AM2301 ──────►│ hardware.py  │  donanım soyutlama katmanı
   MQ-2 ────────►│ (GPIO/SPI)   │  (tüm sensör ve çıkış erişimi burada)
   MFRC522 ─────►│              │
   Kamera ──────►└──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │controller.py │  sensör döngüleri, alarm durum makinesi,
                 │              │  yangın/gaz doğrulama mantığı
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
   ┌──────▼─────┐ ┌─────▼──────┐ ┌────▼─────────┐
   │ app.py     │ │database.py │ │ buzzer + LED │
   │ Flask API  │ │ SQLite     │ │ fiziksel     │
   │ + dashboard│ │ olay logu  │ │ uyarı        │
   └────────────┘ └────────────┘ └──────────────┘
```

Donanım erişimi tek bir katmanda toplanmıştır (`hardware.py`); kontrol mantığı (`controller.py`)
sensörlerin fiziksel detayını bilmez. Bu ayrım sayesinde eşikler ve pinler yalnızca
`config.py` üzerinden değiştirilebilir.

| Dosya | Sorumluluk |
|-------|-----------|
| `app.py` | Flask web sunucusu — dashboard, canlı kamera akışı, REST uçları |
| `controller.py` | Sensör döngüleri, alarm durum makinesi, yangın/gaz karar mantığı |
| `hardware.py` | Donanım katmanı — GPIO, SPI, kamera, RFID erişimi |
| `database.py` | SQLite olay logu ve yetkili kart tablosu |
| `config.py` | Pin tanımları, eşik değerleri, zamanlama ayarları |
| `enroll_card.py` | Yetkili RFID kartı kaydetme aracı |
| `test_donanim.py` | Donanım doğrulama betiği |
| `smart-security.service` | systemd birimi (açılışta otomatik başlatma) |

## Kurulum

> Bu proje **Raspberry Pi OS** üzerinde çalışır. `RPi.GPIO`, `picamera2` ve `spidev`
> fiziksel donanım gerektirdiğinden masaüstü bir işletim sisteminde çalıştırılamaz.

```bash
# 1. SPI arayüzünü etkinleştir (bir kez)
sudo raspi-config nonint do_spi 0 && sudo reboot

# 2. Bağımlılıklar
python -m venv venv
./venv/bin/pip install -r requirements.txt

# 3. Yetkili RFID kartı kaydet (kart başına bir kez)
./venv/bin/python enroll_card.py "Kart Sahibi"

# 4. Başlat
./venv/bin/python app.py
```

Panel: `http://<pi-ip>:5000`

**Açılışta otomatik başlatma:**

```bash
sudo cp smart-security.service /etc/systemd/system/
sudo systemctl enable --now smart-security
```

## Ayarlanabilir eşikler

Tümü `config.py` içinde:

| Ayar | Varsayılan | Anlamı |
|------|-----------|--------|
| `FIRE_TEMP_THRESHOLD` | 50 °C | Mutlak yangın sıcaklığı |
| `FIRE_RISE_THRESHOLD` | 4 °C | Ani artış eşiği |
| `FIRE_RISE_WINDOW` | 20 sn | Artışın ölçüldüğü pencere |
| `FIRE_CLEAR_TEMP` | 38 °C | Histerezis — alarmın kalkma sıcaklığı |
| `GAS_ON_COUNT` / `GAS_OFF_COUNT` | 3 / 6 | Gaz uyarısı için ardışık okuma sayısı |
| `ALARM_REARM_DELAY` | 10 sn | Susturma sonrası yeniden kurulma gecikmesi |
| `CLIP_SECONDS` | 8 sn | Alarm anında kaydedilen klip süresi |

## Belgeler

- **[KABLOLAMA.md](KABLOLAMA.md)** — pin pin fiziksel bağlantı rehberi
- **[GuardPi_Rapor.docx](GuardPi_Rapor.docx)** — proje raporu
- **[GuardPi Afiş.pdf](GuardPi%20Afi%C5%9F.pdf)** — proje afişi

> Demo videosu (110 MB) GitHub'ın dosya boyutu sınırını aştığı için depoya dahil edilmemiştir.

## Proje bilgisi

Işık Üniversitesi · Yönetim Bilişim Sistemleri · dönem projesi · 2026
