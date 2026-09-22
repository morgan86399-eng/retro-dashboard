"""
TubeRepair Local Proxy — yt-dlp powered + iOS 6 Weather (Open-Meteo powered).
Serves:
1. Atom XML feeds for Classic YouTube 1.0 (iOS 6/5).
2. Device Authentication & pepconfig bypass for Apple YouTube framework.
3. 360p video streaming via yt-dlp (/getvideo/<id>).
4. Image proxy for YouTube thumbnails (/thumb/<id>/<name>).
5. Yahoo Weather YQL XML with Open-Meteo for iOS 6 Weather.app.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote, unquote, urljoin
from datetime import datetime, timezone, date
import subprocess
import json
import html
import re
import os
import uuid
import ctypes
import time
import requests
import sys
import threading
import io
from PIL import Image
from bs4 import BeautifulSoup
try:
    from readability import Document
except Exception:
    Document = None

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

PEPCONFIG_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>com.apple.youtubeframework</key>
	<dict>
		<key>ConfiguredServiceHost</key>
		<string>gdata.youtube.com</string>
		<key>PartialFeedType</key>
		<integer>4</integer>
	</dict>
</dict>
</plist>"""

YTDLP = "/opt/homebrew/bin/yt-dlp"
PORT = 8767
CACHE = {}  # simple {key: (timestamp, data)} TTL cache
CACHE_TTL = 600  # 10 min

# In-memory store for woeid -> (city, lat, lon, country, cc)
WOEID_STORE = {
    "2306188": ("桃園市", 24.99368, 121.29696, "台灣", "TWN"),
    "2306179": ("台北市", 25.05306, 121.52639, "台灣", "TWN"),
    "0000": ("桃園市", 24.99368, 121.29696, "台灣", "TWN"),
}


def _cached(key, fn, ttl=CACHE_TTL):
    import time
    now = time.time()
    if key in CACHE and now - CACHE[key][0] < ttl:
        return CACHE[key][1]
    data = fn()
    CACHE[key] = (now, data)
    return data


def _esc(s):
    if not s:
        return ""
    return html.escape(str(s), quote=True)


def _unix_fmt(ts):
    if not ts:
        return "2026-01-01T00:00:00.000Z"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts))
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except Exception:
        return "2026-01-01T00:00:00.000Z"


def _run_ytdlp_cmd(args, timeout=45):
    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{os.path.expanduser('~/.local/bin')}:/usr/bin:/bin:" + env.get("PATH", "")

    # 1. Try known direct paths
    for cand in [YTDLP, "/opt/homebrew/bin/yt-dlp", "/usr/local/bin/yt-dlp", os.path.expanduser("~/.local/bin/yt-dlp"), "yt-dlp"]:
        if cand and (os.path.exists(cand) or cand == "yt-dlp"):
            try:
                res = subprocess.run([cand] + args, capture_output=True, text=True, timeout=timeout, env=env)
                if res.returncode == 0 or res.stdout.strip():
                    return res
            except Exception:
                pass

    # 2. Try sys.executable -m yt_dlp
    try:
        res = subprocess.run([sys.executable, "-m", "yt_dlp"] + args, capture_output=True, text=True, timeout=timeout, env=env)
        if res.returncode == 0 or res.stdout.strip():
            return res
    except Exception:
        pass

    # 3. Try sys.executable on standalone zipapp
    local_bin = os.path.expanduser("~/.local/bin/yt-dlp")
    if os.path.exists(local_bin):
        try:
            return subprocess.run([sys.executable, local_bin] + args, capture_output=True, text=True, timeout=timeout, env=env)
        except Exception:
            pass

    return subprocess.run(["yt-dlp"] + args, capture_output=True, text=True, timeout=timeout, env=env)


def _ytdlp_flat(url, max_items=25):
    """Run yt-dlp --flat-playlist and return list of dicts."""
    try:
        cmd = ["--flat-playlist", "-j", "--no-warnings"]
        if url.startswith("ytsearch"):
            cmd.extend(["--match-filter", "!is_live & live_status != 'is_upcoming' & live_status != 'post_live'"])
        cmd.extend(["--playlist-end", str(max_items * 2), url])
        result = _run_ytdlp_cmd(cmd, timeout=45)
        items = []
        for line in result.stdout.strip().splitlines():
            if line.strip():
                try:
                    data = json.loads(line)
                    if data.get("is_live") or data.get("live_status") in ("is_live", "is_upcoming", "post_live"):
                        continue
                    t = data.get("title") or ""
                    if "直播" in t or "LIVE" in t or "Live" in t:
                        continue
                    items.append(data)
                    if len(items) >= max_items:
                        break
                except json.JSONDecodeError:
                    pass
        return items
    except Exception as e:
        print(f"[yt-dlp flat] {e}")
        return []


def _ytdlp_video_info(video_id):
    """Get full video info (for related videos, duration, etc.)."""
    try:
        result = _run_ytdlp_cmd(
            ["-j", "--no-warnings", "--no-playlist",
             f"https://www.youtube.com/watch?v={video_id}"],
            timeout=35
        )
        if result.stdout.strip():
            return json.loads(result.stdout.strip().splitlines()[0])
    except Exception as e:
        print(f"[yt-dlp info] {e}")
    return None


def _build_entry(v, base_url):
    vid = v.get("id") or v.get("url", "").split("=")[-1] or ""
    if not vid or len(vid) < 5:
        return ""
    title = _esc(v.get("title") or "Untitled")
    author = _esc(v.get("uploader") or v.get("channel") or "Unknown")
    author_id = _esc(v.get("uploader_id") or v.get("channel_id") or "channel")
    duration = int(v.get("duration") or 0)
    views = int(v.get("view_count") or 1000)
    ts = v.get("upload_date") or v.get("timestamp") or 0
    if isinstance(ts, str) and len(ts) == 8:
        ts = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T00:00:00+00:00"
    published = _unix_fmt(ts)

    return f"""  <entry gd:etag="local">
    <id>tag:youtube.com,2008:video:{vid}</id>
    <published>{published}</published>
    <updated>{published}</updated>
    <category scheme="http://schemas.google.com/g/2005#kind" term="http://gdata.youtube.com/schemas/2007#video" />
    <category scheme="http://gdata.youtube.com/schemas/2007/categories.cat" term="Music" label="Music" />
    <title>{title}</title>
    <content type="video/mp4" src="{base_url}/getvideo/{vid}" />
    <link rel="alternate" type="text/html" href="https://www.youtube.com/watch?v={vid}&amp;feature=youtube_gdata" />
    <link rel="http://gdata.youtube.com/schemas/2007#video.related" type="application/atom+xml" href="{base_url}/feeds/api/videos/{vid}/related"/>
    <link rel="http://gdata.youtube.com/schemas/2007#mobile" type="text/html" href="http://m.youtube.com/details?v={vid}" />
    <link rel="http://gdata.youtube.com/schemas/2007#uploader" type="application/atom+xml" href="{base_url}/feeds/api/users/{author_id}" />
    <link rel="self" type="application/atom+xml" href="{base_url}/feeds/api/videos/{vid}" />
    <author>
      <name>{author}</name>
      <uri>{base_url}/feeds/api/users/{author_id}</uri>
      <yt:userId>{author_id}</yt:userId>
    </author>
    <yt:accessControl action="comment" permission="allowed" />
    <yt:accessControl action="rate" permission="allowed" />
    <yt:accessControl action="embed" permission="allowed" />
    <yt:accessControl action="list" permission="allowed" />
    <yt:accessControl action="autoPlay" permission="allowed" />
    <gd:comments><gd:feedLink href="{base_url}/api/videos/{vid}/comments"/></gd:comments>
    <yt:statistics favoriteCount="0" viewCount="{views}" />
    <gd:rating average="5" max="5" min="1" numRaters="100" rel="http://schemas.google.com/g/2005#overall" />
    <yt:rating numDislikes="0" numLikes="100" />
    <yt:hd />
    <media:group>
      <media:category label="Music" scheme="http://gdata.youtube.com/schemas/2007/categories.cat">Music</media:category>
      <media:content url="{base_url}/getvideo/{vid}" type="video/mp4" medium="video" isDefault="true" expression="full" duration="{duration}" yt:format="3" />
      <media:content url="{base_url}/getvideo/{vid}" type="video/mp4" medium="video" expression="full" duration="{duration}" yt:format="2" />
      <media:content url="{base_url}/getvideo/{vid}" type="video/mp4" medium="video" expression="full" duration="{duration}" yt:format="8" />
      <media:content url="{base_url}/getvideo/{vid}" type="video/mp4" medium="video" expression="full" duration="{duration}" yt:format="9" />
      <media:credit role="uploader" scheme="urn:youtube" yt:display="{author}">{author}</media:credit>
      <media:description type="plain">{title}</media:description>
      <media:keywords></media:keywords>
      <media:player url="https://www.youtube.com/watch?v={vid}&amp;feature=youtube_gdata_player" />
      <media:thumbnail url="{base_url}/thumb/{vid}/default.jpg" height="90" width="120" yt:name="default" />
      <media:thumbnail url="{base_url}/thumb/{vid}/mqdefault.jpg" height="180" width="320" yt:name="mqdefault" />
      <media:thumbnail url="{base_url}/thumb/{vid}/hqdefault.jpg" height="360" width="480" yt:name="hqdefault" />
      <media:thumbnail url="{base_url}/thumb/{vid}/sddefault.jpg" height="480" width="640" yt:name="sddefault" />
      <media:title type="plain">{title}</media:title>
      <yt:aspectRatio>widescreen</yt:aspectRatio>
      <yt:duration seconds="{duration}" />
      <yt:uploaded>{published}</yt:uploaded>
      <yt:uploaderId>{author_id}</yt:uploaderId>
      <yt:videoid>{vid}</yt:videoid>
    </media:group>
  </entry>"""


def _wrap_feed(title, entries_xml, base_url, feed_id=None, total_results=25, items_per_page=25, start_index=1):
    if not feed_id:
        feed_id = f"{base_url}/feeds/api/standardfeeds/TW/recently_featured"
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:gd="http://schemas.google.com/g/2005" xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:yt="http://gdata.youtube.com/schemas/2007" xmlns:media="http://search.yahoo.com/mrss/" xmlns:batch="http://schemas.google.com/gdata/batch" gd:etag="">
  <id>{feed_id}</id>
  <category scheme="http://schemas.google.com/g/2005#kind" term="http://gdata.youtube.com/schemas/2007#video" />
  <title>{_esc(title)}</title>
  <logo>http://www.gstatic.com/youtube/img/logo.png</logo>
  <link rel="http://schemas.google.com/g/2005#feed" type="application/atom+xml" href="{feed_id}" />
  <link rel="http://schemas.google.com/g/2005#batch" type="application/atom+xml" href="{feed_id}/batch" />
  <link rel="self" type="application/atom+xml" href="{feed_id}" />
  <author><name>TubeFixer</name></author>
  <generator version="2.0" uri="{base_url}/">TubeFixer API v2</generator>
  <openSearch:totalResults>{total_results}</openSearch:totalResults>
  <openSearch:itemsPerPage>{items_per_page}</openSearch:itemsPerPage>
  <openSearch:startIndex>{start_index}</openSearch:startIndex>
{entries_xml}
</feed>"""


# --- WEATHER HELPERS ---
def _wmo_to_yahoo(wmo_code, is_day=1):
    c = int(wmo_code)
    if c == 0:
        return 32 if is_day else 31
    elif c in (1, 2):
        return 30 if is_day else 29
    elif c == 3:
        return 26
    elif c in (45, 48):
        return 20
    elif c in (51, 53, 55):
        return 9
    elif c in (56, 57):
        return 8
    elif c in (61, 63, 65):
        return 12
    elif c in (66, 67):
        return 10
    elif c in (71, 73, 75, 77):
        return 14
    elif c in (80, 81, 82):
        return 11
    elif c in (85, 86):
        return 16
    elif c in (95, 96, 99):
        return 4
    return 32 if is_day else 31


def _weather_search_xml(q_text):
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote(q_text)}&count=6&language=zh&format=json"
        res = requests.get(url, timeout=6).json()
        items = res.get("results", [])
    except Exception as e:
        print(f"[weather geocode err] {e}")
        items = []

    loc_xml = []
    for item in items:
        name = item.get("name", q_text)
        admin = item.get("admin1", "")
        country = item.get("country", "")
        cc = item.get("country_code", "TW").upper()
        lat = item.get("latitude")
        lon = item.get("longitude")
        woeid = str(abs(hash((name, lat, lon))) % 9000000 + 1000000)
        display_name = f"{name}, {admin}" if admin and admin != name else name
        WOEID_STORE[woeid] = (display_name, lat, lon, country, cc)
        loc_xml.append(f'<location city="{_esc(display_name)}" country="{_esc(country)}" countryAbbr="{_esc(cc)}" locationID="TWXX0021|{woeid}" woeid="{woeid}"/>')

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<query xmlns:yahoo="http://www.yahooapis.com/v1/base.rng" yahoo:count="{len(loc_xml)}" yahoo:created="{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}" yahoo:lang="zh-TW">
  <results>
    {"".join(loc_xml)}
  </results>
</query>"""
    return re.sub(r'\s+(?=<)', '', xml)


def _fetch_one_forecast(woeid, lat=None, lon=None, location_id="TWXX0021|2306188"):
    if lat is None or lon is None:
        info = WOEID_STORE.get(str(woeid), ("桃園市", 24.99368, 121.29696, "台灣", "TWN"))
        city, lat, lon, country, cc = info
    else:
        city = "目前位置"

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"
            f"&hourly=temperature_2m,precipitation_probability,weather_code"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=auto"
        )
        res = requests.get(url, timeout=6).json()
        curr = res.get("current", {})
        daily = res.get("daily", {})
        hourly = res.get("hourly", {})
    except Exception as e:
        print(f"[weather forecast err] {e}")
        curr, daily, hourly = {}, {}, {}

    temp = round(float(curr.get("temperature_2m", 25)))
    feels_like = round(float(curr.get("apparent_temperature", temp)))
    humidity = round(float(curr.get("relative_humidity_2m", 65)))
    pressure = round(float(curr.get("surface_pressure", 1013)))
    wind_speed = round(float(curr.get("wind_speed_10m", 5)))
    wind_deg = round(float(curr.get("wind_direction_10m", 0)))
    is_day = curr.get("is_day", 1)
    condition_code = _wmo_to_yahoo(curr.get("weather_code", 0), is_day)

    sunrise_raw = daily.get("sunrise", ["05:40"])[0]
    sunset_raw = daily.get("sunset", ["18:05"])[0]
    sunrise_24 = sunrise_raw[-5:]
    sunset_24 = sunset_raw[-5:]
    sunrise_12 = f"{sunrise_24} AM"
    sunset_12 = f"{sunset_24} PM"
    now_24 = datetime.now().strftime("%H:%M")
    now_12 = datetime.now().strftime("%I:%M %p")

    daily_xml = []
    d_times = daily.get("time", [])
    for i in range(min(6, len(d_times))):
        d_date = date.fromisoformat(d_times[i])
        day_of_week = (d_date.weekday() + 1) % 7 + 1
        t_max = round(float(daily["temperature_2m_max"][i]))
        t_min = round(float(daily["temperature_2m_min"][i]))
        d_code = _wmo_to_yahoo(daily["weather_code"][i], 1)
        daily_xml.append(f'<day dayOfWeek="{day_of_week}" poP="10"><temp high="{t_max}" low="{t_min}" /><condition code="{d_code}" /></day>')

    hourly_xml = []
    if "time" in hourly:
        now_hour = datetime.now().hour
        h_times = hourly["time"]
        for i in range(now_hour, min(now_hour + 12, len(h_times))):
            h_time24 = h_times[i][-5:]
            h_temp = round(float(hourly["temperature_2m"][i]))
            h_pop = round(float(hourly["precipitation_probability"][i])) if "precipitation_probability" in hourly else 0
            h_code = _wmo_to_yahoo(hourly["weather_code"][i], 1 if 6 <= int(h_time24[:2]) < 18 else 0)
            hourly_xml.append(f'<hour time24="{h_time24}"><condition code="{h_code}" poP="{h_pop}" temp="{h_temp}" /></hour>')

    forecast_loc = f"""<location city="{_esc(city)}" country="" latitude="{lat}" locationID="{location_id}" longitude="{lon}" state="" woeid="{woeid}">
      <currently barometer="{pressure}" barometricTrend="" dewpoint="{temp - 3}" feelsLike="{feels_like}" heatIndex="{feels_like}" moonfacevisible="50%" moonphase="Full" percentHumidity="{humidity}" sunrise="{sunrise_12}" sunrise24="{sunrise_24}" sunset="{sunset_12}" sunset24="{sunset_24}" temp="{temp}" tempBgcolor="" time="{now_12}" time24="{now_24}" timezone="GMT+8" tz="CST" visibility="10" windChill="{feels_like}" windDirection="" windDirectionDegree="{wind_deg}" windSpeed="{wind_speed}">
        <condition code="{condition_code}" />
      </currently>
      <forecast>
        {"".join(daily_xml)}
        <extended_forecast_url>https://open-meteo.com</extended_forecast_url>
      </forecast>
    </location>"""

    hourly_loc = f"""<location woeid="{woeid}">
      <hourlyforecast>
        {"".join(hourly_xml)}
      </hourlyforecast>
    </location>"""

    return forecast_loc, hourly_loc


def _weather_multi_xml(woeid_list, lat=None, lon=None):
    """Builds Yahoo YQL XML with mandatory <meta> and dual <results> tags."""
    created_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    forecast_locations = []
    hourly_locations = []

    if lat is not None and lon is not None:
        f_loc, h_loc = _fetch_one_forecast("0000", lat, lon, "TWXX0021|2306179")
        forecast_locations.append(f_loc)
        hourly_locations.append(h_loc)

    for woeid in woeid_list:
        f_loc, h_loc = _fetch_one_forecast(woeid, location_id=f"TWXX0021|{woeid}")
        forecast_locations.append(f_loc)
        hourly_locations.append(h_loc)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<query xmlns:yahoo="http://www.yahooapis.com/v1/base.rng" yahoo:count="{len(forecast_locations) * 2}" yahoo:created="{created_ts}" yahoo:lang="zh-TW">
  <meta>
    <meta>
      <weather>
        <yahoo_mobile_url>https://weather.yahoo.com/</yahoo_mobile_url>
        <twc_mobile_url>https://weather.yahoo.com/</twc_mobile_url>
        <units distanceUnits="km" pressureUnits="mb" speedUnits="km/h" tempUnits="C" />
      </weather>
    </meta>
    <meta>
      <weather>
        <yahoo_mobile_url>https://weather.yahoo.com/</yahoo_mobile_url>
        <twc_mobile_url>https://weather.yahoo.com/</twc_mobile_url>
        <units tempUnits="C" />
      </weather>
    </meta>
  </meta>
  <results>
    <results>
      {"".join(forecast_locations)}
    </results>
    <results>
      {"".join(hourly_locations)}
    </results>
  </results>
</query>"""
    return re.sub(r'\s+(?=<)', '', xml)


STREAM_URL_CACHE = {}  # {video_id: (timestamp, url)}

def _get_stream_url(video_id):
    import time
    now = time.time()
    if video_id in STREAM_URL_CACHE and now - STREAM_URL_CACHE[video_id][0] < 3600:
        return STREAM_URL_CACHE[video_id][1]

    # Try format 18 (progressive 360p mp4) via android client first
    try:
        res = _run_ytdlp_cmd([
            "--no-playlist", "--no-warnings",
            "--extractor-args", "youtube:player_client=android,web",
            "-f", "18/best[height<=360][ext=mp4]/best[height<=360]/best",
            "-g", f"https://www.youtube.com/watch?v={video_id}"
        ], timeout=25)
        out = res.stdout.strip().splitlines()
        if out and out[0].startswith("http"):
            url = out[0]
            STREAM_URL_CACHE[video_id] = (now, url)
            return url
    except Exception as e:
        print(f"[get_stream_url format 18 err] {e}")

    # Fallback to standard yt-dlp -g
    try:
        res = _run_ytdlp_cmd([
            "--no-playlist", "--no-warnings",
            "-f", "best[height<=360]/best",
            "-g", f"https://www.youtube.com/watch?v={video_id}"
        ], timeout=25)
        out = res.stdout.strip().splitlines()
        if out and out[0].startswith("http"):
            url = out[0]
            STREAM_URL_CACHE[video_id] = (now, url)
            return url
    except Exception as e:
        print(f"[get_stream_url fallback err] {e}")

    return None


GENERIC_STREAM_CACHE = {}  # {video_url: (timestamp, direct_url)}

def _get_generic_stream_url(video_url):
    import time
    now = time.time()
    if video_url in GENERIC_STREAM_CACHE and now - GENERIC_STREAM_CACHE[video_url][0] < 3600:
        return GENERIC_STREAM_CACHE[video_url][1]

    clean_url = video_url.split("?")[0].lower()
    if clean_url.endswith(".mp4"):
        return video_url

    try:
        res = _run_ytdlp_cmd([
            "--no-playlist", "--no-warnings",
            "-f", "18/best[ext=mp4]/best[height<=480]/best",
            "-g", video_url
        ], timeout=20)
        direct = res.stdout.strip().splitlines()[0]
        if direct.startswith("http"):
            GENERIC_STREAM_CACHE[video_url] = (now, direct)
            return direct
    except Exception as e:
        print(f"[generic_stream_url err] {e}")

    return video_url


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def _base_url(self):
        host = self.headers.get("Host") or f"127.0.0.1:{PORT}"
        host = host.rstrip("/")
        return f"http://{host}"

    def _send_xml(self, xml_str):
        data = xml_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/atom+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_weather_xml(self, xml_str):
        data = xml_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_pepconfig(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-apple-plist")
        self.send_header("Content-Length", str(len(PEPCONFIG_XML)))
        self.end_headers()
        self.wfile.write(PEPCONFIG_XML)
        print("[PEPCONFIG] Served embedded pepconfig.plist")

    def _handle_single_video(self, video_id):
        base = self._base_url()
        info = _cached(f"vinfo:{video_id}", lambda: _ytdlp_video_info(video_id), ttl=1800)
        if not info:
            info = {"id": video_id, "title": f"Video {video_id}", "duration": 0}
        entry_xml = _build_entry(info, base)
        if 'xmlns="http://www.w3.org/2005/Atom"' not in entry_xml:
            entry_xml = entry_xml.replace(
                '<entry gd:etag="local">',
                '<entry xmlns="http://www.w3.org/2005/Atom" xmlns:gd="http://schemas.google.com/g/2005" xmlns:yt="http://gdata.youtube.com/schemas/2007" xmlns:media="http://search.yahoo.com/mrss/" gd:etag="local">'
            )
        xml = f"<?xml version='1.0' encoding='UTF-8'?>\n{entry_xml}"
        self._send_xml(xml)

    def _handle_trending(self, feed_name="recently_featured", qs=None):
        base = self._base_url()
        if qs is None:
            qs = {}
        try:
            start_index = int(qs.get("start-index", [1])[0])
        except Exception:
            start_index = 1
        try:
            max_results = int(qs.get("max-results", [25])[0])
        except Exception:
            max_results = 25

        items = _cached("trending_v6", lambda: _ytdlp_flat("ytsearch60:熱門音樂 2026", 60), ttl=3600)
        if not items:
            items = _cached("trending_fallback_v6", lambda: _ytdlp_flat("ytsearch60:trending music 2026", 60), ttl=3600)

        total_count = len(items)
        start_pos = max(0, start_index - 1)
        page_items = items[start_pos : start_pos + max_results]

        entries = "\n".join(_build_entry(v, base) for v in page_items if _build_entry(v, base))
        feed_id = f"{base}{self.path.split('?')[0]}"
        self._send_xml(_wrap_feed("Trending Videos", entries, base, feed_id, total_results=total_count, items_per_page=len(page_items), start_index=start_index))

    def _handle_search(self, query, qs=None):
        base = self._base_url()
        if qs is None:
            qs = {}
        try:
            start_index = int(qs.get("start-index", [1])[0])
        except Exception:
            start_index = 1
        try:
            max_results = int(qs.get("max-results", [25])[0])
        except Exception:
            max_results = 25

        cache_key = f"search_v3:{query}"
        items = _cached(cache_key, lambda: _ytdlp_flat(f"ytsearch50:{query}", 50))
        total_count = len(items)
        start_pos = max(0, start_index - 1)
        page_items = items[start_pos : start_pos + max_results]

        entries = "\n".join(_build_entry(v, base) for v in page_items if _build_entry(v, base))
        feed_id = f"{base}/feeds/api/videos?q={quote(query)}"
        self._send_xml(_wrap_feed(f"Search: {query}", entries, base, feed_id, total_results=total_count, items_per_page=len(page_items), start_index=start_index))

    def _handle_related(self, video_id):
        base = self._base_url()
        cache_key = f"related:{video_id}"

        def fetch_related():
            info = _ytdlp_video_info(video_id)
            if not info:
                return []
            channel_url = info.get("channel_url")
            if channel_url:
                return _ytdlp_flat(channel_url, 15)
            return []

        items = _cached(cache_key, fetch_related)
        entries = "\n".join(_build_entry(v, base) for v in items if _build_entry(v, base))
        feed_id = f"{base}/feeds/api/videos/{video_id}/related"
        self._send_xml(_wrap_feed("Related Videos", entries, base, feed_id))

    def _handle_comments(self, video_id):
        base = self._base_url()
        xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:gd="http://schemas.google.com/g/2005" xmlns:yt="http://gdata.youtube.com/schemas/2007">
  <id>tag:youtube.com,2008:video:{_esc(video_id)}:comments</id>
  <title>Comments</title>
  <author><name>TubeFixer</name></author>
</feed>"""
        self._send_xml(xml)

    def _handle_user_feeds(self, path, qs):
        base = self._base_url()
        clean = path.strip("/")
        parts = clean.split("/")
        username = parts[3] if len(parts) > 3 else "weiyo"
        subfeed = parts[4] if len(parts) > 4 else ""

        if not subfeed or subfeed == "profile":
            xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<entry xmlns='http://www.w3.org/2005/Atom' xmlns:media='http://search.yahoo.com/mrss/' xmlns:yt='http://gdata.youtube.com/schemas/2007' xmlns:gd='http://schemas.google.com/g/2005'>
  <id>tag:youtube.com,2008:user:{_esc(username)}</id>
  <published>2012-01-01T00:00:00.000Z</published>
  <updated>2026-09-10T00:00:00.000Z</updated>
  <category scheme='http://schemas.google.com/g/2005#kind' term='http://gdata.youtube.com/schemas/2007#userProfile'/>
  <title type='text'>{_esc(username)}</title>
  <summary type='text'>{_esc(username)}'s Profile</summary>
  <author>
    <name>{_esc(username)}</name>
    <uri>{base}/feeds/api/users/{_esc(username)}</uri>
  </author>
  <yt:userId>{_esc(username)}</yt:userId>
  <yt:username>{_esc(username)}</yt:username>
  <yt:statistics viewCount="100" subscriberCount="1" lastWebAccess="2026-09-10T00:00:00.000Z"/>
  <gd:feedLink rel='http://gdata.youtube.com/schemas/2007#user.subscriptions' href='{base}/feeds/api/users/{_esc(username)}/subscriptions' countHint='0'/>
  <gd:feedLink rel='http://gdata.youtube.com/schemas/2007#user.playlists' href='{base}/feeds/api/users/{_esc(username)}/playlists' countHint='0'/>
  <gd:feedLink rel='http://gdata.youtube.com/schemas/2007#user.favorites' href='{base}/feeds/api/users/{_esc(username)}/favorites' countHint='0'/>
  <gd:feedLink rel='http://gdata.youtube.com/schemas/2007#user.uploads' href='{base}/feeds/api/users/{_esc(username)}/uploads' countHint='0'/>
</entry>"""
        else:
            xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom' xmlns:openSearch='http://a9.com/-/spec/opensearch/1.1/' xmlns:yt='http://gdata.youtube.com/schemas/2007'>
  <id>tag:youtube.com,2008:user:{_esc(username)}:{_esc(subfeed)}</id>
  <title type='text'>{_esc(username)}'s {_esc(subfeed)}</title>
  <author><name>{_esc(username)}</name></author>
  <openSearch:totalResults>0</openSearch:totalResults>
  <openSearch:startIndex>1</openSearch:startIndex>
  <openSearch:itemsPerPage>25</openSearch:itemsPerPage>
</feed>"""
        self._send_xml(xml)

    def _generate_macmini_installer(self):
        return """#!/bin/bash
set -e

echo "=========================================================="
echo " 🚀 開始在 Mac mini 上部署 iOS 6 懷舊中繼伺服器 (24/7 常駐)"
echo "=========================================================="

PYTHON_BIN=""
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 $(command -v python3 2>/dev/null) /usr/bin/python3; do
    if [ -n "$p" ] && [ -x "$p" ]; then
        PYTHON_BIN="$p"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 找不到 Python 3，請先安裝 Python 3！"
    exit 1
fi
echo "✅ 使用 Python 3: $PYTHON_BIN"

echo "📦 正在安裝依賴套件 (requests, pillow, beautifulsoup4, readability-lxml)..."
$PYTHON_BIN -m pip install requests pillow beautifulsoup4 readability-lxml --break-system-packages 2>/dev/null || \\
$PYTHON_BIN -m pip install requests pillow beautifulsoup4 readability-lxml 2>/dev/null || \\
$PYTHON_BIN -m pip install --user requests pillow beautifulsoup4 readability-lxml --break-system-packages 2>/dev/null || \\
$PYTHON_BIN -m pip install requests pillow beautifulsoup4 2>/dev/null || true
$PYTHON_BIN -m pip install yt-dlp --break-system-packages 2>/dev/null || $PYTHON_BIN -m pip install yt-dlp 2>/dev/null || true

YTDLP_BIN=""
for y in /opt/homebrew/bin/yt-dlp /usr/local/bin/yt-dlp ~/.local/bin/yt-dlp $(command -v yt-dlp 2>/dev/null); do
    if [ -n "$y" ] && [ -x "$y" ]; then
        YTDLP_BIN="$y"
        break
    fi
done

if [ -z "$YTDLP_BIN" ]; then
    echo "⬇️ 正在獲取 yt-dlp..."
    mkdir -p ~/.local/bin
    curl -sL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ~/.local/bin/yt-dlp 2>/dev/null || \\
    curl -s http://192.168.0.155:8767/raw_ytdlp -o ~/.local/bin/yt-dlp
    chmod a+rx ~/.local/bin/yt-dlp
    YTDLP_BIN="$HOME/.local/bin/yt-dlp"
fi
echo "✅ 使用 yt-dlp: $YTDLP_BIN"

echo "⬇️ 正在下載已除錯調校完成的中繼代理程式..."
mkdir -p ~/.local/share/tuberepair
curl -s http://192.168.0.155:8767/raw_proxy_code -o ~/.local/share/tuberepair/tuberepair_proxy.py

echo "⚙️ 正在註冊 LaunchAgent 開機自動常駐服務..."
mkdir -p ~/Library/LaunchAgents
cat <<EOF > ~/Library/LaunchAgents/com.weiyo.tuberepair.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.weiyo.tuberepair</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$HOME/.local/share/tuberepair/tuberepair_proxy.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/tuberepair_proxy.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/tuberepair_proxy.log</string>
</dict>
</plist>
EOF

launchctl unload ~/Library/LaunchAgents/com.weiyo.tuberepair.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.weiyo.tuberepair.plist
launchctl kickstart -k gui/$(id -u)/com.weiyo.tuberepair 2>/dev/null || true

sleep 2
if curl -s http://127.0.0.1:8767/status | grep -q "TubeRepair"; then
    echo ""
    echo "=========================================================="
    echo "  🎉 部署成功！Mac mini 上的懷舊中繼伺服器已正常運行！"
    echo "  服務網址: http://192.168.0.115:8767"
    echo "  以後 MacBook 關機，iPhone 4s 也隨時可以上網與看 YouTube！"
    echo "=========================================================="
else
    echo "⚠️ 正在背景啟動中，請稍候..."
fi
"""

    def _handle_thumbnail(self, vid, name):
        cache_key = f"thumb:{vid}:{name}"
        def fetch_thumb():
            try:
                res = requests.get(f"https://i.ytimg.com/vi/{vid}/{name}", timeout=10)
                if res.status_code == 200:
                    return res.content
            except Exception as e:
                print(f"[thumb err] {e}")
            return None

        img_bytes = _cached(cache_key, fetch_thumb)
        if img_bytes:
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(img_bytes)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(img_bytes)
        else:
            self.send_error(404)

    def _handle_getvideo(self, video_id):
        stream_url = _get_stream_url(video_id)
        if not stream_url:
            print(f"[STREAM ERR] Could not find stream URL for {video_id}")
            self.send_error(502, "Could not extract video stream")
            return

        upstream_headers = {}
        range_header = self.headers.get("Range")
        if range_header:
            upstream_headers["Range"] = range_header
            print(f"[STREAM] {video_id} requested Range: {range_header}")
        else:
            print(f"[STREAM] {video_id} requested full stream")

        try:
            upstream = requests.get(stream_url, headers=upstream_headers, stream=True, timeout=30)
        except Exception as e:
            print(f"[STREAM ERR] Connect error: {e}")
            self.send_error(502, f"Failed to connect to stream: {e}")
            return

        self.send_response(upstream.status_code)
        for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified", "ETag"):
            val = upstream.headers.get(h)
            if val:
                self.send_header(h, val)
        if not upstream.headers.get("Accept-Ranges"):
            self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        if self.command != "HEAD":
            try:
                for chunk in upstream.iter_content(chunk_size=128 * 1024):
                    self.wfile.write(chunk)
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                print(f"[STREAM DISCONNECT] {e}")

    def _handle_categories(self):
        xml = """<?xml version='1.0' encoding='UTF-8'?>
<app:categories xmlns:app="http://www.w3.org/2007/app" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:yt="http://gdata.youtube.com/schemas/2007" scheme="http://gdata.youtube.com/schemas/2007/categories.cat">
  <atom:category term="Music" label="Music"><yt:browsable regions="US"/></atom:category>
  <atom:category term="Entertainment" label="Entertainment"><yt:browsable regions="US"/></atom:category>
  <atom:category term="Gaming" label="Gaming"><yt:browsable regions="US"/></atom:category>
  <atom:category term="Sports" label="Sports"><yt:browsable regions="US"/></atom:category>
  <atom:category term="News" label="News"><yt:browsable regions="US"/></atom:category>
</app:categories>"""
        self._send_weather_xml(xml)

    def _handle_applelogin1(self):
        r2 = uuid.uuid4().hex
        hmackr2 = uuid.uuid4().hex
        body = f"r2={r2}\nhmackr2={hmackr2}\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        print(f"[AUTH] Handled applelogin1 -> r2={r2[:8]}...")

    def _handle_applelogin2(self):
        auth = uuid.uuid4().hex
        body = f"Auth={auth}\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        print(f"[AUTH] Handled applelogin2 -> Auth={auth[:8]}...")

    def _handle_register_device(self):
        key = uuid.uuid4().hex
        body = f"DeviceId={key}\nDeviceKey={key}\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        print(f"[AUTH] Handled registerDevice -> {key[:8]}...")

    def _handle_weather(self, q):
        if not q:
            self._send_weather_xml(_weather_multi_xml(["2306179"]))
            return

        print(f"[WEATHER QUERY] {q[:120]}...")
        if "partner.weather.locations" in q and "yql.query.multi" not in q:
            m = re.search(r'query="([^"]+)"', q)
            query_city = m.group(1) if m else "Taipei"
            xml = _weather_search_xml(query_city)
            self._send_weather_xml(xml)
        else:
            lat = None
            lon = None
            lat_m = re.search(r'lat=([0-9\.\-]+)', q)
            lon_m = re.search(r'lon=([0-9\.\-]+)', q)
            if lat_m and lon_m:
                lat = float(lat_m.group(1))
                lon = float(lon_m.group(1))

            woeid_m = re.findall(r'woeid\s*(?:in|=)\s*\(?([0-9\s,]+)\)?', q)
            woeids = []
            if woeid_m:
                for grp in woeid_m:
                    for w in grp.split(","):
                        w = w.strip()
                        if w and w.isdigit() and w not in woeids:
                            woeids.append(w)
            if not woeids and (lat is None or lon is None):
                woeids = ["2306188"]

            xml = _weather_multi_xml(woeids, lat=lat, lon=lon)
            self._send_weather_xml(xml)

    def _send_web_home(self):
        base = self._base_url()
        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>懷舊網頁傳送門</title>
<style>
* {{ -webkit-box-sizing: border-box; box-sizing: border-box; -webkit-tap-highlight-color: rgba(0,0,0,0); }}
body {{
    margin: 0;
    padding: 0;
    font-family: -apple-system, "Heiti TC", "Helvetica Neue", Helvetica, Arial, sans-serif;
    background: #c5ccd4 url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAIElEQVQIW2NkQAOMQGBkQAcwGqEAXAAMg4MhAMUDAE4qAQkS+w1VAAAAAElFTkSuQmCC') repeat;
    color: #333;
    -webkit-text-size-adjust: 100%;
}}
.header {{
    background: linear-gradient(#b0bcc9, #8292a4 50%, #75869a 51%, #677a8e);
    border-bottom: 1px solid #455567;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    padding: 10px 15px;
    text-align: center;
}}
.header h1 {{
    margin: 0;
    font-size: 18px;
    color: #fff;
    text-shadow: 0 -1px 0 rgba(0,0,0,0.6);
    font-weight: bold;
}}
.container {{
    padding: 12px 10px 20px;
    max-width: 500px;
    margin: 0 auto;
}}
.search-card {{
    background: #fff;
    border: 1px solid #a5b1c0;
    border-radius: 8px;
    padding: 12px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.15);
    margin-bottom: 14px;
}}
.search-input {{
    width: 100%;
    padding: 8px 10px;
    font-size: 15px;
    border: 1px solid #bbb;
    border-radius: 6px;
    outline: none;
    -webkit-appearance: none;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
}}
.engine-row {{
    display: flex;
    justify-content: space-around;
    margin: 10px 0 12px;
    font-size: 13px;
    color: #444;
}}
.engine-row label {{
    display: flex;
    align-items: center;
    cursor: pointer;
}}
.submit-btn {{
    width: 100%;
    padding: 10px;
    background: linear-gradient(#5a88ca, #3b6fb5 50%, #2e5f9e 51%, #244f88);
    border: 1px solid #1a3d6d;
    border-radius: 6px;
    color: #fff;
    font-size: 15px;
    font-weight: bold;
    text-shadow: 0 -1px 0 rgba(0,0,0,0.5);
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}}
.section-title {{
    font-size: 13px;
    color: #4c5663;
    text-shadow: 0 1px 0 rgba(255,255,255,0.7);
    font-weight: bold;
    margin: 12px 4px 6px;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 8px;
}}
.grid-item {{
    background: #fff;
    border: 1px solid #b2bcc8;
    border-radius: 8px;
    padding: 10px 4px;
    text-align: center;
    text-decoration: none;
    color: #333;
    font-size: 12px;
    font-weight: bold;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    display: block;
}}
.grid-item:active {{
    background: #e5edf5;
}}
.grid-icon {{
    font-size: 22px;
    margin-bottom: 3px;
    display: block;
}}
.grid-sub {{
    font-size: 10px;
    color: #777;
    font-weight: normal;
    display: block;
    margin-top: 2px;
}}
.footer {{
    text-align: center;
    font-size: 11px;
    color: #556;
    margin-top: 18px;
    text-shadow: 0 1px 0 rgba(255,255,255,0.6);
    line-height: 1.5;
}}
</style>
</head>
<body>
<div class="header" style="position: relative;">
    <a href="{base}/" style="position: absolute; left: 10px; top: 9px; background: linear-gradient(#5a88ca, #2e5f9e); color: #fff; text-decoration: none; padding: 4px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #1a3d6d; font-size: 11px; text-shadow: 0 -1px 0 rgba(0,0,0,0.5);">📱 儀表板</a>
    <h1>懷舊網頁加速傳送門</h1>
</div>
<div class="container">
    <div class="search-card">
        <form action="{base}/web" method="GET">
            <div style="background: #e8f0fe; border: 1px solid #c2d7f5; border-radius: 6px; padding: 6px 10px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between;">
                <span style="font-size: 12px; font-weight: bold; color: #1a56a6;">📍 所在定位：桃園市 (Taoyuan)</span>
                <label style="font-size: 11px; color: #333; cursor: pointer; display: flex; align-items: center;">
                    <input type="checkbox" name="loc" value="taoyuan" checked style="margin-right: 3px;" /> 鎖定桃園
                </label>
            </div>
            <input type="text" name="q" class="search-input" placeholder="輸入關鍵字或網址 (如 美食、天氣、Threads)..." autofocus />
            <div class="engine-row">
                <label><input type="radio" name="engine" value="smart" checked /> 智慧搜尋</label>
                <label><input type="radio" name="engine" value="wiki" /> 維基</label>
                <label><input type="radio" name="engine" value="direct" /> 直達網址</label>
            </div>
            <button type="submit" class="submit-btn">立即前往 / 搜尋</button>
            <div style="margin-top: 10px; font-size: 11px; color: #667; line-height: 1.6;">
                <span style="font-weight: bold; color: #444;">熱門桃園搜尋：</span>
                <a href="{base}/web?q=桃園美食&loc=taoyuan" style="color: #1a56a6; text-decoration: none; background: #eef2f8; padding: 2px 5px; border-radius: 3px; border: 1px solid #ccd6e0; display: inline-block; margin: 2px;">🍲 美食</a>
                <a href="{base}/web?q=桃園即時天氣&loc=taoyuan" style="color: #1a56a6; text-decoration: none; background: #eef2f8; padding: 2px 5px; border-radius: 3px; border: 1px solid #ccd6e0; display: inline-block; margin: 2px;">⛅ 天氣</a>
                <a href="{base}/web?q=桃園電影院時刻表&loc=taoyuan" style="color: #1a56a6; text-decoration: none; background: #eef2f8; padding: 2px 5px; border-radius: 3px; border: 1px solid #ccd6e0; display: inline-block; margin: 2px;">🎬 電影</a>
                <a href="{base}/web?q=桃園景點推薦&loc=taoyuan" style="color: #1a56a6; text-decoration: none; background: #eef2f8; padding: 2px 5px; border-radius: 3px; border: 1px solid #ccd6e0; display: inline-block; margin: 2px;">🏞️ 景點</a>
                <a href="{base}/web?q=桃園公車動態&loc=taoyuan" style="color: #1a56a6; text-decoration: none; background: #eef2f8; padding: 2px 5px; border-radius: 3px; border: 1px solid #ccd6e0; display: inline-block; margin: 2px;">🚌 公車</a>
            </div>
        </form>
    </div>

    <div class="section-title">💬 台灣熱門社群與討論區</div>
    <div class="grid">
        <a class="grid-item" href="{base}/web/threads">
            <span class="grid-icon">🧵</span>脆 Threads
            <span class="grid-sub">極速串流版</span>
        </a>
        <a class="grid-item" href="{base}/web?url=https://m.facebook.com">
            <span class="grid-icon">📘</span>臉書 FB
            <span class="grid-sub">行動簡易版</span>
        </a>
        <a class="grid-item" href="{base}/web/instagram">
            <span class="grid-icon">📷</span>Instagram
            <span class="grid-sub">熱門與名冊</span>
        </a>
        <a class="grid-item" href="{base}/web?url=https://m.gamer.com.tw">
            <span class="grid-icon">🎮</span>巴哈姆特
            <span class="grid-sub">哈啦區與新聞</span>
        </a>
        <a class="grid-item" href="{base}/web?url=https://disp.cc/m/">
            <span class="grid-icon">📟</span>PTT 批踢踢
            <span class="grid-sub">Disp 極速版</span>
        </a>
        <a class="grid-item" href="{base}/web/dcard">
            <span class="grid-icon">🎓</span>Dcard
            <span class="grid-sub">熱門話題版</span>
        </a>
        <a class="grid-item" href="{base}/web?q=Mobile01%20熱門討論">
            <span class="grid-icon">📱</span>Mobile01
            <span class="grid-sub">科技與生活</span>
        </a>
        <a class="grid-item" href="{base}/web?url=https://mzh.moegirl.org.cn">
            <span class="grid-icon">🌸</span>萌娘百科
            <span class="grid-sub">動漫與ACG</span>
        </a>
        <a class="grid-item" href="{base}/web?url=https://zh.m.wikipedia.org">
            <span class="grid-icon">📖</span>中文維基
            <span class="grid-sub">百科全書</span>
        </a>
    </div>

    <div class="section-title">📰 即時新聞、影音與工具</div>
    <div class="grid">
        <a class="grid-item" href="{base}/web/yahoo">
            <span class="grid-icon">📰</span>Yahoo新聞
            <span class="grid-sub">即時焦點頭條</span>
        </a>
        <a class="grid-item" href="{base}/web/youtube">
            <span class="grid-icon">📺</span>YouTube 網頁
            <span class="grid-sub">經典播放器版</span>
        </a>
        <a class="grid-item" href="{base}/web/weather">
            <span class="grid-icon">⛅</span>中央氣象署
            <span class="grid-sub">桃園即時天氣</span>
        </a>
    </div>

    <div class="footer">
        專為 iPhone 4s (iOS 6.1.3) 極致打造<br>
        即時排版防破版修復 &bull; WebP 轉碼 JPEG &bull; 影片相容串流注入
    </div>
</div>
</body>
</html>"""
        data = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_web_search(self, query, loc="taoyuan"):
        base = self._base_url()
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        effective_query = query.strip()
        is_taoyuan_locked = (loc != "all")

        LOCAL_KEYWORDS = (
            "美食", "小吃", "餐廳", "早午餐", "早餐", "午餐", "晚餐", "宵夜", "火鍋", "牛排",
            "咖啡", "下午茶", "景點", "步道", "夜市", "天氣", "氣溫", "下雨", "電影", "影城",
            "醫院", "診所", "藥局", "公車", "捷運", "客運", "高鐵", "火車站", "台鐵", "路況",
            "活動", "市集", "圖書館", "國小", "國中", "高中", "大學", "行政中心", "公所",
            "找工作", "買屋", "租屋", "房價", "停車場", "加油站", "郵局", "銀行", "便當", "麵包"
        )
        OTHER_CITIES = (
            "台北", "新北", "基隆", "新竹", "苗栗", "台中", "彰化", "南投", "雲林",
            "嘉義", "台南", "高雄", "屏東", "宜蘭", "花蓮", "台東", "澎湖", "金門", "馬祖"
        )
        TAOYUAN_AREAS = (
            "桃園", "中壢", "八德", "平鎮", "龜山", "蘆竹", "南崁", "大溪", "楊梅",
            "龍潭", "大園", "新屋", "觀音", "復興", "青埔", "藝文特區"
        )

        has_other_city = any(c in effective_query for c in OTHER_CITIES)
        has_taoyuan_area = any(a in effective_query for a in TAOYUAN_AREAS)
        is_local_intent = any(k in effective_query for k in LOCAL_KEYWORDS)

        search_query = effective_query
        auto_localized = False
        if is_taoyuan_locked and not has_other_city and not has_taoyuan_area:
            if is_local_intent:
                search_query = f"{effective_query} 桃園"
                auto_localized = True

        results = []
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": search_query, "kl": "tw-tzh"},
                headers=headers,
                timeout=12
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for tr in soup.find_all("tr"):
                a = tr.select_one("a.result-link")
                if not a:
                    continue
                raw_href = a.get("href", "")
                m = re.search(r"uddg=([^&]+)", raw_href)
                target_url = unquote(m.group(1)) if m else raw_href
                if not target_url.startswith("http"):
                    continue

                title = a.get_text(strip=True)
                snippet = ""
                next_tr = tr.find_next_sibling("tr")
                if next_tr:
                    s_td = next_tr.select_one(".result-snippet")
                    if s_td:
                        snippet = s_td.get_text(strip=True)

                display_url = urlparse(target_url).netloc
                results.append((title, target_url, display_url, snippet))
        except Exception as e:
            print(f"[LITE SEARCH ERR] {e}")

        if not results:
            try:
                resp = requests.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": search_query, "kl": "tw-tzh"},
                    headers=headers,
                    timeout=12
                )
                soup = BeautifulSoup(resp.text, "html.parser")
                for res_div in soup.select(".result"):
                    a_title = res_div.select_one(".result__title .result__a, .result__a")
                    if not a_title:
                        continue
                    raw_href = a_title.get("href", "")
                    m = re.search(r"uddg=([^&]+)", raw_href)
                    target_url = unquote(m.group(1)) if m else raw_href
                    if not target_url.startswith("http"):
                        continue

                    title = a_title.get_text(strip=True)
                    snippet_el = res_div.select_one(".result__snippet")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    url_el = res_div.select_one(".result__url")
                    display_url = url_el.get_text(strip=True) if url_el else target_url

                    results.append((title, target_url, display_url, snippet))
            except Exception as e:
                print(f"[HTML SEARCH ERR] {e}")

        cards_html = []
        if results:
            for title, target_url, display_url, snippet in results:
                card = f"""<div class="res-card">
    <a class="res-title" href="{base}/web?url={quote(target_url)}">{html.escape(title)}</a>
    <div class="res-url">{html.escape(display_url)}</div>
    <div class="res-snippet">{html.escape(snippet)}</div>
</div>"""
                cards_html.append(card)
        else:
            cards_html.append(f"""<div class="res-card" style="text-align: center; padding: 20px 10px;">
    <div style="font-size: 16px; font-weight: bold; margin-bottom: 8px;">未找到即時結果</div>
    <p style="color: #666; font-size: 13px;">您可以嘗試：</p>
    <div style="margin-top: 12px;">
        <a href="{base}/web?url={quote('https://zh.m.wikipedia.org/wiki/' + quote(search_query))}" style="display:inline-block; margin:4px; padding:6px 12px; background:#4a82c4; color:#fff; border-radius:4px; text-decoration:none; font-size:13px;">搜尋維基百科</a>
    </div>
</div>""")

        all_cards = "\n".join(cards_html)
        toggle_loc = "all" if is_taoyuan_locked else "taoyuan"
        toggle_text = "🌐 改為全台搜尋" if is_taoyuan_locked else "📍 鎖定桃園搜尋"

        sub_info = f"（已自動附加桃園在地範圍：{html.escape(search_query)}）" if auto_localized else ""
        loc_badge = "📍 台灣桃園市 (Taoyuan)" if is_taoyuan_locked else "🌐 全台灣地區"

        page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>搜尋結果：{html.escape(query)}</title>
<style>
* {{ -webkit-box-sizing: border-box; box-sizing: border-box; -webkit-tap-highlight-color: rgba(0,0,0,0); }}
body {{
    margin: 0;
    padding: 0;
    font-family: -apple-system, "Heiti TC", "Helvetica Neue", Helvetica, Arial, sans-serif;
    background: #eef1f4;
    color: #222;
    -webkit-text-size-adjust: 100%;
}}
.top-bar {{
    background: linear-gradient(#b0bcc9, #8292a4 50%, #75869a 51%, #677a8e);
    border-bottom: 1px solid #455567;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    position: sticky;
    top: 0;
    z-index: 999;
}}
.home-btn {{
    background: linear-gradient(#5a88ca, #2e5f9e);
    color: #fff;
    text-decoration: none;
    padding: 5px 10px;
    border-radius: 4px;
    font-weight: bold;
    border: 1px solid #1a3d6d;
    font-size: 12px;
    white-space: nowrap;
    text-shadow: 0 -1px 0 rgba(0,0,0,0.5);
}}
.search-form {{
    margin-left: 6px;
    flex: 1;
    display: flex;
}}
.search-input {{
    width: 100%;
    padding: 5px 8px;
    border: 1px solid #666;
    border-radius: 4px;
    font-size: 13px;
    outline: none;
    -webkit-appearance: none;
}}
.res-container {{
    padding: 10px;
    max-width: 550px;
    margin: 0 auto;
}}
.res-info-bar {{
    background: #e8f0fe;
    border: 1px solid #c2d7f5;
    border-radius: 6px;
    padding: 6px 10px;
    margin: 4px 0 10px;
    font-size: 12px;
    color: #1a56a6;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.res-count {{
    font-size: 12px;
    color: #667;
    margin: 4px 4px 8px;
}}
.res-card {{
    background: #fff;
    border: 1px solid #ccd3dc;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.res-card:active {{
    background: #f4f7fa;
}}
.res-title {{
    font-size: 16px;
    font-weight: bold;
    color: #1a56a6;
    text-decoration: none;
    display: block;
    line-height: 1.35;
    margin-bottom: 4px;
}}
.res-url {{
    font-size: 11px;
    color: #2e7d32;
    word-break: break-all;
    margin-bottom: 6px;
}}
.res-snippet {{
    font-size: 13px;
    line-height: 1.45;
    color: #444;
}}
</style>
</head>
<body>
<div class="top-bar">
    <a href="{base}/web" class="home-btn">首頁</a>
    <form action="{base}/web" method="GET" class="search-form">
        <input type="text" name="q" value="{html.escape(query)}" class="search-input" />
        <input type="hidden" name="loc" value="{html.escape(loc)}" />
    </form>
</div>
<div class="res-container">
    <div class="res-info-bar">
        <span>📍 定位：{loc_badge}</span>
        <a href="{base}/web?q={quote(query)}&loc={toggle_loc}" style="color: #1a56a6; text-decoration: underline; font-size: 11px; font-weight: bold;">{toggle_text}</a>
    </div>
    <div class="res-count">搜尋關鍵字：「{html.escape(query)}」{sub_info}・共找到 {len(results)} 筆結果</div>
    {all_cards}
</div>
</body>
</html>"""
        data = page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_threads_hub(self, qs):
        base = self._base_url()
        query = qs.get("q", [""])[0].strip()
        user_param = qs.get("u", [""])[0].strip()

        target_user = ""
        if user_param:
            target_user = user_param.lstrip("@")
        elif query.startswith("@"):
            target_user = query.lstrip("@")

        user_card_html = ""
        cards_html = ""

        if target_user:
            try:
                r = requests.get(f"https://www.threads.com/@{target_user}", headers={"User-Agent": "Twitterbot/1.0"}, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                og_title = soup.find("meta", {"property": "og:title"})
                og_desc = soup.find("meta", {"property": "og:description"})
                og_img = soup.find("meta", {"property": "og:image"})
                t_txt = og_title.get("content", "") if og_title else f"@{target_user}"
                d_txt = og_desc.get("content", "") if og_desc else ""
                i_url = og_img.get("content", "") if og_img else ""
                img_tag = f'<img src="{base}/surf?url={quote(i_url)}" style="width:50px;height:50px;border-radius:25px;float:left;margin-right:10px;border:1px solid #ccc;"/>' if i_url else ''
                user_card_html = f"""
                <div style="background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:12px; margin-bottom:12px; overflow:hidden;">
                    {img_tag}
                    <div style="font-weight:bold; font-size:15px; color:#111;">{html.escape(t_txt)}</div>
                    <div style="font-size:12px; color:#555; margin-top:4px;">{html.escape(d_txt)}</div>
                </div>
                """
            except Exception as e:
                user_card_html = f'<div style="color:red;font-size:12px;">載入用戶資料失敗: {e}</div>'

        search_kw = query if (query and not target_user) else "threads 台灣 熱門話題"
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": f"{search_kw}", "kl": "tw-tzh"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a.result-link")[:12]:
                title = a.get_text().strip()
                href = a.get("href", "")
                if "uddg=" in href:
                    m = re.search(r"uddg=([^&]+)", href)
                    if m:
                        href = urllib.parse.unquote(m.group(1))
                tr = a.find_parent("tr")
                snip = tr.find_next_sibling("tr").get_text().strip() if tr and tr.find_next_sibling("tr") else ""
                if len(title) > 2:
                    cards_html += f"""
                    <div style="background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:12px 14px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div style="font-size:14px; font-weight:bold; line-height:1.4; margin-bottom:5px;">
                            <a href="{base}/web?url={quote(href)}" style="color:#1a56a6; text-decoration:none;">{html.escape(title)}</a>
                        </div>
                        <div style="font-size:12px; color:#444; line-height:1.5; margin-bottom:6px;">{html.escape(snip)}</div>
                        <div style="font-size:10px; color:#888; display:flex; justify-content:space-between;">
                            <span>🧵 脆話題討論</span>
                            <a href="{base}/web?url={quote(href)}" style="color:#2b66ad; text-decoration:none; font-weight:bold;">閱讀串文 &rarr;</a>
                        </div>
                    </div>
                    """
        except Exception as e:
            cards_html = f'<div style="padding:20px;text-align:center;color:#666;">載入熱門話題失敗: {e}</div>'

        page_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><title>🧵 脆 Threads 極速版</title>
        <style>
        * {{ -webkit-box-sizing: border-box; box-sizing: border-box; }}
        body {{ margin:0; padding:0; font-family: -apple-system, "Heiti TC", Helvetica, Arial, sans-serif; background: #c5ccd4; color:#333; }}
        .header {{ background: linear-gradient(#333, #111); padding: 10px 12px; text-align:center; color:#fff; font-size:16px; font-weight:bold; text-shadow:0 -1px 0 #000; border-bottom:1px solid #000; display:flex; align-items:center; justify-content:space-between; }}
        .nav-btn {{ background: linear-gradient(#5a88ca, #244f88); border: 1px solid #1a3d6d; color:#fff; padding:4px 8px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; }}
        .container {{ padding:10px; max-width:550px; margin:0 auto; }}
        .search-box {{ background:#fff; border-radius:8px; border:1px solid #a5b1c0; padding:10px; margin-bottom:12px; }}
        .input-bar {{ width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; outline:none; -webkit-appearance:none; }}
        .btn-sub {{ width:100%; margin-top:8px; padding:8px; background:linear-gradient(#444, #111); border:1px solid #000; border-radius:6px; color:#fff; font-weight:bold; font-size:14px; cursor:pointer; }}
        .quick-tags {{ margin-top:8px; font-size:11px; }}
        .quick-tags a {{ color:#1a56a6; text-decoration:none; background:#eef2f8; padding:2px 6px; border-radius:3px; border:1px solid #ccd6e0; display:inline-block; margin:2px 1px; }}
        </style></head><body>
        <div class="header">
            <a href="{base}/web" class="nav-btn">&larr; 首頁</a>
            <span>🧵 脆 Threads 極速版</span>
            <a href="{base}/web/threads" class="nav-btn">重整</a>
        </div>
        <div class="container">
            <div class="search-box">
                <form action="{base}/web/threads" method="GET">
                    <input type="text" name="q" class="input-bar" placeholder="輸入關鍵字或 @帳號 (如 @zuck, @netflixtw)..." value="{html.escape(query)}" />
                    <button type="submit" class="btn-sub">搜尋 Threads 話題或使用者</button>
                    <div class="quick-tags">
                        <span style="font-weight:bold; color:#555;">熱門：</span>
                        <a href="{base}/web/threads?q=台灣+熱議">🔥 熱門話題</a>
                        <a href="{base}/web/threads?q=桃園+美食">🍲 桃園美食</a>
                        <a href="{base}/web/threads?u=zuck">👤 @zuck</a>
                        <a href="{base}/web/threads?u=netflixtw">🍿 @netflixtw</a>
                    </div>
                </form>
            </div>
            {user_card_html}
            {cards_html}
        </div></body></html>"""
        data = page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_yahoo_hub(self, qs):
        base = self._base_url()
        try:
            r = requests.get("https://tw.news.yahoo.com/rss", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(r.content, "html.parser")
            items = soup.find_all("item")
            cards = []
            for it in items[:25]:
                t = it.find("title").get_text().strip() if it.find("title") else ""
                t = re.sub(r"^<!\[CDATA\[|\]\]>$", "", t)
                l = it.find("link")
                link_text = l.next_sibling.strip() if (l and l.next_sibling) else (l.get_text().strip() if l else "")
                desc = it.find("description").get_text().strip() if it.find("description") else ""
                desc = re.sub(r"<[^>]+>", "", desc)
                desc = re.sub(r"^<!\[CDATA\[|\]\]>$", "", desc).strip()
                if t and link_text:
                    cards.append(f"""
                    <div style="background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:12px 14px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div style="font-size:15px; font-weight:bold; line-height:1.4; margin-bottom:6px;">
                            <a href="{base}/web?url={quote(link_text)}&mode=reader" style="color:#1a56a6; text-decoration:none;">{html.escape(t)}</a>
                        </div>
                        <div style="font-size:12px; color:#444; line-height:1.5; margin-bottom:6px;">{html.escape(desc[:100])}...</div>
                        <div style="font-size:11px; color:#777; text-align:right;">
                            <a href="{base}/web?url={quote(link_text)}&mode=reader" style="color:#2b66ad; text-decoration:none; font-weight:bold;">即刻全文閱讀 &rarr;</a>
                        </div>
                    </div>
                    """)
            cards_html = "\n".join(cards)
        except Exception as e:
            cards_html = f'<div style="color:red;padding:20px;">獲取新聞失敗: {e}</div>'

        page_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><title>📰 Yahoo! 奇摩新聞即時焦點</title>
        <style>
        * {{ -webkit-box-sizing: border-box; box-sizing: border-box; }}
        body {{ margin:0; padding:0; font-family: -apple-system, "Heiti TC", Helvetica, Arial, sans-serif; background: #c5ccd4; color:#333; }}
        .header {{ background: linear-gradient(#5a2d82, #391854); padding: 10px 12px; text-align:center; color:#fff; font-size:16px; font-weight:bold; text-shadow:0 -1px 0 #000; border-bottom:1px solid #240c36; display:flex; align-items:center; justify-content:space-between; }}
        .nav-btn {{ background: linear-gradient(#5a88ca, #244f88); border: 1px solid #1a3d6d; color:#fff; padding:4px 8px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; }}
        .container {{ padding:10px; max-width:550px; margin:0 auto; }}
        </style></head><body>
        <div class="header">
            <a href="{base}/web" class="nav-btn">&larr; 首頁</a>
            <span>📰 Yahoo! 新聞焦點</span>
            <a href="{base}/web/yahoo" class="nav-btn">重整</a>
        </div>
        <div class="container">
            <div style="background:#eef2f8; border:1px solid #ccd6e0; border-radius:6px; padding:6px 10px; margin-bottom:10px; font-size:12px; color:#444;">
                🇹🇼 台灣即時熱門要聞 • 點擊任意新聞自動啟動 📱 經典極速閱讀模式
            </div>
            {cards_html}
        </div></body></html>"""
        data = page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_weather_hub(self, qs):
        base = self._base_url()
        try:
            w_url = "https://api.open-meteo.com/v1/forecast?latitude=24.9937&longitude=121.2970&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia%2FTaipei"
            r = requests.get(w_url, timeout=10)
            d = r.json()
            curr = d.get("current", {})
            temp = curr.get("temperature_2m", 25)
            app_temp = curr.get("apparent_temperature", 26)
            hum = curr.get("relative_humidity_2m", 70)
            daily = d.get("daily", {})
            dates = daily.get("time", [])
            maxs = daily.get("temperature_2m_max", [])
            mins = daily.get("temperature_2m_min", [])
            pops = daily.get("precipitation_probability_max", [])

            daily_rows = []
            for i in range(min(5, len(dates))):
                dt = dates[i]
                mx = maxs[i] if i < len(maxs) else ""
                mn = mins[i] if i < len(mins) else ""
                p = pops[i] if i < len(pops) else 0
                daily_rows.append(f"""
                <tr style="border-bottom:1px solid #eee; text-align:center;">
                    <td style="padding:6px; font-weight:bold; font-size:12px;">{dt[5:]}</td>
                    <td style="padding:6px; color:#c33; font-size:12px;">{mx}&deg;</td>
                    <td style="padding:6px; color:#247; font-size:12px;">{mn}&deg;</td>
                    <td style="padding:6px; color:#06c; font-size:12px;">💧 {p}%</td>
                </tr>
                """)
            daily_html = "".join(daily_rows)
        except Exception as e:
            temp = 25
            app_temp = 26
            hum = 70
            daily_html = f"<tr><td colspan='4'>載入天氣異常: {e}</td></tr>"

        page_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><title>⛅ 台灣氣象與即時特報</title>
        <style>
        * {{ -webkit-box-sizing: border-box; box-sizing: border-box; }}
        body {{ margin:0; padding:0; font-family: -apple-system, "Heiti TC", Helvetica, Arial, sans-serif; background: #c5ccd4; color:#333; }}
        .header {{ background: linear-gradient(#4a8cdb, #245ea3); padding: 10px 12px; text-align:center; color:#fff; font-size:16px; font-weight:bold; text-shadow:0 -1px 0 #183e6b; border-bottom:1px solid #183e6b; display:flex; align-items:center; justify-content:space-between; }}
        .nav-btn {{ background: linear-gradient(#5a88ca, #244f88); border: 1px solid #1a3d6d; color:#fff; padding:4px 8px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; }}
        .container {{ padding:10px; max-width:550px; margin:0 auto; }}
        .card {{ background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:14px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
        </style></head><body>
        <div class="header">
            <a href="{base}/web" class="nav-btn">&larr; 首頁</a>
            <span>⛅ 台灣即時氣象</span>
            <a href="{base}/web/weather" class="nav-btn">重整</a>
        </div>
        <div class="container">
            <div class="card" style="text-align:center; background:linear-gradient(#f0f6ff, #fff);">
                <div style="font-size:14px; font-weight:bold; color:#1a56a6;">📍 桃園市即時天氣 (Taoyuan)</div>
                <div style="font-size:42px; font-weight:bold; color:#222; margin:10px 0;">{temp}&deg;<span style="font-size:20px;">C</span></div>
                <div style="font-size:13px; color:#555;">體感溫度：{app_temp}&deg;C • 相對濕度：{hum}%</div>
            </div>
            <div class="card">
                <div style="font-size:13px; font-weight:bold; color:#444; margin-bottom:8px;">📅 桃園未來一週預報</div>
                <table style="width:100%; border-collapse:collapse;">
                    <tr style="background:#f5f7fa; font-size:11px; color:#666;">
                        <th style="padding:4px;">日期</th>
                        <th style="padding:4px;">最高</th>
                        <th style="padding:4px;">最低</th>
                        <th style="padding:4px;">降雨機率</th>
                    </tr>
                    {daily_html}
                </table>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:13px; font-weight:bold; color:#444; margin-bottom:8px;">🛰️ 中央氣象署雷達回波圖</div>
                <img src="{base}/surf?url=https://www.cwa.gov.tw/Data/radar/CV1_3600_1000.png" style="width:100%; max-width:320px; border-radius:6px; border:1px solid #ddd; margin:0 auto; display:block;" alt="雷達回波" />
            </div>
        </div></body></html>"""
        data = page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_youtube_hub(self, qs):
        base = self._base_url()
        query = qs.get("q", [""])[0].strip()
        search_kw = query if query else "熱門音樂 2026"
        items = _cached(f"hub_yt:{search_kw}", lambda: _ytdlp_flat(f"ytsearch15:{search_kw}", 15), ttl=1800)
        cards = []
        for it in items:
            vid = it.get("id") or ""
            t = it.get("title") or "Video"
            ch = it.get("uploader") or it.get("channel") or "Channel"
            dur = int(it.get("duration") or 0)
            dur_str = f"{dur//60}:{dur%60:02d}" if dur else ""
            if vid:
                cards.append(f"""
                <div style="background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:10px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                    <div style="position:relative; width:100%; max-width:320px; margin:0 auto 8px;">
                        <video controls="controls" width="100%" poster="{base}/thumb/{vid}/hqdefault.jpg" preload="none" style="background:#000; border-radius:6px; display:block; max-height:200px;">
                            <source src="{base}/getvideo/{vid}.mp4" type="video/mp4" />
                        </video>
                    </div>
                    <div style="font-size:14px; font-weight:bold; color:#222; line-height:1.3; margin-bottom:4px;">{html.escape(t)}</div>
                    <div style="font-size:11px; color:#666; display:flex; justify-content:space-between;">
                        <span>📺 {html.escape(ch)}</span>
                        <span>⏱️ {dur_str}</span>
                    </div>
                </div>
                """)
        cards_html = "\n".join(cards)

        page_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><title>📺 YouTube 網頁極速版</title>
        <style>
        * {{ -webkit-box-sizing: border-box; box-sizing: border-box; }}
        body {{ margin:0; padding:0; font-family: -apple-system, "Heiti TC", Helvetica, Arial, sans-serif; background: #c5ccd4; color:#333; }}
        .header {{ background: linear-gradient(#c4302b, #8a1f1b); padding: 10px 12px; text-align:center; color:#fff; font-size:16px; font-weight:bold; text-shadow:0 -1px 0 #540e0b; border-bottom:1px solid #540e0b; display:flex; align-items:center; justify-content:space-between; }}
        .nav-btn {{ background: linear-gradient(#5a88ca, #244f88); border: 1px solid #1a3d6d; color:#fff; padding:4px 8px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; }}
        .container {{ padding:10px; max-width:550px; margin:0 auto; }}
        .search-box {{ background:#fff; border-radius:8px; border:1px solid #a5b1c0; padding:10px; margin-bottom:12px; }}
        .input-bar {{ width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; outline:none; -webkit-appearance:none; }}
        .btn-sub {{ width:100%; margin-top:8px; padding:8px; background:linear-gradient(#c4302b, #8a1f1b); border:1px solid #540e0b; border-radius:6px; color:#fff; font-weight:bold; font-size:14px; cursor:pointer; }}
        </style></head><body>
        <div class="header">
            <a href="{base}/web" class="nav-btn">&larr; 首頁</a>
            <span>📺 YouTube 網頁版</span>
            <a href="{base}/web/youtube" class="nav-btn">重整</a>
        </div>
        <div class="container">
            <div class="search-box">
                <form action="{base}/web/youtube" method="GET">
                    <input type="text" name="q" class="input-bar" placeholder="搜尋 YouTube 影片 (如 周杰倫, 桃園...)" value="{html.escape(query)}" />
                    <button type="submit" class="btn-sub">立即搜尋影片</button>
                </form>
            </div>
            {cards_html}
        </div></body></html>"""
        data = page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_dcard_hub(self, qs):
        base = self._base_url()
        query = qs.get("q", [""])[0].strip()

        search_kw = f"dcard {query}" if query else "dcard 台灣 熱門話題"
        cards = []
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": search_kw, "kl": "tw-tzh"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a.result-link")[:15]:
                t = a.get_text().strip()
                h = a.get("href", "")
                if "uddg=" in h:
                    m = re.search(r"uddg=([^&]+)", h)
                    if m:
                        h = urllib.parse.unquote(m.group(1))
                tr = a.find_parent("tr")
                snip = tr.find_next_sibling("tr").get_text().strip() if tr and tr.find_next_sibling("tr") else ""
                if t and h and len(t) > 2:
                    cards.append(f"""
                    <div style="background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:12px 14px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div style="font-size:14px; font-weight:bold; line-height:1.4; margin-bottom:5px;">
                            <a href="{base}/web?url={quote(h)}" style="color:#006aa6; text-decoration:none;">{html.escape(t)}</a>
                        </div>
                        <div style="font-size:12px; color:#444; line-height:1.5; margin-bottom:6px;">{html.escape(snip)}</div>
                        <div style="font-size:10px; color:#777; text-align:right;">
                            <a href="{base}/web?url={quote(h)}" style="color:#006aa6; text-decoration:none; font-weight:bold;">查看話題討論 &rarr;</a>
                        </div>
                    </div>
                    """)
            cards_html = "\n".join(cards) if cards else '<div style="background:#fff;padding:15px;border-radius:8px;text-align:center;color:#666;">查無相關話題，請嘗試其他關鍵字</div>'
        except Exception as e:
            cards_html = f'<div style="color:red;padding:20px;">載入 Dcard 話題失敗: {e}</div>'

        page_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><title>🎓 Dcard 熱門討論極速版</title>
        <style>
        * {{ -webkit-box-sizing: border-box; box-sizing: border-box; }}
        body {{ margin:0; padding:0; font-family: -apple-system, "Heiti TC", Helvetica, Arial, sans-serif; background: #c5ccd4; color:#333; }}
        .header {{ background: linear-gradient(#006aa6, #00456c); padding: 10px 12px; text-align:center; color:#fff; font-size:16px; font-weight:bold; text-shadow:0 -1px 0 #00283f; border-bottom:1px solid #00283f; display:flex; align-items:center; justify-content:space-between; }}
        .nav-btn {{ background: linear-gradient(#5a88ca, #244f88); border: 1px solid #1a3d6d; color:#fff; padding:4px 8px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; }}
        .container {{ padding:10px; max-width:550px; margin:0 auto; }}
        .search-box {{ background:#fff; border-radius:8px; border:1px solid #a5b1c0; padding:10px; margin-bottom:12px; }}
        .input-bar {{ width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; outline:none; -webkit-appearance:none; }}
        .btn-sub {{ width:100%; margin-top:8px; padding:8px; background:linear-gradient(#006aa6, #00456c); border:1px solid #00283f; border-radius:6px; color:#fff; font-weight:bold; font-size:14px; cursor:pointer; }}
        .quick-tags {{ margin-top:8px; font-size:11px; }}
        .quick-tags a {{ color:#006aa6; text-decoration:none; background:#eef4fa; border:1px solid #ccdbe8; padding:3px 6px; border-radius:4px; display:inline-block; margin:2px; }}
        </style></head><body>
        <div class="header">
            <a href="{base}/web" class="nav-btn">&larr; 首頁</a>
            <span>🎓 Dcard 話題專區</span>
            <a href="{base}/web/dcard" class="nav-btn">重整</a>
        </div>
        <div class="container">
            <div class="search-box">
                <form action="{base}/web/dcard" method="GET">
                    <input type="text" name="q" value="{html.escape(query)}" class="input-bar" placeholder="搜尋 Dcard 看板或話題 (如 感情、美食)..." autocorrect="off" autocapitalize="none">
                    <input type="submit" value="🔍 搜尋 Dcard" class="btn-sub">
                    <div class="quick-tags">
                        熱門標籤：
                        <a href="{base}/web/dcard">🔥 全部熱門</a>
                        <a href="{base}/web/dcard?q=感情">❤️ 感情板</a>
                        <a href="{base}/web/dcard?q=美食">🍲 美食板</a>
                        <a href="{base}/web/dcard?q=工作">💼 工作板</a>
                        <a href="{base}/web/dcard?q=遊戲">🎮 遊戲板</a>
                        <a href="{base}/web/dcard?q=穿搭">👗 穿搭板</a>
                    </div>
                </form>
            </div>
            {cards_html}
        </div></body></html>"""
        data = page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_instagram_hub(self, qs):
        base = self._base_url()
        query = qs.get("q", [""])[0].strip()
        user_param = qs.get("u", [""])[0].strip()

        target_user = ""
        if user_param:
            target_user = user_param.lstrip("@")
        elif query.startswith("@"):
            target_user = query.lstrip("@")

        user_card_html = ""
        cards = []

        if target_user:
            try:
                r = requests.get(f"https://www.instagram.com/{target_user}/", headers={"User-Agent": "Twitterbot/1.0"}, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                og_title = soup.find("meta", {"property": "og:title"})
                og_desc = soup.find("meta", {"property": "og:description"})
                og_img = soup.find("meta", {"property": "og:image"})
                t_txt = og_title.get("content", "") if og_title else f"@{target_user}"
                d_txt = og_desc.get("content", "") if og_desc else ""
                i_url = og_img.get("content", "") if og_img else ""
                img_tag = f'<img src="{base}/surf?url={quote(i_url)}" style="width:60px;height:60px;border-radius:30px;float:left;margin-right:12px;border:1px solid #ccc;object-fit:cover;"/>' if i_url else ''
                user_card_html = f"""
                <div style="background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:12px; margin-bottom:12px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                    {img_tag}
                    <div style="font-weight:bold; font-size:15px; color:#111;">{html.escape(t_txt)}</div>
                    <div style="font-size:12px; color:#555; margin-top:4px; line-height:1.4;">{html.escape(d_txt)}</div>
                </div>
                """
            except Exception as e:
                user_card_html = f'<div style="color:red;font-size:12px;padding:8px;">載入用戶資料失敗: {e}</div>'

        search_kw = f"site:instagram.com {query}" if (query and not target_user) else "site:instagram.com 台灣 美食 景點"
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": search_kw, "kl": "tw-tzh"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a.result-link")[:12]:
                title = a.get_text().strip()
                href = a.get("href", "")
                if "uddg=" in href:
                    m = re.search(r"uddg=([^&]+)", href)
                    if m:
                        href = urllib.parse.unquote(m.group(1))
                tr = a.find_parent("tr")
                snip = tr.find_next_sibling("tr").get_text().strip() if tr and tr.find_next_sibling("tr") else ""

                thumb_img = ""
                if "/p/" in href or "/reel/" in href:
                    try:
                        pr = requests.get(href, headers={"User-Agent": "Twitterbot/1.0"}, timeout=3)
                        psoup = BeautifulSoup(pr.text, "html.parser")
                        pimg = psoup.find("meta", {"property": "og:image"})
                        if pimg and pimg.get("content"):
                            thumb_img = f'<div style="margin-top:6px;text-align:center;"><img src="{base}/surf?url={quote(pimg["content"])}" style="max-width:100%;max-height:220px;border-radius:6px;border:1px solid #ddd;"/></div>'
                    except Exception:
                        pass

                if len(title) > 2:
                    cards.append(f"""
                    <div style="background:#fff; border:1px solid #ccd3dc; border-radius:8px; padding:12px 14px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div style="font-size:14px; font-weight:bold; line-height:1.4; margin-bottom:5px;">
                            <a href="{base}/web?url={quote(href)}" style="color:#a82d6b; text-decoration:none;">{html.escape(title)}</a>
                        </div>
                        <div style="font-size:12px; color:#444; line-height:1.5; margin-bottom:6px;">{html.escape(snip)}</div>
                        {thumb_img}
                        <div style="font-size:10px; color:#888; display:flex; justify-content:space-between; margin-top:6px;">
                            <span>📷 Instagram</span>
                            <a href="{base}/web?url={quote(href)}" style="color:#a82d6b; text-decoration:none; font-weight:bold;">開啟貼文 &rarr;</a>
                        </div>
                    </div>
                    """)
            cards_html = "\n".join(cards) if cards else '<div style="background:#fff;padding:15px;border-radius:8px;text-align:center;color:#666;">查無相關貼文，請嘗試其他關鍵字</div>'
        except Exception as e:
            cards_html = f'<div style="padding:20px;text-align:center;color:#666;">載入熱門貼文失敗: {e}</div>'

        page_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"><title>📷 Instagram 極速版</title>
        <style>
        * {{ -webkit-box-sizing: border-box; box-sizing: border-box; }}
        body {{ margin:0; padding:0; font-family: -apple-system, "Heiti TC", Helvetica, Arial, sans-serif; background: #c5ccd4; color:#333; }}
        .header {{ background: linear-gradient(#b83375, #7a1c5b); padding: 10px 12px; text-align:center; color:#fff; font-size:16px; font-weight:bold; text-shadow:0 -1px 0 #52113c; border-bottom:1px solid #52113c; display:flex; align-items:center; justify-content:space-between; }}
        .nav-btn {{ background: linear-gradient(#d45695, #9c286b); border: 1px solid #631543; color:#fff; padding:4px 8px; border-radius:4px; font-size:12px; text-decoration:none; font-weight:bold; }}
        .container {{ padding:10px; max-width:550px; margin:0 auto; }}
        .search-box {{ background:#fff; border-radius:8px; border:1px solid #a5b1c0; padding:10px; margin-bottom:12px; }}
        .input-bar {{ width:100%; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:6px; outline:none; -webkit-appearance:none; }}
        .btn-sub {{ width:100%; margin-top:8px; padding:8px; background:linear-gradient(#b83375, #7a1c5b); border:1px solid #52113c; border-radius:6px; color:#fff; font-weight:bold; font-size:14px; cursor:pointer; }}
        .quick-tags {{ margin-top:8px; font-size:11px; }}
        .quick-tags a {{ color:#a82d6b; text-decoration:none; background:#faeef4; border:1px solid #e8ccdc; padding:3px 6px; border-radius:4px; display:inline-block; margin:2px; }}
        </style></head><body>
        <div class="header">
            <a href="{base}/web" class="nav-btn">&larr; 首頁</a>
            <span>📷 Instagram 極速版</span>
            <a href="{base}/web/instagram" class="nav-btn">重整</a>
        </div>
        <div class="container">
            <div class="search-box">
                <form action="{base}/web/instagram" method="GET">
                    <input type="text" name="q" value="{html.escape(query)}" class="input-bar" placeholder="搜尋話題、美食，或輸入 @帳號..." autocorrect="off" autocapitalize="none">
                    <input type="submit" value="🔍 搜尋 Instagram" class="btn-sub">
                    <div class="quick-tags">
                        熱門標籤：
                        <a href="{base}/web/instagram">🔥 精選探索</a>
                        <a href="{base}/web/instagram?q=台灣美食">🍲 台灣美食</a>
                        <a href="{base}/web/instagram?q=桃園景點">🏞️ 桃園景點</a>
                        <a href="{base}/web/instagram?q=貓咪日常">🐱 萌寵日常</a>
                        <a href="{base}/web/instagram?u=taiwan_foodie">👤 @taiwan_foodie</a>
                    </div>
                </form>
            </div>
            {user_card_html}
            {cards_html}
        </div></body></html>"""
        data = page_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_getvideo_stream(self, target_url):
        if not target_url:
            self.send_error(400, "Missing url parameter")
            return

        stream_url = _get_generic_stream_url(target_url)
        if not stream_url:
            print(f"[STREAM GENERIC ERR] Could not find stream URL for {target_url}")
            self.send_error(502, "Could not extract video stream")
            return

        upstream_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
        }
        range_header = self.headers.get("Range")
        if range_header:
            upstream_headers["Range"] = range_header
            print(f"[GENERIC STREAM] requested Range: {range_header}")

        try:
            upstream = requests.get(stream_url, headers=upstream_headers, stream=True, timeout=30)
        except Exception as e:
            print(f"[STREAM GENERIC ERR] Connect error: {e}")
            self.send_error(502, f"Failed to connect to stream: {e}")
            return

        self.send_response(upstream.status_code)
        content_type_sent = False
        for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified", "ETag"):
            val = upstream.headers.get(h)
            if val:
                if h == "Content-Type":
                    content_type_sent = True
                self.send_header(h, val)
        if not content_type_sent:
            self.send_header("Content-Type", "video/mp4")
        if not upstream.headers.get("Accept-Ranges"):
            self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        try:
            for chunk in upstream.iter_content(chunk_size=65536):
                if chunk:
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as stream_err:
            print(f"[GENERIC STREAM TRANSFER ERR] {stream_err}")

    def _render_reader_article(self, title, content_html, effective_url):
        base = self._base_url()
        soup = BeautifulSoup(content_html, "html.parser")

        for bad in soup(["script", "noscript", "style", "nav", "footer", "aside"]):
            bad.decompose()

        # Handle YouTube iframes
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            m = re.search(r"(?:youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})", src)
            if m:
                vid = m.group(1)
                v_box = soup.new_tag("div", style="margin: 12px 0; text-align: center;")
                v_tag = soup.new_tag("video", attrs={
                    "controls": "controls",
                    "width": "100%",
                    "poster": f"{base}/thumb/{vid}/hqdefault.jpg",
                    "preload": "none",
                    "style": "background:#000; border-radius:6px; max-height:240px; display:block; margin:0 auto;"
                })
                s_tag = soup.new_tag("source", attrs={"src": f"{base}/getvideo/{vid}.mp4", "type": "video/mp4"})
                v_tag.append(s_tag)
                v_box.append(v_tag)
                lbl = soup.new_tag("div", style="font-size: 11px; color: #888; margin-top: 4px;")
                lbl.string = "🎬 原生相容影片串流 (點擊播放)"
                v_box.append(lbl)
                iframe.replace_with(v_box)
            else:
                iframe.decompose()

        # Handle generic video tags
        for vid in soup.find_all("video"):
            vsrc = vid.get("src")
            if not vsrc:
                source = vid.find("source")
                if source:
                    vsrc = source.get("src")
            if vsrc:
                full_vsrc = urljoin(effective_url, vsrc)
                vid["src"] = f"{base}/getvideo_stream?url={quote(full_vsrc)}"
                vid["controls"] = "controls"
                vid["preload"] = "none"
                vid["style"] = "width:100%; max-height:240px; background:#000; border-radius:6px; margin:10px 0;"
                for c in list(vid.children):
                    if c.name == "source":
                        c.decompose()

        # Handle images
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("srcset", "").split(" ")[0]
            if src:
                full_src = urljoin(effective_url, src)
                img["src"] = f"{base}/web?url={quote(full_src)}"
                img["style"] = "max-width: 100% !important; height: auto !important; margin: 12px auto !important; display: block !important; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.15);"
            else:
                img.decompose()

        # Handle links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            full_href = urljoin(effective_url, href)
            if full_href.startswith("http://") or full_href.startswith("https://"):
                a["href"] = f"{base}/web?url={quote(full_href)}"

        # Wrap tables in scrollable divs
        for tbl in soup.find_all("table"):
            wrapper = soup.new_tag("div", style="overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 12px 0;")
            tbl.wrap(wrapper)

        domain = urlparse(effective_url).netloc
        out_body = str(soup)

        html_out = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0, user-scalable=yes">
<title>{html.escape(title)}</title>
<style>
* {{ -webkit-box-sizing: border-box; box-sizing: border-box; }}
body {{
    margin: 0;
    padding: 0;
    font-family: -apple-system, "Heiti TC", "Helvetica Neue", Helvetica, Arial, sans-serif;
    background: #eef1f4;
    color: #222;
    -webkit-text-size-adjust: 100%;
}}
.top-nav {{
    background: linear-gradient(#b0bcc9, #8292a4 50%, #75869a 51%, #677a8e);
    border-bottom: 1px solid #455567;
    padding: 6px 10px;
    position: sticky;
    top: 0;
    z-index: 99999;
    display: flex;
    align-items: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3);
}}
.nav-btn {{
    background: linear-gradient(#5a88ca, #2e5f9e);
    color: #fff;
    text-decoration: none;
    padding: 5px 10px;
    border-radius: 4px;
    font-weight: bold;
    border: 1px solid #1a3d6d;
    text-shadow: 0 -1px 0 rgba(0,0,0,0.5);
    font-size: 12px;
    white-space: nowrap;
}}
.nav-mode {{
    background: linear-gradient(#f0f0f0, #dcdcdc);
    color: #333;
    text-decoration: none;
    padding: 5px 8px;
    border-radius: 4px;
    font-weight: bold;
    border: 1px solid #999;
    font-size: 11px;
    white-space: nowrap;
    margin-left: 6px;
}}
.url-form {{
    margin: 0 6px;
    flex: 1;
    display: flex;
}}
.url-input {{
    width: 100%;
    padding: 5px 8px;
    border: 1px solid #777;
    border-radius: 4px;
    font-size: 12px;
    outline: none;
    -webkit-appearance: none;
}}
.article-card {{
    background: #fff;
    margin: 10px 8px 25px;
    padding: 16px 14px;
    border-radius: 8px;
    border: 1px solid #ccd3dc;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}}
.article-title {{
    font-size: 20px;
    font-weight: bold;
    line-height: 1.35;
    color: #111;
    margin: 0 0 8px;
}}
.article-meta {{
    font-size: 12px;
    color: #667;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #e5e8ec;
}}
.article-meta a {{
    color: #3b6fb5;
    text-decoration: none;
}}
.article-content {{
    font-size: 16px;
    line-height: 1.7;
    color: #2c2c2e;
    word-wrap: break-word;
}}
.article-content p {{
    margin: 0 0 14px;
}}
.article-content a {{
    color: #1a56a6;
    text-decoration: underline;
}}
.article-content pre, .article-content code {{
    background: #f4f5f7;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 13px;
    white-space: pre-wrap;
    word-break: break-all;
}}
.article-content table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 14px;
}}
.article-content th, .article-content td {{
    border: 1px solid #ddd;
    padding: 6px 8px;
}}
.article-content th {{
    background: #f0f2f5;
}}
</style>
</head>
<body>
<div class="top-nav">
    <a href="{base}/web" class="nav-btn">首頁</a>
    <form action="{base}/web" method="GET" class="url-form">
        <input type="text" name="url" value="{html.escape(effective_url)}" class="url-input" />
    </form>
    <a href="{base}/web?url={quote(effective_url)}&mode=raw" class="nav-mode">🌐 原網</a>
</div>
<div class="article-card">
    <h1 class="article-title">{html.escape(title)}</h1>
    <div class="article-meta">
        來源：<a href="{html.escape(effective_url)}" target="_blank">{html.escape(domain)}</a> &bull; 📱 極速排版閱讀模式
    </div>
    <div class="article-content">
        {out_body}
    </div>
</div>
</body>
</html>"""
        data = html_out.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _surf_url(self, target_url, mode="auto"):
        base = self._base_url()

        if any(d in target_url.lower() for d in ["threads.net", "threads.com"]):
            m_user = re.search(r"threads\.(?:net|com)/@([a-zA-Z0-9._]+)", target_url)
            if m_user:
                u = m_user.group(1)
                self.send_response(302)
                self.send_header("Location", f"{base}/web/threads?u={quote(u)}")
                self.end_headers()
                return
            else:
                self.send_response(302)
                self.send_header("Location", f"{base}/web/threads")
                self.end_headers()
                return

        if not (target_url.startswith("http://") or target_url.startswith("https://")):
            target_url = f"https://{target_url}"

        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh-HK,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        try:
            resp = requests.get(target_url, headers=headers, timeout=25, allow_redirects=True, stream=True)
        except Exception as e:
            try:
                resp = requests.get(target_url, headers=headers, timeout=25, allow_redirects=True, stream=True, verify=False)
            except Exception as e2:
                self.send_response(502)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                err_html = f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>連線失敗</title></head><body style="font-family: sans-serif; padding: 20px;"><h2>無法連線至目標網站</h2><p>{html.escape(str(e2))}</p><p><a href="{base}/web">&larr; 返回傳送門首頁</a></p></body></html>"""
                self.wfile.write(err_html.encode("utf-8"))
                return

        content_type = resp.headers.get("Content-Type", "").lower()
        effective_url = resp.url

        if "image/" in content_type or any(effective_url.lower().split("?")[0].endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp"]):
            raw_data = resp.content
            if "webp" in content_type or "avif" in content_type or effective_url.lower().split("?")[0].endswith((".webp", ".avif")):
                try:
                    img = Image.open(io.BytesIO(raw_data)).convert("RGB")
                    out = io.BytesIO()
                    img.save(out, format="JPEG", quality=85)
                    raw_data = out.getvalue()
                    content_type = "image/jpeg"
                except Exception as img_err:
                    print(f"[IMG CONV ERR] {img_err}")
            self.send_response(200)
            self.send_header("Content-Type", content_type or "image/jpeg")
            self.send_header("Content-Length", str(len(raw_data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(raw_data)
            return

        if "text/css" in content_type:
            raw_data = resp.content
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(raw_data)))
            self.end_headers()
            self.wfile.write(raw_data)
            return

        # Ensure correct encoding for Chinese texts
        if resp.encoding and resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"

        html_text = resp.text

        # Detect article suitability for reader mode: ONLY trigger on actual articles, NEVER on homepages/lists!
        target_lower = effective_url.lower()
        is_article_url = False
        if any(dom in target_lower for dom in ["yahoo.com", "gamer.com.tw", "disp.cc", "ptt.cc", "mobile01.com"]):
            if re.search(r"/(?:m/)?(?:Gossiping|Beauty|joke|NBA|Baseball|C_Chat|ACG|WomenTalk)/[a-zA-Z0-9]+", target_lower):
                is_article_url = True
            elif ".html" in target_lower or "sn=" in target_lower or "topicdetail" in target_lower or "/p/" in target_lower:
                is_article_url = True
        elif any(dom in target_lower for dom in ["wikipedia.org", "moegirl.org"]):
            if "/wiki/" in target_lower or "/zh-tw/" in target_lower or "/zh-hant/" in target_lower:
                if not any(k in target_lower for k in ["wiki/special:", "wiki/wikipedia:", "wiki/main_page"]):
                    is_article_url = True

        if mode == "reader" or (mode != "raw" and is_article_url):
            try:
                if Document is not None:
                    doc = Document(html_text)
                    reader_body = doc.summary()
                    reader_title = doc.title() or "文章閱讀"
                    plain_len = len(re.sub(r"<[^>]+>", "", reader_body).strip())
                    if plain_len > 150:
                        self._render_reader_article(reader_title, reader_body, effective_url)
                        return
            except Exception as read_err:
                print(f"[READABILITY ERR] {read_err}")

        # Sanitized web rendering
        soup = BeautifulSoup(html_text, "html.parser")

        for bad in soup(["script", "noscript", "embed", "object"]):
            bad.decompose()

        for meta in soup.find_all("meta"):
            if meta.get("http-equiv", "").lower() == "refresh":
                meta.decompose()
            elif any(k in meta.get("property", "").lower() for k in ["al:ios", "al:android"]):
                meta.decompose()
            elif "apple-itunes-app" in meta.get("name", "").lower():
                meta.decompose()

        # Handle YouTube iframes
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            m = re.search(r"(?:youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})", src)
            if m:
                vid = m.group(1)
                v_box = soup.new_tag("div", style="margin: 12px 0; text-align: center;")
                v_tag = soup.new_tag("video", attrs={
                    "controls": "controls",
                    "width": "100%",
                    "poster": f"{base}/thumb/{vid}/hqdefault.jpg",
                    "preload": "none",
                    "style": "background:#000; border-radius:6px; max-height:240px; display:block; margin:0 auto;"
                })
                s_tag = soup.new_tag("source", attrs={"src": f"{base}/getvideo/{vid}.mp4", "type": "video/mp4"})
                v_tag.append(s_tag)
                v_box.append(v_tag)
                lbl = soup.new_tag("div", style="font-size: 11px; color: #888; margin-top: 4px;")
                lbl.string = "🎬 原生相容影片串流 (點擊播放)"
                v_box.append(lbl)
                iframe.replace_with(v_box)
            else:
                iframe.decompose()

        # Handle generic video tags
        for vid in soup.find_all("video"):
            vsrc = vid.get("src")
            if not vsrc:
                source = vid.find("source")
                if source:
                    vsrc = source.get("src")
            if vsrc:
                full_vsrc = urljoin(effective_url, vsrc)
                vid["src"] = f"{base}/getvideo_stream?url={quote(full_vsrc)}"
                vid["controls"] = "controls"
                vid["preload"] = "none"
                vid["style"] = "width:100%; max-height:240px; background:#000; border-radius:6px; margin:10px 0;"
                for c in list(vid.children):
                    if c.name == "source":
                        c.decompose()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            if any(href.lower().startswith(proto) for proto in ["barcelona:", "threads:", "instagram:", "intent:", "itms-appss:", "itms-apps:"]):
                a.decompose()
                continue
            full_href = urljoin(effective_url, href)
            if full_href.startswith("http://") or full_href.startswith("https://"):
                a["href"] = f"{base}/web?url={quote(full_href)}"

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("srcset", "").split(" ")[0]
            if src:
                full_src = urljoin(effective_url, src)
                if full_src.startswith("http://") or full_src.startswith("https://"):
                    img["src"] = f"{base}/web?url={quote(full_src)}"

        for link in soup.find_all("link", rel=lambda x: x and "stylesheet" in (x if isinstance(x, str) else " ".join(x)).lower() if x else False):
            if link.get("href"):
                full_href = urljoin(effective_url, link["href"])
                link["href"] = f"{base}/web?url={quote(full_href)}"

        nav_banner = f"""<div style="background: linear-gradient(#b0bcc9, #8292a4 50%, #75869a 51%, #677a8e); border-bottom: 1px solid #455567; padding: 6px 10px; font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 13px; position: sticky; top: 0; z-index: 999999; display: flex; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.3);"><a href="{base}/web" style="background: linear-gradient(#5a88ca, #2e5f9e); color: #fff; text-decoration: none; padding: 5px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #1a3d6d; text-shadow: 0 -1px 0 rgba(0,0,0,0.5); font-size: 12px; white-space: nowrap;">首頁</a><form action="{base}/web" method="GET" style="margin: 0 6px; flex: 1; display: flex;"><input type="text" name="url" value="{html.escape(effective_url)}" style="width: 100%; padding: 4px 6px; border: 1px solid #777; border-radius: 4px; font-size: 12px;" /><button type="submit" style="margin-left: 4px; padding: 4px 8px; border-radius: 4px; border: 1px solid #666; background: #eee; font-weight: bold;">Go</button></form><a href="{base}/web?url={quote(effective_url)}&mode=reader" style="background: linear-gradient(#f0f0f0, #dcdcdc); color: #333; text-decoration: none; padding: 4px 6px; border-radius: 4px; font-weight: bold; border: 1px solid #999; font-size: 11px; white-space: nowrap; margin-right: 5px;">📖 閱讀</a><a href="{html.escape(effective_url)}" target="_blank" style="color: #fff; text-decoration: underline; font-size: 11px; white-space: nowrap; text-shadow: 0 1px 1px rgba(0,0,0,0.5);">原網</a></div>"""

        style_tag = soup.new_tag("style")
        style_tag.string = """
            * { -webkit-box-sizing: border-box !important; box-sizing: border-box !important; }
            html, body {
                width: 100% !important;
                overflow-x: hidden !important;
                font-family: -apple-system, "Heiti TC", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
                font-size: 15px !important;
                line-height: 1.55 !important;
                -webkit-text-size-adjust: 100% !important;
                color: #222 !important;
            }
            img { max-width: 100% !important; height: auto !important; display: inline-block !important; }
            table { max-width: 100% !important; overflow-x: auto !important; display: block !important; }
            pre, code { white-space: pre-wrap !important; word-wrap: break-word !important; word-break: break-all !important; }
            div[style*="position: fixed"], header[style*="position: fixed"], nav[style*="position: fixed"] {
                position: static !important;
            }
        """
        if soup.head:
            meta_viewport = soup.new_tag("meta", attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0, maximum-scale=3.0, user-scalable=yes"})
            soup.head.insert(0, meta_viewport)
            soup.head.append(style_tag)

        if soup.body:
            soup.body.insert(0, BeautifulSoup(nav_banner, "html.parser"))

        out_html = str(soup).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(out_html)))
        self.end_headers()
        self.wfile.write(out_html)

    def _handle_web(self, qs):
        target_url = qs.get("url", [""])[0]
        query = qs.get("q", [""])[0]
        engine = qs.get("engine", ["smart"])[0]
        mode = qs.get("mode", ["auto"])[0]
        loc = qs.get("loc", ["taoyuan"])[0]

        if query:
            q_clean = query.strip()
            if q_clean.startswith("http://") or q_clean.startswith("https://"):
                target_url = q_clean
            elif "." in q_clean and " " not in q_clean and not q_clean.endswith("."):
                target_url = f"https://{q_clean}"
            elif engine == "wiki":
                target_url = f"https://zh.m.wikipedia.org/wiki/{quote(q_clean)}"
            elif engine == "direct":
                target_url = f"https://{q_clean}"
            else:
                self._handle_web_search(q_clean, loc=loc)
                return

        if not target_url:
            self._send_web_home()
            return

        self._surf_url(target_url, mode=mode)

    def do_GET(self):
        touch_active()
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        clean = re.sub(r"/+", "/", parsed.path)

        if "/getvideo/" in clean:
            vid = clean.split("/getvideo/")[1].split("/")[0].split("?")[0]
            if vid.endswith(".mp4"):
                vid = vid[:-4]
            print(f"[PLAY] {vid}")
            self._handle_getvideo(vid)

        elif clean.startswith("/getvideo_stream"):
            url = qs.get("url", [""])[0]
            print(f"[STREAM GENERIC] {url}")
            self._handle_getvideo_stream(url)

        elif clean.startswith("/thumb/"):
            parts = clean.split("/")
            if len(parts) >= 4:
                vid = parts[2]
                name = parts[3]
                self._handle_thumbnail(vid, name)
            else:
                self.send_error(404)

        elif "pepconfig.plist" in clean:
            self._send_pepconfig()

        elif clean.startswith("/feeds/api/standardfeeds"):
            feed_name = clean.split("/")[-1] or "recently_featured"
            print(f"[FEED] {clean} -> {feed_name} (start-index={qs.get('start-index', ['1'])[0]})")
            self._handle_trending(feed_name, qs=qs)

        elif clean in ("/feeds/api/videos", "/feeds/api/videos/"):
            q = qs.get("q", [""])[0]
            print(f"[SEARCH] q={q} (start-index={qs.get('start-index', ['1'])[0]})")
            if q:
                self._handle_search(q, qs=qs)
            else:
                self._handle_trending("recently_featured", qs=qs)

        elif re.match(r"/feeds/api/videos/([^/]+)/related", clean):
            vid = re.match(r"/feeds/api/videos/([^/]+)/related", clean).group(1)
            print(f"[RELATED] {vid}")
            threading.Thread(target=_get_stream_url, args=(vid,), daemon=True).start()
            self._handle_related(vid)

        elif re.match(r"/(feeds/)?api/videos/([^/]+)/comments", clean):
            vid = re.match(r"/(feeds/)?api/videos/([^/]+)/comments", clean).group(2)
            print(f"[COMMENTS] {vid}")
            threading.Thread(target=_get_stream_url, args=(vid,), daemon=True).start()
            self._handle_comments(vid)

        elif re.match(r"^/(feeds/)?api/videos/([a-zA-Z0-9_-]{5,30})/?$", clean):
            vid = re.match(r"^/(feeds/)?api/videos/([a-zA-Z0-9_-]{5,30})/?$", clean).group(2)
            print(f"[SINGLE VIDEO ENTRY] {vid}")
            threading.Thread(target=_get_stream_url, args=(vid,), daemon=True).start()
            self._handle_single_video(vid)

        elif clean == "/web/threads":
            self._send_threads_hub(qs)

        elif clean == "/web/instagram":
            self._send_instagram_hub(qs)

        elif clean == "/web/yahoo":
            self._send_yahoo_hub(qs)

        elif clean == "/web/youtube":
            self._send_youtube_hub(qs)

        elif clean == "/web/weather":
            self._send_weather_hub(qs)

        elif clean == "/web/dcard":
            self._send_dcard_hub(qs)

        elif clean == "/schemas/2007/categories.cat" in clean:
            self._handle_categories()

        elif "/yql/weather" in clean or "/v1/yql" in clean or "/dgw" in clean or "yql" in clean:
            q = qs.get("q", [""])[0]
            self._handle_weather(q)

        elif clean == "/web" or clean.startswith("/web/") or clean == "/surf" or clean.startswith("/surf/"):
            self._handle_web(qs)

        elif clean.startswith("/feeds/api/users"):
            self._handle_user_feeds(clean, qs)

        elif clean == "/raw_proxy_code":
            with open(__file__, "rb") as f:
                code_data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(code_data)))
            self.end_headers()
            self.wfile.write(code_data)

        elif clean == "/raw_ytdlp":
            import os
            if os.path.exists(YTDLP):
                with open(YTDLP, "rb") as f:
                    ytdlp_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(ytdlp_data)))
                self.end_headers()
                self.wfile.write(ytdlp_data)
            else:
                self.send_error(404, "yt-dlp not found")

        elif clean == "/install_macmini.sh":
            sh_data = self._generate_macmini_installer().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/x-shellscript")
            self.send_header("Content-Length", str(len(sh_data)))
            self.end_headers()
            self.wfile.write(sh_data)

        elif clean == "/" or clean == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"TubeRepair + Weather Proxy is running!\n")

        else:
            print(f"[MISS GET] {clean}")
            self.send_error(404, f"not handled: {clean}")

    def do_POST(self):
        touch_active()
        parsed = urlparse(self.path)
        clean = re.sub(r"/+", "/", parsed.path)

        length = int(self.headers.get("Content-Length", "0"))

        if clean == "/remote_update":
            new_code = self.rfile.read(length) if length else b""
            if new_code:
                with open(__file__, "wb") as f:
                    f.write(new_code)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"UPDATE_OK\n")
                def _restart():
                    import time
                    time.sleep(1)
                    os.execv(sys.executable, [sys.executable, __file__])
                threading.Thread(target=_restart, daemon=True).start()
                return
            else:
                self.send_error(400, "Empty payload")
                return

        if length:
            self.rfile.read(length)

        if "ClientLogin" in clean:
            body = b"SID=DQAAdummy_sid_tuberepair\nLSID=DQAAdummy_lsid_tuberepair\nAuth=DQAAdummy_auth_tuberepair\nYouTubeUser=weiyo\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            print("[AUTH] Handled ClientLogin with YouTubeUser=weiyo")
        elif "applelogin1" in clean:
            self._handle_applelogin1()
        elif "applelogin2" in clean:
            self._handle_applelogin2()
        elif "registerDevice" in clean:
            self._handle_register_device()
        elif "applelogin" in clean:
            self._handle_applelogin2()
        elif "/yql/weather" in clean or "/dgw" in clean:
            self._send_weather_xml(_weather_multi_xml(["2306179"]))
        else:
            print(f"[MISS POST] {clean}")
            self.send_error(404)

    def do_HEAD(self):
        touch_active()
        self.do_GET()


import ctypes
import time

c_int_p = ctypes.POINTER(ctypes.c_int)
c_size_t = ctypes.c_size_t
try:
    _launch_activate_socket = ctypes.CDLL(None).launch_activate_socket
    _launch_activate_socket.argtypes = [ctypes.c_char_p, ctypes.POINTER(c_int_p), ctypes.POINTER(c_size_t)]
    _launch_activate_socket.restype = ctypes.c_int
except Exception:
    _launch_activate_socket = None

def get_launchd_sockets(name=b"Listeners"):
    if not _launch_activate_socket:
        return []
    fds_ptr = c_int_p()
    cnt = c_size_t()
    ret = _launch_activate_socket(name, ctypes.byref(fds_ptr), ctypes.byref(cnt))
    if ret == 0 and cnt.value > 0:
        return [fds_ptr[i] for i in range(cnt.value)]
    return []

LAST_ACTIVE = time.time()
IDLE_TIMEOUT = 600  # 10 minutes of inactivity -> exit to 0 MB RAM

def touch_active():
    global LAST_ACTIVE
    LAST_ACTIVE = time.time()

def _idle_watchdog(server):
    while True:
        time.sleep(30)
        idle_seconds = time.time() - LAST_ACTIVE
        if idle_seconds > IDLE_TIMEOUT:
            print(f"[IDLE] No requests for {int(idle_seconds)}s. Shutting down to 0 MB memory...")
            server.shutdown()
            sys.exit(0)

if __name__ == "__main__":
    fds = get_launchd_sockets(b"Listeners")
    if fds:
        print(f"[LAUNCHD] Socket-activated on Port {PORT} (fd={fds[0]}). Idle timeout: {IDLE_TIMEOUT}s.")
        import socket
        s = socket.fromfd(fds[0], socket.AF_INET, socket.SOCK_STREAM)
        server = ThreadingHTTPServer(None, Handler, bind_and_activate=False)
        server.socket = s
        server.server_address = s.getsockname()
    else:
        print(f"[STANDALONE] TubeRepair + Weather Local Proxy on :{PORT}. Idle timeout: {IDLE_TIMEOUT}s.")
        server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)

    threading.Thread(target=_idle_watchdog, args=(server,), daemon=True).start()
    server.serve_forever()
