import os
import re
import json
import requests
import feedparser
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SEEN_FILE = "seen.json"

# Chỉ nhận bài đăng trong 30 phút gần nhất
MAX_AGE_MINUTES = 30

HEADERS = {
    "User-Agent": "FCMobileCodeBot/1.0"
}

# Reddit RSS - nguồn có timestamp
REDDIT_FEEDS = [
    "https://www.reddit.com/r/FUTMobile/new/.rss",
    "https://www.reddit.com/r/redeemgiftcodes/new/.rss",
]

CODE_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9_-]{5,24}\b",
    re.IGNORECASE
)

BLACKLIST = {
    "FCMOBILE",
    "FUTMOBILE",
    "MOBILE2025",
    "MOBILE2026",
    "REDEEM",
    "REWARDS",
    "REWARD",
    "LATEST",
    "UPDATE",
    "FOLLOWER",
    "FOLLOWERS",
    "WEBSITE",
    "TELEGRAM",
    "INSTAGRAM",
    "FACEBOOK",
    "DISCORD",
    "YOUTUBE",
    "TWITTER",
    "REDDIT",
    "ANDROID",
    "IPHONE",
    "DOWNLOAD",
    "PLAYER",
    "PLAYERS",
    "GAMES",
    "GAME",
    "CODE",
    "CODES",
    "NEW",
    "FC",
    "FIFA",
}


def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
        },
        timeout=20,
    )

    print("Telegram status:", response.status_code)
    print("Telegram response:", response.text)

    response.raise_for_status()

    return True


def extract_codes(text):
    """
    Tìm các chuỗi có khả năng là FC Mobile redeem code.
    """

    codes = set()

    text_upper = text.upper()

    matches = CODE_PATTERN.findall(text_upper)

    for code in matches:

        code = code.strip()

        if code in BLACKLIST:
            continue

        if code.isdigit():
            continue

        # Phải có ít nhất một chữ
        if not any(c.isalpha() for c in code):
            continue

        # Loại các chuỗi quá giống từ thông thường
        if len(code) < 6:
            continue

        codes.add(code)

    return codes


def get_entry_time(entry):
    """
    Lấy thời gian bài Reddit được đăng.
    """

    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc
            )

        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime(
                *entry.updated_parsed[:6],
                tzinfo=timezone.utc
            )

    except Exception as e:
        print("Không đọc được thời gian:", e)

    return None


def scan_reddit():
    """
    Quét Reddit và chỉ lấy bài trong 30 phút gần nhất.
    """

    results = []

    now = datetime.now(timezone.utc)

    for feed_url in REDDIT_FEEDS:

        print(f"Đang quét Reddit: {feed_url}")

        try:
            response = requests.get(
                feed_url,
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for entry in feed.entries:

                published_time = get_entry_time(entry)

                if not published_time:
                    continue

                age = now - published_time

                # Bài trong tương lai do lỗi timestamp
                if age.total_seconds() < 0:
                    continue

                # QUAN TRỌNG:
                # Chỉ nhận bài <= 30 phút
                if age > timedelta(minutes=MAX_AGE_MINUTES):
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")

                content = f"{title} {summary}"

                # Chỉ quan tâm bài có liên quan FC Mobile
                content_upper = content.upper()

                if not any(
                    keyword in content_upper
                    for keyword in [
                        "FC MOBILE",
                        "FCMOBILE",
                        "FUT MOBILE",
                        "REDEEM CODE",
                        "REDEEM",
                    ]
                ):
                    continue

                codes = extract_codes(content)

                for code in codes:

                    results.append({
                        "code": code,
                        "published": published_time,
                        "link": link,
                        "title": title,
                    })

        except Exception as e:
            print(f"Lỗi Reddit: {e}")

    return results


def main():

    if not BOT_TOKEN:
        raise Exception("Thiếu BOT_TOKEN")

    if not CHAT_ID:
        raise Exception("Thiếu CHAT_ID")

    print("====================================")
    print("FC MOBILE CODE BOT")
    print("Chỉ nhận code trong 30 phút gần nhất")
    print("====================================")

    seen = load_seen()

    results = scan_reddit()

    print(f"Tìm thấy {len(results)} code tiềm năng.")

    new_results = []

    for item in results:

        code = item["code"]

        if code in seen:
            continue

        new_results.append(item)

    if not new_results:
        print("Không có code mới trong 30 phút gần nhất.")
        return

    # Loại trùng code nếu nhiều bài đăng cùng chứa code
    unique = {}

    for item in new_results:

        code = item["code"]

        if code not in unique:
            unique[code] = item

    new_results = list(unique.values())

    # Gửi một tin duy nhất
    lines = [
        "🚨 FC MOBILE CODE MỚI",
        "",
        "🎁 Code vừa được phát hiện:",
        ""
    ]

    for item in new_results:

        code = item["code"]

        age_minutes = int(
            (datetime.now(timezone.utc) - item["published"])
            .total_seconds() / 60
        )

        lines.append(f"🎁 {code}")
        lines.append(
            f"🕐 Khoảng {age_minutes} phút trước"
        )

    lines.append("")
    lines.append("⚡ Hãy nhập code ngay.")
    lines.append("")
    lines.append("Nguồn: Reddit")

    message = "\n".join(lines)

    try:

        if send_telegram(message):

            for item in new_results:
                seen.add(item["code"])

            save_seen(seen)

            print(
                f"Đã gửi {len(new_results)} code mới."
            )

    except Exception as e:

        print("Không gửi được Telegram:", e)


if __name__ == "__main__":
    main()

