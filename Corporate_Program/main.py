import asyncio
import os
from fastapi import FastAPI, Query
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
import ollama  # ✅ Ollama 추가

# ------------------------
# FastAPI 초기 설정
# ------------------------
app = FastAPI(title="Scholarship Foundation Crawler", version="2.0")

# ------------------------
# 환경변수
# ------------------------
load_dotenv("apikey.env")

# ------------------------
# 후보 셀렉터
# ------------------------
CONTENT_SELECTORS = [
    "main", "article", "#content", ".content", ".post",
    ".program", ".board-view", "#container"
]

# ------------------------
# URL 필터링 규칙
# ------------------------
EXCLUDE_KEYWORDS_URL = [
    "intro", "greeting", "about", "history", "연혁",
    "privacy", "terms", "login", "logout", "qna", "faq", "contact",
    "공지", "소식", "news", "board", "notice",
]

def is_excluded_url(url: str) -> bool:
    lower_url = url.lower()
    return any(k in lower_url for k in EXCLUDE_KEYWORDS_URL)


# ------------------------
# 텍스트 필터링 규칙
# ------------------------
def is_meaningless_text(text: str):
    text = text.strip()
    exclude_phrases = [
        "인사말", "설립취지", "연혁", "소개합니다", "아이디", "비밀번호",
        "이사회", "정보마당", "찾아오시는 길", "오시는 길", "공지사항", "조직도", "일반공지", "영상"
    ]
    matched = [p for p in exclude_phrases if p in text]
    if matched:
        return True, f"[스킵 단어] {', '.join(matched)}"
    return False, ""


# ------------------------
# 페이지 렌더링 및 본문 추출
# ------------------------
async def fetch_rendered(page, url):
    try:
        await page.goto(url, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(1500)
    except PlaywrightTimeoutError:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

    await page.eval_on_selector_all(
        "header, footer, script, style, noscript",
        "els => els.forEach(e => e.remove())"
    )

    text = ""
    for sel in CONTENT_SELECTORS:
        try:
            node = await page.query_selector(sel)
            if node:
                await node.eval_on_selector_all(
                    "nav, aside, .menu, .sidebar",
                    "els => els.forEach(e => e.remove())"
                )
                text = await node.inner_text()
                if len(text.strip()) > 100:
                    break
        except Exception:
            continue

    if not text:
        body = await page.locator("body").element_handle()
        if body:
            await body.eval_on_selector_all(
                "nav, aside, .menu, .sidebar",
                "els => els.forEach(e => e.remove())"
            )
            text = await body.inner_text()

    title = await page.title()
    text = " ".join(text.split())

    skip, reason = is_meaningless_text(text)
    if skip:
        print(f"[스킵됨] {url} | 이유: {reason} | 텍스트 길이: {len(text)}")
        return title.strip(), ""
    else:
        print(f"[수집됨] {url} | 텍스트 길이: {len(text)}")

    return title.strip(), text[:1500]


# ------------------------
# Ollama 기반 필터링
# ------------------------
async def filter_with_ollama(item):
    """
    Ollama를 사용하여 '지원사업 공고' 관련 여부를 판별하고 요약 생성
    """
    if not item.get("snippet"):
        return None

    # ---- 프롬프트 구성 ----
    prompt = f"""
다음 웹페이지 본문이 단순한 '재단소개, 인사말, 연혁, 메뉴구조'인지,
아니면 실제 '지원사업, 장학, 복지, 프로그램 모집 공고'인지 구분하세요.

단순 소개형이면 "IGNORE"만 출력하세요.
지원사업 관련이면 아래 형식으로 요약하세요:

[프로그램명]: ...
[지원대상]: ...
[지원내용]: ...
[신청기간]: ...
[신청링크]: {item['url']}

본문:
{item['snippet']}
"""

    try:
        # ✅ Ollama는 동기 함수이므로 asyncio.to_thread 로 감쌈
        response = await asyncio.to_thread(
            ollama.chat,
            model="gpt-oss:20b",
            messages=[{"role": "user", "content": prompt}],
        )

        # ✅ 응답 구조 호환 처리
        output_text = ""
        if "message" in response:
            output_text = response["message"]["content"]
        elif "messages" in response:
            output_text = response["messages"][-1]["content"]
        else:
            output_text = str(response)

        output_text = output_text.strip()

        # ✅ 디버깅 로그
        print(f"[Ollama 응답] {item['url']} | {output_text[:100]}...")

        # ✅ IGNORE 판별
        if output_text.upper() == "IGNORE":
            return None

        item["filtered_snippet"] = output_text
        return item

    except Exception as e:
        print(f"[Ollama 오류] {item['url']} | {e}")
        item["error"] = f"Ollama error: {e}"
        return None

# ------------------------
# 크롤링 메인 엔드포인트
# ------------------------
@app.get("/crawl_playwright")
async def crawl_playwright(
    start_url: str = Query(..., description="시작 URL"),
    max_depth: int = Query(2, ge=1, le=4, description="최대 탐색 깊이")
):
    visited = set()
    results = []
    queue = [(start_url, 0)]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="ScholarshipBot/1.1")
        page = await context.new_page()

        while queue:
            url, depth = queue.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            if is_excluded_url(url):
                continue

            try:
                title, snippet = await fetch_rendered(page, url)
                if snippet:
                    results.append({"url": url, "title": title, "snippet": snippet})
            except Exception as e:
                results.append({"url": url, "error": str(e)})

            try:
                anchors = await page.eval_on_selector_all("a[href]", "els => els.map(e=>e.href)")
            except Exception:
                anchors = []

            for href in anchors:
                if not href:
                    continue
                if urlparse(href).netloc == urlparse(start_url).netloc:
                    normalized = href.split("#")[0]
                    if normalized not in visited and not is_excluded_url(normalized):
                        queue.append((normalized, depth + 1))
            await asyncio.sleep(0.3)

        await browser.close()

    # ✅ Ollama 필터링 적용
    filtered_results = await asyncio.gather(*[filter_with_ollama(item) for item in results])
    filtered_results = [item for item in filtered_results if item is not None]

    return {"count": len(filtered_results), "data": filtered_results}


# ------------------------
# 서버 실행
# ------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="127.0.0.1", port=port)
