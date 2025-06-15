import os

def remove_leading_id(input_file, output_file):
    """
    读取输入文件，如果某行以"数字 + 空格"开头，则移除这部分，
    否则保持原样。结果写入输出文件。

    :param input_file: 你的源文件路径。
    :param output_file: 处理后要保存的新文件路径。
    """
    lines_modified = 0
    lines_kept = 0

    print(f"正在处理文件: '{input_file}'...")

    try:
        with open(input_file, 'r', encoding='utf-8') as f_in, \
             open(output_file, 'w', encoding='utf-8') as f_out:

            for line in f_in:
                # 将每一行按第一个空格分割成两部分
                parts = line.split(' | ', 1)

                # 检查：1. 是否能分割成两部分； 2. 分割出的第一部分是否是纯数字
                if len(parts) == 2 and parts[0].isdigit():
                    # 如果满足条件，说明是需要处理的行
                    # 我们只写入分割后的第二部分 (parts[1])
                    # parts[1] 自身已经包含了原始行末尾的换行符，所以直接写入即可
                    f_out.write(parts[1])
                    lines_modified += 1
                else:
                    
                    # 如果不满足条件（比如行首不是数字，或者没有空格），
                    # 则将原始行原封不动地写入
                    f_out.write(line)
                    lines_kept += 1

        # 打印总结报告
        print("-" * 20)
        print("处理完成！ 🎉")
        print(f"成功修改了 {lines_modified} 行。")
        print(f"保持了 {lines_kept} 行不变。")
        print(f"结果已保存到新文件: '{os.path.abspath(output_file)}'")

    except FileNotFoundError:
        print(f"错误: 输入文件 '{input_file}' 未找到。请检查文件名和路径是否正确。")
    except Exception as e:
        print(f"处理过程中发生未知错误: {e}")


# --- 使用说明 ---
# 1. 请将下面的 'your_source_file.txt' 替换成你的实际文件名。
source_filename = 'updated2.txt'

# 2. 这是处理后输出的文件名，你也可以自己修改。
output_filename = 'end2.txt'

# 3. 确保这个Python脚本和你的 .txt 文件在同一个文件夹下，然后运行脚本。
if __name__ == "__main__":
    # 在运行前，最好先手动创建一个与 source_filename 同名的文件，并把你的内容粘贴进去
    if not os.path.exists(source_filename):
        print(f"提示: 源文件 '{source_filename}' 不存在。")
        print("请先将您的内容保存到该文件中，或修改脚本中的 'source_filename' 变量。")
    else:
        remove_leading_id(source_filename, output_filename)