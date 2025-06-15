import os

def process_files_corrected(filtered_path, fine_path, output_path):
    """
    修正后的代码逻辑：
    读取 filtered_path，如果某行仅为数字ID，则在 fine_path 中查找
    以该ID开头的完整行，并用其替换。其他行保持不变。

    :param filtered_path: 待处理的文件路径 (e.g., 'filtered1.txt')
    :param fine_path: 提供ID和内容的数据源文件路径 (e.g., 'fine1.txt')
    :param output_path: 输出结果的文件路径 (e.g., 'filtered_updated.txt')
    """
    # 1. 高效读取 fine1.txt，将其内容存入一个字典中
    #    键(key)是ID，值(value)是 fine1.txt 中的完整原始行
    lookup_data = {}
    print(f"正在从 '{fine_path}' 加载数据...")
    try:
        with open(fine_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 假设ID是行开头、以空格或'|'分隔的部分
                # .split() 默认按空格分割，取第一个元素即可
                id_str = line.split(None, 1)[0]
                if id_str.isdigit():
                    # 关键：将【完整的原始行】作为值存起来
                    lookup_data[id_str] = line
    except FileNotFoundError:
        print(f"错误: 数据源文件 '{fine_path}' 未找到。请检查文件名和路径。")
        return

    if not lookup_data:
        print(f"警告: 未能从 '{fine_path}' 中加载任何数据。请检查文件内容和格式。")
        return
        
    print(f"数据加载完成，共 {len(lookup_data)} 条。")
    print("-" * 20)

    # 2. 逐行读取 filtered1.txt，进行替换，并写入新文件
    replaced_count = 0
    kept_count = 0
    print(f"正在处理 '{filtered_path}'...")
    try:
        with open(filtered_path, 'r', encoding='utf-8') as f_in, \
             open(output_path, 'w', encoding='utf-8') as f_out:
            
            for line in f_in:
                # 去除行首和行尾的空白字符，方便判断
                clean_line = line.strip()

                # 判断这一行是否是【纯数字ID】，并且这个ID在我们的数据源中存在
                if clean_line.isdigit() and clean_line in lookup_data:
                    # 如果是，就从字典中取出对应的【完整行】写入新文件
                    replacement_line = lookup_data[clean_line]
                    # 从字典取出的值已包含换行符，所以直接写入
                    f_out.write(replacement_line)
                    replaced_count += 1
                else:
                    # 如果不是纯数字ID行，或者ID在fine1.txt中找不到，就保持原样写入
                    f_out.write(line)
                    kept_count += 1
    except FileNotFoundError:
        print(f"错误: 输入文件 '{filtered_path}' 未找到。请检查文件名和路径。")
        return
        
    # 3. 输出总结报告
    print("-" * 20)
    print("处理完成！ ✨")
    print(f"成功替换了 {replaced_count} 行。")
    print(f"保持了 {kept_count} 行未作修改。")
    print(f"结果已保存到新文件: '{os.path.abspath(output_path)}'")


# --- 使用说明 ---
# 1. 将下面的文件名替换成你自己的文件名
filtered_filename = 'filtered2.txt'
fine_filename = 'fine2.txt'
output_filename = 'updated2.txt'

# 2. 确保这个Python脚本和你的 .txt 文件在同一个文件夹下
# 3. 运行这个脚本
if __name__ == "__main__":
    process_files_corrected(filtered_filename, fine_filename, output_filename)