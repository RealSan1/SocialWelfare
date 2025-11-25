import ollama, re, os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db import engine

conn = engine.raw_connection()
cur = conn.cursor()

# ------------------------
# NLP 분류 준비
# ------------------------
with open("NLP/prompt.txt", "r", encoding="utf-8") as f:
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

def generate_policy_name(text: str) -> str:
    """요약 텍스트에서 정책명을 생성"""
    prompt = f"""
다음 복지정보 요약에서 간결하고 매력적인 정책명(2-5단어)을 생성해주세요. 정책명만 출력하세요.

요약: {text}
"""
    try:
        response = ollama.chat(
            model='gpt-oss:20b',
            messages=[{"role": "user", "content": prompt}]
        )
        policy_name = clean_text(response.get('message', {}).get('content', '정책'))
        
        # 기업/정부 여부 판단
        text_lower = text.lower()
        기업_키워드 = ['재단', '기업', '회사', '은행', '금융기관', 'ibk', '삼성', '현대', '신한', 'lg', 'sk']
        is_corporate = any(kw in text_lower for kw in 기업_키워드)
        
        # 접두사 붙이기
        prefix = "[기업] " if is_corporate else "[정부] "
        return prefix + policy_name
    except Exception as e:
        return f"정책 ({e})"

def generate_target(text: str) -> str:
    """요약 텍스트에서 지원대상을 추출/생성"""
    prompt = f"""
다음 복지정보에서 지원대상(예: 아동, 청년, 저소득층 등)을 추출해주세요. 해당 내용이 없으면 "일반인"으로 표기하세요. 지원대상만 출력하세요.

정보: {text}
"""
    try:
        response = ollama.chat(
            model='gpt-oss:20b',
            messages=[{"role": "user", "content": prompt}]
        )
        return clean_text(response.get('message', {}).get('content', '일반인'))
    except Exception as e:
        return "일반인"

def generate_note(text: str) -> str:
    """요약 텍스트에서 참고사항을 생성"""
    prompt = f"""
다음 복지정보에서 신청 조건, 기한, 주의사항 등 중요한 참고사항을 1-2문장으로 추출/생성해주세요. 참고사항만 출력하세요.

정보: {text}
"""
    try:
        response = ollama.chat(
            model='gpt-oss:20b',
            messages=[{"role": "user", "content": prompt}]
        )
        return clean_text(response.get('message', {}).get('content', ''))
    except Exception as e:
        return ""

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

cur.execute("SELECT 서비스ID, 정책명, 지원대상, 참고사항, 상세내용 FROM 복지서비스")
rows = cur.fetchall()
# ------------------------
# 필드 생성 + 카테고리 분류 + 저장
# ------------------------
for row in rows:
    서비스ID, 정책명, 지원대상, 참고사항, 상세내용 = row

    # 상세내용이 없으면 스킵
    if not 상세내용:
        print(f"[SKIP] {서비스ID} 상세내용 없음, 스킵")
        continue

    # 모든 필드를 항상 재생성 (기존 데이터 덮어쓰기)
    생성된_정책명 = generate_policy_name(상세내용)
    # 생성된 제목에서 [기업], [정부] 등의 접두사/괄호 제거
    생성된_정책명_clean = re.sub(r'^\[[^\]]+\]\s*', '', 생성된_정책명).strip()

    # 기존 정책명에서 기관명만 추출해서 대괄호로 사용
    기존제목 = clean_text(정책명) if 정책명 else ""
    org_name = None
    if 기존제목:
        m = re.match(r'^\[([^\]]+)\]\s*(.*)$', 기존제목)
        if m:
            # 이미 [기관명] ... 형태면 괄호 안의 기관명 사용
            org_name = m.group(1).strip()
        else:
            # 괄호가 없을 때는 단일 토큰(공백 없음) 또는 짧은 텍스트를 기관명으로 간주
            if len(기존제목) <= 20 and ' ' not in 기존제목:
                org_name = 기존제목
            else:
                org_name = None

    if org_name:
        최종_정책명 = f"[{org_name}] {생성된_정책명_clean}"
    else:
        최종_정책명 = 생성된_정책명_clean

    생성된_지원대상 = generate_target(상세내용)
    생성된_참고사항 = generate_note(상세내용)

    print(f"\n[{서비스ID}] 처리 중...")
    print(f"  기존정책명: {정책명}")
    print(f"  최종_정책명: {최종_정책명}")
    print(f"  지원대상: {생성된_지원대상}")
    print(f"  참고사항: {생성된_참고사항}")

    # 복지서비스 테이블 업데이트
    try:
        cur.execute("""
            UPDATE 복지서비스
            SET 정책명=%s, 지원대상=%s, 참고사항=%s
            WHERE 서비스ID=%s
        """, (최종_정책명, 생성된_지원대상, 생성된_참고사항, 서비스ID))
        conn.commit()
        print(f"  ✓ 복지서비스 정보 업데이트 완료")
    except Exception as e:
        print(f"  [!] 복지서비스 업데이트 실패: {e}")
        conn.rollback()

    # 카테고리 분류 (분류에는 DB에 저장될 최종 제목을 사용)
    text_for_classify = prepare_text_for_nlp(최종_정책명, 생성된_지원대상, 생성된_참고사항, 상세내용)

    try:
        category = classify_welfare(text_for_classify)
        category = clean_text(category)
        print(f"  카테고리: {category}")
    except Exception as e:
        print(f"  [!] 카테고리 분류 오류: {e}")
        category = ""

    # 카테고리 저장
    try:
        cur.execute("""
            INSERT INTO 카테고리
            (서비스ID, 카테고리)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                카테고리=VALUES(카테고리)
        """, (서비스ID, category))
        conn.commit()
        print(f"  ✓ 카테고리 저장 완료")
    except Exception as e:
        print(f"  [!] 카테고리 저장 실패: {e}")
        conn.rollback()

conn.close()
