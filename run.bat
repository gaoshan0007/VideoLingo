@echo off
cd /d %~dp0

$env:HTTP_PROXY="http://127.0.0.1:4780"
$env:HTTPS_PROXY="http://127.0.0.1:4780"

if exist runtime (
    echo Using runtime folder...
    runtime\python.exe -m streamlit run st.py
) else (
    echo Runtime folder not found. Using conda environment...
    call activate videolingo
    python -m streamlit run st.py
    call deactivate
)

pause