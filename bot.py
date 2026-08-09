import os
import re
import json
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

# Giới hạn số code tối đa gửi trong một lần
MAX_CODES_PER_MESSAGE = 10

# Chỉ dùng 1 feed để tránh Reddit rate limit 429
REDDIT_FEED = (
    "https://www.reddit.com/r/FUTMobile/new/.rss"
)

HEADERS = {
    "User-Agent": "FCMobileCodeBot/1.0"
}


# ============================================================
# BLACKLIST
# ============================================================

BLACKLIST = {
    "FCMOBILE",
    "FCMOBILE2024",
    "FCMOBILE2025",
    "FCMOBILE2026",

    "FUTMOBILE",
    "MOBILE2024",
    "MOBILE2025",
    "MOBILE2026",

    "REDEEM",
    "REDEEMCODE",
    "REWARDS",
    "REWARD",
    "REWARDCODE",

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
    "GAME",
    "GAMES",
    "CODE",
    "CODES",
    "NEW",
    "FC",
    "FIFA",

    "COMMENTS",
    "SUBMITTED",
    "PREVIEW",
    "EXTERNAL",
    "RECENTLY",
    "ACTUALLY",
    "AGAINST",
    "NORMAL",
    "SCHOOL",
    "DEVELOPERS",
    "EVERYONE",
    "ALWAYS",
    "SINGLE",
    "CONTROL",
    "PERFORM",
    "WORKED",
    "REPLACE",

    "MONEY",
    "LUCK",
    "SKILLS",
    "INCREDIBLY",
    "WORTH",
    "VALID",
    "READY",
}


# ============================================================
# REGEX
# ============================================================

# Code thông thường:
# ABC123
# FC26WELCOME
# EA2026XYZ
# ABC-123
# ABC_123
CODE_PATTERN = re.compile(
    r"\b[A-Z0-9][A-Z0-9_-]{5,19}\b",
    re.IGNORECASE
)


# ============================================================
# SEEN
# ============================================================

def load_seen():
    try:
        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(data)

        return set()

    except Exception:
        return set()


def save_seen(seen):
    try:
        # Không để seen.json phình quá lớn
        recent_seen = sorted(seen)[-5000:]

        with open(
            SEEN_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                recent_seen,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:
        print("Lỗi lưu seen.json:", e)


# ============================================================
# TELEGRAM
# ============================================================

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
            timeout=15,
        )

        print(
            "Telegram status:",
            response.status_code
        )

        if response.status_code != 200:
            print(
                "Telegram response:",
                response.text
            )

        response.raise_for_status()

        return True

    except Exception as e:

        print(
            "Lỗi Telegram:",
            e
        )

        return False


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

        print(
            "Không đọc được thời gian:",
            e
        )

    return None


# ============================================================
# CHECK WHETHER POST IS ABOUT CODES
# ============================================================

def is_code_related(text):

    text_upper = text.upper()

    keywords = [
        "REDEEM CODE",
        "REDEEMCODE",
        "REDEEM",
        "GIFT CODE",
        "GIFTCODE",
        "REWARD CODE",
        "REWARDCODE",
        "PROMO CODE",
        "PROMOCODE",
        "FREE CODE",
        "NEW CODE",
        "CODE",
        "CODES",
    ]

    for keyword in keywords:

        if keyword in text_upper:
            return True

    return False


# ============================================================
# EXTRACT CODES
# ============================================================

def extract_codes(text):

    codes = set()

    text_upper = text.upper()

    # --------------------------------------------------------
    # 1. Tìm các vùng có liên quan đến CODE
    #
    # Cho phép code nằm:
    #
    # CODE: ABC123
    #
    # CODE
    # ABC123
    #
    # REDEEM CODE:
    # ABC123
    #
    # REDEEM CODE ABC123
    # --------------------------------------------------------

    keyword_pattern = re.compile(
        r"""
        (?:
            REDEEM\s*CODE
            |
            REDEEMCODE
            |
            GIFT\s*CODE
            |
            GIFTCODE
            |
            REWARD\s*CODE
            |
            REWARDCODE
            |
            PROMO\s*CODE
            |
            PROMOCODE
            |
            FREE\s*CODE
            |
            NEW\s*CODE
            |
            CODE
            |
            CODES
        )
        """,
        re.IGNORECASE | re.VERBOSE
    )

    keyword_matches = list(
        keyword_pattern.finditer(text_upper)
    )

    # Không có từ khóa code -> không lấy gì
    if not keyword_matches:
        return codes

    # --------------------------------------------------------
    # 2. Lấy một đoạn xung quanh từ khóa
    # --------------------------------------------------------

    for keyword_match in keyword_matches:

        start = keyword_match.start()

        end = min(
            len(text_upper),
            keyword_match.end() + 180
        )

        area = text_upper[start:end]

        candidates = CODE_PATTERN.findall(area)

        for code in candidates:

            code = code.strip().upper()

            # --------------------------------------------
            # BLACKLIST
            # --------------------------------------------

            if code in BLACKLIST:
                continue

            # --------------------------------------------
            # Độ dài
            # --------------------------------------------

            if len(code) < 6:
                continue

            if len(code) > 20:
                continue

            # --------------------------------------------
            # Không phải số thuần
            # --------------------------------------------

            if code.isdigit():
                continue

            # --------------------------------------------
            # Phải có chữ
            # --------------------------------------------

            if not any(
                character.isalpha()
                for character in code
            ):
                continue

            # --------------------------------------------
            # Phải có số
            #
            # Điều này rất quan trọng để tránh bắt các
            # từ tiếng Anh dài như:
            #
            # COMMENTS
            # PLAYERS
            # DEVELOPERS
            # --------------------------------------------

            if not any(
                character.isdigit()
                for character in code
            ):
                continue

            # --------------------------------------------
            # Không có quá nhiều _
            # --------------------------------------------

            if code.count("_") >= 2:
                continue

            # --------------------------------------------
            # Không lấy Reddit ID
            #
            # Các chuỗi kiểu:
            # 1VJH633
            # 1VJGFT3
            # --------------------------------------------

            if code.startswith(
                (
                    "1V",
                    "1W",
                    "1X",
                    "1Y",
                    "1Z",
                )
            ):
                continue

            # --------------------------------------------
            # Không lấy chuỗi giống ID ngẫu nhiên
            #
            # Ví dụ:
            # N3BDXCSDAIH1
            # FGL92FRFDAIH1
            #
            # Nếu quá dài và có rất nhiều chữ/số xen kẽ
            # thì khả năng cao không phải redeem code.
            # --------------------------------------------

            if len(code) >= 13:

                letters = sum(
                    character.isalpha()
                    for character in code
                )

                digits = sum(
                    character.isdigit()
                    for character in code
                )

                if (
                    letters >= 8
                    and digits <= 2
                ):
                    continue

            # --------------------------------------------
            # Không lấy chuỗi bắt đầu bằng Reddit-style ID
            # --------------------------------------------

            if re.fullmatch(
                r"1[A-Z0-9]{6,12}",
                code
            ):
                continue

            # --------------------------------------------
            # Không lấy chuỗi có quá nhiều chữ liên tiếp
            # nếu không có dấu phân cách.
            #
            # Ví dụ:
            # INCREDIBLY
            # DEVELOPERS
            # --------------------------------------------

            if code.isalpha():
                continue

            # --------------------------------------------
            # Thêm code
            # --------------------------------------------

            codes.add(code)

    return codes


# ============================================================
# SCAN REDDIT
# ============================================================

def scan_reddit():

    results = []

    now = datetime.now(timezone.utc)

    print("")
    print("=" * 40)
    print(
        "Đang quét:",
        REDDIT_FEED
    )
    print("=" * 40)

    try:

        response = requests.get(
            REDDIT_FEED,
            headers=HEADERS,
            timeout=15
        )

        print(
            "Reddit status:",
            response.status_code
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

        print(
            "Số bài Reddit nhận được:",
            len(feed.entries)
        )

        for entry in feed.entries:

            # ------------------------------------------------
            # TIME
            # ------------------------------------------------

            published_time = get_entry_time(
                entry
            )

            if not published_time:
                continue

            age = (
                now - published_time
            )

            # Bài có timestamp tương lai
            if age.total_seconds() < 0:
                continue

            # ------------------------------------------------
            # CHỈ NHẬN 30 PHÚT
            # ------------------------------------------------

            if age > timedelta(
                minutes=MAX_AGE_MINUTES
            ):
                continue

            age_minutes = (
                age.total_seconds() / 60
            )

            # ------------------------------------------------
            # POST DATA
            # ------------------------------------------------

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
                f"{title}\n{summary}"
            )

            # ------------------------------------------------
            # KIỂM TRA CÓ LIÊN QUAN CODE
            # ------------------------------------------------

            if not is_code_related(
                content
            ):
                continue

            # ------------------------------------------------
            # TÌM CODE
            # ------------------------------------------------

            codes = extract_codes(
                content
            )

            if not codes:
                continue

            # ------------------------------------------------
            # LOG
            # ------------------------------------------------

            print("")
            print("BÀI CÓ CODE:")
            print(
                "Title:",
                title
            )

            print(
                "Tuổi bài:",
                round(
                    age_minutes,
                    1
                ),
                "phút"
            )

            print(
                "Code tìm được:",
                codes
            )

            # ------------------------------------------------
            # SAVE RESULT
            # ------------------------------------------------

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


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # CHECK ENV
    # --------------------------------------------------------

    if not BOT_TOKEN:
        raise Exception(
            "Thiếu BOT_TOKEN"
        )

    if not CHAT_ID:
        raise Exception(
            "Thiếu CHAT_ID"
        )

    print("")
    print("=" * 40)
    print("FC MOBILE CODE ALERT")
    print(
        "Chỉ nhận bài trong 30 phút gần nhất"
    )
    print("=" * 40)

    # --------------------------------------------------------
    # LOAD SEEN
    # --------------------------------------------------------

    seen = load_seen()

    print(
        "Số code đã từng gửi:",
        len(seen)
    )

    # --------------------------------------------------------
    # SCAN
    # --------------------------------------------------------

    results = scan_reddit()

    print("")
    print(
        "Tổng code tiềm năng:",
        len(results)
    )

    # --------------------------------------------------------
    # REMOVE ALREADY SENT
    # --------------------------------------------------------

    new_results = []

    for item in results:

        code = item["code"]

        if code in seen:
            continue

        new_results.append(
            item
        )

    print(
        "Code mới chưa gửi:",
        len(new_results)
    )

    # --------------------------------------------------------
    # NO NEW CODE
    # --------------------------------------------------------

    if not new_results:

        print(
            "Không có code mới trong 30 phút gần nhất."
        )

        return

    # --------------------------------------------------------
    # REMOVE DUPLICATE CODE
    # --------------------------------------------------------

    unique = {}

    for item in new_results:

        code = item["code"]

        if code not in unique:

            unique[code] = item

    new_results = list(
        unique.values()
    )

    # --------------------------------------------------------
    # SORT BY POST TIME
    # --------------------------------------------------------

    new_results.sort(
        key=lambda item: item["published"]
    )

    # --------------------------------------------------------
    # LIMIT
    # --------------------------------------------------------

    new_results = new_results[
        :MAX_CODES_PER_MESSAGE
    ]

    # --------------------------------------------------------
    # BUILD TELEGRAM MESSAGE
    # --------------------------------------------------------

    lines = [
        "🚨 FC MOBILE CODE MỚI",
        "",
        "🎁 Code vừa được phát hiện:",
        "",
    ]

    for item in new_results:

        code = item["code"]

        age_minutes = int(
            (
                datetime.now(
                    timezone.utc
                )
                - item["published"]
            ).total_seconds()
            / 60
        )

        lines.append(
            f"🎁 {code}"
        )

        lines.append(
            f"🕐 Khoảng {age_minutes} phút trước"
        )

        lines.append("")

    lines.append(
        "⚡ Nhập code ngay."
    )

    lines.append("")

    lines.append(
        "🌐 Nguồn: Reddit / r/FUTMobile"
    )

    message = "\n".join(
        lines
    )

    # --------------------------------------------------------
    # LOG MESSAGE
    # --------------------------------------------------------

    print("")
    print(
        "Tin nhắn sẽ gửi Telegram:"
    )
    print("-" * 40)
    print(message)
    print("-" * 40)

    # --------------------------------------------------------
    # SEND TELEGRAM
    # --------------------------------------------------------

    if send_telegram(
        message
    ):

        # Chỉ đánh dấu seen sau khi
        # Telegram gửi thành công

        for item in new_results:

            seen.add(
                item["code"]
            )

        save_seen(
            seen
        )

        print(
            "Đã gửi",
            len(new_results),
            "code mới."
        )

    else:

        print(
            "Telegram gửi thất bại."
        )

        print(
            "Không cập nhật seen.json."
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
