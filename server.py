import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"啟動 iPhone 4s 專屬復古儀表板伺服器 (Port: {port})...")
    print(f"本機請連：http://localhost:{port}")
    print(f"iPhone 請連：http://[Mac區域網路IP]:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
