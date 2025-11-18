import asyncio
import json, sys
from fastmcp import Client
from fastmcp.client.logging import LogMessage

def _extract_text(res):
    try:
        if hasattr(res, 'text') and isinstance(res.text, str):
            return res.text
        if hasattr(res, 'data'):
            return res.data
        if hasattr(res, 'content'):
            c = res.content
            try:
                first = c[0]
                if hasattr(first, 'text'):
                    return first.text
                if hasattr(first, 'data'):
                    return first.data
                return str(first)
            except Exception:
                return str(c)
        return str(res)
    except Exception:
        return str(res)

async def log_handler(msg: LogMessage):
    print(f"[SERVER {msg.level.upper()}] {msg.data}")

async def main():
    async with Client("server.py", log_handler=log_handler) as client:
        # urls_json = await client.call_tool("search_sites_with_gemini", {})
        # urls = json.loads(urls_json.data)
        # data = [item["url"] for item in urls]
        data = ['https://www.ibkfoundation.or.kr']
        results = await client.call_tool("crawl_from_search", { "urls": data, "max_depth": 1 })

        text_data = results.content[0].text
        parsed = json.loads(text_data)
        count = parsed[0]["count"]
        data = parsed[0]["data"]
        info = []
        for item in data:
            url = item.get("url", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")

            verify_res = await client.call_tool("verify_crawled_info", {"title": title, "snippet": snippet})
            res_text = _extract_text(verify_res).strip().upper()

            if res_text == "VALID":
                summary_res = await client.call_tool("summary_info", {"title": title, "snippet": snippet})
                sum_text = _extract_text(summary_res).strip()

                try:
                    analysis_res = await client.call_tool("generate_title_and_category", {"summary": sum_text})
                    analysis_text = _extract_text(analysis_res).strip()
                except Exception as e:
                    print("generate_title_and_category 호출 예외:", repr(e))
                    import traceback
                    traceback.print_exc()
                    analysis_text = ""

                gen_title = ""
                categories = ""
                try:
                    parsed = json.loads(analysis_text)
                    gen_title = parsed.get("generated_title", "")
                    cats = parsed.get("categories", [])
                    if isinstance(cats, list):
                        categories = ",".join(cats)
                    else:
                        categories = str(cats)
                except Exception:
                    # 분석 결과가 JSON이 아닌 경우 원문을 카테고리 텍스트로 사용
                    categories = analysis_text

                info.append([url, gen_title or title, sum_text, categories])
                print(f"VALID: {url} | title: {gen_title or title} | categories: {categories}")
            else:
                print(f"Not valid: {url} | verify: {res_text}")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
