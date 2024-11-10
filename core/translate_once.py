import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.ask_gpt import ask_gpt
from core.prompts_storage import generate_shared_prompt, get_prompt_faithfulness, get_prompt_expressiveness
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich import box
import re
import json
import traceback

console = Console()

def valid_translate_result(result: dict, required_keys: list, required_sub_keys: list):
    # Check for the required key
    if not all(key in result for key in required_keys):
        return {"status": "error", "message": f"Missing required key(s): {', '.join(set(required_keys) - set(result.keys()))}"}
    
    # Check for required sub-keys in all items
    for key in result:
        if not all(sub_key in result[key] for sub_key in required_sub_keys):
            return {"status": "error", "message": f"Missing required sub-key(s) in item {key}: {', '.join(set(required_sub_keys) - set(result[key].keys()))}"}

    return {"status": "success", "message": "Translation completed"}

def log_translation_error(prompt, error_msg, step_name, index):
    """记录翻译错误到日志文件"""
    error_log_dir = 'output/gpt_log'
    os.makedirs(error_log_dir, exist_ok=True)
    error_log_path = os.path.join(error_log_dir, 'error.json')
    
    error_data = {
        'timestamp': os.path.getctime(error_log_path) if os.path.exists(error_log_path) else None,
        'step': step_name,
        'block_index': index,
        'error_message': error_msg,
        'prompt': prompt
    }
    
    with open(error_log_path, 'w', encoding='utf-8') as f:
        json.dump(error_data, f, ensure_ascii=False, indent=2)

def translate_lines(lines, previous_content_prompt, after_cotent_prompt, things_to_note_prompt, summary_prompt, index = 0):
    # 如果输入为空，直接返回空翻译
    if not lines or lines.strip() == '':
        console.print(f"[yellow]⚠️ 跳过空白内容块 {index}[/yellow]")
        return '', lines

    try:
        shared_prompt = generate_shared_prompt(previous_content_prompt, after_cotent_prompt, summary_prompt, things_to_note_prompt)

        # 改进的重试翻译机制
        def retry_translation(prompt, step_name):
            def valid_faith(response_data):
                return valid_translate_result(response_data, ['1'], ['direct'])
            def valid_express(response_data):
                return valid_translate_result(response_data, ['1'], ['free'])
            
            max_retries = 3
            
            for retry in range(max_retries):
                try:
                    if step_name == 'faithfulness':
                        result = ask_gpt(prompt, response_json=True, valid_def=valid_faith, log_title=f'translate_{step_name}')
                    elif step_name == 'expressiveness':
                        result = ask_gpt(prompt, response_json=True, valid_def=valid_express, log_title=f'translate_{step_name}')
                    
                    # 检查翻译结果的行数
                    if len(lines.split('\n')) == len(result):
                        return result
                    
                    console.print(f'[yellow]⚠️ {step_name.capitalize()} translation of block {index} failed, line count mismatch. Retry {retry+1}...[/yellow]')
                
                except Exception as e:
                    error_msg = f"Translation error: {str(e)}\n{traceback.format_exc()}"
                    console.print(f'[red]❌ {step_name.capitalize()} translation error: {error_msg}[/red]')
                    log_translation_error(prompt, error_msg, step_name, index)
            
            # 如果所有重试都失败，返回空结果
            console.print(f'[red]❌ {step_name.capitalize()} translation of block {index} failed after {max_retries} retries. Returning blank translation.[/red]')
            return {str(i+1): {'origin': line, 'direct': '', 'free': ''} for i, line in enumerate(lines.split('\n'))}

        ## Step 1: Faithful to the Original Text
        prompt1 = get_prompt_faithfulness(lines, shared_prompt)
        faith_result = retry_translation(prompt1, 'faithfulness')

        for i in faith_result:
            faith_result[i]["direct"] = faith_result[i]["direct"].replace('\n', ' ')

        ## Step 2: Express Smoothly  
        prompt2 = get_prompt_expressiveness(faith_result, lines, shared_prompt)
        express_result = retry_translation(prompt2, 'expressiveness')

        translate_result = "\n".join([express_result[i]["free"].replace('\n', ' ').strip() for i in express_result])

        # 如果翻译结果为空，返回原文
        if not translate_result.strip():
            console.print(f'[yellow]⚠️ Translation of block {index} is blank. Returning original text.[/yellow]')
            return lines, lines

        return translate_result, lines

    except Exception as e:
        # 捕获任何未预料的异常
        error_msg = f"Unexpected error in translation: {str(e)}\n{traceback.format_exc()}"
        console.print(f'[red]❌ Unexpected translation error for block {index}: {error_msg}[/red]')
        log_translation_error('', error_msg, 'unexpected', index)
        
        # 返回原文
        console.print(f'[yellow]⚠️ Returning original text for block {index}.[/yellow]')
        return lines, lines


if __name__ == '__main__':
    # test e.g.
    lines = '''All of you know Andrew Ng as a famous computer science professor at Stanford.
He was really early on in the development of neural networks with GPUs.
Of course, a creator of Coursera and popular courses like deeplearning.ai.
Also the founder and creator and early lead of Google Brain.'''
    previous_content_prompt = None
    after_cotent_prompt = None
    things_to_note_prompt = None
    summary_prompt = None
    translate_lines(lines, previous_content_prompt, after_cotent_prompt, things_to_note_prompt, summary_prompt)
