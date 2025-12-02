import asyncio
import json, sys, os
import uuid
from pathlib import Path
from fastmcp import Client
from dotenv import load_dotenv
from fastmcp.client.logging import LogMessage
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


dotenv_path = os.path.join(parent_dir, "apikey.env")
load_dotenv(dotenv_path)

from db import engine, 복지서비스, 카테고리

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
        urls_json = await client.call_tool("search_sites_with_gemini", {})
        urls = json.loads(urls_json.data)
        data = [item["url"] for item in urls]
        # data = ['']
        results = await client.call_tool("crawl_from_search", { "urls": data, "max_depth": 2 })

        text_data = results.content[0].text
        parsed = json.loads(text_data)
        count = parsed[0]["count"]
        data = parsed[0]["data"]
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
                    # 서버측 도구 이름에 맞춰 호출
                    analysis_res = await client.call_tool("generate_title_and_category", {"summary": sum_text})
                    analysis_text = _extract_text(analysis_res).strip()
                except Exception as e:
                    print("generate_title 호출 예외:", repr(e))
                    import traceback
                    traceback.print_exc()
                    analysis_text = ""

                # JSON 파싱
                try:
                    parsed = json.loads(analysis_text)
                    gen_title = parsed.get("generated_title", "")
                    cats = parsed.get("categories", [])
                    if isinstance(cats, list):
                        categories_csv = ",".join(cats)
                    else:
                        categories_csv = str(cats)
                    # DB 필드 매핑: 정책명은 생성된 제목, 상세내용은 요약문
                    policy_name = gen_title or title
                    policy_link = url
                    target = ""
                    note = ""
                    details = sum_text
                except Exception:
                    # JSON 아닌 경우 fallback
                    gen_title = title
                    policy_name = title
                    policy_link = url
                    target = ""
                    note = ""
                    details = sum_text
                    categories_csv = ""

                print(
                    f"title: {gen_title} \n policy_name: {policy_name} \n policy_link: {policy_link} \n taget: {target} \n note: {note} \n details: {details}\n"
                )

                # DB에 저장 (None 값은 빈 문자열로 대체)
                service_id = uuid.uuid4().hex[:20]
                # 안전하게 None -> '' 변환
                def _s(v):
                    return v if v is not None else ""

                policy_name = _s(policy_name)
                policy_link = _s(policy_link)
                target = _s(target)
                note = _s(note)
                details = _s(details)
                categories_csv = _s(categories_csv)

                # DB 연결 정보 확인: 엔진에 설정된 호스트가 없으면 연결 시도하지 않음
                try:
                    host = None
                    try:
                        host = getattr(engine, 'url').host
                    except Exception:
                        # SQLAlchemy 버전 차이 또는 engine 객체에 url이 없을 수 있음
                        host = None

                    if not host:
                        print("DB 연결 정보가 설정되지 않았습니다 (DB_HOST 없음). 삽입을 건너뜁니다.")
                    else:
                        with engine.begin() as conn:
                            conn.execute(
                                복지서비스.insert().values(
                                    서비스ID=service_id,
                                    정책명=policy_name,
                                    링크=policy_link,
                                    지원대상=target,
                                    참고사항=note,
                                    상세내용=details
                                )
                            )

                            # 카테고리 테이블에 분리된 카테고리 삽입
                            if categories_csv:
                                for cat in categories_csv.split(','):
                                    cat = cat.strip()
                                    if not cat:
                                        continue
                                    conn.execute(
                                        카테고리.insert().values(
                                            서비스ID=service_id,
                                            카테고리=cat
                                        )
                                    )

                        print(f"DB에 저장됨: 서비스ID={service_id}")
                except Exception as e:
                    print("DB 저장 실패:", repr(e))
            else:
                print(f"검증 실패로 저장 건너뜀: 제목={title}, URL={url}, 결과={res_text}")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
