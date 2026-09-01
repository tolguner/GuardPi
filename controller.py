"""Sistem kontrolcusu: sensor dongusu, alarm durumu, ayarlar ve olay mantigi."""
import threading
import time
from collections import deque

import config
import database
import hardware


class SecurityController:
    # Ayarlanabilir degerler ve config'teki varsayilanlari
    SETTING_DEFAULTS = {
        "armed": True,
        "gas_on_count": config.GAS_ON_COUNT,
        "gas_off_count": config.GAS_OFF_COUNT,
        "rearm_delay": config.ALARM_REARM_DELAY,
    }

    def __init__(self):
        self.lock = threading.Lock()
        self.settings = dict(self.SETTING_DEFAULTS)
        self.state = {
            "temperature": None,
            "humidity": None,
            "gas": None,
            "gas_alert": False,
            "alarm": False,
            "fire": False,
            "temp_rate": 0.0,
            "armed": True,
            "last_motion": None,
            "last_photo": None,
            "silenced_by": None,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._alarm_event = threading.Event()
        self._rearm_until = 0.0
        self._temp_hist = deque()  # (zaman, sicaklik) - rate-of-rise icin

    # ---------- yasam dongusu ----------

    def start(self):
        database.init_db()
        self._load_settings()
        database.purge_old_readings(days=7)
        database.log_event("system", "Sistem baslatildi")
        hardware.pir.when_motion = self._on_motion
        for fn in (self._dht_loop, self._mq2_loop, self._rfid_loop,
                   self._alarm_loop, self._reading_loop):
            threading.Thread(target=fn, daemon=True).start()

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    # ---------- ayarlar ----------

    def _load_settings(self):
        """DB'den ayarlari yukler, yoksa varsayilani yazar."""
        for key, default in self.SETTING_DEFAULTS.items():
            raw = database.get_setting(key)
            if raw is None:
                database.set_setting(key, int(default) if isinstance(default, bool) else default)
                val = default
            else:
                val = self._coerce(key, raw, default)
            self.settings[key] = val
        with self.lock:
            self.state["armed"] = bool(self.settings["armed"])

    @staticmethod
    def _coerce(key, raw, default):
        try:
            if isinstance(default, bool):
                return str(raw) in ("1", "True", "true")
            if isinstance(default, int):
                return int(float(raw))
            if isinstance(default, float):
                return float(raw)
        except (ValueError, TypeError):
            return default
        return raw

    def get_settings(self):
        return dict(self.settings)

    def update_settings(self, new):
        """Dashboard'dan gelen ayarlari uygular ve kalici yazar."""
        applied = {}
        for key, default in self.SETTING_DEFAULTS.items():
            if key in new:
                val = self._coerce(key, new[key], default)
                self.settings[key] = val
                database.set_setting(key, int(val) if isinstance(default, bool) else val)
                applied[key] = val
        if "armed" in applied:
            with self.lock:
                self.state["armed"] = bool(applied["armed"])
        database.log_event("system", f"Ayar guncellendi: {applied}")
        return applied

    def set_armed(self, armed):
        armed = bool(armed)
        self.settings["armed"] = armed
        database.set_setting("armed", int(armed))
        with self.lock:
            self.state["armed"] = armed
            # kurarken bekleyen alarmi temizle degil; kapatirken alarmi sustur
            if not armed and self.state["alarm"]:
                self.state["alarm"] = False
                self._alarm_event.clear()
        database.log_event("system", "Sistem KURULDU" if armed else "Sistem KAPATILDI (disarm)")
        return armed

    # ---------- alarm ----------

    def _on_motion(self):
        now = time.time()
        with self.lock:
            if not self.state["armed"]:
                self.state["last_motion"] = time.strftime("%H:%M:%S")
                return
            if self.state["alarm"] or now < self._rearm_until:
                return
            self.state["alarm"] = True
            self.state["silenced_by"] = None
            self.state["last_motion"] = time.strftime("%H:%M:%S")
        database.log_event("motion", "PIR hareket algiladi - ALARM")
        self._alarm_event.set()

        # Kamera kaydini ayri thread'de yap (klip ~saniyelerce surer, callback'i bloklamasin)
        threading.Thread(target=self._capture_evidence, daemon=True).start()

    def _capture_evidence(self):
        """Alarm kaniti: CLIP_ON_MOTION ise kisa video, degilse foto."""
        if config.CLIP_ON_MOTION:
            media = hardware.record_clip(prefix="alarm")
            fail_msg = "Klip kaydedilemedi (kamera yok?)"
        else:
            media = hardware.take_photo()
            fail_msg = "Fotograf cekilemedi (kamera yok?)"
        if media:
            with self.lock:
                self.state["last_photo"] = media
            database.log_event("photo", media)
        else:
            database.log_event("photo", fail_msg)

    def manual_snapshot(self):
        """Kullanici talebiyle anlik foto ceker, durumu ve logu gunceller."""
        photo = hardware.take_photo(prefix="snapshot")
        if photo:
            with self.lock:
                self.state["last_photo"] = photo
            database.log_event("photo", f"Manuel snapshot: {photo}")
        return photo

    def silence(self, who):
        """Alarmi susturur. who: 'web' veya kart sahibinin adi."""
        with self.lock:
            if not self.state["alarm"]:
                return False
            self.state["alarm"] = False
            self.state["silenced_by"] = who
            self._rearm_until = time.time() + float(self.settings["rearm_delay"])
            # Yangin/duman aktifse siren susmaz (gercek tehlike, susturulamaz)
            if not self.state["fire"] and not self.state["gas_alert"]:
                self._alarm_event.clear()
        database.log_event("silence", f"Alarm susturuldu: {who}")
        return True

    def _alarm_loop(self):
        """Alarm aktifken buzzer ve LED'i 0.25 sn araliklarla yakip sondurur."""
        while True:
            self._alarm_event.wait()
            while self._alarm_event.is_set():
                hardware.buzzer.on()
                hardware.led.on()
                time.sleep(0.25)
                hardware.buzzer.off()
                hardware.led.off()
                time.sleep(0.25)
            hardware.buzzer.off()
            hardware.led.off()

    # ---------- sensor donguleri ----------

    def _dht_loop(self):
        while True:
            temp, hum = hardware.read_dht()
            if temp is not None:
                with self.lock:
                    self.state["temperature"] = round(temp, 1)
                    if hum is not None:
                        self.state["humidity"] = round(hum, 1)
                self._check_fire(temp)
            time.sleep(config.TEMP_READ_INTERVAL)

    # ---------- yangin / asiri isi ----------

    def _check_fire(self, temp):
        """Sicaklik esigi VE ani artis (rate-of-rise) ile yangin tespiti."""
        if not config.FIRE_DETECTION:
            return
        now = time.time()
        self._temp_hist.append((now, temp))
        while self._temp_hist and now - self._temp_hist[0][0] > config.FIRE_RISE_WINDOW:
            self._temp_hist.popleft()
        rate = temp - self._temp_hist[0][1] if self._temp_hist else 0.0
        with self.lock:
            self.state["temp_rate"] = round(rate, 1)
            fire = self.state["fire"]
        hot = temp >= config.FIRE_TEMP_THRESHOLD
        rising = rate >= config.FIRE_RISE_THRESHOLD
        if not fire and (hot or rising):
            self._trigger_fire(temp, rate, hot, rising)
        elif fire and temp < config.FIRE_CLEAR_TEMP and not rising:
            self._clear_fire(temp)

    def _trigger_fire(self, temp, rate, hot, rising):
        reason = []
        if hot:
            reason.append(f"sicaklik {temp}°C")
        if rising:
            reason.append(f"ani artis +{rate:.1f}°C/{int(config.FIRE_RISE_WINDOW)}sn")
        with self.lock:
            self.state["fire"] = True
            self._alarm_event.set()  # siren (kur/kapat'tan bagimsiz - guvenlik)
        database.log_event("fire", "YANGIN / ASIRI ISI! " + ", ".join(reason))
        threading.Thread(target=self._capture_evidence, daemon=True).start()

    def _clear_fire(self, temp):
        with self.lock:
            self.state["fire"] = False
            if not self.state["alarm"] and not self.state["gas_alert"]:
                self._alarm_event.clear()
        database.log_event("fire", f"Yangin/isi riski gecti (sicaklik {temp}°C)")

    def _mq2_loop(self):
        """MQ-2 DO'yu histerezisle okur (ayarlanabilir GAS_ON/OFF_COUNT)."""
        on = off = 0
        while True:
            raw = hardware.gas_detected()
            if raw is not None:
                if raw:
                    on += 1; off = 0
                else:
                    off += 1; on = 0
                cur = self.state["gas_alert"]
                new = cur
                if not cur and on >= int(self.settings["gas_on_count"]):
                    new = True
                elif cur and off >= int(self.settings["gas_off_count"]):
                    new = False
                changed = new != cur
                with self.lock:
                    self.state["gas_alert"] = new
                    self.state["gas"] = "Yuksek" if new else "Normal"
                    if changed and new:
                        self._alarm_event.set()  # duman = yangin/tehlike -> siren
                    elif changed and not new and not self.state["alarm"] and not self.state["fire"]:
                        self._alarm_event.clear()
                if changed and new:
                    database.log_event("gas", "DUMAN/GAZ algilandi (MQ-2, dogrulandi) - tehlike")
                    threading.Thread(target=self._capture_evidence, daemon=True).start()
                elif changed:
                    database.log_event("gas", "Gaz seviyesi normale dondu")
            time.sleep(config.MQ2_READ_INTERVAL)

    def _rfid_loop(self):
        while True:
            uid = hardware.read_rfid()
            if uid is not None:
                name = database.is_authorized(uid)
                if name:
                    if not self.silence(f"RFID: {name}"):
                        database.log_event("rfid", f"Yetkili kart okundu: {name} ({uid})")
                    time.sleep(2)
                else:
                    database.log_event("rfid", f"YETKISIZ kart denemesi: {uid}")
                    time.sleep(2)
            time.sleep(config.RFID_POLL_INTERVAL)

    def _reading_loop(self):
        """Sensor verisini periyodik olarak SQLite'a yazar (grafik gecmisi)."""
        while True:
            time.sleep(config.READING_LOG_INTERVAL)
            with self.lock:
                t, h, g = self.state["temperature"], self.state["humidity"], self.state["gas_alert"]
            if t is not None or h is not None:
                database.log_reading(t, h, g)


controller = SecurityController()
