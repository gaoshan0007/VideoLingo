import pandas as pd
import datetime
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
from core.ask_gpt import ask_gpt
from core.prompts_storage import get_subtitle_trim_prompt
from rich import print as rprint
from rich.panel import Panel
from rich.console import Console
from core.config_utils import load_key  

console = Console()
speed_factor = load_key("speed_factor")

def check_len_then_trim(text, duration):
    multiplier = speed_factor['normal'] * speed_factor['max']
    # Define speech speed: characters/second or words/second, punctuation/second
    speed_zh_ja = 4 * multiplier  # Chinese and Japanese characters per second
    speed_en_and_others = 5 * multiplier   # Words per second for English and other languages
    speed_punctuation = 4 * multiplier   # Punctuation marks per second
    
    # Count characters, words, and punctuation for each language
    chinese_japanese_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf\uf900-\ufaff\uff66-\uff9f]', text))
    en_and_others_words = len(re.findall(r'\b[a-zA-ZàâçéèêëîïôûùüÿñæœáéíóúüñÁÉÍÓÚÜÑàèéìíîòóùúÀÈÉÌÍÎÒÓÙÚäöüßÄÖÜа-яА-Я]+\b', text))
    punctuation_count = len(re.findall(r'[,.!?;:，。！？；：](?=.)', text))
    
    # Estimate duration for each language part and punctuation
    chinese_japanese_duration = chinese_japanese_chars / speed_zh_ja
    en_and_others_duration = en_and_others_words / speed_en_and_others
    punctuation_duration = punctuation_count / speed_punctuation
    
    # Total estimated duration
    estimated_duration = chinese_japanese_duration + en_and_others_duration + punctuation_duration
    
    console.print(f"Subtitle text: {text}, "
                  f"Subtitle info: Chinese/Japanese chars: {chinese_japanese_chars}, "
                  f"English and other language words: {en_and_others_words}, "
                  f"Punctuation marks: {punctuation_count}, "
                  f"[bold green]Estimated reading duration: {estimated_duration:.2f} seconds[/bold green]")

    if estimated_duration > duration:
        rprint(Panel(f"Estimated reading duration {estimated_duration:.2f} seconds exceeds given duration {duration:.2f} seconds, shortening...", title="Processing", border_style="yellow"))
        original_text = text
        prompt = get_subtitle_trim_prompt(text, duration)
        def valid_trim(response):
            # 严格校验 JSON 结构
            if not isinstance(response, dict):
                return {'status': 'error', 'message': '返回必须是一个字典'}
            
            if 'analysis' not in response or not isinstance(response['analysis'], str) or not response['analysis'].strip():
                return {'status': 'error', 'message': '必须包含非空的 analysis 字段'}
            
            if 'trans_text_processed' not in response or not isinstance(response['trans_text_processed'], str) or not response['trans_text_processed'].strip():
                return {'status': 'error', 'message': '必须包含非空的 trans_text_processed 字段'}
            
            return {'status': 'success', 'message': ''}
        try:    
            response = ask_gpt(prompt, response_json=True, log_title='subtitle_trim', valid_def=valid_trim)
            shortened_text = response['trans_text_processed']
        except Exception:
            rprint("[bold red]🚫 AI refused to answer due to sensitivity, so manually remove punctuation[/bold red]")
            shortened_text = re.sub(r'[,.!?;:，。！？；：]', ' ', text).strip()
        rprint(Panel(f"Subtitle before shortening: {original_text}\nSubtitle after shortening: {shortened_text}", title="Subtitle Shortening Result", border_style="green"))
        return shortened_text
    else:
        return text

# 其余代码保持不变
def pre_process_srt(df):
    """
    对字幕进行预处理，删除开始时间异常的字幕
    
    参数：
    - df: 包含字幕信息的 DataFrame
    
    功能：
    1. 删除开始时间在结束时间之后的数据
    2. 删除持续时间大于20秒的数据
    3. 比较相邻字幕的开始时间
    4. 如果某个字幕的开始时间与前后字幕开始时间的差值大于10秒，则删除该字幕
    
    返回：
    - 处理后的 DataFrame
    """
    # 如果字幕数量少于3，无需处理
    if len(df) < 3:
        return df
    
    # 创建一个布尔掩码，用于标记需要保留的字幕
    mask = pd.Series([True] * len(df), index=df.index)
    
    for i in range(len(df)):
        # 将字符串时间转换为 datetime.time 对象
        current_start_time = datetime.datetime.strptime(df.loc[i, 'start_time'], '%H:%M:%S.%f').time()
        current_end_time = datetime.datetime.strptime(df.loc[i, 'end_time'], '%H:%M:%S.%f').time()
        
        # 使用 datetime.datetime.combine 将日期和时间组合
        current_start_datetime = datetime.datetime.combine(datetime.date.today(), current_start_time)
        current_end_datetime = datetime.datetime.combine(datetime.date.today(), current_end_time)
        
        # 删除开始时间在结束时间之后的数据
        if df.loc[i, 'duration'] < 0:
            rprint(f"[bold yellow]删除第 {df.loc[i, 'number']} 个字幕，开始时间在结束时间之后[/bold yellow]")
            mask[i] = False
            continue
        
        # 删除持续时间大于20秒的数据
        if df.loc[i, 'duration'] > 20:
            rprint(f"[bold yellow]删除第 {df.loc[i, 'number']} 个字幕，持续时间超过20秒[/bold yellow]")
            mask[i] = False
            continue
        
        # 对于第一个和最后一个字幕，只比较一侧
        if i == 0:
            next_start_time = datetime.datetime.strptime(df.loc[i+1, 'start_time'], '%H:%M:%S.%f').time()
            next_start_datetime = datetime.datetime.combine(datetime.date.today(), next_start_time)
            
            # 如果当前字幕的开始时间比下一个字幕的开始时间大10秒
            if (current_start_datetime - next_start_datetime).total_seconds() > 10:
                rprint(f"[bold yellow]删除第 {df.loc[i, 'number']} 个字幕，开始时间异常[/bold yellow]")
                mask[i] = False
                continue
        
        elif i == len(df) - 1:
            prev_start_time = datetime.datetime.strptime(df.loc[i-1, 'start_time'], '%H:%M:%S.%f').time()
            prev_start_datetime = datetime.datetime.combine(datetime.date.today(), prev_start_time)
            
            # 如果当前字幕的开始时间比前一个字幕的开始时间大10秒
            if (current_start_datetime - prev_start_datetime).total_seconds() > 10:
                rprint(f"[bold yellow]删除第 {df.loc[i, 'number']} 个字幕，开始时间异常[/bold yellow]")
                mask[i] = False
                continue
        
        else:
            prev_start_time = datetime.datetime.strptime(df.loc[i-1, 'start_time'], '%H:%M:%S.%f').time()
            next_start_time = datetime.datetime.strptime(df.loc[i+1, 'start_time'], '%H:%M:%S.%f').time()
            
            prev_start_datetime = datetime.datetime.combine(datetime.date.today(), prev_start_time)
            next_start_datetime = datetime.datetime.combine(datetime.date.today(), next_start_time)
            
            # 如果当前字幕的开始时间比前一个和下一个字幕的开始时间都大10秒
            if (current_start_datetime - prev_start_datetime).total_seconds() > 10 and (current_start_datetime - next_start_datetime).total_seconds() > 10:
                rprint(f"[bold yellow]删除第 {df.loc[i, 'number']} 个字幕，开始时间异常[/bold yellow]")
                mask[i] = False
                continue
    
    # 根据掩码过滤 DataFrame
    return df[mask].reset_index(drop=True)

def process_srt():
    """
    处理字幕文件，生成音频任务
    
    主要功能：
    1. 读取翻译后的字幕文件和原始字幕文件
    2. 解析字幕文件，提取每个字幕块的信息
    3. 处理字幕文本，去除括号和特殊字符
    4. 合并过短的字幕，确保每个字幕的最小持续时间
    5. 检查并修剪字幕长度，确保可以在给定时间内朗读
    
    返回：
    - pandas DataFrame，包含处理后的字幕信息
    """
    # 设置输出目录和文件路径
    output_dir = 'output/audio'
    trans_subs = os.path.join(output_dir, 'trans_subs_for_audio.srt')
    src_file_path = os.path.join(output_dir, 'src_subs_for_audio.srt')
    
    # 读取翻译后的字幕文件
    with open(trans_subs, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # 读取原始字幕文件
    with open(src_file_path, 'r', encoding='utf-8') as src_file:
        src_content = src_file.read()
    
    subtitles = []
    src_subtitles = {}
    
    # 解析原始字幕文件，建立原始文本映射
    for block in src_content.strip().split('\n\n'):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) < 3:
            continue
        
        number = int(lines[0])
        src_text = ' '.join(lines[2:])
        src_subtitles[number] = src_text
    
    # 解析翻译后的字幕文件
    for block in content.strip().split('\n\n'):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) < 3:
            continue
        
        try:
            # 提取字幕块的序号、时间戳和文本
            number = int(lines[0])
            start_time, end_time = lines[1].split(' --> ')
            start_time = datetime.datetime.strptime(start_time, '%H:%M:%S,%f').time()
            end_time = datetime.datetime.strptime(end_time, '%H:%M:%S,%f').time()
            
            # 计算字幕持续时间
            duration = (datetime.datetime.combine(datetime.date.today(), end_time) - 
                        datetime.datetime.combine(datetime.date.today(), start_time)).total_seconds()
            
            # 处理字幕文本，去除括号和特殊字符
            text = ' '.join(lines[2:])
            text = re.sub(r'\([^)]*\)', '', text).strip()
            text = re.sub(r'（[^）]*）', '', text).strip()
            text = text.replace('-', '')

            # 获取原始文本
            origin = src_subtitles.get(number, '')

        except ValueError as e:
            # 处理解析错误的字幕块
            rprint(Panel(f"Unable to parse subtitle block '{block}', error: {str(e)}, skipping this subtitle block.", title="Error", border_style="red"))
            continue
        
        # 保存处理后的字幕信息
        subtitles.append({
            'number': number,
            'start_time': start_time.strftime('%H:%M:%S.%f')[:-3],
            'end_time': end_time.strftime('%H:%M:%S.%f')[:-3],
            'duration': duration,
            'text': text,
            'origin': origin
        })
    
    # 转换为 DataFrame
    df = pd.DataFrame(subtitles)
    
    df = pre_process_srt(df)
    # 处理过短的字幕
    i = 0
    MIN_SUBTITLE_DURATION = load_key("min_subtitle_duration")
    while i < len(df):
        if df.loc[i, 'duration'] < MIN_SUBTITLE_DURATION:
            # 如果当前字幕和下一个字幕间隔太短，则合并
            if i < len(df) - 1:
                next_start_datetime = datetime.datetime.strptime(df.loc[i+1, 'start_time'], '%H:%M:%S.%f')
                current_start_datetime = datetime.datetime.strptime(df.loc[i, 'start_time'], '%H:%M:%S.%f')
                
                if (next_start_datetime - current_start_datetime).total_seconds() < MIN_SUBTITLE_DURATION:
                    rprint(f"[bold yellow]Merging subtitles {i+1} and {i+2} -- duration: {df.loc[i, 'duration']}[/bold yellow]")
                    df.loc[i, 'text'] += ' ' + df.loc[i+1, 'text']
                    df.loc[i, 'origin'] += ' ' + df.loc[i+1, 'origin']
                    df.loc[i, 'end_time'] = df.loc[i+1, 'end_time']
                    df.loc[i, 'duration'] = (datetime.datetime.strptime(df.loc[i, 'end_time'], '%H:%M:%S.%f') - 
                                            datetime.datetime.strptime(df.loc[i, 'start_time'], '%H:%M:%S.%f')).total_seconds()
                    df = df.drop(i+1).reset_index(drop=True)
                    continue

            # 对于过短的字幕，尝试延长持续时间
            if i < len(df) - 1:  # 不是最后一个字幕
                rprint(f"[bold blue]Extending subtitle {i+1} duration to {MIN_SUBTITLE_DURATION} seconds[/bold blue]")
                start_time = datetime.datetime.strptime(df.loc[i, 'start_time'], '%H:%M:%S.%f').time()
                new_end_time = (datetime.datetime.combine(datetime.date.today(), start_time) + 
                                datetime.timedelta(seconds=MIN_SUBTITLE_DURATION)).time()
                df.loc[i, 'end_time'] = new_end_time.strftime('%H:%M:%S.%f')[:-3]
                df.loc[i, 'duration'] = MIN_SUBTITLE_DURATION
            else:
                # 最后一个字幕不延长
                rprint(f"[bold red]The last subtitle {i+1} duration is less than {MIN_SUBTITLE_DURATION} seconds, but not extending[/bold red]")
            i += 1
        else:
            i += 1
    
    # 检查并修剪字幕长度，执行两次以确保字幕长度在限制范围内
    for _ in range(2):
        df['text'] = df.apply(lambda x: check_len_then_trim(x['text'], x['duration']), axis=1)

    # 最后预处理字幕，删除开始时间异常的字幕
    df = pre_process_srt(df)

    return df

def gen_audio_task_main():
    output_dir = 'output/audio'
    tasks_file = os.path.join(output_dir, 'sovits_tasks.xlsx')
    
    if os.path.exists(tasks_file):
        rprint(Panel(f"{tasks_file} already exists, skip.", title="Info", border_style="blue"))
    else:
        df = process_srt()
        console.print(df)
        df.to_excel(tasks_file, index=False)

        rprint(Panel(f"Successfully generated {tasks_file}", title="Success", border_style="green"))

if __name__ == '__main__':
    gen_audio_task_main()
