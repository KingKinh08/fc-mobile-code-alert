
import os
import re
import json
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

SEEN_FILE = "seen.json"

SEARCH_QUERIES = [
    "FC Mobile redeem code",
    "FC Mobile codes",
    "FC Mobile code",
]

CODE_PATTERN = re.compile(r"\b[A-Z0-9]{6,20}\b", re.IGNORECASE)


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False, indent=2)


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=20,
    )

    response.raise_for_status()


def search_youtube(query):
    url = "https://www.googleapis.com/youtube/v3/search"

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "maxResults": 10,
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json().get("items", [])


def find_codes(text):
    results = set()

    for match in CODE_PATTERN.findall(text.upper()):
        # Bỏ qua các từ quá phổ biến để giảm code giả
        if match in {
            "MOBILE",
            "REDEEM",
            "CODES",
            "CODE",
            "FC",
            "FIFA",
            "EA",
            "SPORTS",
        }:
            continue

        # Code thường có cả chữ và số
        if any(c.isalpha() for c in match) and any(c.isdigit() for c in match):
            results.add(match)

    return results


def main():
    if not BOT_TOKEN:
        raise Exception("Thiếu BOT_TOKEN")

    if not CHAT_ID:
        raise Exception("Thiếu CHAT_ID")

    if not YOUTUBE_API_KEY:
        raise Exception("Thiếu YOUTUBE_API_KEY")

    seen = load_seen()
    found_new = False

    for query in SEARCH_QUERIES:
        videos = search_youtube(query)

        for video in videos:
            video_id = video["id"]["videoId"]
            snippet = video["snippet"]

            title = snippet.get("title", "")
            description = snippet.get("description", "")
            channel = snippet.get("channelTitle", "")

            text = f"{title}\n{description}"

            codes = find_codes(text)

            for code in codes:
                if code in seen:
                    continue

                seen.add(code)
                found_new = True

                message = (
                    "🚨 FC MOBILE CODE MỚI\n\n"
                    f"🎁 Code: {code}\n"
                    f"📺 Kênh: {channel}\n"
                    f"🎬 {title}\n\n"
                    f"https://www.youtube.com/watch?v={video_id}"
                )

                send_telegram(message)

    save_seen(seen)

    if not found_new:
        print("Không có code mới.")


if __name__ == "__main__":
    main()
