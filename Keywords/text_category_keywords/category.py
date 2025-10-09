import json
import csv

def load_category_keywords(file_path="category_keywords.txt"):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            category_keywords = json.load(file)
        return category_keywords
    except FileNotFoundError:
        print(f"오류: {file_path} 파일을 찾을 수 없습니다.")
        return {}
    except json.JSONDecodeError:
        print("오류: category_keywords.txt 파일이 올바른 JSON 형식이 아닙니다.")
        return {}

def classify_policy(policy_text, category_keywords):
    result = []
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in policy_text:
                result.append(category)
                break
    if not result:
        result.append("기타")
    return result

def classify_csv(input_csv="servDgst_list.csv", output_csv="classified_policies.csv"):
    category_keywords = load_category_keywords("category_keywords.txt")
    
    classified_rows = []

    # CSV 읽기 (한 줄씩)
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:  # 빈 줄 건너뛰기
                continue
            policy_text = row[0]  # 첫 번째 컬럼만 사용
            categories = ", ".join(classify_policy(policy_text, category_keywords))
            classified_rows.append([policy_text, categories])

    # 결과 저장
    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["policy_text", "categories"])
        writer.writerows(classified_rows)

    print(f"분류 완료: {output_csv} 파일로 저장되었습니다.")

if __name__ == "__main__":
    classify_csv()
