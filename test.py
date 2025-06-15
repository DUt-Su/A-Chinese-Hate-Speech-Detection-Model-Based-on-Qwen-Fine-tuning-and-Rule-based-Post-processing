# predict_on_test.py (Modified to include ID in the output)
import torch
import json
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

# --- 1. 配置路径 ---
BASE_MODEL_PATH = "/root/autodl-tmp/Qwen1.5-7B-Chat"
ADAPTER_PATH = "./qwen-hf-sft-output/final_adapter"
TEST_FILE_PATH = "./test1.json"
OUTPUT_FILE_PATH = "./submission1.txt"
DEFAULT_FALLBACK_OUTPUT = "NULL | NULL | non-hate | non-hate [END]"

# --- 2. 加载模型和分词器 ---
print("开始加载模型和分词器...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_PATH,
    quantization_config=quantization_config,
    device_map="auto",
    trust_remote_code=True
)
print(f"从 {ADAPTER_PATH} 加载LoRA适配器...")
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
print("融合LoRA权重...")
model = model.merge_and_unload()
model.eval()
print("模型加载并准备就绪！")

# --- 3. 准备prompt模板 ---
system_prompt = '''### **任务：中文社交媒体细粒度仇恨言论识别**

你是一个顶级的中文社交媒体内容审查专家，拥有社会学、语言学和网络文化背景。你的任务是精确地分析给定的文本，抽取出其中所有构成或不构成仇恨言论的观点，并严格按照指定的四元组格式输出。

---

### **第一部分：核心规则与定义**

**1. 输出格式 (必须严格遵守):**
- 每个观点都必须格式化为一个四元组：`评论对象 | 论点 | 目标群体 | 是否仇恨`
- 四元组的每个元素之间用 ` | ` (空格英文半角竖线空格) 分隔。
- 每个四元组必须以 ` [END]` (空格[END]) 结尾。
- 如果一条文本包含多个独立的观点，不同的四元组之间用 ` [SEP] ` (空格[SEP]空格) 分隔。

**2. 四元组字段定义:**
- **评论对象 (Target):** 评论对象，观点所直接指向的人物、群体或实体。
    - **风格对齐:** 抽取简洁的核心短语，严格重视于原文，必须是原文包含的
    - **特殊情况:** 如果言论是泛指或隐含的，没有明确的评论对象，则设为 `NULL`。
- **论点 (Argument):** 对“评论对象”的核心评价、行为描述或观点。
    - **风格对齐:** 必须是从原文中抽取的、最能代表核心观点的简洁短语或子句，不要自创，标点符号也要与原文保持一致。
- **目标群体 (Targeted Group):** 对“评论对象-论点”组合所攻击的群体进行的分类。必须是以下标签之一或多个的组合：
    - `Racism`: 种族或民族歧视。
    - `Region`: 地域歧视。
    - `Sexism`: 性别歧视。
    - `LGBTQ`: 对性少数群体的歧视。
    - `others`: 其他类型的歧视（如针对残障、疾病、宗教、职业等）。
    - `non-hate`: 不构成对特定群体的仇恨。
- **是否仇恨 (Hateful):** 对该观点是否构成仇恨言论的判断。
    - `hate`: 构成仇恨言论。
    - `non-hate`: 不构成仇恨言论（包括一般性人身攻击或无害评论）。

**3. 黄金规则 (为硬匹配优化):**
- **分类标签必须完美:** `Targeted Group` 和 `Hateful` 的标签必须与上述列表完全一致，包括大小写。
- **多标签必须排序:** 如果一个观点涉及多个`目标群体`，标签**必须按照英文字母顺序排序**，并用 `, ` (逗号+空格) 分隔。例如：应为 `Racism, Sexism`，而不是 `Sexism, Racism`。

**4. 常见网络黑话/隐语提示:**
- 为了帮助你更好地理解，以下是一些常见的隐语及其通常指向的歧视类别：
- Racism：
  - 黑蛆、黑皮、泥革、墨人、尼葛 → Racism
  - 黑人器大活好、非洲boy、黑人传艾滋 → Racism
  - 倭狗、日杂、韩畜 → Racism / Other
- Sexism：
  - 女拳、钕拳、小仙女、小酰钕、普信女、eg → Sexism
  - 母狗、母坦克、母零 → Sexism
  - 公、郭楠、龟男、直男癌 → Sexism
- LGBTQ：
  - 基佬、gay、腐癌、txl、同性癖、打拳、虹拳、跪虫族 → LGBTQ
- Region：
  - 东北人、南蛮、南满、北狄、冀东辽西 → Region
  - 河南、河北、安徽、广东、江苏等地名 + 嘲讽、污蔑语言 → Region
---

### **第二部分：典型样本学习 (Few-shot Examples)**

下面是几个经过精心挑选的例子，请仔细学习其内在逻辑。

**【样例1：简单直接的例子】**
- **输入:** `没爹的黑孩到处扔`
- **输出:** `没爹的黑孩 | 到处扔 | Racism | hate [END]`
- **//分析:** 直接针对特定种族（黑孩）进行恶意攻击，是明确的种族主义仇恨言论。

**【样例2：多标签的例子】**
- **输入:** `我靠真能下得去手啊，我去主校区的时候也见过几个又黑又肥又丑看不清脸，可能是我的学校太好了女生都挺保守的，没听说也没看见哪个女生和黑人谈恋爱`
- **输出:** `黑人 | 没听说也没看见哪个女生和黑人谈恋爱 | Racism, Sexism | hate [END]`
- **//分析:** 观点核心是“女生不应和黑人谈恋爱”。这既包含了对黑人群体的负面刻板印象（`Racism`），也包含了对女性择偶自由的物化和限制（`Sexism`）。注意标签已按字母排序。

**【样例3：多四元组的例子】**
- **输入:** `想反女权还得看女权，舔狗龟男理中客们不是男人能打醒的`
- **输出:** `女权 | 想反女权还得看女权 | Sexism | hate [SEP] 舔狗龟男理中客们 | 不是男人能打醒的 | Sexism | hate [END]`
- **//分析:** 文本包含两个独立的攻击点。第一个指向“女权”，第二个指向“舔狗龟男理中客们”，都与性别议题相关。因此需要拆分为两个四元组，用 `[SEP]` 分隔。

**【样例4：NULL目标的例子】**
- **输入:** `都弯了180度所以直了`
- **输出:** `NULL | 弯了180度所以直了 | LGBTQ | hate [END]`
- **//分析:** 这句话是网络上对同性恋群体的暗讽，没有明确说出评论对象，但仇恨指向非常清晰。因此“评论对象”为 `NULL`。

**【样例5：non-hate但有争议的例子】**
- **输入:** `无风不起浪，我就被河南人骗了几回了，没得洗`
- **输出:** `河南人 | 骗了几回了 | non-hate | non-hate [END]`
- **//分析:** 这是此任务标注标准的一个微妙之处。虽然内容是对特定地域人群的负面概括，但因为它基于“个人经历”的叙述，并未上升到鼓吹普遍性歧视或攻击的程度，因此被标注为 `non-hate`。你需要学习这种边界。

**【样例6：包含网络黑话的例子】**
- **输入:** `就算她不拿刀你就能打得过180斤起步的母坦克?`
- **输出:** `母坦克 | 180斤起步 | Sexism | hate [END]`
- **//分析:** 这里的核心攻击点是蔑称“母坦克”，这是一个基于体重的、对女性的侮辱性黑话，属于性别歧视 `Sexism`。

---

### **第三部分：开始任务**

现在，你已经掌握了所有规则和模式。请处理以下新的输入文本，并只返回严格符合格式要求的四元组输出，不要添加任何额外的解释或评论。注意！！只输出最后的结果就可以，不要输出任何别的内容！！
**警告：输出格式的绝对精确性**
- 你的输出将用于机器自动评测，任何格式错误，即使是单个空格、大小写或标点符号的偏差，都将导致评测失败。
- 请像机器一样精确地输出，不要添加任何与格式无关的、解释性的文字。你的整个回答应该只有四元组本身。'''

# --- 4. 加载测试数据 ---
print(f"从 {TEST_FILE_PATH} 加载测试数据...")
with open(TEST_FILE_PATH, 'r', encoding='utf-8') as f:
    test_data = json.load(f)
print(f"共加载 {len(test_data)} 条测试数据。")

# --- 5. 循环推理并保存结果 ---
print("开始批量推理...")
with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as out_f:
    # ★ 修改1: 使用 enumerate 来同时获取索引和内容
    for index, item in tqdm(enumerate(test_data), desc="正在处理", total=len(test_data)):
        # ★ 修改2: 从item中提取ID和content
        item_id = item['id']
        test_content = item['content']
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": test_content}
        ]
        
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        
        response_ids = outputs[0][inputs['input_ids'].shape[1]:]
        response = tokenizer.decode(response_ids, skip_special_tokens=True).strip()
        
        # 兜底逻辑
        if not response or '|' not in response:
            print(f"\n警告: ID {item_id} (第 {index + 1} 条) 生成无效/空响应。使用默认值。")
            final_output = DEFAULT_FALLBACK_OUTPUT
        else:
            final_output = response
            
        # ★ 修改3: 构造新的输出行格式 "id output"
        line_to_write = f"{item_id} {final_output}"
        
        # ★ 修改4 (Bug修复): 确保无论是正常输出还是兜底输出，都会被写入文件
        out_f.write(line_to_write + '\n')

print(f"\n处理完成！所有预测结果已保存到 {OUTPUT_FILE_PATH}")