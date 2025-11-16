import asyncio
import json, sys
from fastmcp import Client
from fastmcp.client.logging import LogMessage

async def log_handler(msg: LogMessage):
    print(f"[SERVER {msg.level.upper()}] {msg.data}")

async def main():
    async with Client("server.py", log_handler=log_handler) as client:
        # urls_json = await client.call_tool("search_sites_with_gemini", {})
        # urls = json.loads(urls_json.data)
        # data = [item["url"] for item in urls]
        data = ['https://www.ibkfoundation.or.kr']
        results  = await client.call_tool("crawl_from_search", { "urls": data, "max_depth": 1 })

        text_data = results.content[0].text
        parsed = json.loads(text_data)
        count = parsed[0]["count"]
        data = parsed[0]["data"]
        info = []
        for item in data:
            url = item.get("url", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")

            A = await client.call_tool("verify_crawled_info", {"title": title, "snippet": snippet})
            print(A, snippet, url)

            # verify_res = await client.call_tool("verify_crawled_info", {"title": title, "snippet": snippet})
            # verify_data = verify_res.content[0].text
            # verify_parsed = json.loads(verify_data)
            # if verify_parsed == "VALID":
            #     print(verify_parsed)
            #     info.append([url, title, snippet])
            # else:
            #     print(verify_parsed)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
