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
    "https://www.reddit.com/r/redeemgiftcodes/new/.rss",
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
    Chỉ tìm code trong nội dung có liên quan trực tiếp đến redeem code.
    Hạn chế nhận các từ Reddit thông thường.
    """

    codes = set()

    text_upper = text.upper()

    # Chỉ phân tích những đoạn có dấu hiệu nói về redeem code
    sentences = re.split(r"[\n.!?]+", text_upper)

    for sentence in sentences:

        if not any(keyword in sentence for keyword in [
            "CODE",
            "REDEEM",
            "REDEEM CODE",
            "REWARD CODE",
            "GIFT CODE",
        ]):
            continue

        # Code FC Mobile thường là chuỗi chữ/số viết hoa.
        # Không cho phép dấu "_" để tránh nhận tiêu đề Reddit.
        matches = re.findall(
            r"\b[A-Z0-9-]{6,24}\b",
            sentence
        )

        for code in matches:

            code = code.strip("-")

            # Không nhận số thuần
            if code.isdigit():
                continue

            # Không nhận chuỗi không có chữ
            if not any(c.isalpha() for c in code):
                continue

            # Không nhận blacklist
            if code in BLACKLIST:
                continue

            # Không nhận những từ quá phổ biến
            if code in {
                "COMMENTS",
                "SUBMITTED",
                "PREVIEW",
                "NORMAL",
                "ACTUALLY",
                "RECENTLY",
                "OVERPRICED",
                "DEVELOPERS",
                "EVERYONE",
                "AGAINST",
                "EXTERNAL",
                "SINGLE",
                "CONTROL",
                "ALWAYS",
                "PLAYER",
                "PLAYERS",
                "GAMES",
                "GAME",
            }:
                continue

            codes.add(code)

    return codes

# =========================================================
# VALIDATE CODE
# =========================================================

def is_valid_code(code):

    code = code.upper().strip()

    # Độ dài
    if len(code) < 6:
        return False

    if len(code) > 25:
        return False

    # Chỉ toàn số
    if code.isdigit():
        return False

    # Phải có chữ
    if not any(char.isalpha() for char in code):
        return False

    # Blacklist
    if code in BLACKLIST:
        return False

    # Loại chuỗi kiểu URL
    if "HTTP" in code:
        return False

    # Loại một số chuỗi rõ ràng không phải code
    bad_words = [
        "REDEEMCODE",
        "REDEEMCODES",
        "FCMOBILECODE",
        "FCMOBILECODES",
        "MOBILECODE",
        "MOBILECODES",
    ]

    if code in bad_words:
        return False

    return True


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
