# review_and_finalize.py
import re
import json
from tqdm import tqdm

# --- 配置 ---
RAW_SUBMISSION_FILE = "./submission2.txt"
FINAL_PARTIAL_FILE = "./final_submission_partial2.txt"
ERROR_REPORT_FILE = "./error_report2.txt"
TEST_FILE_PATH = "./test2.json"

DEFAULT_FALLBACK_OUTPUT = "NULL | NULL | non-hate | non-hate [END]"
NEEDS_REVIEW_PLACEHOLDER = "[NEEDS_MANUAL_REVIEW]"
VALID_TARGET_GROUPS = {"Racism", "Region", "Sexism", "LGBTQ", "others", "non-hate"}
VALID_HATEFUL_LABELS = {"hate", "non-hate"}

def repair_quadruplet_string(quad_str: str) -> tuple[str | None, str]:
    """
    对单个四元组进行深度修复。
    返回一个元组 (修复后的字符串 或 None, 状态信息)
    """
    original_for_report = quad_str
    
    # 预处理
    quad_str = re.sub(r'^\d+\s*', '', quad_str).strip()
    quad_str = re.sub(r'[`【】*]', '', quad_str)
    quad_str = re.sub(r'\s*\[END\]\s*$', '', quad_str, flags=re.IGNORECASE).strip()

    parts = [p.strip() for p in quad_str.split('|')]
    
    # 字段数量修复
    status = "SUCCESS"
    if len(parts) != 4:
        status = "REPAIRED"
        if len(parts) == 3 and parts[2].lower() in VALID_HATEFUL_LABELS:
            parts.insert(1, "NULL")
        elif len(parts) == 3:
            parts.insert(2, "non-hate")
        else:
            return None, f"字段数严重错误 ({len(parts)}个): {original_for_report}"
    
    target, argument, targeted_group, hateful = parts

    # Hateful 字段校正
    hateful_corrected = hateful.lower().strip()
    if hateful_corrected not in VALID_HATEFUL_LABELS:
        hateful_corrected = "non-hate"

    # Targeted Group 字段校正
    groups_raw = targeted_group.split(',')
    groups_processed = set()
    for g in groups_raw:
        g_clean = g.strip()
        g_capitalized = g_clean.capitalize()
        if g_capitalized in VALID_TARGET_GROUPS: groups_processed.add(g_capitalized)
        elif g_clean.upper() == 'LGBT': groups_processed.add('LGBTQ')
        elif g_clean.lower() == "null": groups_processed.add("others" if hateful_corrected == "hate" else "non-hate")

    if not groups_processed:
        groups_processed.add("others" if hateful_corrected == "hate" else "non-hate")
    
    targeted_group_corrected = ', '.join(sorted(list(groups_processed)))

    repaired = f"{target} | {argument} | {targeted_group_corrected} | {hateful_corrected} [END]"
    return repaired, status

def process_raw_record(record_content: str) -> tuple[str, bool]:
    """
    处理一个可能包含多行的记录。
    返回 (处理后的字符串, 是否成功)
    """
    # 优先提取结构化内容
    potential_matches = re.findall(r'((?:[\w\W]*?\|){3}[\w\W]*?\[END\])', record_content, re.IGNORECASE)
    if not potential_matches:
        # 如果完全找不到像样的结构，就认为它失败了
        return NEEDS_REVIEW_PLACEHOLDER, False

    content_to_process = ' [SEP] '.join(potential_matches)
    
    quadruplets_raw = re.split(r'\s*\[SEP\]\s*', content_to_process, flags=re.IGNORECASE)
    repaired_quadruplets = []
    has_errors = False
    
    for quad_str in quadruplets_raw:
        if quad_str.strip():
            repaired_quad, status = repair_quadruplet_string(quad_str)
            if repaired_quad:
                repaired_quadruplets.append(repaired_quad)
            else:
                has_errors = True # 标记此记录中存在无法修复的部分
    
    if has_errors or not repaired_quadruplets:
        return NEEDS_REVIEW_PLACEHOLDER, False
    else:
        # 如果您只想要单行输出，取消下面这行注释
        # return repaired_quadruplets[0], True
        return ' [SEP] '.join(repaired_quadruplets), True

def main():
    print(f"--- 开始修复与报告生成: '{RAW_SUBMISSION_FILE}' ---")
    
    # 读取原始测试集的ID列表
    try:
        with open(TEST_FILE_PATH, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        target_ids = {str(item['id']) for item in test_data}
    except Exception as e:
        print(f"❌ 严重错误: 无法读取基准测试文件 '{TEST_FILE_PATH}'! {e}")
        return

    # 读取原始输出文件
    try:
        with open(RAW_SUBMISSION_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ 错误: 原始输出文件 '{RAW_SUBMISSION_FILE}' 未找到！")
        return

    # 按ID和行号解析记录
    records = {}
    current_id = None
    current_content = []
    start_line_num = 0

    for i, line in enumerate(lines):
        match = re.match(r'^(\d+)\s', line)
        if match:
            # 发现新ID，保存上一个记录
            if current_id is not None:
                records[current_id] = ("".join(current_content), start_line_num)
            # 开始新记录
            current_id = match.group(1)
            current_content = [line[len(match.group(0)):]] # 保存除ID和空格之外的内容
            start_line_num = i + 1
        elif current_id is not None:
            # 如果不是新ID行，就追加到当前记录的内容中
            current_content.append(line)
    
    # 保存最后一个记录
    if current_id is not None:
        records[current_id] = ("".join(current_content), start_line_num)
        
    print(f"从 '{RAW_SUBMISSION_FILE}' 中解析出 {len(records)} 条记录。")

    # 打开两个文件用于写入
    f_out = open(FINAL_PARTIAL_FILE, 'w', encoding='utf-8')
    f_report = open(ERROR_REPORT_FILE, 'w', encoding='utf-8')
    
    f_report.write("--- 需人工审核的错误报告 ---\n\n")
    error_count = 0

    for record_id in tqdm(sorted(target_ids, key=int), desc="修复与写入"):
        if record_id in records:
            record_content, line_num = records[record_id]
            final_string, success = process_raw_record(record_content)
            
            f_out.write(final_string + '\n')

            if not success:
                error_count += 1
                f_report.write(f"--- 问题记录 ---\n")
                f_report.write(f"ID: {record_id}\n")
                f_report.write(f"原始文件行号 (大约): {line_num}\n")
                f_report.write(f"原始输出内容:\n---\n{record_content.strip()}\n---\n\n")
        else:
            f_out.write(NEEDS_REVIEW_PLACEHOLDER + '\n')
            error_count += 1
            f_report.write(f"--- 问题记录 ---\n")
            f_report.write(f"ID: {record_id}\n")
            f_report.write(f"原始文件行号 (大约): N/A (在输出文件中完全缺失)\n")
            f_report.write(f"原始输出内容: [不存在]\n---\n\n")
            
    f_out.close()
    f_report.close()

    print("-" * 50)
    print(f"✅ 处理完成！")
    print(f"一个半自动修复的文件已保存至: '{FINAL_PARTIAL_FILE}'")
    print(f"一份包含 {error_count} 条待办事项的错误报告已保存至: '{ERROR_REPORT_FILE}'")
    print("\n下一步：请打开 error_report.txt，根据其中的指引，手动修正 partial 文件。")

if __name__ == "__main__":
    main()