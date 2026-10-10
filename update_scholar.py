import json
import time
import random
import traceback
from pathlib import Path
import os
import requests

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
    """Configuration or account error that should not be retried."""


def parse_scholar_stats(data):
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("SerpApi returned an error response; old data retained.")
    if data.get("search_metadata", {}).get("status") != "Success":
        raise ValueError("SerpApi search did not complete successfully.")
    if data.get("search_parameters", {}).get("author_id") != SCHOLAR_ID:
        raise ValueError("SerpApi author ID mismatch; old data retained.")
    table = data.get("cited_by", {}).get("table")
    if not isinstance(table, list):
        raise ValueError("SerpApi statistics table missing.")
    values = {}
    for row in table:
        if not isinstance(row, dict):
            raise ValueError("Invalid statistics row.")
        for key in ("citations", "h_index", "i10_index"):
            if key not in row:
                continue
            metric = row[key]
            value = metric.get("all") if isinstance(metric, dict) else None
            if key in values or type(value) is not int or value < 0:
                raise ValueError("Invalid or duplicate total in SerpApi statistics.")
            values[key] = value
    if len(values) != 3:
        raise ValueError("Incomplete SerpApi totals; old data retained.")
    return values["citations"], values["h_index"], values["i10_index"]


def fetch_scholar_stats():
    api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not api_key:
        raise ScholarAccessError("Missing SERPAPI_API_KEY. Configure the GitHub Actions repository secret.")
    print("Requesting author totals from SerpApi...", flush=True)
    try:
        response = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "google_scholar_author", "author_id": SCHOLAR_ID,
                    "hl": "en", "api_key": api_key},
            timeout=(10, 60), allow_redirects=False,
        )
    except requests.RequestException:
        # Request exceptions can contain URLs with the private API key.
        raise RuntimeError("SerpApi network request failed or timed out.") from None
    print(f"SerpApi HTTP status: {response.status_code}", flush=True)
    if response.status_code in (401, 403, 429):
        raise ScholarAccessError(f"SerpApi HTTP {response.status_code}: check API key, account access, or quota.")
    if response.status_code != 200:
        raise RuntimeError(f"SerpApi HTTP {response.status_code}; old data retained.")
    try:
        data = response.json()
    except ValueError:
        raise ValueError("SerpApi returned invalid JSON.") from None
    stats = parse_scholar_stats(data)
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
