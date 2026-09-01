"""Flask dashboard - akilli guvenlik sistemi web arayuzu."""
import json
import os
import time

from flask import (Flask, Response, jsonify, render_template, request,
                   send_from_directory)

import config
import database
import hardware
from controller import controller

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/sunum")
def sunum():
    """Gomulu, canli-veri destekli proje sunumu (GuardPi)."""
    return render_template("sunum.html")


# ---------- durum / olaylar ----------

@app.route("/api/status")
def api_status():
    return jsonify(controller.snapshot())


@app.route("/api/events")
def api_events():
    return jsonify(database.get_events(limit=50))


@app.route("/api/stream")
def api_stream():
    """Server-Sent Events: durum degisince aninda gonderir (polling yerine)."""
    def gen():
        last = None
        keep = 0
        while True:
            snap = controller.snapshot()
            payload = json.dumps(snap)
            if payload != last:
                last = payload
                yield f"data: {payload}\n\n"
                keep = 0
            else:
                keep += 1
                if keep >= 30:  # ~15 sn keepalive
                    keep = 0
                    yield ": keep-alive\n\n"
            time.sleep(0.5)
    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- kontrol ----------

@app.route("/api/silence", methods=["POST"])
def api_silence():
    ok = controller.silence("web")
    return jsonify({"silenced": ok})


@app.route("/api/arm", methods=["POST"])
def api_arm():
    armed = bool((request.get_json(silent=True) or {}).get("armed", True))
    return jsonify({"armed": controller.set_armed(armed)})


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        return jsonify({"applied": controller.update_settings(data),
                        "settings": controller.get_settings()})
    return jsonify(controller.get_settings())


@app.route("/api/snapshot", methods=["POST"])
def api_snapshot():
    photo = controller.manual_snapshot()
    return jsonify({"photo": photo, "ok": photo is not None})


# ---------- gecmis / galeri ----------

@app.route("/api/history")
def api_history():
    minutes = request.args.get("minutes", default=180, type=int)
    return jsonify(database.get_readings(minutes=minutes))


@app.route("/api/photos")
def api_photos():
    items = []
    try:
        for fn in os.listdir(config.PHOTO_DIR):
            low = fn.lower()
            if low.endswith(".jpg") or low.endswith(".mp4"):
                p = os.path.join(config.PHOTO_DIR, fn)
                items.append({"file": fn, "mtime": os.path.getmtime(p),
                              "video": low.endswith(".mp4"),
                              "kind": "snapshot" if fn.startswith("snapshot") else "alarm"})
    except OSError:
        pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return jsonify(items[:60])


# ---------- kamera ----------

@app.route("/video_feed")
def video_feed():
    """Canli MJPEG kamera yayini."""
    return Response(hardware.mjpeg_generator(),
                    mimetype="multipart/x-mixed-replace; boundary=FRAME")


@app.route("/photos/<path:filename>")
def photos(filename):
    return send_from_directory(config.PHOTO_DIR, filename)


# ---------- PWA ----------

@app.route("/manifest.webmanifest")
def manifest():
    return jsonify({
        "name": "Akilli Guvenlik Sistemi",
        "short_name": "Guvenlik",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#2563eb",
        "icons": [{"src": "/static/icon.svg", "sizes": "any",
                   "type": "image/svg+xml", "purpose": "any maskable"}],
    })


@app.route("/sw.js")
def service_worker():
    sw = (
        "self.addEventListener('install',e=>self.skipWaiting());\n"
        "self.addEventListener('activate',e=>self.clients.claim());\n"
        "self.addEventListener('fetch',e=>{});\n"
    )
    return Response(sw, mimetype="application/javascript")


if __name__ == "__main__":
    controller.start()
    # use_reloader=False: reloader sureci ikiye katlar, GPIO iki kez acilir
    app.run(host=config.WEB_HOST, port=config.WEB_PORT,
            threaded=True, use_reloader=False)
