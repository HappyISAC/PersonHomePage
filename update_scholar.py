import json
import time
import random
import traceback
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup

# 这里只保留 Google Scholar 主页里 user= 后面的纯 ID
SCHOLAR_ID = "OufvGTkAAAAJ"

OUTPUT_DIR = Path("google-scholar-stats")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_RETRIES = 2
RETRY_SLEEP_MIN = 5
RETRY_SLEEP_MAX = 10


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


class ScholarAccessError(RuntimeError):
    """Google explicitly refused access; do not keep retrying."""


def parse_scholar_stats(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#gsc_rsb_st")
    if table is None:
        text = soup.get_text(" ", strip=True).lower()
        if soup.select_one('form[action*="/sorry"], .g-recaptcha') or any(
            marker in text for marker in ("unusual traffic", "not a robot", "captcha")
        ):
            raise ScholarAccessError("Google Scholar returned a verification page; old data retained.")
        raise ValueError("Google Scholar statistics table missing; page format or access response changed.")
    expected = {"citations": "citations", "h-index": "hindex", "i10-index": "i10index"}
    values = {}
    for row in table.select("tr"):
        label = row.select_one(".gsc_rsb_sc1")
        cells = row.select("td.gsc_rsb_std")
        if label is None:
            continue
        key = expected.get(label.get_text(" ", strip=True).lower())
        if key is None:
            continue
        if key in values or len(cells) != 2:
            raise ValueError("Unexpected or duplicate Google Scholar metric row.")
        # First numeric column is All; second is the recent-years total.
        number = cells[0].get_text(strip=True)
        if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", number):
            raise ValueError(f"Invalid total for {key}: {number!r}")
        values[key] = int(number.replace(",", ""))
    if set(values) != set(expected.values()):
        raise ValueError("Incomplete Google Scholar metrics; old data retained.")
    return values["citations"], values["hindex"], values["i10index"]


def fetch_scholar_stats():
    print("Requesting author statistics (connect timeout 10s, read timeout 25s)...", flush=True)
    response = requests.get(
        "https://scholar.google.com/citations",
        params={"user": SCHOLAR_ID, "hl": "en"},
        timeout=(10, 25),
    )
    print(f"Google Scholar HTTP status: {response.status_code}", flush=True)
    if response.status_code in (403, 429) or "/sorry/" in response.url:
        raise ScholarAccessError(f"Google Scholar denied or limited access (HTTP {response.status_code}); old data retained.")
    response.raise_for_status()
    stats = parse_scholar_stats(response.text)
    print(f"Fetched totals: citations={stats[0]}, hindex={stats[1]}, i10index={stats[2]}", flush=True)
    return stats


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

        except ScholarAccessError as e:
            print(f"Access blocked: {e}", flush=True)
            raise

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
