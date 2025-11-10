import asyncio
from fastmcp import Client
import sys
import json

async def get_program_list(client):
    res = await client.call_tool("chat_gemini", {
        "prompt": (
            "대한민국 기업들의 사회복지 프로그램 중 임직원을 제외한, "
            "지원이 필요한 사람이 직접 신청할 수 있는 프로그램만 골라서, "
            "아래 JSON 배열 형식으로 프로그램명과 실제 신청 가능한 공식 웹사이트 URL을 반드시 포함해서 작성해줘. \n"
            "홍보용 사이트나 안내 페이지만 있는 프로그램은 제외해줘.\n"
            "만약 URL이 확실하지 않으면 빈 문자열('')로 표시해줘.\n\n"
            "출력 예시:\n"
            "[\n"
            "  {\"program_name\": \"프로그램A\", \"official_application_url\": \"https://example.com/apply\"},\n"
            "  {\"program_name\": \"프로그램B\", \"official_application_url\": \"https://example2.com/apply\"}\n"
            "]"
        )
    })
    return res.content[0].text.strip()

async def get_program_detail(client, program_name):
    res = await client.call_tool("chat_gemini", {
        "prompt": (
            f"'{program_name}' 프로그램에 대해, 지원자가 직접 신청할 수 있도록 다음 항목을 JSON 객체로 상세히 설명해줘:\n"
            f"- 지원대상\n"
            f"- 신청조건\n"
            f"- 신청 방법과 절차 (구체적 단계 포함)\n"
            f"- 필요한 서류\n"
            f"- 실제 신청 가능한 공식 웹사이트 링크\n\n"
            f"홍보나 단순 안내용 링크는 제외하고, 반드시 직접 신청 가능한 링크여야 해.\n"
            f"출력 예시:\n"
            "{{\n"
            "  \"program_name\": \"프로그램명\",\n"
            "  \"eligibility\": \"지원대상 설명\",\n"
            "  \"requirements\": \"신청조건\",\n"
            "  \"application_process\": \"신청 방법과 절차\",\n"
            "  \"required_documents\": \"필요한 서류\",\n"
            "  \"official_application_url\": \"https://example.com/apply\"\n"
            "}}\n\n"
            f"URL이 확실하지 않으면 빈 문자열('')로 표시해줘."
        )
    })
    return res.content[0].text.strip()


async def main():
    try:
        async with Client("server.py") as client:
            program_list_text = await get_program_list(client)
            print("=== 신청 가능한 프로그램 목록(JSON) ===")
            print(program_list_text)
            
            try:
                program_list = json.loads(program_list_text)
            except json.JSONDecodeError:
                print("프로그램 목록 JSON 파싱 실패")
                program_list = []
            
            for program in program_list:
                pname = program.get("program_name")
                if not pname:
                    continue
                
                detail_text = await get_program_detail(client, pname)
                print(f"\n=== {pname} 상세정보 (JSON) ===")
                print(detail_text)
                
                try:
                    detail_json = json.loads(detail_text)
                except json.JSONDecodeError:
                    print(f"{pname} 상세정보 JSON 파싱 실패")
                    detail_json = None
                
                # 필요시 detail_json으로 후처리 가능
                
    except Exception as e:
        print("오류 발생:", e)

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
