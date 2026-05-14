import csv
import json
import os

base = r"c:\Users\parkj\IdeaProjects\schoolclub1"
results = []

def clean(s):
    return s.strip().strip('"').strip("'").strip()

# ===== 서구: 번호, 약국명칭, 약국주소(도로명), 약국전화번호 =====
with open(os.path.join(base, "대전광역시 서구_약국현황_20250820.csv"), encoding="euc-kr") as f:
    reader = csv.reader(f)
    headers = next(reader)
    print("서구 headers:", headers)
    for row in reader:
        if len(row) < 3: continue
        results.append({
            "district": "서구",
            "name": clean(row[1]),
            "address": clean(row[2]),
            "phone": clean(row[3]) if len(row) > 3 else ""
        })

print(f"서구: {sum(1 for r in results if r['district']=='서구')}")

# ===== 동구: 번호, 약국명칭, 약국전화번호, 약국주소(도로명) =====
with open(os.path.join(base, "대전광역시 동구 약국 현황_20250701.csv"), encoding="euc-kr") as f:
    reader = csv.reader(f)
    headers = next(reader)
    print("동구 headers:", headers)
    for row in reader:
        if len(row) < 4: continue
        results.append({
            "district": "동구",
            "name": clean(row[1]),
            "address": clean(row[3]),
            "phone": clean(row[2])
        })

print(f"동구: {sum(1 for r in results if r['district']=='동구')}")

# ===== 대덕구: 약국명칭, 약국주소(도로명), 전화번호, 기준일 =====
with open(os.path.join(base, "대전광역시 대덕구_약국정보_20250101.csv"), encoding="euc-kr") as f:
    reader = csv.reader(f)
    headers = next(reader)
    print("대덕구 headers:", headers)
    for row in reader:
        if len(row) < 2: continue
        results.append({
            "district": "대덕구",
            "name": clean(row[0]),
            "address": clean(row[1]),
            "phone": clean(row[2]) if len(row) > 2 else ""
        })

print(f"대덕구: {sum(1 for r in results if r['district']=='대덕구')}")

# ===== 유성구: 구분코드, 구분기준, 약국명, 도로명주소, 전화번호 =====
with open(os.path.join(base, "대전광역시 유성구_약국현황_20250731.csv"), encoding="euc-kr") as f:
    reader = csv.reader(f)
    headers = next(reader)
    print("유성구 headers:", headers)
    for row in reader:
        if len(row) < 5: continue
        results.append({
            "district": "유성구",
            "name": clean(row[2]),
            "address": clean(row[3]),
            "phone": clean(row[4])
        })

print(f"유성구: {sum(1 for r in results if r['district']=='유성구')}")

# ===== 중구: 번호, 약국명칭, 약국전화번호, 약국번호(도로명), 약국주소(도로명), 한줄번호 =====
with open(os.path.join(base, "대전광역시 중구 약국 정보_20250905.csv"), encoding="euc-kr") as f:
    reader = csv.reader(f)
    headers = next(reader)
    print("중구 headers:", headers)
    for row in reader:
        if len(row) < 5: continue
        results.append({
            "district": "중구",
            "name": clean(row[1]),
            "address": clean(row[4]),
            "phone": clean(row[2])
        })

print(f"중구: {sum(1 for r in results if r['district']=='중구')}")
print(f"\n전체: {len(results)}")

# Filter out empty addresses
results = [r for r in results if r["address"] and len(r["address"]) > 5]
print(f"주소 있는 약국: {len(results)}")

# Save to JSON
out_path = os.path.join(base, "pharmacies.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"저장 완료: {out_path}")

# Preview
for r in results[:3]:
    print(r)
