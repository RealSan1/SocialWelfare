import db, ollama, re

con = db.get_conn()
cur = con.cursor()

# ------------------------
# NLP 분류 준비
# ------------------------
with open("prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read()

def classify_welfare(text: str) -> str:
    """NLP 모델로 카테고리 분류"""
    response = ollama.chat(
        model='gpt-oss:20b',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )
    return response.get('message', {}).get('content', '응답 없음')

def clean_text(text: str) -> str:
    """공백, 줄바꿈 제거 및 연속 공백 정리"""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def prepare_text_for_nlp(정책명, 지원대상, 참고사항, 상세내용) -> str:
    """NLP 모델이 이해하기 좋게 각 필드를 라벨과 함께 연결"""
    parts = []
    if 정책명:
        parts.append(f"정책명: {clean_text(정책명)}")
    if 지원대상:
        parts.append(f"지원대상: {clean_text(지원대상)}")
    if 참고사항:
        parts.append(f"참고사항: {clean_text(참고사항)}")
    if 상세내용:
        parts.append(f"상세내용: {clean_text(상세내용)}")
    return " | ".join(parts)  # 구분자로 "|" 사용

# ------------------------
# DB에서 복지서비스 내용 가져오기
# ------------------------
cur.execute("SELECT 서비스ID, 정책명, 지원대상, 참고사항, 상세내용 FROM 복지서비스")
rows = cur.fetchall()

# ------------------------
# 카테고리 분류 + 저장
# ------------------------
# ------------------------
# 카테고리 분류 + 저장
# ------------------------
for row in rows:
    서비스ID, 정책명, 지원대상, 참고사항, 상세내용 = row

    # 이미 분류된 서비스인지 확인
    cur.execute("SELECT 카테고리 FROM 카테고리 WHERE 서비스ID=%s", (서비스ID,))
    existing = cur.fetchone()
    if existing and existing[0]:  # 카테고리 값이 이미 존재하면 스킵
        print(f"[SKIP] {서비스ID} ({정책명}) 이미 분류됨 → {existing[0]}")
        continue

    text_for_classify = prepare_text_for_nlp(정책명, 지원대상, 참고사항, 상세내용)

    if not text_for_classify:
        print(f"[!] {서비스ID} 분류할 텍스트 없음, 스킵")
        continue

    try:
        category = classify_welfare(text_for_classify)
        category = clean_text(category)
        print(정책명, "→", category)
    except Exception as e:
        print(f"[!] 카테고리 분류 오류: {서비스ID}, {e}")
        category = ""

    # 부모 존재 확인 후 저장
    cur.execute("SELECT 1 FROM 복지서비스 WHERE 서비스ID=%s", (서비스ID,))
    if cur.fetchone():
        cur.execute("""
            INSERT INTO 카테고리
            (서비스ID, 카테고리)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                카테고리=VALUES(카테고리)
        """, (서비스ID, category))
        con.commit()
        print(f"[{서비스ID}] 카테고리 저장 완료 → {category}")
    else:
        print(f"[!] 부모 복지서비스 없음, 카테고리 저장 스킵: {서비스ID}")
