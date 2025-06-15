# prepare_data_hf.py
import json
import pandas as pd
from datasets import Dataset, DatasetDict
from sklearn.model_selection import train_test_split
from transformers import AutoTokenizer

# 模型的ID，我们需要用它的分词器来应用模板
# 将它修改为本地路径:
MODEL_ID = "/root/autodl-tmp/Qwen1.5-7B-Chat"

# 1. 标准化函数 (和之前一样，用于处理标签)
def standardize_output(output_str: str) -> str:
    quadruplets = output_str.strip().split(' [SEP] ')
    processed_quads = []
    for quad_str in quadruplets:
        quad_str = quad_str.replace(' [END]', '').strip()
        parts = quad_str.split(' | ')
        if len(parts) != 4: continue
        target, argument, targeted_group, hateful = parts
        groups = [g.strip() for g in targeted_group.split(',')]
        groups.sort()
        sorted_groups = ', '.join(groups)
        processed_quad = f"{target.strip()} | {argument.strip()} | {sorted_groups} | {hateful.strip()}"
        processed_quads.append(processed_quad)
    final_output = ' [SEP] '.join(processed_quads) + ' [END]'
    return final_output

# 2. 使用官方ChatML模板进行格式化的函数
def format_with_chat_template(example, tokenizer):
    # 系统指令
    system_prompt = "你是一个中文仇恨言论识别专家。请根据输入文本，抽取出所有仇恨言论四元组。每个四元组的格式为'评论对象 | 论点 | 目标群体 | 是否仇恨'，并以'[END]'结尾。多个四元组用'[SEP]'分隔。注意：'目标群体'必须是 'Region', 'Racism', 'Sexism', 'LGBTQ', 'others', 'non-hate'中的一个或多个（用逗号和空格分隔，并按字母排序）。'是否仇恨'必须是 'hate' 或 'non-hate'。输出必须严格遵守格式。"
    
    # 构建消息列表
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": example['content']},
        {"role": "assistant", "content": standardize_output(example['output'])}
    ]
    
    # 使用分词器的apply_chat_template方法
    # add_generation_prompt=False表示我们同时提供了user和assistant的内容，用于训练
    formatted_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": formatted_text}

# 3. 主处理流程
def main():
    print("开始加载分词器...")
    # 从Hugging Face Hub加载分词器
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    
    print("开始加载和处理JSON数据...")
    with open('train.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    df = pd.DataFrame(data)
    
    print("划分训练集和验证集...")
    train_df, val_df = train_test_split(df, test_size=0.1, random_state=42)
    
    train_dataset = Dataset.from_pandas(train_df)
    val_dataset = Dataset.from_pandas(val_df)
    
    print("应用ChatML模板格式化数据...")
    # 使用.map()方法批量处理数据
    train_dataset = train_dataset.map(lambda x: format_with_chat_template(x, tokenizer))
    val_dataset = val_dataset.map(lambda x: format_with_chat_template(x, tokenizer))
    
    dataset_dict = DatasetDict({'train': train_dataset, 'validation': val_dataset})
    
    # 保存到磁盘
    dataset_dict.save_to_disk('./hf_processed_data')
    print("数据处理完成，已保存到 './hf_processed_data' 目录下。")
    print("\n格式化后的数据样例:")
    print(dataset_dict['train'][0]['text'])

if __name__ == '__main__':
    main()