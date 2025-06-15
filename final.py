# finalize_and_repair.py
import re
import json
from tqdm import tqdm

# --- 配置 ---
# 您的模型生成的、带有ID的、混乱的原始文件
RAW_SUBMISSION_FILE = "./submission2.txt" 
# 修复后用于最终提交的文件（不含ID）
FINAL_SUBMISSION_FILE = "./final_submission_repaired.txt"
# 原始的测试集文件，用于获取ID总数以供校验
TEST_FILE_PATH = "./test2.json"

DEFAULT_FALLBACK_OUTPUT = "NULL | NULL | non-hate | non-hate [END]"
VALID_TARGET_GROUPS = {"Racism", "Region", "Sexism", "LGBTQ", "others", "non-hate"}
VALID_HATEFUL_LABELS = {"hate", "non-hate"}

def repair_and_normalize_quadruplet(text: str) -> str:
    """
    接收一个可能很乱的字符串，尝试从中修复出唯一一个、格式完美的四元组。
    """
    # 1. 预处理：移除各种可能的干扰物
    text = re.sub(r'^\d+\s*', '', text).strip()
    text = re.sub(r'[`【】*]', '', text, flags=re.MULTILINE) # 移除特殊括号、反引号、星号
    text = re.sub(r'^-.+', '', text, flags=re.MULTILINE) # 移除markdown列表
    text = re.sub(r'\s*\[END\]\s*$', '', text, flags=re.IGNORECASE).strip()

    # 如果包含 [SEP]，只取第一个
    text = re.split(r'\s*\[SEP\]\s*', text, flags=re.IGNORECASE)[0]
    
    parts = [p.strip() for p in text.split('|')]

    # 2. 核心修复逻辑：处理字段数量不为4的情况
    if len(parts) == 3:
        if parts[2].lower() in VALID_HATEFUL_LABELS:
            parts.insert(1, "NULL") # 补充'论点'
        else:
            parts.insert(2, "non-hate") # 补充'目标群体'
    
    if len(parts) != 4:
        return DEFAULT_FALLBACK_OUTPUT # 无法修复，返回默认值

    target, argument, targeted_group, hateful = parts

    # 3. 校正 Hateful 和 Targeted Group 字段
    hateful_corrected = hateful.lower().strip()
    if hateful_corrected not in VALID_HATEFUL_LABELS: hateful_corrected = "non-hate"

    groups_raw = targeted_group.split(',')
    groups_processed = set()
    for g in groups_raw:
        g_clean = g.strip()
        g_capitalized = g_clean.capitalize()
        g_upper = g_clean.upper()
        if g_capitalized in VALID_TARGET_GROUPS: groups_processed.add(g_capitalized)
        elif g_upper == 'LGBT': groups_processed.add('LGBTQ')
        elif g_clean.lower() == "null": groups_processed.add("others" if hateful_corrected == "hate" else "non-hate")

    if not groups_processed:
        groups_processed.add("others" if hateful_corrected == "hate" else "non-hate")
    
    targeted_group_corrected = ', '.join(sorted(list(groups_processed)))

    # 4. 重新组装成完美的四元组
    return f"{target} | {argument} | {targeted_group_corrected} | {hateful_corrected} [END]"

def main():
    print(f"--- 开始智能修复与对齐: '{RAW_SUBMISSION_FILE}' ---")
    
    # 读取原始测试集的ID列表，作为我们必须对齐的基准
    try:
        with open(TEST_FILE_PATH, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        target_ids = {str(item['id']) for item in test_data}
        print(f"基准文件 '{TEST_FILE_PATH}' 加载成功，目标ID数量: {len(target_ids)}")
    except Exception as e:
        print(f"❌ 严重错误: 无法读取基准测试文件 '{TEST_FILE_PATH}'! {e}")
        return

    # 读取包含所有混乱输出的原始文件
    try:
        with open(RAW_SUBMISSION_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ 错误: 原始输出文件 '{RAW_SUBMISSION_FILE}' 未找到！")
        return

    # 使用正则表达式按ID分割整个文件内容，这可以正确处理多行记录
    records = {}
    # 这个复杂的正则查找所有以数字和空格开头的行
    record_starts = list(re.finditer(r'^\d+\s', content, re.MULTILINE))
    
    for i, start_match in enumerate(tqdm(record_starts, desc="解析记录")):
        start_pos = start_match.start()
        # 记录的结束位置是下一个记录的开始，或者是文件末尾
        end_pos = record_starts[i+1].start() if i + 1 < len(record_starts) else len(content)
        
        record_full_text = content[start_pos:end_pos].strip()
        
        try:
            record_id, record_content = record_full_text.split(' ', 1)
            records[record_id] = record_content
        except ValueError:
            # 如果一行只有一个ID，没有内容，也给它一个空内容
            records[record_full_text.strip()] = ""
            
    print(f"从 '{RAW_SUBMISSION_FILE}' 中解析出 {len(records)} 条记录。")

    # 写入最终的、干净的提交文件
    with open(FINAL_SUBMISSION_FILE, 'w', encoding='utf-8') as f_out:
        print(f"开始生成最终提交文件: '{FINAL_SUBMISSION_FILE}'")
        for record_id in tqdm(sorted(target_ids, key=int), desc="修复并写入"):
            # 如果某个ID在输出文件中存在，就处理它
            if record_id in records:
                repaired_line = repair_and_normalize_quadruplet(records[record_id])
                f_out.write(repaired_line + '\n')
            else:
                # 如果某个ID在输出文件中完全不存在，也写入默认值以保证对齐
                print(f"  [警告] ID {record_id} 在输出文件中缺失，写入默认值。")
                f_out.write(DEFAULT_FALLBACK_OUTPUT + '\n')

    print("-" * 50)
    print(f"✅ 修复与对齐完成！")
    print(f"最终可提交的文件已保存至: '{FINAL_SUBMISSION_FILE}'")


if __name__ == "__main__":
    main()