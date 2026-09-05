import feedparser
import re
import csv
import os
from datetime import datetime, timezone

# ==========================================
# Future Stock Radar
# 無料テンバガー早期発見システム
# ==========================================

KEYWORDS = {
    "AIデータセンター": [
        "AI data center",
        "AI infrastructure",
        "data center power",
        "data center cooling"
    ],
    "光通信": [
        "co-packaged optics",
        "CPO",
        "silicon photonics",
        "optical interconnect",
        "optical I/O"
    ],
    "冷却・熱管理": [
        "liquid cooling",
        "immersion cooling",
        "thermal management",
        "heat exchanger",
        "radiator"
    ],
    "電力・蓄電": [
        "data center electricity",
        "data center power",
        "grid",
        "energy storage",
        "fuel cell"
    ],
    "半導体": [
        "advanced packaging",
        "chiplet",
        "HBM",
        "compound semiconductor",
        "GaN",
        "SiC"
    ],
    "宇宙": [
        "space data center",
        "orbital data center",
        "satellite computing",
        "space optical communication",
        "inter-satellite laser"
    ],
    "宇宙熱管理": [
        "space radiator",
        "spacecraft thermal",
        "space thermal management",
        "heat rejection"
    ]
}

RSS_URLS = [
    "https://news.google.com/rss/search?q=AI+data+center",
    "https://news.google.com/rss/search?q=co-packaged+optics",
    "https://news.google.com/rss/search?q=silicon+photonics",
    "https://news.google.com/rss/search?q=liquid+cooling+data+center",
    "https://news.google.com/rss/search?q=space+data+center",
    "https://news.google.com/rss/search?q=space+optical+communication",
    "https://news.google.com/rss/search?q=advanced+packaging+semiconductor"
]


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def detect_themes(title, summary):
    text = normalize((title + " " + summary).lower())
    themes = []

    for theme, words in KEYWORDS.items():
        for word in words:
            if word.lower() in text:
                themes.append(theme)
                break

    return list(dict.fromkeys(themes))


def score_article(title, summary, themes):
    text = (title + " " + summary).lower()
    score = 0
    reasons = []

    # 技術テーマ
    if themes:
        score += 10
        reasons.append("注目技術")

    # 大企業・政府・研究などのシグナル
    signals = {
        "partnership": [
            "partnership", "partner", "collaboration",
            "agreement", "alliance"
        ],
        "investment": [
            "investment", "funding", "invest",
            "capital expenditure", "capex"
        ],
        "order": [
            "order", "contract", "purchase",
            "customer", "deployment"
        ],
        "government": [
            "government", "department", "ministry",
            "subsidy", "grant", "program"
        ],
        "research": [
            "research", "university", "laboratory",
            "prototype", "demonstration"
        ],
        "patent": [
            "patent", "intellectual property"
        ]
    }

    weights = {
        "partnership": 15,
        "investment": 10,
        "order": 20,
        "government": 15,
        "research": 10,
        "patent": 10
    }

    for signal, words in signals.items():
        if any(word in text for word in words):
            score += weights[signal]
            reasons.append(signal)

    return min(score, 100), ", ".join(reasons)


def main():

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results = []

    for rss_url in RSS_URLS:

        try:
            feed = feedparser.parse(rss_url)

            for entry in feed.entries[:20]:

                title = normalize(entry.get("title", ""))
                summary = normalize(
                    re.sub("<.*?>", " ", entry.get("summary", ""))
                )
                link = entry.get("link", "")

                themes = detect_themes(title, summary)

                if not themes:
                    continue

                score, reasons = score_article(
                    title,
                    summary,
                    themes
                )

                results.append({
                    "date": today,
                    "score": score,
                    "themes": " / ".join(themes),
                    "title": title,
                    "reasons": reasons,
                    "link": link
                })

        except Exception as e:
            print("RSS error:", e)

    # スコア順
    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    os.makedirs("data", exist_ok=True)

    filename = f"data/radar_{today}.csv"

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "score",
                "themes",
                "title",
                "reasons",
                "link"
            ]
        )

        writer.writeheader()

        for row in results:
            writer.writerow(row)

    print("")
    print("================================")
    print(" Future Stock Radar")
    print("================================")
    print(f"Date: {today}")
    print(f"Articles found: {len(results)}")
    print("")
    
    for row in results[:10]:
        print(
            f"[{row['score']:>3}] "
            f"{row['themes']} | "
            f"{row['title']}"
        )

    print("")
    print("Report saved:", filename)


if __name__ == "__main__":
    main()
