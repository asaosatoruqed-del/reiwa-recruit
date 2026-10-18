import os
import json
import streamlit as st

# ページ基本設定
st.set_page_config(
    page_title="令和リクルート - グロース市場・直結求人ポータル",
    page_icon="🚀",
    layout="wide"
)

JOBS_FILE = "jobs.json"

def load_jobs():
    """保存された求人JSONデータを読み込む"""
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"データの読み込みに失敗しました: {e}")
            return []
    return []

def main():
    # ヘッダー
    st.title("🚀 令和リクルート（仮）")
    st.markdown("仲介エージェントを挟まない。グロース上場企業の**「公式サイト直結・ダイレクト求人」**レーダーサイト。")
    st.markdown("---")

    jobs = load_jobs()

    if not jobs:
        st.info("💡 まだ求人データが収集されていません。裏側のスクレイピングスクリプト (`main.py`) を実行してデータを生成してください。")
        # サンプルデータの表示（UIイメージ用）
        jobs = [
            {
                "company_name": "サンプルテクノロジー株式会社",
                "is_hiring": True,
                "positions": ["バックエンドエンジニア (Python/Go)", "フロントエンドリード"],
                "key_requirements": "Webアプリケーション開発経験3年以上、自社サービスの開発に熱意のある方",
                "direct_appeal": "「中間マージンなしでエンジニアに還元したい！」社長の直メッセージあり。フルリモート＆開発環境自由。",
                "url": "https://example.com/recruit"
            }
        ]

    # --- サイドバー：フィルター機能 ---
    st.sidebar.header("🔍 検索・フィルター")
    search_keyword = st.sidebar.text_input("キーワード検索（社名・スキル等）", "")
    
    # データのフィルタリング
    filtered_jobs = []
    for job in jobs:
        # キーワードマッチ判定
        target_text = f"{job['company_name']} {' '.join(job['positions'])} {job['key_requirements']} {job['direct_appeal']}"
        if search_keyword.lower() in target_text.lower():
            filtered_jobs.append(job)

    st.sidebar.markdown(f"**表示中:** {len(filtered_jobs)} 件の企業")

    # --- メインエリア：求人カード一覧 ---
    if not filtered_jobs:
        st.warning("条件に一致する求人が見つかりませんでした。")
        return

    for job in filtered_jobs:
        with st.container():
            # カード風の見た目を作るカスタムコンテナ
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.subheader(f"🏢 {job['company_name']}")
                
                # 募集職種のバッジ風表示
                positions_str = " ｜ ".join([f"`{p}`" for p in job['positions']])
                st.markdown(f"**【募集職種】** {positions_str}")
                
                # 求める人物像
                st.write(f"**【必須スキル・人物像】** {job['key_requirements']}")
                
                # 企業からの直アピール（AI要約）
                st.info(f"🔥 **直接応募の魅力（AI要約）:** {job['direct_appeal']}")

            with col2:
                st.write("") # スペース調整
                st.write("")
                # 企業の公式サイトへ直接飛ぶボタン
                if st.button("公式サイトへ ➔", key=job['company_name']):
                    st.markdown(f'<meta http-equiv="refresh" content="0;url={job["url"]}">', unsafe_allow_html=True)

            st.markdown("---")

if __name__ == "__main__":
    main()
