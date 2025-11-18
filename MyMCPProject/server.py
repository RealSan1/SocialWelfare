import asyncio
import requests
import os
import re
import json
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastmcp import FastMCP, Context
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import ollama
from google import genai
from google.genai import types
import traceback

# ========================================
# 환경설정
# ========================================

load_dotenv("api.env")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/100.0.4896.127 Safari/537.36"
    )
}

mcp = FastMCP(name="MCPServer")
# ========================================
# Ollama 필터링 함수
# ========================================
async def filter_with_ollama(item):
    if not item.get("snippet"):
        return None

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
        response = await asyncio.to_thread(
            ollama.chat,
            model="gpt-oss:20b",
            messages=[{"role": "user", "content": prompt}],
        )

        output_text = ""
        if "message" in response:
            output_text = response["message"]["content"]
        elif "messages" in response:
            output_text = response["messages"][-1]["content"]
        else:
            output_text = str(response)

        output_text = output_text.strip()
        print(f"[Ollama 응답] {item['url']} | {output_text[:100]}...")

        if output_text.upper() == "IGNORE":
            return None

        item["filtered_snippet"] = output_text
        return item

    except Exception as e:
        print(f"[Ollama 오류] {item['url']} | {e}")
        item["error"] = f"Ollama error: {e}"
        return None

# ========================================
# Playwright 크롤링
# ========================================

CONTENT_SELECTORS = [
    "main", "article", "#content", ".content", ".post",
    ".program", ".board-view", "#container"
]

EXCLUDE_KEYWORDS_URL = [
    "intro", "greeting", "about", "history", "연혁",
    "privacy", "terms", "login", "logout", "qna", "faq", "contact",
    "공지", "소식", "news", "board", "notice",
]

def is_excluded_url(url: str) -> bool:
    lower_url = url.lower()
    return any(k in lower_url for k in EXCLUDE_KEYWORDS_URL)

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

def is_valid_url(url: str) -> bool:
    try:
        resp = requests.head(url, timeout=1, allow_redirects=True)
        return resp.status_code == 200
    except Exception as e:
        return False

def extract_first_json_array(text: str) -> str | None:
    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        return match.group(0)
    return None

async def fetch_rendered(ctx: Context, page, url):
    ctx.debug(f"탐색 시작: {url}")
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
        ctx.debug(f"[스킵됨] {url} | 이유: {reason} | 텍스트 길이: {len(text)}")
        return title.strip(), ""
    else:
        ctx.debug(f"[수집됨] {url} | 텍스트 길이: {len(text)}")

    return title.strip(), text[:1500]

async def crawl_playwright_async(ctx: Context, start_url: str, max_depth: int):
    await ctx.debug(f"사이트 검색 시작 {start_url}")
    visited = set()
    results = []
    queue = [(start_url, 0)]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="ScholarshipBot/1.1")
        page = await context.new_page()

        while queue:
            url, depth = queue.pop(0)
            await ctx.debug(f"크롤링 대상 URL: {url} | depth: {depth}")

            # depth 초과 및 중복 URL 필터링
            if url in visited or depth > max_depth:
                continue

            # URL 유효성 검증 추가
            if not is_valid_url(url):
                continue

            # 크롤링 제외 URL
            if is_excluded_url(url):
                continue

            visited.add(url)


            # 렌더링 시도
            try:
                title, snippet = await fetch_rendered(ctx, page, url)
                if snippet:
                    results.append({"url": url, "title": title, "snippet": snippet})
            except Exception as e:
                results.append({"url": url, "error": str(e)})

            # 내부 링크 수집
            try:
                anchors = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            except Exception as e:
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

    return {"count": len(results), "data": results}

# ========================================
# Gemini 기반 구글서치 + URL 리스트 추출 도구
# ========================================

@mcp.tool
async def search_sites_with_gemini(ctx: Context) -> str:
    await ctx.debug("URL 검색 시작")

    client = genai.Client(api_key=GEMINI_KEY)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])

    # 기업 그룹별 쿼리 리스트
    foundations_groups = [
        "삼성, 현대",
        "신한, 현대",
        "LG, SK",
        "롯데, 한화",
        "포스코, CJ",
        "KT, IBK",
    ]

    all_results = []
    seen_urls = set()

    for group in foundations_groups:
        prompt = f"""
        검색을 수행하라. Tool 호출 없이는 답변하면 안 된다.

        기존 지식으로 답변 금지.
        반드시 Google Search 도구를 사용해 실제 검색 결과를 참고해라.
        
        다음 재단들의 장학재단 URL을 최대한 많이 찾아줘: {group}

        JSON 배열로 출력:
        [{{"foundation": "재단명", "url": "https://..."}}]
        """

        try:
            response = client.models.generate_content(
                # model="gemini-2.5-flash-lite",
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )
            text = response.text or ""

            # JSON 배열 부분만 추출하는 함수 필요
            json_str = extract_first_json_array(text)
            if not json_str:
                await ctx.debug(f"[{group}] JSON 배열 추출 실패")
                continue

            data = json.loads(json_str)

            for item in data:
                url = item.get("url", "").strip()
                if url and url not in seen_urls and is_valid_url(url):
                    seen_urls.add(url)
                    all_results.append(item)
                else:
                    await ctx.debug(f"유효하지 않은 URL 제외: {url}")

        except Exception as e:
            await ctx.debug(f"[{group}] Gemini 호출 또는 파싱 오류: {e}")
            continue

    await ctx.debug(f"총 유니크 URL 개수: {len(all_results)}")
    return json.dumps(all_results, ensure_ascii=False)


@mcp.tool
async def crawl_from_search(ctx: Context, urls: list, max_depth: int) -> str:
    await ctx.debug("크롤링 시작")

    handled = []

    try:
        for url in urls:
            await ctx.debug(f"단일 URL 처리 시작: {url}")
            try:
                r = await crawl_playwright_async(ctx, url, max_depth)
                handled.append(r)
            except Exception as e:
                err = str(e) or "unknown_error"
                handled.append({"url": url, "error": err})
                await ctx.debug(f"크롤링 예외 처리: {err}")

        return json.dumps(handled, ensure_ascii=False)

    except Exception as e:
        await ctx.debug(f"크롤링 에러발생: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool
async def verify_crawled_info(title: str, snippet: str) -> str:
    prompt = f"""
    다음은 크롤링한 장학사업 정보입니다.

    제목: {title}

    요약:
    {snippet}

    이 정보가 실제 '대한민국 기업 장학재단'의 공식 장학금 또는 복지 서비스 신청 페이지에 관한 내용인지 검증해 주세요.

    - 만약 내용이 명확히 장학금이나 복지 서비스 신청과 관련되어 있으면, "VALID"만 정확히 출력하세요.
    - 관련이 없거나 불명확하거나 광고, 뉴스, 기타 정보라면 "INVALID"만 정확히 출력하세요.
    - 다른 설명이나 문장은 출력하지 마세요.
    """

    # try:
    #     resp = requests.post(
    #         "http://localhost:11434/api/generate",
    #         json={"model": "gpt-oss:20b", "prompt": prompt, "stream": False},
    #         headers=headers,
    #         timeout=30,
    #     )
    #     result = resp.json().get("response", "").strip().upper()
    try:
        client = genai.Client(api_key=GEMINI_KEY)

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        
        text = (response.text or "").strip()
        # 정규화: 모델이 여분의 문장이나 설명을 반환할 수 있으므로
        # 'VALID' 또는 'INVALID' 토큰을 찾아 우선적으로 반환합니다.
        txt_up = text.upper()
        if txt_up == "VALID" or txt_up == "INVALID":
            return txt_up

        m = re.search(r"\b(VALID|INVALID)\b", txt_up)
        if m:
            return m.group(1)

        # 토큰을 못 찾으면 원문을 포함한 식별 가능한 메시지 반환
        short = text if len(text) <= 200 else text[:200] + "..."
        return f"UNKNOWN RESPONSE: {short}"
    except Exception as e:
        return f"VERIFICATION_FAILED: {e}"

@mcp.tool
async def summary_info(title: str, snippet: str) -> str:
    """제공된 제목과 요약을 바탕으로 복지 내용을 한국어로 간결하게 요약하여 반환합니다.
    출력은 최대 1-3문장의 간결한 요약문(핵심 지원대상, 지원내용, 신청방법/조건 포함)을 반환하며,
    불필요한 설명이나 카테고리명은 포함하지 마세요.
    """

    prompt = f"""
    당신은 한국 복지정보를 정확하고 간결하게 요약하는 전문가입니다.

    다음 제목과 내용을 읽고, 핵심 지원대상, 지원내용, 신청방법(가능한 경우), 주요조건을 포함하여 한국어로 1~3문장으로 요약하세요.
    절대 다른 설명이나 출력은 오직 요약문만 포함해야 합니다.

    제목: {title}
    내용: {snippet}
    """

    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
        )
        text = (response.text or "").strip()
        if text:
            return text
        return "요약 불가"
    except Exception as e:
        return f"SUMMARIZE_FAILED: {e}"

@mcp.tool
async def generate_title_and_category(summary: str) -> str:
    """요약된 복지 정보를 받아, 사용자 친화적인 제목과 해당하는 복지 카테리(복수 가능)를
    JSON 형식으로 반환합니다. 반환 예시:
    {"generated_title": "새로운 제목", "categories": ["아동", "교육"]}
    """
    categories = [
        '임신·출산','영유아','아동','청소년','청년','중장년·노인','저소득층','장애인','여성','한부모',
        '다문화·북한이탈주민','보훈대상','맞벌이','환경·교통','디지털','안전','위기','법률','신체건강','정신건강',
        '문화·여가','생활지원','주거','보육','교육','입양·위탁보호','돌봄','금융','에너지','농어민','기타'
    ]

    prompt = f"""
    당신은 한국 복지정보를 요약해서 사용자 친화적인 제목을 만들고, 주된 복지 대상/주제를 아래 카테고리 목록에서 선택하는 전문가입니다.

    입력으로 제공되는 '요약'을 읽고:
    - 1문장 내외의 간결하고 매력적인 `generated_title`을 생성하세요.
    - 해당 요약에 가장 적절한 카테고리(복수 가능)를 선택해 `categories` 배열로 만드세요.

    반드시 출력은 유효한 JSON 한 개체만 다음 형식으로 출력하세요 (다른 텍스트는 허용하지 않음):
    {{"generated_title": "...", "categories": ["...", "..."]}}

    카테고리 목록:
    {', '.join(categories)}

    요약:
    {summary}
    """
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        text = (response.text or "").strip()

        # JSON 객체 추출
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            jtxt = m.group(0)
            try:
                obj = json.loads(jtxt)
                return json.dumps(obj, ensure_ascii=False)
            except Exception:
                return jtxt

        # fallback: 간단한 JSON 생성
        # 가능한 경우 카테고리 키워드 추출
        found = []
        for c in categories:
            if c in summary and c not in found:
                found.append(c)

        gen_title = summary.split('\n')[0][:80]
        return json.dumps({"generated_title": gen_title, "categories": found or ["기타"]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"generated_title": "", "categories": ["기타"], "error": str(e)}, ensure_ascii=False)

# ========================================
# Ollama / Gemini MCP 도구
# ========================================
@mcp.tool
def chat_ollama(prompt: str) -> str:
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gpt-oss:20b", "prompt": prompt, "stream": False},
            headers=headers,
            timeout=30
        )
        return resp.json().get("response", "No response")
    except Exception as e:
        logging.error("GPT-OSS 에러발생")
        return f"Ollama request failed: {e}"

@mcp.tool
def chat_gemini(prompt: str) -> str:
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[grounding_tool])

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=config
        )

        text = response.text if response.text else ""
        return text.strip() if text else "(No response)"
    except Exception as e:
        return f"[ERROR] Gemini: {e}"

# ========================================
# MCP 서버 실행
# ========================================
if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(level=logging.DEBUG)
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("=== MCP Server started (stdio mode) ===")
    mcp.run()
