import os
import re
import json
import requests
import feedparser
from datetime import datetime, timezone, timedelta


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SEEN_FILE = "seen.json"

# Chỉ nhận bài Reddit trong 30 phút gần nhất
MAX_AGE_MINUTES = 30

HEADERS = {
    "User-Agent": "FCMobileCodeAlert/1.0"
}


# =========================================================
# REDDIT SOURCES
# =========================================================

REDDIT_FEEDS = [
    "https://www.reddit.com/r/FUTMobile/new/.rss",
]


# =========================================================
# CODE PATTERN
# =========================================================

CODE_PATTERN = re.compile(
    r"\b[A-Z0-9][A-Z0-9_-]{5,24}\b",
    re.IGNORECASE
)


# =========================================================
# BLACKLIST
# =========================================================

BLACKLIST = {
    "FCMOBILE",
    "FCMOBILE2025",
    "FCMOBILE2026",
    "FUTMOBILE",

    "MOBILE2025",
    "MOBILE2026",

    "REDEEM",
    "REDEEMCODE",
    "REWARDS",
    "REWARD",
    "CODE",
    "CODES",

    "LATEST",
    "UPDATE",
    "UPDATES",

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

    "NEW",
    "NEWS",

    "FC",
    "FIFA",

    "MOBILE",
    "SPORTS",

    "EA",
    "EASPORTS",

    "CHAMPIONS",
}


# =========================================================
# LOAD SEEN CODES
# =========================================================

def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(data)

        return set()

    except Exception:
        return set()


# =========================================================
# SAVE SEEN CODES
# =========================================================

def save_seen(seen):

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            sorted(seen),
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# SEND TELEGRAM
# =========================================================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    try:

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

        if response.ok:
            return True

        return False

    except Exception as e:

        print("Lỗi Telegram:", e)

        return False


# =========================================================
# GET REDDIT POST TIME
# =========================================================

def get_entry_time(entry):

    try:

        if (
            hasattr(entry, "published_parsed")
            and entry.published_parsed
        ):

            return datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc
            )

        if (
            hasattr(entry, "updated_parsed")
            and entry.updated_parsed
        ):

            return datetime(
                *entry.updated_parsed[:6],
                tzinfo=timezone.utc
            )

    except Exception as e:

        print("Không đọc được thời gian:", e)

    return None


# =========================================================
# EXTRACT CODES
# =========================================================

def extract_codes(text):
    """
    Lọc các chuỗi có khả năng là FC Mobile redeem code.
    Ưu tiên chuỗi giống code thật, loại ID/token/chữ thông thường.
    """

    codes = set()

    text_upper = text.upper()

    matches = CODE_PATTERN.findall(text_upper)

    for code in matches:

        code = code.strip()

        # 1. Không lấy blacklist
        if code in BLACKLIST:
            continue

        # 2. Không lấy chuỗi chỉ toàn số
        if code.isdigit():
            continue

        # 3. Phải có cả chữ và số
        has_letter = any(c.isalpha() for c in code)
        has_digit = any(c.isdigit() for c in code)

        if not has_letter or not has_digit:
            continue

        # 4. Code quá ngắn
        if len(code) < 6:
            continue

        # 5. Loại chuỗi có quá nhiều dấu _
        if code.count("_") >= 2:
            continue

        # 6. Loại chuỗi giống Reddit ID
        if code.startswith(("1V", "1W", "1X", "1Y", "1Z")):
            continue

        # 7. Loại chuỗi giống ID/token dài
        if len(code) >= 14:
            continue

        # 8. Không lấy các từ phổ biến
        common_words = {
            "COMMENTS",
            "SUBMITTED",
            "PREVIEW",
            "EXTERNAL",
            "ACTUALLY",
            "RECENTLY",
            "AGAINST",
            "NORMAL",
            "SCHOOL",
            "PLAYERS",
            "PLAYER",
            "DEVELOPERS",
            "EVERYONE",
            "ALWAYS",
            "SINGLE",
            "CONTROL",
            "PERFORM",
            "WORKED",
            "REPLACE",
        }

        if code in common_words:
            continue

        codes.add(code)

    return codes


# =========================================================
# SCAN REDDIT
# =========================================================

def scan_reddit():

    results = []

    now = datetime.now(timezone.utc)

    for feed_url in REDDIT_FEEDS:

        print("")
        print("====================================")
        print("Đang quét:", feed_url)
        print("====================================")

        try:

            response = requests.get(
                feed_url,
                headers=HEADERS,
                timeout=20
            )

            print("Reddit status:", response.status_code)

            response.raise_for_status()

            feed = feedparser.parse(
                response.content
            )

            print(
                "Số bài Reddit nhận được:",
                len(feed.entries)
            )

            for entry in feed.entries:

                published_time = get_entry_time(entry)

                if not published_time:
                    continue

                age = (
                    now - published_time
                )

                age_minutes = (
                    age.total_seconds() / 60
                )

                # -----------------------------------------
                # BỎ BÀI TƯƠNG LAI
                # -----------------------------------------

                if age.total_seconds() < 0:
                    continue

                # -----------------------------------------
                # CHỈ NHẬN <= 30 PHÚT
                # -----------------------------------------

                if age > timedelta(
                    minutes=MAX_AGE_MINUTES
                ):
                    continue

                title = entry.get(
                    "title",
                    ""
                )

                summary = entry.get(
                    "summary",
                    ""
                )

                link = entry.get(
                    "link",
                    ""
                )

                content = (
                    f"{title} {summary}"
                )

                content_upper = (
                    content.upper()
                )

                # -----------------------------------------
                # CHỈ NHẬN BÀI LIÊN QUAN FC MOBILE
                # -----------------------------------------

                fc_keywords = [
                    "FC MOBILE",
                    "FCMOBILE",
                    "FUT MOBILE",
                    "FUTMOBILE",
                    "REDEEM CODE",
                    "REDEEM",
                ]

                if not any(
                    keyword in content_upper
                    for keyword in fc_keywords
                ):
                    continue

                # -----------------------------------------
                # TÌM CODE
                # -----------------------------------------

                codes = extract_codes(
                    content
                )

                if not codes:
                    continue

                print("")
                print("BÀI MỚI:")
                print("Title:", title)
                print(
                    "Tuổi bài:",
                    round(age_minutes, 1),
                    "phút"
                )
                print(
                    "Code tìm được:",
                    codes
                )

                for code in codes:

                    results.append({
                        "code": code,
                        "published": published_time,
                        "link": link,
                        "title": title,
                    })

        except Exception as e:

            print(
                "Lỗi Reddit:",
                e
            )

    return results


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        raise Exception(
            "Thiếu BOT_TOKEN"
        )

    if not CHAT_ID:
        raise Exception(
            "Thiếu CHAT_ID"
        )

    print("")
    print("====================================")
    print("FC MOBILE CODE ALERT")
    print(
        f"Chỉ nhận bài trong "
        f"{MAX_AGE_MINUTES} phút gần nhất"
    )
    print("====================================")
    print("")

    seen = load_seen()

    print(
        "Số code đã từng gửi:",
        len(seen)
    )

    results = scan_reddit()

    print("")
    print(
        "Tổng code tiềm năng:",
        len(results)
    )

    # =====================================================
    # LOẠI CODE ĐÃ GỬI
    # =====================================================

    new_results = []

    for item in results:

        code = item["code"]

        if code in seen:
            continue

        new_results.append(item)

    # =====================================================
    # LOẠI TRÙNG
    # =====================================================

    unique = {}

    for item in new_results:

        code = item["code"]

        if code not in unique:

            unique[code] = item

    new_results = list(
        unique.values()
    )

    print(
        "Code mới chưa gửi:",
        len(new_results)
    )

    # =====================================================
    # KHÔNG CÓ CODE
    # =====================================================

    if not new_results:

        print(
            "Không có code mới trong "
            "30 phút gần nhất."
        )

        return

    # =====================================================
    # SẮP XẾP CODE MỚI NHẤT TRƯỚC
    # =====================================================

    new_results.sort(
        key=lambda x: x["published"],
        reverse=True
    )

    # =====================================================
    # TẠO TELEGRAM MESSAGE
    # =====================================================

    lines = [
        "🚨 FC MOBILE CODE MỚI",
        "",
        "🎁 Code vừa được phát hiện:",
        "",
    ]

    now = datetime.now(
        timezone.utc
    )

    for item in new_results:

        code = item["code"]

        age_minutes = int(
            (
                now - item["published"]
            ).total_seconds() / 60
        )

        lines.append(
            f"🎁 {code}"
        )

        lines.append(
            f"🕐 Khoảng {age_minutes} phút trước"
        )

        lines.append("")

    lines.append(
        "⚡ Hãy nhập code ngay."
    )

    lines.append("")

    lines.append(
        "🌐 Nguồn: Reddit"
    )

    message = "\n".join(lines)

    print("")
    print("Tin nhắn sẽ gửi Telegram:")
    print("------------------------------------")
    print(message)
    print("------------------------------------")

    # =====================================================
    # SEND
    # =====================================================

    if send_telegram(message):

        for item in new_results:

            seen.add(
                item["code"]
            )

        save_seen(seen)

        print("")
        print(
            f"✅ Đã gửi "
            f"{len(new_results)} code mới."
        )

    else:

        print("")
        print(
            "❌ Telegram gửi thất bại."
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
