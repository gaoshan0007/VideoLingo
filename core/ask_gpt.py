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

def ask_gpt(prompt, response_json=True, valid_def=None, log_title='default', re_try=False, **kwargs):
    # 获取所有 API 配置
    apis = load_key("apis")
    llm_support_json = load_key("llm_support_json")
    
    with LOCK:
        # 如果 re_try 为 False，则检查历史记录
        if not re_try:
            # 使用第一个 API 的模型检查历史记录
            first_api = apis.get("api1", {})
            history_response = check_ask_gpt_history(prompt, first_api.get("model", ""), log_title)
            if history_response:
                return history_response
    
    # 如果没有 API 配置，抛出异常
    if not apis:
        raise ValueError("⚠️No API configurations found")
    
    messages = [{"role": "user", "content": prompt}]
    
    # 存储最后一次的异常，以便在所有 API 都失败时抛出
    last_exception = None
    
    # 遍历所有 API 配置
    for api_name, api_config in apis.items():
        # 如果 API 配置不完整，跳过
        if not api_config.get("key") or not api_config.get("base_url") or not api_config.get("model"):
            print(f"Skipping incomplete API configuration: {api_name}")
            continue
        
        try:
            # 使用当前 API 配置
            client = OpenAI(
                api_key=api_config.get("key"), 
                base_url=api_config.get("base_url")
            )
            
            # 确定是否使用 JSON 响应格式
            response_format = {"type": "json_object"} if response_json and api_config.get("model") in llm_support_json else None
            
            # 尝试获取响应
            response = client.chat.completions.create(
                model=api_config.get("model"),
                messages=messages,
                response_format=response_format,
                timeout=150
            )
            
            # 解析响应
            if response_json:
                try:
                    response_data = json_repair.loads(response.choices[0].message.content)
                    
                    # 如果定义了验证函数，进行验证
                    if valid_def:
                        valid_response = valid_def(response_data)
                        if valid_response['status'] != 'success':
                            save_log(
                                api_config.get("model"), 
                                prompt, 
                                response_data, 
                                log_title="error", 
                                message=valid_response['message']
                            )
                            # 如果验证失败，继续尝试下一个 API
                            continue
                    
                    # 成功获取并验证响应，保存日志并返回
                    with LOCK:
                        if log_title != 'None':
                            save_log(
                                api_config.get("model"), 
                                prompt, 
                                response_data, 
                                log_title=log_title
                            )
                    
                    return response_data
                
                except Exception as e:
                    # JSON 解析或验证失败
                    print(f"❎ Error parsing response from {api_name}: {e}")
                    save_log(
                        api_config.get("model"), 
                        prompt, 
                        str(e), 
                        log_title="error", 
                        message="JSON parsing or validation failed"
                    )
                    last_exception = e
                    continue
        
        except Exception as e:
            # API 调用失败
            print(f"❎ Error with API {api_name}: {e}")
            last_exception = e
            continue
    
    # 如果所有 API 都失败，抛出最后一个异常
    if last_exception:
        raise Exception(f"Failed after trying all API configurations: {last_exception}")
    
    # 如果没有任何可用的 API 配置
    raise ValueError("No valid API configurations found")


if __name__ == '__main__':
    print(ask_gpt('hi there hey response in json format, just return 200.' , response_json=True, log_title=None))
