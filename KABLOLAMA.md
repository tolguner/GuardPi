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

## 2. DHT22
| DHT22 | Bağlantı |
|---|---|
| VCC (+) | 3.3V |
| DATA | **GPIO4** (fiziksel 7) |
| GND (−) | GND |

DATA ile VCC arasına **10kΩ pull-up direnci** bağla (bazı modül kartlarında dahili vardır, çıplak sensörde şarttır).

## 3. MCP3008 + MQ-2 (SPI, CS=CE1)
MCP3008 çentiği sola bakacak şekilde (pin 1 sol üst):

| MCP3008 pin | Bağlantı |
|---|---|
| 16 VDD | 3.3V |
| 15 VREF | 3.3V |
| 14 AGND | GND |
| 13 CLK | **GPIO11 / SCLK** (fiziksel 23) |
| 12 DOUT | **GPIO9 / MISO** (fiziksel 21) |
| 11 DIN | **GPIO10 / MOSI** (fiziksel 19) |
| 10 CS | **GPIO7 / CE1** (fiziksel 26) |
| 9 DGND | GND |
| 1 CH0 | MQ-2 **AO** çıkışı |

MQ-2 modülü: VCC → **5V**, GND → GND, **AO** → MCP3008 CH0. (DO çıkışı kullanılmıyor.)
⚠️ MQ-2 ısıtıcısı ilk açılışta ~24 saat "yanma" (burn-in) ister; ilk gün değerler kayar, normaldir. AO çıkışı 5V'a kadar çıkabilir — VREF 3.3V olduğundan okuma 1.0'da doyar, sorun değil ama istersen AO'yu gerilim bölücüyle (örn. 2k2/3k3) düşürebilirsin.

## 4. RC522 RFID (SPI, CS=CE0)
> Not: Projede "CS=GPIO25" yazmıştın — standart `mfrc522` kütüphanesinde **SDA(CS) → CE0 (GPIO8)** ve **RST → GPIO25** kullanılır. GPIO25 RST pinidir; bu rehber kütüphane varsayılanına göredir.

| RC522 | Bağlantı |
|---|---|
| SDA | **GPIO8 / CE0** (fiziksel 24) |
| SCK | **GPIO11 / SCLK** (fiziksel 23) — MCP3008 ile ortak |
| MOSI | **GPIO10 / MOSI** (fiziksel 19) — ortak |
| MISO | **GPIO9 / MISO** (fiziksel 21) — ortak |
| IRQ | boş |
| GND | GND |
| RST | **GPIO25** (fiziksel 22) |
| 3.3V | **3.3V** (⚠️ asla 5V verme!) |

SPI hattı (SCK/MOSI/MISO) iki cihaz arasında paylaşılır; yalnızca CS pinleri ayrıdır (RC522→CE0, MCP3008→CE1).

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
