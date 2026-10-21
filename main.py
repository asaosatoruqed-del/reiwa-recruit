import os
import re
import json
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
JOBS_FILE = "jobs.json"

TARGET_SOURCES = [
    {
        "company": "SmartHR",
        "url": "https://open.talentio.com/r/1/c/smarthr/pages/77114",
        "type": "domestic"
    },
    {
        "company": "LayerX",
        "url": "https://open.talentio.com/r/1/c/layerx/pages/75432",
        "type": "domestic"
    }
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

class JobItem(BaseModel):
    title: str = Field(description="募集職種名（例: シニアバックエンドエンジニア）")
    remote_type: str = Field(description="リモート区分: 'フルリモート', 'ハイブリッド', '出社前提' のいずれか")
    salary_range: Optional[str] = Field(description="年収・報酬表記（例: 800万〜1,200万円、または $80,000 - $120,000）")
    tech_stack: List[str] = Field(description="主要な必須・歓迎技術タグ（例: ['Go', 'AWS', 'Kubernetes']）")
    summary_points: List[str] = Field(description="求人の要点・業務内容の箇条書き（求職者向けに2〜3行）")
    currency: str = Field(description="通貨: 'JPY', 'USD', 'EUR', 'その他'")

def load_jobs() -> list:
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []

def save_jobs(jobs: list):
    try:
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] jobs.json 保存失敗: {e}")

def clean_html(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:6000]

def parse_with_gemini(company_name: str, raw_text: str) -> Optional[JobItem]:
    if not GEMINI_API_KEY or not raw_text.strip():
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            f"以下は企業「{company_name}」の公式求人ページから抽出したテキストです。\n"
            "募集職種、実質的なリモート度、年収レンジ、主要技術スタック、および2〜3行の簡潔な要点を抽出し、指定のスキーマに従ってJSON出力してください。\n\n"
            f"{raw_text}"
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JobItem,
                temperature=0.2
            )
        )
        return JobItem.model_validate_json(response.text)
    except Exception as e:
        print(f"[GEMINI] パースエラー ({company_name}): {e}")
        return None

def run():
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    today_str = now.strftime("%Y-%m-%d")

    print(f"=== 求人クローラー巡回開始 ({today_str}) ===")
    existing_jobs = load_jobs()
    existing_urls = {job.get("source_url") for job in existing_jobs}

    updated_count = 0

    for item in TARGET_SOURCES:
        url = item["url"]
        company = item["company"]

        if url in existing_urls:
            print(f"[SKIP] 取得済み: {company}")
            continue

        print(f"[FETCH] 取得中: {company} ({url})")
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                print(f"[WARN] HTTP {res.status_code}: {url}")
                continue

            cleaned_text = clean_html(res.text)
            parsed: Optional[JobItem] = parse_with_gemini(company, cleaned_text)

            if parsed:
                job_record = {
                    "id": f"{int(time.time())}_{len(existing_jobs) + 1}",
                    "company": company,
                    "title": parsed.title,
                    "remote_type": parsed.remote_type,
                    "salary_range": parsed.salary_range or "応相談",
                    "currency": parsed.currency,
                    "tech_stack": parsed.tech_stack,
                    "summary_points": parsed.summary_points,
                    "source_url": url,
                    "updated_at": today_str,
                    "is_active": True
                }
                existing_jobs.insert(0, job_record)
                existing_urls.add(url)
                updated_count += 1
                print(f"[SUCCESS] {company} - {parsed.title} (リモート: {parsed.remote_type}, 技術: {', '.join(parsed.tech_stack[:3])})")

            time.sleep(2)

        except Exception as e:
            print(f"[ERROR] 処理失敗 ({company}): {e}")

    if updated_count > 0:
        save_jobs(existing_jobs)
        print(f"=== {updated_count} 件の新規求人を jobs.json に保存しました ===")
    else:
        print("=== 新規求人はありませんでした ===")

if __name__ == "__main__":
    run()
