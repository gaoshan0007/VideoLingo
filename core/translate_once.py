import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.ask_gpt import ask_gpt
from core.prompts_storage import generate_shared_prompt, get_prompt_faithfulness, get_prompt_expressiveness
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich import box
import re

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

def translate_lines(lines, previous_content_prompt, after_cotent_prompt, things_to_note_prompt, summary_prompt, index = 0):
    shared_prompt = generate_shared_prompt(previous_content_prompt, after_cotent_prompt, summary_prompt, things_to_note_prompt)

    
    def valid_faith(response_data):
        # 严格校验返回数据的格式
        if not isinstance(response_data, dict):
            return {"status": "error", "message": "返回数据必须是字典"}
        
        # 检查键是否为连续的字符串数字
        keys = list(response_data.keys())
        if not all(str(i) in keys for i in range(1, len(keys) + 1)):
            return {"status": "error", "message": "键必须是连续的字符串数字，如 '1', '2', '3'"}
        
        if len(lines.split('\n')) != len(response_data):
             return {"status": "error", "message": "长度不匹配"}

        # 检查每个值的格式
        for key, value in response_data.items():
            if not isinstance(value, dict):
                return {"status": "error", "message": f"键 {key} 的值必须是字典"}
            
            if not {"origin", "direct"}.issubset(value.keys()):
                return {"status": "error", "message": f"键 {key} 的值必须包含 'origin' 和 'direct' 两个键"}
            
            if not all(isinstance(v, str) for v in value.values()):
                return {"status": "error", "message": f"键 {key} 的 'origin' 和 'direct' 值必须是字符串"}
        
        return {"status": "success", "message": "Translation completed"}

    def valid_express(response_data):
        # 严格校验返回数据的格式
        if not isinstance(response_data, dict):
            return {"status": "error", "message": "返回数据必须是字典"}
        
        if len(lines.split('\n')) != len(response_data):
             return {"status": "error", "message": "长度不匹配"}

        # 检查键是否为连续的字符串数字
        keys = list(response_data.keys())
        if not all(str(i) in keys for i in range(1, len(keys) + 1)):
            return {"status": "error", "message": "键必须是连续的字符串数字，如 '1', '2', '3'"}
        
        # 检查每个值的格式
        for key, value in response_data.items():
            if not isinstance(value, dict):
                return {"status": "error", "message": f"键 {key} 的值必须是字典"}
            
            # 检查是否包含 'origin', 'direct', 'reflection', 'free' 四个键
            if not {"origin", "direct", "reflection", "free"}.issubset(value.keys()):
                return {"status": "error", "message": f"键 {key} 的值必须包含 'origin', 'direct', 'reflection', 'free' 四个键"}
            
            # 检查所有值是否为字符串
            if not all(isinstance(v, str) for v in value.values()):
                return {"status": "error", "message": f"键 {key} 的所有值必须是字符串"}
        
        return {"status": "success", "message": "Translation completed"}
   


    # Retry translation if the length of the original text and the translated text are not the same, or if the specified key is missing
    def retry_translation(prompt, step_name):
        
        for retry in range(5):
            if step_name == 'faithfulness':
                result = ask_gpt(prompt, response_json=True, valid_def=valid_faith, log_title=f'translate_{step_name}', re_try = retry!=1)
            elif step_name == 'expressiveness':
                result = ask_gpt(prompt, response_json=True, valid_def=valid_express, log_title=f'translate_{step_name}', re_try = retry!=1)
            if len(lines.split('\n')) == len(result):
                return result
            if retry != 1:
                console.print(f'[yellow]⚠️ {step_name.capitalize()} translation of block {index} failed, Retry...[/yellow]')
        raise ValueError(f'[red]❌ {step_name.capitalize()} translation of block {index} failed after 5 retries. Please check `output/gpt_log/error.json` for more details.[/red]')

    ## Step 1: Faithful to the Original Text
    prompt1 = get_prompt_faithfulness(lines, shared_prompt)
    faith_result = retry_translation(prompt1, 'faithfulness')

    for i in faith_result:
        faith_result[i]["direct"] = faith_result[i]["direct"].replace('\n', ' ')

    ## Step 2: Express Smoothly  
    prompt2 = get_prompt_expressiveness(faith_result, lines, shared_prompt)
    express_result = retry_translation(prompt2, 'expressiveness')

    table = Table(title="Translation Results", show_header=False, box=box.ROUNDED)
    table.add_column("Translations", style="bold")
    for i, key in enumerate(express_result):
        table.add_row(f"[cyan]Origin:  {faith_result[key]['origin']}[/cyan]")
        table.add_row(f"[magenta]Direct:  {faith_result[key]['direct']}[/magenta]")
        table.add_row(f"[green]Free:    {express_result[key]['free']}[/green]")
        if i < len(express_result) - 1:
            table.add_row("[yellow]" + "-" * 50 + "[/yellow]")

    console.print(table)

    translate_result = "\n".join([express_result[i]["free"].replace('\n', ' ').strip() for i in express_result])

    if len(lines.split('\n')) != len(translate_result.split('\n')):
        console.print(Panel(f'[red]❌ Translation of block {index} failed, Length Mismatch, Please check `output/gpt_log/translate_expressiveness.json`[/red]'))
        raise ValueError(f'Origin ···{lines}···,\nbut got ···{translate_result}···')

    return translate_result, lines


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
