import json
from datasets import Dataset, DatasetDict
from sklearn.model_selection import train_test_split
import pandas as pd
import re

# --- 1. 定义标准化函数 ---
def standardize_output(output_str: str) -> str:
    """
    对模型的输出字符串进行标准化，以符合硬匹配要求。
    - 对多标签按字母顺序排序
    - 确保分隔符格式统一
    """
    quadruplets = output_str.strip().split(' [SEP] ')
    processed_quads = []

    for quad_str in quadruplets:
        # 清理结尾的 [END]
        quad_str = quad_str.replace(' [END]', '').strip()
        parts = quad_str.split(' | ')
        
        if len(parts) != 4:
            # 如果格式不正确，直接返回原始格式，在微调时作为错误数据点
            # 或者可以跳过这个数据点
            continue

        target, argument, targeted_group, hateful = parts
        
        # 标准化 Targeted Group (排序多标签)
        groups = [g.strip() for g in targeted_group.split(',')]
        groups.sort()
        sorted_groups = ', '.join(groups)

        # 重新组合成标准格式
        processed_quad = f"{target.strip()} | {argument.strip()} | {sorted_groups} | {hateful.strip()}"
        processed_quads.append(processed_quad)

    # 重新拼接所有四元组
    final_output = ' [SEP] '.join(processed_quads) + ' [END]'
    return final_output

# --- 2. 定义指令模板和格式化函数 ---
INSTRUCTION_TEMPLATE = """你是一个中文仇恨言论识别专家。请根据输入文本，抽取出所有仇恨言论四元组。
每个四元组的格式为'评论对象 | 论点 | 目标群体 | 是否仇恨'，并以'[END]'结尾。
多个四元组用'[SEP]'分隔。
注意：'目标群体'必须是 'Region', 'Racism', 'Sexism', 'LGBTQ', 'others', 'non-hate'中的一个或多个（用逗号和空格分隔，并按字母排序）。
'是否仇恨'必须是 'hate' 或 'non-hate'。
输出必须严格遵守格式。"""

def format_data_point(example):
    """
    将单个数据点格式化为包含instruction, input, output的字典。
    """
    # 对标准答案进行标准化处理
    standardized_output_val = standardize_output(example['output'])
    
    return {
        "instruction": INSTRUCTION_TEMPLATE,
        "input": example['content'],
        "output": standardized_output_val
    }

def create_prompt(record):
    """为SFTTrainer创建最终的训练文本"""
    return f"<s>[INST] {record['instruction']}\n{record['input']} [/INST]\n{record['output']}</s>"


# --- 3. 主处理流程 ---
def main():
    # 加载原始JSON数据
    # 注意：你的JSON文件可能是一个包含多个字典的列表，请根据实际情况调整加载方式
    # 这里假设你的train.json是 'list of dicts' 格式
    try:
        with open('train.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("JSON文件格式错误，请检查。它应该是一个有效的JSON列表。")
        return
        
    # 应用格式化函数
    formatted_data = [format_data_point(rec) for rec in data]
    df = pd.DataFrame(formatted_data)
    
    # 划分训练集和验证集
    train_df, val_df = train_test_split(df, test_size=0.1, random_state=42)
    
    # 转换为Hugging Face Dataset
    train_dataset = Dataset.from_pandas(train_df)
    val_dataset = Dataset.from_pandas(val_df)
    
    # 将格式化好的prompt应用到数据集中
    train_dataset = train_dataset.map(lambda x: {"text": create_prompt(x)})
    val_dataset = val_dataset.map(lambda x: {"text": create_prompt(x)})

    # 创建DatasetDict
    dataset_dict = DatasetDict({
        'train': train_dataset,
        'validation': val_dataset
    })
    
    # 保存到磁盘
    dataset_dict.save_to_disk('./processed_data')
    print("数据处理完成，并已保存到 './processed_data' 目录下。")
    print(f"训练集大小: {len(train_dataset)}")
    print(f"验证集大小: {len(val_dataset)}")
    print("\n数据样例:")
    print(dataset_dict['train'][0]['text'])

if __name__ == '__main__':
    main()