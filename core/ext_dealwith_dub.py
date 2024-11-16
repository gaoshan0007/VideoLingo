import pandas as pd
import os
import re

def read_cleaned_chunks(file_path='output/log/cleaned_chunks.xlsx'):
    """
    读取 cleaned_chunks.xlsx 文件
    
    参数:
    file_path (str): Excel 文件路径，默认为 'output/log/cleaned_chunks.xlsx'
    
    返回:
    pandas.DataFrame: 读取的 Excel 数据
    """
    try:
        # 确保文件夹存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        df = pd.read_excel(file_path)
        return df
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到")
        return None
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return None

def read_translation_results(file_path='output/log/sentence_splitbymeaning.txt'):
    """
    读取 sentence_splitbymeaning.txt 文件
    
    参数:
    file_path (str): 文本文件路径，默认为 'output/log/sentence_splitbymeaning.txt'
    
    返回:
    pandas.DataFrame: 读取的文本数据
    """
    try:
        # 确保文件夹存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # 读取单列文件
        df = pd.read_csv(file_path, sep='\t', header=None, names=['Source'])
        return df
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到")
        return None
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return None

def validate_and_clean_translation_results(cleaned_chunks_path, translation_results_path):
    """
    验证并清理翻译结果，确保 Source 中的单词存在且顺序与 cleaned_chunks 中 text 列一致
    
    参数:
    cleaned_chunks_path (str): 清理后的块数据文件路径
    translation_results_path (str): 翻译结果数据文件路径
    
    返回:
    pandas.DataFrame: 清理后的翻译结果
    """
    cleaned_chunks = read_cleaned_chunks(cleaned_chunks_path)
    if cleaned_chunks is None:
        return None
    
    translation_results = read_translation_results(translation_results_path)
    if translation_results is None:
        return None
    
    if cleaned_chunks is None or translation_results is None:
        print("输入数据不能为空")
        return None
    
    # 合并所有 text 列的内容为一个大字符串
    all_text = ' '.join(cleaned_chunks['text'].dropna().astype(str))
    
    # 创建一个新的 DataFrame 来存储清理后的翻译结果
    cleaned_translation_results = translation_results.copy()
    
    def clean_source(source):
        # 将 source 拆分为单词
        source_words = str(source).split()
        
        # 过滤出存在于 all_text 中的单词
        valid_words = [word for word in source_words if word in all_text]
        
        # 如果没有有效单词，返回原始 source
        if not valid_words:            
            return source
        
        # 返回有效单词组成的字符串
        return ' '.join(valid_words)
    
    # 对每一行的 Source 列进行处理
    cleaned_translation_results['Source'] = cleaned_translation_results['Source'].apply(clean_source)
    
    # 保存清理后的结果到文本文件
    output_path = 'output/log/sentence_splitbymeaning.txt'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cleaned_translation_results.to_csv(output_path, sep='\t', index=False, header=False)
    print(f"已保存清理后的翻译结果到 {output_path}")
    
    return cleaned_translation_results

def main():
    """
    主函数，演示如何使用 read_cleaned_chunks 和 read_translation_results 函数，
    并进行数据验证和清理
    """
    # 读取清理后的块
    cleaned_chunks_path = 'output/log/cleaned_chunks.xlsx'
    translation_results_path = 'output/log/sentence_splitbymeaning.txt'
    
    # 验证并清理翻译结果
    cleaned_translation_results = validate_and_clean_translation_results(cleaned_chunks_path, translation_results_path)
    
    if cleaned_translation_results is not None:
        print("\n清理后的翻译结果:")
        print(cleaned_translation_results)

if __name__ == "__main__":
    main()
