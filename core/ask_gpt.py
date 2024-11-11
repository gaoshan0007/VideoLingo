import os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from threading import Lock
import json_repair
import json 
from openai import OpenAI
import time
from requests.exceptions import RequestException
from core.config_utils import load_key

LOG_FOLDER = 'output/gpt_log'
LOCK = Lock()

def save_log(model, prompt, response, log_title = 'default', message = None):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    log_data = {
        "model": model,
        "prompt": prompt,
        "response": response,
        "message": message
    }
    log_file = os.path.join(LOG_FOLDER, f"{log_title}.json")
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    else:
        logs = []
    logs.append(log_data)
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)
        
def check_ask_gpt_history(prompt, model, log_title):
    # check if the prompt has been asked before
    if not os.path.exists(LOG_FOLDER):
        return False
    file_path = os.path.join(LOG_FOLDER, f"{log_title}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item["prompt"] == prompt and item["model"] == model:
                    return item["response"]
    return False

def ask_gpt(prompt, response_json=True, valid_def=None, log_title='default', re_try=False):
    api_set = load_key("api")
    llm_support_json = load_key("llm_support_json")
    with LOCK:
        # 如果 re_try 为 False，则检查历史记录
        if not re_try:
            history_response = check_ask_gpt_history(prompt, api_set["model"], log_title)
            if history_response:
                return history_response
    
    if not api_set["key"]:
        raise ValueError(f"⚠️API_KEY is missing")
    
    messages = [{"role": "user", "content": prompt}]
    
    base_url = api_set["base_url"]
    client = OpenAI(api_key=api_set["key"], base_url=base_url)
    
    # 当 re_try 为 True 时，强制使用 betterModel
    models_to_try = [api_set["betterModel"]] if re_try else [api_set["model"], api_set["betterModel"]]
    
    for current_model in models_to_try:
        response_format = {"type": "json_object"} if response_json and current_model in llm_support_json else None

        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=messages,
                response_format=response_format,
                timeout=150 #! set timeout                
            )
            #print(f"current_model-------------------------{current_model}--------------------------")
            if response_json:
                try:
                    response_data = json_repair.loads(response.choices[0].message.content)
                    
                    # check if the response is valid, otherwise save the log and raise error and retry
                    if valid_def:
                        valid_response = valid_def(response_data)
                        if valid_response['status'] != 'success':
                            save_log(current_model, prompt, response_data, log_title="error", message=valid_response['message'])
                            raise ValueError(f"❎ API response error: {valid_response['message']}")
                        
                    break  # Successfully accessed and parsed, break the loop
                except Exception as e:                    
                    print(f"❎ json_repair parsing failed. Retrying: Attempting to switch to next model... '''{response_data}'''")
                    save_log(current_model, prompt, response_data, log_title="error", message=f"json_repair parsing failed.")
        
                
        except Exception as e:
            # 如果是第一个模型出错，尝试切换到下一个模型
            if current_model == models_to_try[0]:
                print(f"Error with model {current_model}: {e}. Attempting to switch to next model...")
                continue
            else:
                # 如果最后一个模型也失败，则抛出异常
                raise Exception(f"Failed after trying all models: {e}")

    with LOCK:
        if log_title != 'None':
            save_log(current_model, prompt, response_data, log_title=log_title)

    return response_data


if __name__ == '__main__':
    print(ask_gpt('hi there hey response in json format, just return 200.' , response_json=True, log_title=None))
