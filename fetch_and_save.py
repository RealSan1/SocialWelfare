import requests
import time
import xml.etree.ElementTree as ET
import db
import re
import os
from dotenv import load_dotenv

BASE_URL_LIST = "http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
BASE_URL_DETAIL = "http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfaredetailedV001"

load_dotenv(dotenv_path="apikey.env")

SERVICE_KEY = os.getenv("SERVICE_KEY")

con = db.get_conn()

COMMON_PARAMS = {
    "serviceKey": SERVICE_KEY,
    "callTp": "L",
    "pageNo": 1,
    "numOfRows": 10,
    "srchKeyCode": "001",
}


def 정리(text: str) -> str:
    if not text:
        return ""
    # 1. 양쪽 공백 제거
    text = text.strip()
    # 2. 연속 공백 → 한 칸
    text = re.sub(r'\s+', ' ', text)
    # 3. 줄바꿈 제거
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text


def fetch_list(page_no: int):
    params = COMMON_PARAMS.copy()
    params["pageNo"] = page_no
    res = requests.get(BASE_URL_LIST, params=params, timeout=10)
    res.raise_for_status()
    return res.text

def fetch_detail(serv_id: str):
    params = {
        "serviceKey": SERVICE_KEY,
        "callTp": "D",
        "servId": serv_id,
    }
    res = requests.get(BASE_URL_DETAIL, params=params, timeout=10)
    res.raise_for_status()
    return res.text

if __name__ == "__main__":
    total_pages = 10
    result_data = []

    for page in range(5, total_pages + 1):
        try:
            xml_text = fetch_list(page)
            root = ET.fromstring(xml_text)

            serv_list = root.findall(".//servList")
            if not serv_list:
                continue

            for item in serv_list:
                serv_id = item.findtext("servId")
                serv_dgst = item.findtext("servDgst") or ""
                serv_link = item.findtext("servDtlLink") or ""

                try:
                    detail_xml = fetch_detail(serv_id)
                    detail_root = ET.fromstring(detail_xml)
                    tgtrDtlCn = 정리(detail_root.findtext("tgtrDtlCn")) or ""
                    slctCritCn = 정리(detail_root.findtext("slctCritCn")) or ""
                    alwServCn = 정리(detail_root.findtext("alwServCn")) or ""
                except Exception as e:
                    print(f"[!] 상세조회 오류: {serv_id}, {e}")
                    tgtrDtlCn = slctCritCn = alwServCn = ""

                result_data.append({
                    "servId": serv_id,
                    "servDgst": serv_dgst,
                    "serv_link": serv_link,
                    "tgtrDtlCn": tgtrDtlCn,
                    "slctCritCn": slctCritCn,
                    "alwServCn": alwServCn
                })

                time.sleep(0.3)
            print(result_data)
            cur = con.cursor()

            for row in result_data:
                sql = """
                INSERT INTO 복지서비스
                (서비스ID, 정책명, 링크, 지원대상, 참고사항, 상세내용)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    정책명=VALUES(정책명),
                    링크=VALUES(링크),
                    지원대상=VALUES(지원대상),
                    참고사항=VALUES(참고사항),
                    상세내용=VALUES(상세내용)
                """
                cur.execute(sql, (
                    row["servId"],
                    row["servDgst"],
                    row["serv_link"],
                    row["tgtrDtlCn"],
                    row["slctCritCn"],
                    row["alwServCn"]
                ))
                print("저장 완료")
            con.commit()
            print(f"총 {len(result_data)}개 항목 DB에 저장 완료")


        except Exception as e:
            print(f"[!] page {page} 에서 오류: {e}")