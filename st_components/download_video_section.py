import streamlit as st
import os, sys, shutil
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config_utils import load_key
from core.step1_ytdlp import download_video_ytdlp, find_video_files
from time import sleep
import re
import subprocess

def download_video_section():
    st.header("Download or Upload Video")
    with st.container(border=True):
        try:
            video_file = find_video_files()
            st.video(video_file)
            if st.button("Delete and Reselect", key="delete_video_button"):
                os.remove(video_file)
                if os.path.exists("output"):
                    shutil.rmtree("output")
                sleep(1)
                st.rerun()
            return True
        except:
            col1, col2 = st.columns([3, 1])
            with col1:
                # 添加默认的 YouTube URL
                default_url = load_key("default_youtube_url")
                url = st.text_input("Enter YouTube link:", value=default_url)
            with col2:
                resolution_dict = {
                    "360p": "360",
                    "1080p": "1080",
                    "Best": "best"
                }
                YTB_RESOLUTION = load_key("ytb_resolution")
                resolution_options = list(resolution_dict.keys())
                default_index = list(resolution_dict.values()).index(YTB_RESOLUTION) if YTB_RESOLUTION in resolution_dict.values() else 0
                resolution_display = st.selectbox("Resolution", options=resolution_options, index=default_index)
                resolution = resolution_dict[resolution_display]
            if st.button("Download Video", key="download_button", use_container_width=True):
                if url:
                    with st.spinner("Downloading video..."):
                        download_video_ytdlp(url, resolution=resolution)
                    st.rerun()

            uploaded_file = st.file_uploader("Or upload video", type=load_key("allowed_video_formats") + load_key("allowed_audio_formats"))
            if uploaded_file:
                #delte file in output
                if os.path.exists("output"):
                    shutil.rmtree("output")
                os.makedirs("output", exist_ok=True)
                # Normalize filename and convert extension to lowercase
                original_name = uploaded_file.name.replace(' ', '_')
                name, ext = os.path.splitext(original_name)
                normalized_name = re.sub(r'[^\w\-_\.]', '', name) + ext.lower()
                # Save uploaded video with normalized name
                with open(os.path.join("output", normalized_name), "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Convert audio to video if it's an audio file
                if normalized_name.split('.')[-1] in load_key("allowed_audio_formats"):
                    convert_audio_to_video(os.path.join("output", normalized_name))
                st.rerun()
            else:
                return False

def convert_audio_to_video(audio_file: str) -> str:
    output_video = 'output/black_screen.mp4'
    if not os.path.exists(output_video):
        print(f"🎵➡️🎬 Converting audio to video with FFmpeg ......")
        ffmpeg_cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=640x360', '-i', audio_file, '-shortest', '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', output_video]
        try:
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            print(f"🎵➡️🎬 Converted <{audio_file}> to <{output_video}> with FFmpeg\n")
            # delete audio file
            os.remove(audio_file)
        except subprocess.CalledProcessError as e:
            raise(f"❌ Failed to convert <{audio_file}> to <{output_video}>. Error: {e.stderr}")
    return output_video
