cd..
$env:HTTP_PROXY="http://127.0.0.1:4780"
$env:HTTPS_PROXY="http://127.0.0.1:4780"
conda activate videolingo
python batch\utils\batch_processor.py