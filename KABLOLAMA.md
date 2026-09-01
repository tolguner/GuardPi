# Fiziksel Kablolama Rehberi — Raspberry Pi 3B+

> Tüm pin numaraları **BCM (GPIO)** numarasıdır; parantez içindekiler fiziksel pin numarasıdır.
> Kablolama yaparken Pi **kapalı** olsun!

## Güç rayları (breadboard)
- Pi **5V** (fiziksel 2) → breadboard 5V rayı
- Pi **3.3V** (fiziksel 1) → breadboard 3.3V rayı
- Pi **GND** (fiziksel 6, 9, 14...) → breadboard GND rayı

## 1. PIR HC-SR501
| HC-SR501 | Bağlantı |
|---|---|
| VCC | 5V |
| OUT | **GPIO17** (fiziksel 11) |
| GND | GND |

Çıkış 3.3V seviyesindedir, direnç gerekmez. Modül üstündeki iki potansiyometre: hassasiyet ve gecikme — ikisini de saat yönünün tersine (minimuma) çevirerek başla.

## 2. AM2301 (DHT22 protokolu)
| AM2301 | Bağlantı |
|---|---|
| VCC (+) | 3.3V |
| DATA | **GPIO4** (fiziksel 7) |
| GND (−) | GND |

DATA ile VCC arasına **10kΩ pull-up direnci** bağla (bazı modül kartlarında dahili vardır, çıplak sensörde şarttır).

## 3. MQ-2 Gaz Sensörü (dijital DO)

| MQ-2 modülü | Bağlantı |
|---|---|
| VCC | **5V** |
| GND | GND |
| **DO** (dijital çıkış) | **GPIO23** (fiziksel 16) |
| AO (analog çıkış) | kullanılmıyor — boşta bırak |

Modül üzerindeki potansiyometre eşiği belirler: gaz eşiği aştığında **DO LOW** olur
(active-low). Bu davranış `config.MQ2_ACTIVE_LOW` ile değiştirilebilir.

Yazılım tarafında ADC **kullanılmaz**; `hardware.py` DO pinini doğrudan
`gpiozero.DigitalInputDevice` ile okur. Tek örneklik gürültünün alarm üretmemesi için
üst üste `GAS_ON_COUNT` (3) pozitif okuma aranır, `GAS_OFF_COUNT` (6) normal okumada
uyarı kalkar.

⚠️ MQ-2 ısıtıcısı ilk açılışta ~24 saat "yanma" (burn-in) ister; ilk gün eşik kayabilir,
bu normaldir. Potansiyometreyi burn-in sonrası ayarla.

> **Not:** Projenin ilk tasarımında MQ-2'nin analog çıkışı (AO) bir MCP3008 ADC üzerinden
> okunuyordu. Dijital DO çıkışı ihtiyacı karşıladığı için MCP3008 devreden çıkarıldı;
> artık ne devrede ne de kodda yer alıyor.

## 4. RC522 RFID (SPI, CS=CE0)
> Not: Projede "CS=GPIO25" yazmıştın — standart `mfrc522` kütüphanesinde **SDA(CS) → CE0 (GPIO8)** ve **RST → GPIO25** kullanılır. GPIO25 RST pinidir; bu rehber kütüphane varsayılanına göredir.

| RC522 | Bağlantı |
|---|---|
| SDA | **GPIO8 / CE0** (fiziksel 24) |
| SCK | **GPIO11 / SCLK** (fiziksel 23) |
| MOSI | **GPIO10 / MOSI** (fiziksel 19) — ortak |
| MISO | **GPIO9 / MISO** (fiziksel 21) — ortak |
| IRQ | boş |
| GND | GND |
| RST | **GPIO25** (fiziksel 22) |
| 3.3V | **3.3V** (⚠️ asla 5V verme!) |

RC522 tek SPI cihazıdır; CS olarak CE0 (GPIO8) kullanılır. SPI0 hattındaki CE1 (GPIO7) boştadır.

## 5. Buzzer (aktif) ve LED
| Bileşen | Bağlantı |
|---|---|
| Buzzer (+) | **GPIO27** (fiziksel 13) |
| Buzzer (−) | GND |
| LED anot (+, uzun bacak) | **GPIO22** (fiziksel 15) → **330Ω direnç** üzerinden |
| LED katot (−) | GND |

Aktif buzzer 3.3V GPIO'dan doğrudan sürülebilir (küçük olanlar ~15-20mA). Ses zayıfsa NPN transistör (2N2222) + 1kΩ baz direnciyle 5V'tan sür.

## 6. Kamera Modülü v2
- Pi **kapalıyken** tak. CSI konnektörü (HDMI ile ethernet arasındaki) mandalını yukarı çek, şerit kabloyu **mavi taraf ethernet portuna bakacak** şekilde tak, mandalı bastır.
- Kontrol: `rpicam-hello --list-cameras`

## Yazılım öncesi yapılacaklar
```bash
# SPI'yı aç (kalıcı) — bunu senin çalıştırman gerekiyor:
sudo raspi-config nonint do_spi 0
# veya: sudo sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' /boot/firmware/config.txt
sudo reboot
```
Reboot sonrası `ls /dev/spidev*` → `spidev0.0` ve `spidev0.1` görünmeli.
