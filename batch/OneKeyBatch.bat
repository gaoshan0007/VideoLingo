
cd /d %~dp0..

set HTTP_PROXY="http://127.0.0.1:4780"
set HTTPS_PROXY="http://127.0.0.1:4780"


if exist runtime (
    echo Using runtime folder...
    runtime\python.exe batch\utils\batch_processor.py
) else (
    echo Runtime folder not found. Using conda environment...
    call conda activate videolingo
    python batch\utils\batch_processor.py
    call conda deactivate
)

pause
