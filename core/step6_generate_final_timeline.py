import pandas as pd
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
from rich.panel import Panel
from rich.console import Console
import autocorrect_py as autocorrect

console = Console()

CLEANED_CHUNKS_FILE = 'output/log/cleaned_chunks.xlsx'
TRANSLATION_RESULTS_FOR_SUBTITLES_FILE = 'output/log/translation_results_for_subtitles.xlsx'
TRANSLATION_RESULTS_REMERGED_FILE = 'output/log/translation_results_remerged.xlsx'

OUTPUT_DIR = 'output'
AUDIO_OUTPUT_DIR = 'output/audio'

SUBTITLE_OUTPUT_CONFIGS = [ 
    ('src.srt', ['Source']),
    ('trans.srt', ['Translation']),
    ('src_trans.srt', ['Source', 'Translation']),
    ('trans_src.srt', ['Translation', 'Source'])
]

AUDIO_SUBTITLE_OUTPUT_CONFIGS = [
    ('src_subs_for_audio.srt', ['Source']),
    ('trans_subs_for_audio.srt', ['Translation'])
]

def convert_to_srt_format(start_time, end_time):
    """Convert time (in seconds) to the format: hours:minutes:seconds,milliseconds"""
    def seconds_to_hmsm(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int(seconds * 1000) % 1000
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

    start_srt = seconds_to_hmsm(start_time)
    end_srt = seconds_to_hmsm(end_time)
    return f"{start_srt} --> {end_srt}"

def remove_punctuation(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def show_difference(str1, str2):
    """显示两个字符串之间的差异位置"""
    # 获取两个字符串中较短的长度
    min_len = min(len(str1), len(str2))
    
    # 初始化一个存储差异位置的列表
    diff_positions = []
    
    # 逐字符比较，找出不同的位置
    for i in range(min_len):
        if str1[i] != str2[i]:
            diff_positions.append(i)
    
    # 如果两个字符串长度不同，将剩余的位置也标记为差异
    if len(str1) != len(str2):
        diff_positions.extend(range(min_len, max(len(str1), len(str2))))
    
    # 打印期望的句子
    print("Difference positions:")
    print(f"Expected sentence: {str1}")
    
    # 打印实际匹配的句子
    print(f"Actual match: {str2}")
    
    # 打印带有差异标记的位置标记
    print("Position markers: " + "".join("^" if i in diff_positions else " " for i in range(max(len(str1), len(str2)))))
    
    # 打印差异的索引位置
    print(f"Difference indices: {diff_positions}")

def get_sentence_timestamps(df_words, df_sentences):
    """
    获取句子的时间戳
    
    异常抛出条件：
    1. 当无法在完整单词字符串中找到匹配的句子时
       - 可能原因：
         a. 输入的单词列表和句子列表不匹配
         b. 句子清理后的文本与单词字符串不完全对应
         c. 存在特殊字符或格式导致匹配失败
    
    2. 具体异常场景：
       - 句子中包含特殊标记或格式
       - 单词列表和句子列表的文本处理不一致
       - 输入数据存在预期外的文本格式
    
    异常处理：
    - 打印未匹配句子的详细信息
    - 使用 show_difference 显示匹配失败的具体位置
    - 抛出 ValueError，提供详细的错误信息
    """
    # 初始化存储时间戳的列表
    time_stamp_list = []
    
    # 构建完整的单词字符串和位置映射
    full_words_str = ''
    position_to_word_idx = {}
    
    # 遍历所有单词，构建完整的单词字符串并建立位置映射
    for idx, word in enumerate(df_words['text']):
        # 清理单词，去除标点和转换为小写
        clean_word = remove_punctuation(word.lower())
        
        # 记录当前单词在完整字符串中的起始位置
        start_pos = len(full_words_str)
        
        # 将清理后的单词添加到完整字符串中
        full_words_str += clean_word
        
        # 为完整字符串中的每个字符建立位置到单词索引的映射
        for pos in range(start_pos, len(full_words_str)):
            position_to_word_idx[pos] = idx
    
    # 初始化当前搜索位置
    current_pos = 0
    
    # 遍历每个句子
    for idx, sentence in df_sentences['Source'].items():
        # 清理句子，去除标点、空格和特殊标记
        clean_sentence = remove_punctuation(sentence.lower()).replace(" ", "")
        
        # 获取清理后句子的长度
        sentence_len = len(clean_sentence)
        
        # 标记是否找到匹配
        match_found = False
        
        # 在完整单词字符串中搜索匹配的句子
        while current_pos <= len(full_words_str) - sentence_len:
            # 检查是否找到完全匹配的句子
            if full_words_str[current_pos:current_pos+sentence_len] == clean_sentence:
                # 获取句子起始和结束单词的索引
                start_word_idx = position_to_word_idx[current_pos]
                end_word_idx = position_to_word_idx[current_pos + sentence_len - 1]
                
                # 将句子的起始和结束时间戳添加到列表中
                time_stamp_list.append((float(df_words['start'][start_word_idx]), float(df_words['end'][end_word_idx])))
                
                # 更新当前搜索位置
                current_pos += sentence_len
                
                # 标记找到匹配
                match_found = True
                break
            
            # 如果未找到匹配，移动搜索位置
            current_pos += 1
            
            # 如果仍未找到匹配，抛出异常并显示差异
            if not match_found:
                print(f"\n⚠️ Warning: No exact match found for sentence: {sentence}")
                show_difference(clean_sentence, full_words_str[current_pos:current_pos+len(clean_sentence)])
                print("\nOriginal sentence:", df_sentences['Source'][idx])
                print(f"\n不匹配的句子: {sentence}")
                print(f"不匹配的字幕: {df_sentences['Translation'][idx]}")
                #raise ValueError("❎ No match found for sentence.")
    
    # 返回时间戳列表
    return time_stamp_list

def align_timestamp(df_text, df_translate, subtitle_output_configs: list, output_dir: str, for_display: bool = True):
    """Align timestamps and add a new timestamp column to df_translate"""
    df_trans_time = df_translate.copy()

    # Assign an ID to each word in df_text['text'] and create a new DataFrame
    words = df_text['text'].str.split(expand=True).stack().reset_index(level=1, drop=True).reset_index()
    words.columns = ['id', 'word']
    words['id'] = words['id'].astype(int)

    # Process timestamps ⏰
    time_stamp_list = get_sentence_timestamps(df_text, df_translate)
    df_trans_time['timestamp'] = time_stamp_list
    df_trans_time['duration'] = df_trans_time['timestamp'].apply(lambda x: x[1] - x[0])

    # Remove gaps 🕳️
    for i in range(len(df_trans_time)-1):
        delta_time = df_trans_time.loc[i+1, 'timestamp'][0] - df_trans_time.loc[i, 'timestamp'][1]
        if 0 < delta_time < 1:
            df_trans_time.at[i, 'timestamp'] = (df_trans_time.loc[i, 'timestamp'][0], df_trans_time.loc[i+1, 'timestamp'][0])

    # Convert start and end timestamps to SRT format
    df_trans_time['timestamp'] = df_trans_time['timestamp'].apply(lambda x: convert_to_srt_format(x[0], x[1]))

    # Polish subtitles: replace punctuation in Translation if for_display
    if for_display:
        df_trans_time['Translation'] = df_trans_time['Translation'].apply(lambda x: re.sub(r'[，。]', ' ', x).strip())

    # Output subtitles 📜
    def generate_subtitle_string(df, columns):
        return ''.join([f"{i+1}\n{row['timestamp']}\n{row[columns[0]].strip()}\n{row[columns[1]].strip() if len(columns) > 1 else ''}\n\n" for i, row in df.iterrows()]).strip()

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for filename, columns in subtitle_output_configs:
            subtitle_str = generate_subtitle_string(df_trans_time, columns)
            with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
                f.write(subtitle_str)
    
    return df_trans_time

# ✨ Beautify the translation
def clean_translation(x):
    """
    清理翻译文本的函数，用于美化和规范化翻译结果

    参数:
    x (str): 输入的翻译文本

    处理逻辑:
    1. 如果输入为空或NaN，返回空字符串
    2. 去除文本开头和结尾的中文句号和逗号
    3. 使用 autocorrect 进行文本格式化和自动纠正

    返回:
    str: 清理和美化后的翻译文本
    """
    if pd.isna(x):
        return ''
    cleaned = str(x).strip('。').strip('，')
    return autocorrect.format(cleaned)


def validate_and_clean_translation_results(cleaned_chunks, translation_results):
    """
    验证并清理翻译结果，确保Source中的单词存在且顺序与cleaned_chunks中text列一致
    
    参数:
    cleaned_chunks (pandas.DataFrame): 清理后的块数据
    translation_results (pandas.DataFrame): 翻译结果数据
    
    返回:
    pandas.DataFrame: 清理后的翻译结果
    """
    if cleaned_chunks is None or translation_results is None:
        print("输入数据不能为空")
        return None
    
    # 合并所有text列的内容为一个大字符串
    all_text = ' '.join(cleaned_chunks['text'].dropna().astype(str))
    
    # 创建一个新的DataFrame来存储清理后的翻译结果
    cleaned_translation_results = translation_results.copy()
    
    def clean_source(source):
        # 将source拆分为单词
        source_words = str(source).split()
        
        # 过滤出存在于all_text中的单词
        valid_words = [word for word in source_words if word in all_text]
        
        # 如果没有有效单词，返回原始source
        if not valid_words:
            return source
        
        # 返回有效单词组成的字符串
        return ' '.join(valid_words)
    
    # 对每一行的Source列进行处理
    cleaned_translation_results['Source'] = cleaned_translation_results['Source'].apply(clean_source)
    
    # 保存清理后的结果
    output_path = 'output/log/cleaned_translation_results.xlsx'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cleaned_translation_results.to_excel(output_path, index=False)
    print(f"已保存清理后的翻译结果到 {output_path}")
    
    return cleaned_translation_results


def align_timestamp_main():
    df_text = pd.read_excel(CLEANED_CHUNKS_FILE)
    df_text['text'] = df_text['text'].str.strip('"').str.strip()
    df_translate = pd.read_excel(TRANSLATION_RESULTS_FOR_SUBTITLES_FILE)
    df_translate['Translation'] = df_translate['Translation'].apply(clean_translation)
    df_translate['Source'] = df_translate['Source'].apply(clean_translation)
    df_translate= validate_and_clean_translation_results(df_text,df_translate)
    align_timestamp(df_text, df_translate, SUBTITLE_OUTPUT_CONFIGS, OUTPUT_DIR)
    console.print(Panel("[bold green]🎉📝 Subtitles generation completed! Please check in the `output` folder 👀[/bold green]"))

    # for audio
    df_translate_for_audio = pd.read_excel(TRANSLATION_RESULTS_REMERGED_FILE) # use remerged file to avoid unmatched lines when dubbing
    df_translate_for_audio['Translation'] = df_translate_for_audio['Translation'].apply(clean_translation)
    
    # 同样处理音频字幕的 Source 列
    df_translate_for_audio = clean_source_column(df_text, df_translate_for_audio)
    
    align_timestamp(df_text, df_translate_for_audio, AUDIO_SUBTITLE_OUTPUT_CONFIGS, AUDIO_OUTPUT_DIR)
    console.print(Panel("[bold green]🎉📝 Audio subtitles generation completed! Please check in the `output/audio` folder 👀[/bold green]"))



if __name__ == '__main__':
    align_timestamp_main()
