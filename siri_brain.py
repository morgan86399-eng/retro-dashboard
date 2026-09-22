import os
import re
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

BLANKAPI_API_KEY = os.environ.get("BLANKAPI_API_KEY", "")
if not BLANKAPI_API_KEY:
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("BLANKAPI_API_KEY="):
                    BLANKAPI_API_KEY = line.strip().split("=", 1)[1]
                    break

def get_siri_response(user_query, weather_cache=None, stocks_fetcher=None):
    q = user_query.strip().lower()
    
    # 1. 時間與日期查詢
    if any(k in q for k in ["幾點", "時間", "現在時間"]):
        now = datetime.now()
        time_str = now.strftime("%p %I 點 %M 分").replace("AM", "上午").replace("PM", "下午")
        return {
            "reply": f"現在時間是{time_str}。",
            "card_type": "time",
            "card_data": {"time": now.strftime("%H:%M:%S"), "date": now.strftime("%Y年%m月%d日 星期%w")}
        }
        
    if any(k in q for k in ["星期幾", "禮拜幾", "今天幾號", "今天日期"]):
        now = datetime.now()
        weekdays = ["日", "一", "二", "三", "四", "五", "六"]
        w = weekdays[int(now.strftime("%w"))]
        date_str = now.strftime(f"%Y年%m月%d日 星期{w}")
        return {
            "reply": f"今天是 {date_str}。",
            "card_type": "time",
            "card_data": {"date": date_str}
        }

    # 2. 天氣查詢
    if any(k in q for k in ["天氣", "氣溫", "下雨", "會冷嗎", "會熱嗎"]):
        temp = "24"
        condition = "晴朗多雲"
        if weather_cache and weather_cache.get("data"):
            wdata = weather_cache["data"]
            temp = wdata.get("temp", "24")
            condition = wdata.get("condition", "晴朗多雲")
            city = wdata.get("city", "桃園市")
        else:
            city = "桃園市"
        reply = f"目前{city}的天氣是{condition}，氣溫約 {temp} 度。"
        return {
            "reply": reply,
            "card_type": "weather",
            "card_data": {
                "city": city,
                "temp": f"{temp}°C",
                "condition": condition
            }
        }

    # 3. 股票查詢
    if any(k in q for k in ["股票", "股市", "台積電", "蘋果", "道瓊", "大盤"]):
        symbol = "^TWII"
        name = "台股加權指數"
        if "台積電" in q or "2330" in q:
            symbol = "2330.TW"
            name = "台積電"
        elif "蘋果" in q or "aapl" in q:
            symbol = "AAPL"
            name = "Apple Inc."
        elif "道瓊" in q or "dji" in q:
            symbol = "^DJI"
            name = "道瓊工業指數"
            
        quote_text = f"正在為您查看{name}的行情。"
        card_data = {"symbol": symbol, "name": name, "price": "1,020", "change": "+15.0 (+1.49%)"}
        try:
            if stocks_fetcher:
                quotes = stocks_fetcher([symbol])
                if quotes and symbol in quotes:
                    sq = quotes[symbol]
                    p = sq.get("price", "N/A")
                    c = sq.get("change", "0.0")
                    card_data["price"] = str(p)
                    card_data["change"] = str(c)
                    quote_text = f"{name}目前的價格是 {p}，變動幅度為 {c}。"
        except Exception:
            pass
            
        return {
            "reply": quote_text,
            "card_type": "stock",
            "card_data": card_data
        }

    # 4. 經典彩蛋與 Siri 哲學問答
    if "你是誰" in q or "你叫什麼" in q:
        return {
            "reply": "我是 Siri，您在 iPhone 4s 上的專屬智慧個人助理。如今我連上了現代 AI 大腦，比以往更加聰明了。",
            "card_type": "text",
            "card_data": {}
        }
    if "賈伯斯" in q or "喬布斯" in q or "steve jobs" in q:
        return {
            "reply": "感謝史蒂夫·賈伯斯，是他創造了 iPhone 4s 這座優雅的里程碑，也賦予了我聲音與靈魂。",
            "card_type": "text",
            "card_data": {}
        }
    if "講笑話" in q or "笑話" in q:
        jokes = [
            "為什麼電腦永遠不冷？因為它有 Windows（窗戶）開著，但隨時都在運轉散熱。",
            "人工智慧走進一家酒吧，調酒師問：『想喝點什麼？』AI 回答：『給我來點記憶體，我想忘記剛剛遇見的 Bug。』",
            "世界上有 10 種人：懂二進位的，和不懂二進位的。"
        ]
        import random
        chosen = random.choice(jokes)
        return {
            "reply": chosen,
            "card_type": "text",
            "card_data": {}
        }

    # 5. 連接現代 LLM 大腦 (Grok / AI Proxy)
    if BLANKAPI_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {BLANKAPI_API_KEY}",
                "Content-Type": "application/json"
            }
            system_prompt = (
                "你是經典的 iOS 6 Siri 智慧助理，說話優雅、簡潔親切、偶爾帶點幽默，使用繁體中文（台灣）。"
                "回答盡量控制在 1 到 3 句話以內，保持俐落適合語音朗讀。"
            )
            payload = {
                "model": "grok-4.6",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                "max_tokens": 120
            }
            req = urllib.request.Request(
                "https://api.blankapi.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data["choices"][0]["message"]["content"].strip()
                return {
                    "reply": reply,
                    "card_type": "text",
                    "card_data": {}
                }
        except Exception as e:
            print(f"LLM Error: {e}")

    # Fallback response
    return {
        "reply": f"我了解您問的是「{user_query}」。雖然我在 iPhone 4s 的復古世界裡，但我隨時都在您身邊效勞。",
        "card_type": "text",
        "card_data": {}
    }
