import os
import json
import time
import shutil
import subprocess
import threading
import requests
import urllib.request
import urllib.parse
from datetime import datetime
from PIL import Image
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context, abort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "music")
STATIC_DIR = os.path.join(BASE_DIR, "static")
MESSAGES_FILE = os.path.join(BASE_DIR, "messages.json")

app = Flask(__name__, static_folder=STATIC_DIR)

# Initialize messages file if not exists
if not os.path.exists(MESSAGES_FILE):
    initial_messages = [
        {
            "id": 1,
            "author": "系統管理員",
            "content": "歡迎使用 iPhone 4s 專屬復古智慧儀表板！",
            "time": datetime.now().strftime("%m/%d %H:%M")
        },
        {
            "id": 2,
            "author": "Antigravity",
            "content": "時鐘、氣象、大盤指數與自建音樂播放已全數就緒。",
            "time": datetime.now().strftime("%m/%d %H:%M")
        }
    ]
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_messages, f, ensure_ascii=False, indent=2)

# In-memory caches
cache = {
    "weather": {"data": None, "ts": 0},
    "stocks": {"data": None, "ts": 0}
}

WEATHER_CODE_MAP = {
    0: "晴朗無雲",
    1: "主要晴朗",
    2: "多雲時晴",
    3: "陰天多雲",
    45: "有霧",
    48: "霧氣結霜",
    51: "毛毛細雨",
    53: "小陣雨",
    55: "綿綿細雨",
    61: "微雨",
    63: "中陣雨",
    65: "大雨滂沱",
    71: "微雪",
    73: "中雪",
    75: "大雪",
    80: "微短暫陣雨",
    81: "陣雨",
    82: "暴雨",
    95: "雷陣雨",
    96: "雷雨夾帶冰雹",
    99: "強烈雷暴冰雹"
}

@app.route("/")
def index():
    response = send_from_directory(STATIC_DIR, "index.html")
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response

@app.route("/static/<path:filename>")
def serve_static(filename):
    response = send_from_directory(STATIC_DIR, filename)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response

@app.route("/music/<path:filename>")
def serve_music(filename):
    response = send_from_directory(MUSIC_DIR, filename, conditional=True)
    response.headers["Cache-Control"] = "public, max-age=604800"
    return response

# ============================================================
# TubeRepair & 懷舊網頁加速傳送門 (整合至同一伺服器)
# ============================================================
TUBEREPAIR_PORT = 8767

def ensure_tuberepair_running():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{TUBEREPAIR_PORT}/status")
        with urllib.request.urlopen(req, timeout=1) as resp:
            if resp.status == 200:
                return
    except Exception:
        pass

    def _run():
        try:
            import tuberepair_proxy
            tuberepair_proxy.IDLE_TIMEOUT = 999999999
            server = tuberepair_proxy.ThreadingHTTPServer(("0.0.0.0", TUBEREPAIR_PORT), tuberepair_proxy.Handler)
            print(f"[TubeRepair] Background service running on 0.0.0.0:{TUBEREPAIR_PORT}")
            server.serve_forever()
        except Exception as e:
            print(f"[TubeRepair] Background service notice: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

ensure_tuberepair_running()

def forward_to_tuberepair():
    ensure_tuberepair_running()
    path = request.path
    qs = request.environ.get("QUERY_STRING", "")
    if qs:
        try:
            fixed_qs = qs.encode("latin-1").decode("utf-8")
        except Exception:
            fixed_qs = qs
        quoted_qs = urllib.parse.quote(fixed_qs, safe="=&?/%+~:@")
        target_url = f"http://127.0.0.1:{TUBEREPAIR_PORT}{path}?{quoted_qs}"
    else:
        target_url = f"http://127.0.0.1:{TUBEREPAIR_PORT}{path}"

    headers = {k: v for k, v in request.headers if k.lower() not in ["content-length", "host"]}
    headers["Host"] = request.headers.get("Host", "127.0.0.1:8080")

    body = request.get_data() if request.method in ["POST", "PUT"] else None

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=body,
            allow_redirects=False,
            stream=True,
            timeout=60
        )

        excluded_headers = ["content-encoding", "transfer-encoding", "connection"]
        response_headers = [
            (name, value) for name, value in resp.raw.headers.items()
            if name.lower() not in excluded_headers
        ]

        def generate():
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk

        return Response(generate(), status=resp.status_code, headers=response_headers, direct_passthrough=True)
    except Exception as e:
        return f"TubeRepair Proxy Service Error: {str(e)}", 502

@app.route("/web", strict_slashes=False, methods=["GET", "POST", "HEAD"])
@app.route("/web/<path:subpath>", methods=["GET", "POST", "HEAD"])
def route_web(subpath=""):
    return forward_to_tuberepair()

@app.route("/surf", strict_slashes=False, methods=["GET", "POST", "HEAD"])
@app.route("/surf/<path:subpath>", methods=["GET", "POST", "HEAD"])
def route_surf(subpath=""):
    return forward_to_tuberepair()

@app.route("/getvideo/<path:subpath>", methods=["GET", "POST", "HEAD"])
def route_getvideo(subpath=""):
    return forward_to_tuberepair()

@app.route("/getvideo_stream", methods=["GET", "POST", "HEAD"])
def route_getvideo_stream():
    return forward_to_tuberepair()

@app.route("/thumb/<path:subpath>", methods=["GET", "POST", "HEAD"])
def route_thumb(subpath=""):
    return forward_to_tuberepair()

@app.route("/feeds/api/<path:subpath>", methods=["GET", "POST", "HEAD"])
def route_feeds(subpath=""):
    return forward_to_tuberepair()

@app.route("/schemas/<path:subpath>", methods=["GET", "POST", "HEAD"])
def route_schemas(subpath=""):
    return forward_to_tuberepair()

@app.route("/yql/weather", methods=["GET", "POST", "HEAD"])
@app.route("/v1/yql", methods=["GET", "POST", "HEAD"])
@app.route("/dgw", methods=["GET", "POST", "HEAD"])
def route_yql():
    if request.path == "/dgw":
        body = request.get_data()
        try:
            import stocks_bridge
            xml_resp = stocks_bridge.handle_dgw(body)
            with open("/tmp/dgw_debug.log", "ab") as f:
                f.write(f"\n=== DGW REQ ===\n{body.decode('utf-8', errors='replace')}\n=== DGW RESP ===\n{xml_resp.decode('utf-8', errors='replace')}\n".encode("utf-8"))
            return Response(xml_resp, mimetype="text/xml; charset=utf-8")
        except Exception as e:
            print(f"[DGW ERROR] {e}")
    return forward_to_tuberepair()

# ============================================================
# Passbook 擬物黑卡 & 經典遊戲 OTA 無線安裝市集
# ============================================================
@app.route("/store")
@app.route("/retro_store")
def route_store():
    response = send_from_directory(STATIC_DIR, "store.html")
    response.headers["Cache-Control"] = "no-cache"
    return response

@app.route("/pass/vip.pkpass")
def route_vip_pass():
    try:
        import pass_generator
        pkpass_data = pass_generator.generate_vip_pass()
        resp = Response(pkpass_data, mimetype="application/vnd.apple.pkpass")
        resp.headers["Content-Disposition"] = "attachment; filename=vip.pkpass"
        return resp
    except Exception as e:
        return f"Pass Generation Error: {e}", 500

RETRO_APPS = {
    "angrybirds": {
        "title": "Angry Birds (憤怒鳥 1.0)",
        "bundle_id": "com.clickgamer.AngryBirds",
        "version": "1.0",
        "ipa": "angrybirds.ipa"
    },
    "catphysics": {
        "title": "Cat Physics (貓咪物理)",
        "bundle_id": "com.donutgames.catphysics",
        "version": "1.10",
        "ipa": "catphysics.ipa"
    },
    "castlesmasher": {
        "title": "Castle Smasher (城堡粉碎者)",
        "bundle_id": "com.donutgames.castlesmasher",
        "version": "1.0",
        "ipa": "castlesmasher.ipa"
    },
    "gba4ios": {
        "title": "GBA4iOS (Game Boy Advance 掌機)",
        "bundle_id": "com.rileytestut.enterprise.GBA4iOS.Original",
        "version": "1.6.2",
        "ipa": "gba4ios.ipa"
    },
    "podcasts": {
        "title": "Apple Podcasts (經典雙盤磁帶錄音機)",
        "bundle_id": "com.apple.podcasts",
        "version": "1.2.3",
        "ipa": "podcasts.ipa"
    }
}

@app.route("/manifest/<appid>.plist")
def route_manifest(appid):
    app_info = RETRO_APPS.get(appid)
    if not app_info:
        abort(404)
    host = request.host
    ipa_url = f"http://{host}/ipa/{app_info['ipa']}"
    manifest = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string>{ipa_url}</string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>{app_info['bundle_id']}</string>
                <key>bundle-version</key>
                <string>{app_info['version']}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>{app_info['title']}</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>"""
    return Response(manifest, mimetype="application/xml")

@app.route("/ipa/<path:filename>")
def serve_ipa(filename):
    ipa_dir = os.path.join(BASE_DIR, "ipa")
    return send_from_directory(ipa_dir, filename, conditional=True)

@app.route("/api/upload_rom", methods=["POST"])
def route_upload_rom():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "沒有選擇任何檔案"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "檔案名稱不得為空"}), 400
    
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".gba", ".gbc", ".gb", ".zip", ".nes"]:
        return jsonify({"status": "error", "message": f"不支援的副檔名: {ext}，僅支援 .gba, .gbc, .zip, .nes"}), 400
    
    roms_dir = os.path.join(BASE_DIR, "roms")
    os.makedirs(roms_dir, exist_ok=True)
    local_path = os.path.join(roms_dir, filename)
    file.save(local_path)
    
    # Push to iPhone 4s WebDAV / Media / Documents
    iphone_uploaded = False
    try:
        with open(local_path, "rb") as rf:
            rom_data = rf.read()
        dav_url = f"http://192.168.0.104/Media/ROMs/{urllib.parse.quote(filename)}"
        dav_req = urllib.request.Request(dav_url, data=rom_data, method="PUT")
        dav_req.add_header("Expect", "")
        with urllib.request.urlopen(dav_req, timeout=5) as dav_resp:
            if dav_resp.status in (200, 201, 204):
                iphone_uploaded = True
    except Exception as e:
        print(f"WebDAV upload to iPhone 4s failed: {e}")
        
    return jsonify({
        "status": "ok",
        "filename": filename,
        "iphone_synced": iphone_uploaded,
        "message": f"ROM [{filename}] 上傳成功！{'已即時無線注入 iPhone 4s，打開 GBA4iOS 即可開玩！' if iphone_uploaded else '已保存在伺服器！'}"
    })

@app.route("/roms/<path:filename>")
def serve_rom(filename):
    roms_dir = os.path.join(BASE_DIR, "roms")
    return send_from_directory(roms_dir, filename, conditional=True)

PODCAST_FEEDS = {
    "gooaye": {
        "title": "Gooaye 股癌",
        "author": "謝孟恭",
        "desc": "台灣最熱門財經與科技投資幽默隨筆",
        "url": "https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml",
        "cover": "https://is1-ssl.mzstatic.com/image/thumb/Podcasts126/v4/04/b5/eb/04b5ebdf-7072-21fc-5876-e5feb5ba3dac/mza_7653733142335128691.jpeg/600x600bb.jpg"
    },
    "bailingguo": {
        "title": "百靈果 News",
        "author": "Kylie & Ken",
        "desc": "華語最自由的國際新聞與時事雙語脫口秀",
        "url": "https://feed.firstory.me/rss/user/cmjaz594i0000hdvpdpnd4fw8",
        "cover": "https://is1-ssl.mzstatic.com/image/thumb/Podcasts221/v4/42/e6/9b/42e69b29-8267-28a0-89d1-6a8a27d2c42e/mza_17512456390832780230.jpg/600x600bb.jpg"
    },
    "mindi": {
        "title": "敏迪選讀",
        "author": "敏迪",
        "desc": "把國際大事寫成輕鬆好懂的早安新聞與深度訪談",
        "url": "https://feeds.soundon.fm/podcasts/44833083-490d-4f97-a782-fd5e34c0abef.xml",
        "cover": "https://is1-ssl.mzstatic.com/image/thumb/Podcasts114/v4/2a/59/46/2a5946cc-7521-0dc4-5b03-9f0c46b81eef/mza_4964299199116822710.jpg/600x600bb.jpg"
    },
    "commute": {
        "title": "台灣通勤第一品牌",
        "author": "李毅誠 & 柯呈舫",
        "desc": "下班通勤放鬆必備的真性情對話與生活哲學",
        "url": "https://anchor.fm/s/1ea77470/podcast/rss",
        "cover": "https://is1-ssl.mzstatic.com/image/thumb/Podcasts123/v4/02/4c/58/024c58d2-5b90-84a2-4861-f052b147e1d6/mza_3950128602506399095.jpg/600x600bb.jpg"
    },
    "bbc": {
        "title": "BBC 6 Minute English",
        "author": "BBC Learning English",
        "desc": "標準英式發音與熱門時事英語精華聽力訓練",
        "url": "https://podcasts.files.bbci.co.uk/p02pc9tn.rss",
        "cover": "https://is1-ssl.mzstatic.com/image/thumb/Podcasts211/v4/ba/98/35/ba9835eb-1ef3-60e4-bf05-3d141b8d1c7a/mza_3844641997714022659.jpg/600x600bb.jpg"
    }
}

@app.route("/podcasts")
def route_podcasts_page():
    return send_from_directory(STATIC_DIR, "podcasts.html")

@app.route("/api/podcasts")
def route_api_podcasts():
    host = request.host
    items = []
    for fid, p in PODCAST_FEEDS.items():
        feed_url = f"http://{host}/podcast/feed/{fid}.xml"
        pcast_url = f"pcast://{host}/podcast/feed/{fid}.xml"
        items.append({
            "id": fid,
            "title": p["title"],
            "author": p["author"],
            "desc": p["desc"],
            "cover": p["cover"],
            "feed_url": feed_url,
            "pcast_url": pcast_url
        })
    return jsonify(items)

@app.route("/podcast/feed/<fid>")
@app.route("/podcast/feed/<fid>.xml")
def route_podcast_feed(fid):
    p = PODCAST_FEEDS.get(fid.replace(".xml", ""))
    if not p:
        abort(404)
    upstream_url = p["url"]
    try:
        req = urllib.request.Request(upstream_url, headers={"User-Agent": "iTunes/10.6 (Macintosh; Intel Mac OS X 10.6.8)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read()
            return Response(content, mimetype="application/rss+xml; charset=utf-8")
    except Exception as e:
        return f"Error fetching podcast feed: {e}", 502

@app.route("/siri")
def route_siri_page():
    return send_from_directory(STATIC_DIR, "siri.html")

@app.route("/api/siri", methods=["POST"])
def route_api_siri():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"status": "error", "reply": "請問有什麼我可以幫您的？"}), 400
    
    import siri_brain
    import stocks_bridge
    res = siri_brain.get_siri_response(
        query,
        weather_cache=cache.get("weather"),
        stocks_fetcher=stocks_bridge.fetch_quotes_batch
    )
    return jsonify(res)

@app.route("/api/tts")
def route_api_tts():
    text = request.args.get("text", "").strip()
    if not text:
        abort(400)
    q = urllib.parse.quote(text[:100])
    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=zh-TW&client=tw-ob&q={q}"
    try:
        req = urllib.request.Request(tts_url, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 6_1_3 like Mac OS X)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            audio_data = resp.read()
            return Response(audio_data, mimetype="audio/mpeg")
    except Exception as e:
        return f"TTS Error: {e}", 500

@app.route("/ClientLogin", methods=["GET", "POST", "HEAD"])
def route_clientlogin():
    return forward_to_tuberepair()

@app.route("/applelogin1", methods=["GET", "POST", "HEAD"])
@app.route("/applelogin2", methods=["GET", "POST", "HEAD"])
@app.route("/registerDevice", methods=["GET", "POST", "HEAD"])
def route_applelogin():
    return forward_to_tuberepair()

@app.route("/pepconfig.plist", methods=["GET", "POST", "HEAD"])
def route_pepconfig():
    return forward_to_tuberepair()

@app.route("/raw_proxy_code", methods=["GET"])
@app.route("/raw_ytdlp", methods=["GET"])
@app.route("/install_macmini.sh", methods=["GET"])
def route_raw():
    return forward_to_tuberepair()

@app.errorhandler(404)
def fallback_tuberepair(e):
    p = request.path
    if p.startswith(("/feeds", "/getvideo", "/thumb", "/schemas", "/api", "/web", "/surf", "/v1", "/yql")) or "ClientLogin" in p or "applelogin" in p or "registerDevice" in p:
        return forward_to_tuberepair()
    return e


RADIO_STREAMS = {
    "icrt": {
        "name": "ICRT FM 100.7",
        "url": "https://stream.rcs.revma.com/nkdfurztxp3vv",
        "type": "audio/aac"
    },
    "asia": {
        "name": "亞洲電台 92.7",
        "url": "https://stream.rcs.revma.com/xpgtqc74hv8uv",
        "type": "audio/aac"
    },
    "lofi": {
        "name": "24/7 Lofi Chillhop",
        "url": "https://streams.ilovemusic.de/iloveradio17.mp3",
        "type": "audio/mpeg"
    },
    "fly": {
        "name": "飛揚調頻 89.5",
        "url": "https://stream.rcs.revma.com/e0tdah74hv8uv",
        "type": "audio/aac"
    },
    "dance": {
        "name": "舞曲活力 Hits",
        "url": "https://streams.ilovemusic.de/iloveradio2.mp3",
        "type": "audio/mpeg"
    },
    "asia-pac": {
        "name": "亞太電台 92.3",
        "url": "https://stream.rcs.revma.com/kydend74hv8uv",
        "type": "audio/aac"
    }
}

@app.route("/api/radio/stream")
def proxy_radio_stream():
    station_id = request.args.get("id", "icrt")
    info = RADIO_STREAMS.get(station_id)
    if not info:
        return jsonify({"error": "Station not found"}), 404

    target_url = info["url"]
    content_type = info["type"]

    def generate():
        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Icy-MetaData": "0",
                "Accept": "*/*"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    yield chunk
        except (GeneratorExit, BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            pass

    headers = {
        "Content-Type": content_type,
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Access-Control-Allow-Origin": "*",
        "X-Accel-Buffering": "no"
    }
    return Response(generate(), mimetype=content_type, headers=headers)


@app.route("/api/music/list")
def list_music():
    if not os.path.exists(MUSIC_DIR):
        return jsonify([])
    files = [
        f for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith((".mp3", ".m4a", ".wav", ".aac"))
    ]
    files.sort()
    track_list = []
    for f in files:
        title = os.path.splitext(f)[0].replace("_", " ")
        track_list.append({
            "filename": f,
            "title": title,
            "url": "/music/" + urllib.parse.quote(f)
        })
    return jsonify(track_list)

@app.route("/api/weather")
def get_weather():
    now = time.time()
    if cache["weather"]["data"] and (now - cache["weather"]["ts"] < 120):
        return jsonify(cache["weather"]["data"])

    # Taipei coordinates
    url = "https://api.open-meteo.com/v1/forecast?latitude=25.0478&longitude=121.5319&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature&timezone=Asia%2FTaipei"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RetroDashboard/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            curr = raw.get("current", {})
            w_code = curr.get("weather_code", 0)
            desc = WEATHER_CODE_MAP.get(w_code, "多雲")
            temp = curr.get("temperature_2m", 25.0)
            apparent = curr.get("apparent_temperature", temp)
            humidity = curr.get("relative_humidity_2m", 70)

            data = {
                "city": "台北 (Taipei)",
                "temperature": round(temp, 1),
                "apparent": round(apparent, 1),
                "humidity": humidity,
                "description": desc,
                "code": w_code,
                "updated_at": datetime.now().strftime("%H:%M")
            }
            cache["weather"] = {"data": data, "ts": now}
            return jsonify(data)
    except Exception:
        if cache["weather"]["data"]:
            return jsonify(cache["weather"]["data"])
        return jsonify({
            "city": "台北 (Taipei)",
            "temperature": 26.0,
            "apparent": 27.0,
            "humidity": 75,
            "description": "多雲",
            "updated_at": "--:--"
        })

@app.route("/api/stocks")
def get_stocks():
    now = time.time()
    if cache["stocks"]["data"] and (now - cache["stocks"]["ts"] < 20):
        return jsonify(cache["stocks"]["data"])

    indices = [
        {"symbol": "^TWII", "name": "加權指數 (台股大盤)"},
        {"symbol": "^DJI", "name": "道瓊工業 (美股)"},
        {"symbol": "^IXIC", "name": "那斯達克 (美股)"},
        {"symbol": "^GSPC", "name": "標普 500 (美股)"}
    ]

    results = []
    for item in indices:
        sym = item["symbol"]
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?interval=1d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice")
                prev = meta.get("chartPreviousClose") or price
                diff = price - prev
                pct = (diff / prev) * 100 if prev else 0.0

                results.append({
                    "symbol": sym,
                    "name": item["name"],
                    "price": f"{price:,.2f}",
                    "change": f"{diff:+,.2f}",
                    "change_pct": f"{pct:+.2f}%",
                    "is_up": diff >= 0
                })
        except Exception:
            pass

    if results:
        payload = {"items": results, "updated_at": datetime.now().strftime("%H:%M:%S")}
        cache["stocks"] = {"data": payload, "ts": now}
        return jsonify(payload)

    if cache["stocks"]["data"]:
        return jsonify(cache["stocks"]["data"])

    return jsonify({
        "items": [
            {"symbol": "^TWII", "name": "加權指數 (台股大盤)", "price": "--", "change": "--", "change_pct": "--", "is_up": True}
        ],
        "updated_at": "--:--:--"
    })

@app.route("/api/messages", methods=["GET", "POST"])
def handle_messages():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        author = data.get("author", "").strip() or "訪客"
        content = data.get("content", "").strip()
        if not content:
            return jsonify({"error": "留言內容不可為空"}), 400

        messages = []
        if os.path.exists(MESSAGES_FILE):
            try:
                with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except Exception:
                messages = []

        new_msg = {
            "id": int(time.time() * 1000),
            "author": author[:20],
            "content": content[:200],
            "time": datetime.now().strftime("%m/%d %H:%M")
        }
        messages.insert(0, new_msg)
        messages = messages[:50]

        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "message": new_msg})

    # GET
    messages = []
    if os.path.exists(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except Exception:
            messages = []
    return jsonify(messages)

# ============================================================
# iPhone 4s 無線相片上傳至 192.168.0.115 (disk1s2) 橋樑
# ============================================================
SMB_TARGET_HOST = "192.168.0.115"
SMB_SHARE_NAME = "disk1s2"
SMB_MOUNT_POINT = "/Volumes/disk1s2"
PHOTO_DEST_DIR = os.path.join(SMB_MOUNT_POINT, "iPhone4s_Photos")
LOCAL_FALLBACK_DIR = os.path.join(BASE_DIR, "uploaded_photos")

def ensure_smb_mounted():
    """確保 192.168.0.115/disk1s2 網路磁碟已掛載，若未掛載則自動以系統鑰匙圈無感重連"""
    if os.path.ismount(SMB_MOUNT_POINT) or os.path.exists(SMB_MOUNT_POINT):
        try:
            os.makedirs(PHOTO_DEST_DIR, exist_ok=True)
            return True, PHOTO_DEST_DIR
        except Exception:
            pass

    try:
        cmd = ["osascript", "-e", f'mount volume "smb://user@{SMB_TARGET_HOST}/{SMB_SHARE_NAME}"']
        subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if os.path.exists(SMB_MOUNT_POINT):
            os.makedirs(PHOTO_DEST_DIR, exist_ok=True)
            return True, PHOTO_DEST_DIR
    except Exception as e:
        print(f"[SMB MOUNT ERR] {e}")

    os.makedirs(LOCAL_FALLBACK_DIR, exist_ok=True)
    return False, LOCAL_FALLBACK_DIR

@app.route("/photos")
@app.route("/upload")
def photos_page():
    return send_from_directory(STATIC_DIR, "photos.html")

@app.route("/api/photos/status")
def photos_status():
    mounted, active_dir = ensure_smb_mounted()
    free_gb = 0.0
    total_photos = 0
    try:
        usage = shutil.disk_usage(active_dir)
        free_gb = round(usage.free / (1024 ** 3), 2)
    except Exception:
        pass

    try:
        valid_exts = (".jpg", ".jpeg", ".png", ".gif", ".mov", ".mp4", ".heic")
        files = [f for f in os.listdir(active_dir) if f.lower().endswith(valid_exts)]
        total_photos = len(files)
    except Exception:
        pass

    return jsonify({
        "mounted": mounted,
        "target_host": SMB_TARGET_HOST,
        "share_name": SMB_SHARE_NAME,
        "dest_dir": active_dir,
        "free_gb": free_gb,
        "total_photos": total_photos
    })

@app.route("/api/photos/upload", methods=["POST"])
def photos_upload():
    mounted, active_dir = ensure_smb_mounted()
    thumbs_dir = os.path.join(active_dir, ".thumbs")
    try:
        os.makedirs(thumbs_dir, exist_ok=True)
    except Exception:
        pass

    uploaded_files = []
    file_objs = []
    for key in ("photos", "file", "files", "image", "images"):
        file_objs.extend(request.files.getlist(key))
    if not file_objs and request.files:
        for k in request.files:
            file_objs.extend(request.files.getlist(k))

    if not file_objs:
        return jsonify({"error": "未收到任何照片檔案"}), 400

    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    for idx, f in enumerate(file_objs):
        if not f or not f.filename:
            continue
        orig_name = secure_filename(f.filename) or f"photo_{idx}.jpg"
        clean_name = f"IMG_{now_str}_{idx+1:02d}_{orig_name}"
        save_path = os.path.join(active_dir, clean_name)

        try:
            f.save(save_path)
            size_kb = round(os.path.getsize(save_path) / 1024, 1)

            # Generate thumbnail for fast gallery view on iPhone 4s
            thumb_path = os.path.join(thumbs_dir, clean_name)
            try:
                if clean_name.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                    with Image.open(save_path) as im:
                        if im.mode in ("RGBA", "P", "LA"):
                            im = im.convert("RGB")
                        im.thumbnail((200, 200))
                        im.save(thumb_path, "JPEG", quality=80)
            except Exception as te:
                print(f"[THUMB ERR] {te}")

            uploaded_files.append({
                "name": clean_name,
                "size_kb": size_kb,
                "url": f"/api/photos/file/{urllib.parse.quote(clean_name)}",
                "thumb_url": f"/api/photos/thumb/{urllib.parse.quote(clean_name)}"
            })
        except Exception as e:
            print(f"[SAVE ERR] {e}")

    target_label = f"192.168.0.115 ({SMB_SHARE_NAME})" if mounted else "本機暫存 (待連線)"
    return jsonify({
        "success": True,
        "count": len(uploaded_files),
        "files": uploaded_files,
        "mounted": mounted,
        "message": f"成功上傳 {len(uploaded_files)} 張照片至 {target_label}！"
    })

@app.route("/api/photos/sync_auto", methods=["POST"])
def photos_sync_auto():
    import sync_iphone_photos
    import importlib
    importlib.reload(sync_iphone_photos)
    try:
        res = sync_iphone_photos.sync_all()
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/photos/list")
def photos_list():
    mounted, active_dir = ensure_smb_mounted()
    valid_exts = (".jpg", ".jpeg", ".png", ".gif", ".mov", ".mp4", ".heic")

    results = []
    try:
        entries = []
        for name in os.listdir(active_dir):
            if name.startswith(".") or not name.lower().endswith(valid_exts):
                continue
            full_path = os.path.join(active_dir, name)
            if os.path.isfile(full_path):
                entries.append((os.path.getmtime(full_path), name, os.path.getsize(full_path)))

        entries.sort(key=lambda x: x[0], reverse=True)
        for mtime, name, size in entries[:60]:
            results.append({
                "name": name,
                "size_kb": round(size / 1024, 1),
                "time": datetime.fromtimestamp(mtime).strftime("%m/%d %H:%M"),
                "url": f"/api/photos/file/{urllib.parse.quote(name)}",
                "thumb_url": f"/api/photos/thumb/{urllib.parse.quote(name)}"
            })
    except Exception as e:
        print(f"[LIST ERR] {e}")

    return jsonify({"photos": results, "mounted": mounted, "dest_dir": active_dir})

@app.route("/api/photos/file/<path:filename>")
def photos_get_file(filename):
    mounted, active_dir = ensure_smb_mounted()
    return send_from_directory(active_dir, filename)

@app.route("/api/photos/thumb/<path:filename>")
def photos_get_thumb(filename):
    mounted, active_dir = ensure_smb_mounted()
    thumbs_dir = os.path.join(active_dir, ".thumbs")
    thumb_path = os.path.join(thumbs_dir, filename)
    if os.path.exists(thumb_path):
        return send_from_directory(thumbs_dir, filename)

    orig_path = os.path.join(active_dir, filename)
    if os.path.exists(orig_path):
        try:
            os.makedirs(thumbs_dir, exist_ok=True)
            with Image.open(orig_path) as im:
                if im.mode in ("RGBA", "P", "LA"):
                    im = im.convert("RGB")
                im.thumbnail((200, 200))
                im.save(thumb_path, "JPEG", quality=80)
            return send_from_directory(thumbs_dir, filename)
        except Exception:
            return send_from_directory(active_dir, filename)
    abort(404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ensure_tuberepair_running()
    print("=" * 60)
    print(f"🚀 iPhone 4s 全功能整合伺服器 (Port: {port} & {TUBEREPAIR_PORT}) 啟動！")
    print(f"  📱 智慧儀表板：http://localhost:{port}/ 或 http://192.168.0.185:{port}/")
    print(f"  🌐 網頁傳送門：http://localhost:{port}/web 或 http://192.168.0.185:{port}/web")
    print(f"  📺 懷舊YouTube：http://localhost:{port}/web/youtube 或 8767 埠直連")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
