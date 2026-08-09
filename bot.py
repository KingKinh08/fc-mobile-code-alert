import os
import re
import json
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SEEN_FILE = "seen.json"

SOURCES = [
    "https://www.fifamobileguide.com/redeem-code",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

CODE_PATTERN = re.compile(r"\b[A-Z0-9]{6,20}\b", re.IGNORECASE)

BLACKLIST = {
    "FCMOBILE",
    "MOBILE2025",
    "MOBILE2026",
    "REDEEM",
    "REWARDS",
    "LATEST",
    "UPDATE",
    "FOLLOWER",
    "ANDROID",
    "IPHONE",
    "DOWNLOAD",
    "YOUTUBE",
    "TWITTER",
    "FACEBOOK",
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


def scan_page(url):
    try:
        print(f"Đang quét: {url}")

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        return text

    except Exception as e:
        print(f"Lỗi khi quét {url}: {e}")
        return ""


def find_codes(text):
    codes = set()

    for code in CODE_PATTERN.findall(text.upper()):

        # Phải có cả chữ và số
        if not any(c.isalpha() for c in code):
            continue

        if not any(c.isdigit() for c in code):
            continue

        if code in BLACKLIST:
            continue

        codes.add(code)

    return codes


def main():

    if not BOT_TOKEN:
        raise Exception("Thiếu BOT_TOKEN")

    if not CHAT_ID:
        raise Exception("Thiếu CHAT_ID")
        
    send_telegram("✅ FC Mobile Bot đã kết nối Telegram thành công!")

    seen = load_seen()
    new_codes = []

    for source in SOURCES:

        text = scan_page(source)

        if not text:
            continue

        codes = find_codes(text)

        print(f"Tìm thấy {len(codes)} chuỗi có khả năng là code.")

        for code in codes:

            if code not in seen:
                new_codes.append((code, source))

    if not new_codes:
        print("Không tìm thấy code mới.")
        return

    sent_codes = []

    for code, source in new_codes:

        message = (
            "🚨 FC MOBILE CODE MỚI!\n\n"
            f"🎁 CODE: {code}\n\n"
            f"🌐 Nguồn: {source}"
        )

        if send_telegram(message):
            print(f"Đã gửi code: {code}")
            sent_codes.append(code)
        else:
            print(f"Không gửi được code: {code}")

    # Chỉ đánh dấu đã thấy nếu Telegram gửi thành công
    seen.update(sent_codes)
    save_seen(seen)


if __name__ == "__main__":
    main()
