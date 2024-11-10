import pandas as pd
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from difflib import SequenceMatcher
import re
from core.config_utils import load_key, get_joiner
from rich.panel import Panel
from rich.console import Console
import autocorrect_py as autocorrect
import json

console = Console()

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

def get_sentence_timestamps(df_words, df_sentences):
    time_stamp_list = []
    whisper_language = load_key("whisper.language")
    language = load_key("whisper.detected_language") if whisper_language == 'auto' else whisper_language
    joiner = get_joiner(language)

    for idx, sentence in df_sentences['Source'].items():
        # 特殊处理：单个字母的句子直接返回原文的时间戳
        if len(remove_punctuation(sentence)) <= 1:
            time_stamp_list.append((float(df_words['start'][0]), float(df_words['end'][0])))
            continue

        sentence = remove_punctuation(sentence.lower())
        best_match = {'score': 0, 'start': 0, 'end': 0, 'word_count': 0, 'phrase': ''}
        
        # 更严格的滑动窗口策略
        window_size = max(len(sentence.split()) + 1, 3)  # 减小窗口大小
        
        for start_index in range(len(df_words) - window_size + 1):
            current_phrase = ""
            current_start_time = float(df_words['start'][start_index])
            current_end_time = float(df_words['end'][start_index + window_size - 1])
            
            # 构建窗口内的短语
            for j in range(start_index, start_index + window_size):
                word = remove_punctuation(df_words['text'][j].lower())
                current_phrase += word + joiner
            
            current_phrase = current_phrase.strip()
            
            # 计算相似度，增加对短语长度的惩罚
            similarity = SequenceMatcher(None, sentence, current_phrase).ratio()
            length_penalty = min(1, len(sentence) / len(current_phrase))
            adjusted_similarity = similarity * length_penalty
            
            # 更新最佳匹配
            if adjusted_similarity > best_match['score']:
                best_match = {
                    'score': adjusted_similarity,
                    'start': current_start_time,
                    'end': current_end_time,
                    'word_count': window_size,
                    'phrase': current_phrase
                }
        
        # 提高匹配阈值，减少不准确的匹配
        if best_match['score'] >= 0.8:  
            time_stamp_list.append((best_match['start'], best_match['end']))
            
            console.print(f"✅ 匹配成功: 原句 {repr(sentence)}, 匹配短语 {repr(best_match['phrase'])}, 相似度 {best_match['score']:.2f}")
        else:
            console.print(f"❌ 匹配失败: 原句 {repr(sentence)}, 匹配短语 {repr(best_match['phrase'])}, 相似度 {best_match['score']:.2f}")
            
            # 如果匹配失败，尝试使用最佳匹配的时间戳
            if best_match['score'] > 0:
                time_stamp_list.append((best_match['start'], best_match['end']))
            else:
                # 将 DataFrame 以 JSON 格式写入 log.txt
                with open('output/log/sentences_log.json', 'w', encoding='utf-8') as f:
                    json.dump(df_sentences.to_dict(orient='records'), f, ensure_ascii=False, indent=2)
                raise ValueError(f"❎ 无法匹配句子时间戳：{sentence}。可能是由于背景音乐太大或语言检测不准确。目前无法自动处理，请提交问题报告！")
    
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

    # 更严格地处理时间间隔，防止重叠 🕳️
    for i in range(len(df_trans_time)-1):
        current_end = df_trans_time.loc[i, 'timestamp'][1]
        next_start = df_trans_time.loc[i+1, 'timestamp'][0]
        
        # 如果当前字幕结束时间大于下一个字幕的开始时间，调整时间
        if current_end > next_start:
            # 将当前字幕的结束时间设置为下一个字幕开始时间的前0.1秒
            df_trans_time.at[i, 'timestamp'] = (df_trans_time.loc[i, 'timestamp'][0], next_start - 0.1)
            
            # 如果调整后的结束时间小于开始时间，则设置为开始时间
            if df_trans_time.loc[i, 'timestamp'][1] <= df_trans_time.loc[i, 'timestamp'][0]:
                df_trans_time.at[i, 'timestamp'] = (df_trans_time.loc[i, 'timestamp'][0], df_trans_time.loc[i, 'timestamp'][0] + 0.1)

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

def clean_translation(x):
    if pd.isna(x):
        return ''
    cleaned = str(x).strip('。').strip('，')
    return autocorrect.format(cleaned)

def align_timestamp_main():
    df_text = pd.read_excel('output/log/cleaned_chunks.xlsx')
    df_text['text'] = df_text['text'].str.strip('"').str.strip()
    df_translate = pd.read_excel('output/log/translation_results_for_subtitles.xlsx')
    df_translate['Translation'] = df_translate['Translation'].apply(clean_translation)
    subtitle_output_configs = [ 
        ('src_subtitles.srt', ['Source']),
        ('trans_subtitles.srt', ['Translation']),
        ('bilingual_src_trans_subtitles.srt', ['Source', 'Translation']),
        ('bilingual_trans_src_subtitles.srt', ['Translation', 'Source'])
    ]
    align_timestamp(df_text, df_translate, subtitle_output_configs, 'output')
    console.print("[🎉📝] 字幕生成完成！请在 `output` 文件夹中查看")

    # for audio
    df_translate_for_audio = pd.read_excel('output/log/translation_results.xlsx')
    df_translate_for_audio['Translation'] = df_translate_for_audio['Translation'].apply(clean_translation)
    subtitle_output_configs = [
        ('src_subs_for_audio.srt', ['Source']),
        ('trans_subs_for_audio.srt', ['Translation'])
    ]
    align_timestamp(df_text, df_translate_for_audio, subtitle_output_configs, 'output/audio')
    console.print("[🎉📝] 音频字幕生成完成！请在 `output/audio` 文件夹中查看")
    

if __name__ == '__main__':
    align_timestamp_main()
