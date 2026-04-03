import json
import time
import random
import traceback
from pathlib import Path
from scholarly import scholarly

# 这里只保留 Google Scholar 主页里 user= 后面的纯 ID
SCHOLAR_ID = "OufvGTkAAAAJ"

OUTPUT_DIR = Path("google-scholar-stats")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_RETRIES = 3
RETRY_SLEEP_MIN = 20
RETRY_SLEEP_MAX = 60


def write_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def build_badge_json(label: str, message: str):
    return {
        "schemaVersion": 1,
        "label": label,
        "message": str(message),
        "color": "9cf",
        "style": "flat",
        "labelColor": "f6f6f6"
    }


def fetch_scholar_stats():
    """
    抓取 Google Scholar 作者信息。
    成功时返回 (citations, hindex, i10index)
    失败时抛出异常
    """
    author = scholarly.search_author_id(SCHOLAR_ID)
    if not author:
        raise ValueError("search_author_id returned empty result.")

    author = scholarly.fill(author, sections=["basics", "indices"])

    citedby = author.get("citedby")
    hindex = author.get("hindex")
    i10index = author.get("i10index")

    print("Fetched author keys:", list(author.keys()))
    print(f"Fetched stats -> citedby: {citedby}, hindex: {hindex}, i10index: {i10index}")

    if citedby is None:
        raise ValueError("citedby is None, fetched data is invalid.")

    return citedby, hindex if hindex is not None else 0, i10index if i10index is not None else 0


def save_stats(citedby: int, hindex: int, i10index: int):
    write_json(OUTPUT_DIR / "gs_data_shieldsio.json", build_badge_json("citations", citedby))
    write_json(OUTPUT_DIR / "gs_hindex_shieldsio.json", build_badge_json("h-index", hindex))
    write_json(OUTPUT_DIR / "gs_i10index_shieldsio.json", build_badge_json("i10-index", i10index))

    # 额外保存一份原始统计，便于以后排查
    write_json(
        OUTPUT_DIR / "gs_stats.json",
        {
            "scholar_id": SCHOLAR_ID,
            "citations": citedby,
            "hindex": hindex,
            "i10index": i10index,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    )


def main():
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[Attempt {attempt}/{MAX_RETRIES}] Fetching Google Scholar stats...")
            citedby, hindex, i10index = fetch_scholar_stats()
            save_stats(citedby, hindex, i10index)
            print("Google Scholar stats updated successfully.")
            return

        except Exception as e:
            last_error = e
            print(f"[Attempt {attempt}/{MAX_RETRIES}] Failed.")
            print("Error:", repr(e))
            traceback.print_exc()

            if attempt < MAX_RETRIES:
                sleep_seconds = random.randint(RETRY_SLEEP_MIN, RETRY_SLEEP_MAX)
                print(f"Retrying in {sleep_seconds} seconds...")
                time.sleep(sleep_seconds)

    raise RuntimeError(f"All retries failed. Last error: {repr(last_error)}")


if __name__ == "__main__":
    main()