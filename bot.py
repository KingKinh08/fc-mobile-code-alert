import os
import re
import json
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SEEN_FILE = "seen.json"

SOURCES = [
    "https://www.fifamobileguide.com/",
    "https://www.fcmobileforum.com/",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Tìm các chuỗi có cả chữ và số, dài 6-20 ký tự
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

    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
        },
        timeout=20,
    )


def scan_page(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Lấy toàn bộ nội dung chữ trên trang
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

        # Bỏ những từ phổ biến dễ bị nhận nhầm
        blacklist = {
            "FCMOBILE",
            "MOBILE2025",
            "MOBILE2026",
            "REDEEM",
            "REWARDS",
            "LATEST",
            "UPDATE",
            "FOLLOWER",
        }

        if code in blacklist:
            continue

        codes.add(code)

    return codes


def main():

    if not BOT_TOKEN:
        raise Exception("Thiếu BOT_TOKEN")

    if not CHAT_ID:
        raise Exception("Thiếu CHAT_ID")

    seen = load_seen()
    new_codes = []

    for source in SOURCES:

        print(f"Đang quét: {source}")

        text = scan_page(source)

        if not text:
            continue

        codes = find_codes(text)

        for code in codes:

            if code not in seen:

                seen.add(code)
                new_codes.append((code, source))

    save_seen(seen)

    # Gửi code mới
    for code, source in new_codes:

        message = (
            "🚨 FC MOBILE CODE MỚI!\n\n"
            f"🎁 CODE: {code}\n\n"
            f"🌐 Nguồn: {source}"
        )

        send_telegram(message)

        print(f"Đã gửi code: {code}")

    if not new_codes:
        print("Không tìm thấy code mới.")


if __name__ == "__main__":
    main()
