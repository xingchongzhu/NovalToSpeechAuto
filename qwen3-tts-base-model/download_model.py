from huggingface_hub import snapshot_download

# 下载模型到当前目录
snapshot_download(repo_id="Qwen/Qwen3-TTS-12Hz-1.7B-Base", local_dir="./")
