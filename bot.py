import os
import re
import json
import time
import requests
import feedparser

from datetime import datetime, timezone, timedelta


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SEEN_FILE = "seen.json"

# Chỉ nhận bài Reddit trong khoảng thời gian này
MAX_AGE_MINUTES = 30

# Reddit RSS
REDDIT_FEEDS = [
    "https://www.reddit.com/r/FUTMobile/new/.rss",
]

HEADERS = {
    "User-Agent": "FCMobileCodeAlert/1.0"
}


# ============================================================
# BLACKLIST
# ============================================================

BLACKLIST = {
    # Reddit / social
    "COMMENTS",
    "COMMENT",
    "SUBMITTED",
    "SUBMIT",
    "PREVIEW",
    "RECENTLY",
    "EXTERNAL",
    "REDDIT",
    "TELEGRAM",
    "DISCORD",
    "INSTAGRAM",
    "FACEBOOK",
    "TWITTER",
    "YOUTUBE",

    # FC Mobile generic words
    "FCMOBILE",
    "FUTMOBILE",
    "MOBILE",
    "FC",
    "FIFA",
    "GAME",
    "GAMES",
    "PLAYER",
    "PLAYERS",
    "REDEEM",
    "REDEEMCODE",
    "REWARDCODE",
    "REWARDS",
    "REWARD",
    "CODE",
    "CODES",
    "LATEST",
    "UPDATE",
    "NEW",
    "NEWS",
    "WEBSITE",
    "DOWNLOAD",

    # Common English words frequently detected as fake codes
    "HOW",
    "WHAT",
    "WHEN",
    "WHERE",
    "THIS",
    "THAT",
    "IS",
    "ARE",
    "THE",
    "AND",
    "FOR",
    "WITH",
    "FROM",
    "YOUR",
    "YOU",
    "JUST",
    "HAVE",
    "HAS",
    "WILL",
    "READY",
    "DREAM",
    "TEAM",
    "MONEY",
    "LUCK",
    "SKILLS",
    "VALID",
    "WORTH",
    "PERFORM",
    "SCHOOL",
    "ACTUALLY",
    "NORMAL",
    "WORKED",
    "AGAINST",
    "BICYCLE",
    "REPLACE",
    "REPLACEMENT",
    "OWNERS",
    "DEVELOPERS",
    "EVERYONE",
    "ALWAYS",
    "SINGLE",
    "FOLLOWER",
    "FOLLOWERS",
}


# ============================================================
# CODE PATTERNS
# ============================================================

# Các code FC Mobile thường là chuỗi chữ + số.
# Cho phép dấu - hoặc _ ở giữa.
CODE_PATTERN = re.compile(
    r"\b[A-Z0-9][A-Z0-9_-]{7,23}\b",
    re.IGNORECASE
)


# ============================================================
# LOAD / SAVE SEEN
# ============================================================

def load_seen():
    try:
        if not os.path.exists(SEEN_FILE):
            return set()

        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return set()

        return set(str(x).upper() for x in data)

    except Exception as e:
        print("Lỗi đọc seen.json:", e)
        return set()


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(
                sorted(seen),
                f,
                ensure_ascii=False,
                indent=2
            )

        print("Đã lưu seen.json.")

    except Exception as e:
        print("Lỗi lưu seen.json:", e)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not BOT_TOKEN:
        raise Exception("Thiếu BOT_TOKEN")

    if not CHAT_ID:
        raise Exception("Thiếu CHAT_ID")

    url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": "true",
        },
        timeout=20,
    )

    print("Telegram status:", response.status_code)

    if response.status_code != 200:
        print("Telegram response:", response.text)

    response.raise_for_status()

    return True


# ============================================================
# CHECK WHETHER TEXT IS RELATED TO FC MOBILE CODES
# ============================================================

def is_redeem_related(text):

    text_upper = text.upper()

    keywords = [
        "REDEEM CODE",
        "REDEEMCODE",
        "REDEEM",
        "CODE",
        "CODES",
        "GIFT CODE",
        "GIFT CODES",
        "REWARD CODE",
        "REWARD CODES",
        "FC MOBILE",
        "FCMOBILE",
        "FUT MOBILE",
        "FUTMOBILE",
    ]

    return any(keyword in text_upper for keyword in keywords)


# ============================================================
# VALIDATE POSSIBLE CODE
# ============================================================

def is_valid_code(candidate):

    code = candidate.strip().upper()

    # Độ dài
    if len(code) < 8 or len(code) > 24:
        return False

    # Không nằm trong blacklist
    if code in BLACKLIST:
        return False

    # Phải có chữ
    if not any(char.isalpha() for char in code):
        return False

    # Phải có số
    # Điều này loại phần lớn từ tiếng Anh bình thường.
    if not any(char.isdigit() for char in code):
        return False

    # Không chứa quá nhiều dấu _
    if code.count("_") > 2:
        return False

    # Không chứa quá nhiều dấu -
    if code.count("-") > 2:
        return False

    # Loại chuỗi chỉ là một từ bình thường
    letters_only = re.sub(r"[^A-Z]", "", code)

    if letters_only in BLACKLIST:
        return False

    # Không chấp nhận chuỗi quá giống URL
    if "HTTP" in code or "WWW" in code:
        return False

    return True


# ============================================================
# EXTRACT CODES
# ============================================================

def extract_codes(text):

    if not text:
        return set()

    text_upper = text.upper()

    # Không phải bài liên quan code thì bỏ luôn.
    if not is_redeem_related(text_upper):
        return set()

    codes = set()

    # --------------------------------------------------------
    # 1. Tìm code ngay sau các từ khóa thường gặp
    # --------------------------------------------------------

    context_patterns = [
        r"(?:REDEEM\s*CODE|REDEEMCODE|CODE)\s*[:=\-]?\s*([A-Z0-9_-]{8,24})",
        r"(?:GIFT\s*CODE|REWARD\s*CODE)\s*[:=\-]?\s*([A-Z0-9_-]{8,24})",
        r"(?:CODE\s*IS|CODE\s*:\s*)([A-Z0-9_-]{8,24})",
    ]

    for pattern in context_patterns:

        matches = re.findall(
            pattern,
            text_upper,
            flags=re.IGNORECASE
        )

        for candidate in matches:

            candidate = candidate.strip()

            if is_valid_code(candidate):
                codes.add(candidate)

    # --------------------------------------------------------
    # 2. Tìm các chuỗi có khả năng là code trong toàn bài
    # --------------------------------------------------------

    matches = CODE_PATTERN.findall(text_upper)

    for candidate in matches:

        candidate = candidate.strip()

        if is_valid_code(candidate):
            codes.add(candidate)

    return codes


# ============================================================
# REDDIT TIME
# ============================================================

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


# ============================================================
# SCAN ONE REDDIT FEED
# ============================================================

def scan_reddit_feed(feed_url):

    results = []

    now = datetime.now(timezone.utc)

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

        # Reddit rate limit
        if response.status_code == 429:

            print(
                "Reddit đang giới hạn request (429). "
                "Bỏ qua nguồn này."
            )

            return results

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        print(
            "Số bài Reddit nhận được:",
            len(feed.entries)
        )

        for entry in feed.entries:

            published_time = get_entry_time(entry)

            if not published_time:
                continue

            age = now - published_time

            # Bài trong tương lai
            if age.total_seconds() < 0:
                continue

            # Chỉ lấy bài trong 30 phút
            if age > timedelta(
                minutes=MAX_AGE_MINUTES
            ):
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")

            content = (
                f"{title}\n"
                f"{summary}"
            )

            # Chỉ xử lý bài liên quan code
            if not is_redeem_related(content):
                continue

            codes = extract_codes(content)

            if not codes:
                continue

            age_minutes = (
                age.total_seconds() / 60
            )

            print("")
            print("BÀI CÓ KHẢ NĂNG CHỨA CODE:")
            print("Title:", title)
            print(
                "Tuổi bài:",
                round(age_minutes, 1),
                "phút"
            )
            print("Code:", codes)

            for code in codes:

                results.append({
                    "code": code,
                    "published": published_time,
                    "link": link,
                    "title": title,
                })

    except requests.RequestException as e:

        print("Lỗi kết nối Reddit:", e)

    except Exception as e:

        print("Lỗi xử lý Reddit:", e)

    return results


# ============================================================
# SCAN ALL REDDIT
# ============================================================

def scan_reddit():

    all_results = []

    for feed_url in REDDIT_FEEDS:

        results = scan_reddit_feed(
            feed_url
        )

        all_results.extend(results)

        # Nghỉ nhẹ giữa các request
        time.sleep(2)

    return all_results


# ============================================================
# BUILD TELEGRAM MESSAGE
# ============================================================

def build_message(results):

    lines = [
        "🚨 FC MOBILE CODE MỚI",
        "",
        "🎁 Code vừa được phát hiện:",
        "",
    ]

    now = datetime.now(timezone.utc)

    for item in results:

        code = item["code"]

        age_minutes = int(
            (
                now - item["published"]
            ).total_seconds() / 60
        )

        if age_minutes < 0:
            age_minutes = 0

        lines.append(
            f"🎁 {code}"
        )

        lines.append(
            f"🕐 Khoảng {age_minutes} phút trước"
        )

        if item.get("link"):
            lines.append(
                f"🔗 {item['link']}"
            )

        lines.append("")

    lines.append(
        "⚡ Hãy nhập code ngay."
    )

    lines.append("")
    lines.append(
        "Nguồn: Reddit"
    )

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("====================================")
    print("FC MOBILE CODE ALERT")
    print(
        "Chỉ nhận bài trong",
        MAX_AGE_MINUTES,
        "phút gần nhất"
    )
    print("====================================")
    print("")

    if not BOT_TOKEN:
        raise Exception(
            "Thiếu BOT_TOKEN trong GitHub Secrets"
        )

    if not CHAT_ID:
        raise Exception(
            "Thiếu CHAT_ID trong GitHub Secrets"
        )

    seen = load_seen()

    print(
        "Số code đã từng gửi:",
        len(seen)
    )

    # --------------------------------------------------------
    # QUÉT REDDIT
    # --------------------------------------------------------

    results = scan_reddit()

    print("")
    print(
        "Tổng code tiềm năng:",
        len(results)
    )

    # --------------------------------------------------------
    # LOẠI CODE ĐÃ GỬI
    # --------------------------------------------------------

    new_results = []

    for item in results:

        code = item["code"].upper()

        if code in seen:
            continue

        new_results.append(item)

    # --------------------------------------------------------
    # LOẠI TRÙNG CODE
    # --------------------------------------------------------

    unique = {}

    for item in new_results:

        code = item["code"].upper()

        if code not in unique:
            unique[code] = item

    new_results = list(
        unique.values()
    )

    print(
        "Code mới chưa gửi:",
        len(new_results)
    )

    # --------------------------------------------------------
    # KHÔNG CÓ CODE
    # --------------------------------------------------------

    if not new_results:

        print(
            "Không có code mới trong",
            MAX_AGE_MINUTES,
            "phút gần nhất."
        )

        return

    # --------------------------------------------------------
    # HIỂN THỊ CODE
    # --------------------------------------------------------

    print("")
    print("Các code mới:")

    for item in new_results:

        print(
            "-",
            item["code"]
        )

    # --------------------------------------------------------
    # TẠO MESSAGE
    # --------------------------------------------------------

    message = build_message(
        new_results
    )

    print("")
    print("Tin nhắn sẽ gửi Telegram:")
    print("------------------------------------")
    print(message)
    print("------------------------------------")

    # --------------------------------------------------------
    # GỬI TELEGRAM
    # --------------------------------------------------------

    try:

        send_telegram(message)

        # Chỉ đánh dấu seen SAU KHI gửi Telegram thành công
        for item in new_results:

            seen.add(
                item["code"].upper()
            )

        save_seen(seen)

        print("")
        print(
            f"Đã gửi {len(new_results)} code mới."
        )

    except Exception as e:

        print("")
        print(
            "GỬI TELEGRAM THẤT BẠI:"
        )
        print(e)

        # Không save seen nếu Telegram lỗi.
        # Lần chạy sau sẽ thử gửi lại.

        raise


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
