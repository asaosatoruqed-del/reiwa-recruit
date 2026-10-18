import os
import re
import json
import requests
from google import genai
from google.genai import types

# データの保存先（GitHub Actionsでコミットしていくベース）
JOBS_FILE = "jobs.json"

# テスト用のグロース上場企業サンプルリスト（実際にはここに企業の採用ページURLを並べる）
TARGET_COMPANIES = [
    {
        "name": "サンプルテクノロジー株式会社",
        "url": "https://example.com/recruit", # テスト用に後で実際のURLや適当なサイトに差し替え可能
    }
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def clean_html_text(raw_html: str) -> str:
    """HTMLからタグや不要なスクリプトを削ぎ落としてテキスト化する"""
    text = re.sub(r'<(script|style|noscript)[^>]*>[\s\S]*?</\1>', '', raw_html, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n', '\n', text).strip()

def parse_job_with_gemini(company_name: str, raw_text: str, api_key: str) -> dict:
    """Geminiにテキストを投げ、求人情報をJSON構造化させる"""
    if not api_key or not raw_text.strip():
        return None

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
以下の企業（{company_name}）の採用ページテキストから、求人情報を抽出してJSON形式で出力してください。

【抽出項目】
- company_name: 企業名 (string)
- is_hiring: 現在中途や新卒などの求人を募集しているか (boolean)
- positions: 募集職種のリスト (array of strings)
- key_requirements: 求める人物像や必須スキル (string)
- direct_appeal: 企業からのメッセージや「直接応募してほしい」熱量のあるアピール文の要約 (string)

※JSONフォーマットのみで出力してください。余計な解説は不要です。
"""

    # 構造化出力のためのスキーマ定義
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "company_name": {"type": "STRING"},
            "is_hiring": {"type": "BOOLEAN"},
            "positions": {"type": "ARRAY", "items": {"type": "STRING"}},
            "key_requirements": {"type": "STRING"},
            "direct_appeal": {"type": "STRING"}
        },
        "required": ["company_name", "is_hiring", "positions", "key_requirements", "direct_appeal"]
    }

    try:
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.1
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash", # 高速・安価なFlashモデルを使用
            contents=[raw_text[:4000], prompt],
            config=cfg
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini parsing failed for {company_name}: {e}")
        return None

def main():
    print("=== 令和リクルート パトロール開始 ===")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is missing.")
        return

    collected_jobs = []

    for comp in TARGET_COMPANIES:
        name = comp["name"]
        url = comp["url"]
        print(f"巡回中: {name} ({url})")

        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            res.raise_for_status()
            text_body = clean_html_text(res.text)

            # Geminiで構造化
            job_data = parse_job_with_gemini(name, text_body, api_key)
            if job_data and job_data.get("is_hiring"):
                job_data["url"] = url
                collected_jobs.append(job_data)
                print(f" -> 採用情報GET! 職種: {job_data['positions']}")
            else:
                print(f" -> 募集なし or パース失敗")
        except Exception as e:
            print(f"Fetch failed for {name}: {e}")

    # 結果をJSONに保存（後でStreamlitアプリがこれを読み込む）
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(collected_jobs, f, ensure_ascii=False, indent=2)
    
    print(f"=== 巡回完了 (有効求人数: {len(collected_jobs)}件) ===")

if __name__ == "__main__":
    main()
