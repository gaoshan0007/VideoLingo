import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from st_components.imports_and_utils import ask_gpt
import streamlit as st
from core.config_utils import update_key, load_key
import requests

def page_setting():
    # 使用 session_state 来管理 API 配置的动态变化
    if 'apis_modified' not in st.session_state:
        st.session_state.apis_modified = False

    with st.expander("LLM Configuration", expanded=True):
        # 显示现有的 API 配置列表
        apis = load_key("apis")
        api_names = list(apis.keys())
        
        # 选择当前活跃的 API
        selected_api = st.selectbox("选择 API 配置", options=api_names)
        
        # 添加新的 API 配置按钮
        if st.button("➕ 添加新 API 配置"):
            new_api_name = f"api{len(api_names) + 1}"
            apis[new_api_name] = {
                "key": "",
                "base_url": "",
                "model": ""
            }
            update_key("apis", apis)
            st.session_state.apis_modified = True
            st.rerun()
        
        # 当前选中的 API 配置
        current_api = apis[selected_api]
        
        # API 配置输入
        api_key = st.text_input(f"API_KEY ({selected_api})", value=current_api.get("key", ""))
        if api_key != current_api.get("key", ""):
            apis[selected_api]["key"] = api_key
            update_key("apis", apis)
            st.session_state.apis_modified = True

        selected_base_url = st.text_input(f"BASE_URL ({selected_api})", value=current_api.get("base_url", ""), help="Base URL for API requests")
        if selected_base_url != current_api.get("base_url", ""):
            apis[selected_api]["base_url"] = selected_base_url
            update_key("apis", apis)
            st.session_state.apis_modified = True

        col1, col2 = st.columns([4, 1])
        with col1:
            model = st.text_input(f"MODEL ({selected_api})", value=current_api.get("model", ""))
            if model and model != current_api.get("model", ""):
                apis[selected_api]["model"] = model
                update_key("apis", apis)
                st.session_state.apis_modified = True
        with col2:
            if st.button("📡", key="api"):
                if valid_llm_api(current_api):
                    st.toast("API Key is valid", icon="✅")
                else:
                    st.toast("API Key is invalid", icon="❌")
        
        # 删除 API 配置按钮（如果不是第一个 API）
        if selected_api != "api1" and st.button(f"🗑️ 删除 {selected_api} 配置"):
            del apis[selected_api]
            update_key("apis", apis)
            st.session_state.apis_modified = True
            st.rerun()
    
    # 其余部分保持不变
    with st.expander("Transcription and Subtitle Settings", expanded=True):
        whisper_method_options = ["whisperX 💻", "whisperX ☁️"]
        whisper_method_mapping = {"whisperX 💻": "whisperx", "whisperX ☁️": "whisperxapi"}
        selected_whisper_method_display = st.selectbox("Whisper Method:", options=whisper_method_options, index=whisper_method_options.index("whisperX 💻" if load_key("whisper.method") == "whisperx" else "whisperX ☁️"))
        selected_whisper_method = whisper_method_mapping[selected_whisper_method_display]
        if selected_whisper_method != load_key("whisper.method"):
            update_key("whisper.method", selected_whisper_method)
            
        if selected_whisper_method == "whisperxapi":    
            col1, col2 = st.columns([4, 1])
            with col1:
                replicate_api_token = st.text_input("Replicate API Token", value=load_key("replicate_api_token"), help="Replicate API Token")
                if replicate_api_token != load_key("replicate_api_token"):
                    update_key("replicate_api_token", replicate_api_token)
            with col2:
                if st.button("📡", key="replicate"):
                    if valid_replicate_token(replicate_api_token):
                        st.toast("Replicate API Token is valid", icon="✅")
                    else:
                        st.toast("Replicate API Token is invalid", icon="❌")
            
        col1, col2 = st.columns(2)
        with col1:
            whisper_language_options_dict = {
            "🇺🇸 English": "en",
            "🇨🇳 Chinese": "zh",
            "🇷🇺 Russian": "ru",
            "🇫🇷 French": "fr",
            "🇩🇪 German": "de",
            "🇮🇹 Italian": "it",
            "🇪🇸 Spanish": "es",
            "🇯🇵 Japanese": "ja"
            }
            selected_whisper_language = st.selectbox(
                "Recognition Language:", 
                options=list(whisper_language_options_dict.keys()),
                index=list(whisper_language_options_dict.values()).index(load_key("whisper.language"))
            )
            if whisper_language_options_dict[selected_whisper_language] != load_key("whisper.language"):
                update_key("whisper.language", whisper_language_options_dict[selected_whisper_language])

        with col2:
            target_language = st.text_input("Translation Target Language", value=load_key("target_language") , help="Translation Target Language")
            if target_language != load_key("target_language"):
                update_key("target_language", target_language)

        include_video = st.toggle("Include Video", value=load_key("resolution") != "0x0")

        resolution_options = {
            "1080p": "1920x1080",
            "360p": "640x360"
        }
        selected_resolution = st.selectbox(
            "Video Resolution",
            options=list(resolution_options.keys()),
            index=list(resolution_options.values()).index(load_key("resolution")) if load_key("resolution") != "0x0" else 0,
            disabled=not include_video
        )

        if include_video:
            resolution = resolution_options[selected_resolution]
        else:
            resolution = "0x0"

        if resolution != load_key("resolution"):
            update_key("resolution", resolution)
        
    # 其余部分保持不变
    with st.expander("Dubbing Settings", expanded=False):
        tts_methods = ["openai_tts", "azure_tts", "gpt_sovits", "fish_tts"]
        selected_tts_method = st.selectbox("TTS Method", options=tts_methods, index=tts_methods.index(load_key("tts_method")))
        if selected_tts_method != load_key("tts_method"):
            update_key("tts_method", selected_tts_method)

        if selected_tts_method == "openai_tts":
            oai_voice = st.text_input("OpenAI Voice", value=load_key("openai_tts.voice"))
            if oai_voice != load_key("openai_tts.voice"):
                update_key("openai_tts.voice", oai_voice)

            oai_tts_api_key = st.text_input("OpenAI TTS API Key", value=load_key("openai_tts.api_key"))
            if oai_tts_api_key != load_key("openai_tts.api_key"):
                update_key("openai_tts.api_key", oai_tts_api_key)

            oai_api_base_url = st.text_input("OpenAI TTS API Base URL", value=load_key("openai_tts.base_url"))
            if oai_api_base_url != load_key("openai_tts.base_url"):
                update_key("openai_tts.base_url", oai_api_base_url)

        elif selected_tts_method == "fish_tts":
            fish_tts_api_key = st.text_input("Fish TTS API Key", value=load_key("fish_tts.api_key"))
            if fish_tts_api_key != load_key("fish_tts.api_key"):
                update_key("fish_tts.api_key", fish_tts_api_key)

            fish_tts_character = st.selectbox("Fish TTS Character", options=list(load_key("fish_tts.character_id_dict").keys()), index=list(load_key("fish_tts.character_id_dict").keys()).index(load_key("fish_tts.character")))
            if fish_tts_character != load_key("fish_tts.character"):
                update_key("fish_tts.character", fish_tts_character)

        elif selected_tts_method == "azure_tts":
            azure_key = st.text_input("Azure Key", value=load_key("azure_tts.key"))
            if azure_key != load_key("azure_tts.key"):
                update_key("azure_tts.key", azure_key)

            azure_region = st.text_input("Azure Region", value=load_key("azure_tts.region"))
            if azure_region != load_key("azure_tts.region"):
                update_key("azure_tts.region", azure_region)

            azure_voice = st.text_input("Azure Voice", value=load_key("azure_tts.voice"))
            if azure_voice != load_key("azure_tts.voice"):
                update_key("azure_tts.voice", azure_voice)

        elif selected_tts_method == "gpt_sovits":
            st.info("配置GPT_SoVITS，请参考Github主页")
            sovits_character = st.text_input("SoVITS Character", value=load_key("gpt_sovits.character"))
            if sovits_character != load_key("gpt_sovits.character"):
                update_key("gpt_sovits.character", sovits_character)
            
            refer_mode_options = {1: "模式1：仅用提供的参考音频", 2: "模式2：仅用视频第1条语音做参考", 3: "模式3：使用视频每一条语音做参考"}
            selected_refer_mode = st.selectbox(
                "Refer Mode",
                options=list(refer_mode_options.keys()),
                format_func=lambda x: refer_mode_options[x],
                index=list(refer_mode_options.keys()).index(load_key("gpt_sovits.refer_mode")),
                help="配置GPT-SoVITS的参考音频模式"
            )
            if selected_refer_mode != load_key("gpt_sovits.refer_mode"):
                update_key("gpt_sovits.refer_mode", selected_refer_mode)

        original_volume_options = {"mute": 0, "10%": 0.1}

        selected_original_volume = st.selectbox(
            "Original Volume",
            options=list(original_volume_options.keys()),
            index=list(original_volume_options.values()).index(load_key("original_volume"))
        )
        if original_volume_options[selected_original_volume] != load_key("original_volume"):
            update_key("original_volume", original_volume_options[selected_original_volume])

def valid_llm_api(api_config):
    try:
        response = ask_gpt("This is a test, response 'message':'success' in json format.", 
                           response_json=True, 
                           log_title='None', 
                           api_key=api_config.get('key'), 
                           base_url=api_config.get('base_url'), 
                           model=api_config.get('model'))
        return response.get('message') == 'success'
    except Exception:
        return False

def valid_replicate_token(token):
    url = "https://api.replicate.com/v1/predictions"
    headers = {"Authorization": f"Token {token}"}
    response = requests.get(url, headers=headers)
    return response.status_code == 200
