# Fish Speech 本地测试

> 独立测试目录，不影响主项目。评估 Fish Speech 的音质和声音克隆效果。

## 快速开始

```bash
cd fish-speech-test

# 方式 1: pip 安装 (Mac Apple Silicon / CPU 模式)
bash setup.sh --pip
bash start_server.sh

# 方式 2: Docker (NVIDIA GPU)
bash setup.sh --docker

# 方式 3: Docker CPU 模式 (Mac)
bash setup.sh --docker-cpu
```

## 测试命令

```bash
# 列出可用声音
python test_fish_speech.py --list

# 搜索声音
python test_fish_speech.py --search "云希"

# 测试单个声音克隆
python test_fish_speech.py --voice "云希-全能配音,全网最热"

# 自定义合成文本
python test_fish_speech.py --voice "云野-情感,磁性" \
  --text "话说那蜀山之上，剑气纵横，一道白光划破天际。"

# 与 Qwen3-TTS 对比（生成同名文件到 output/）
python test_fish_speech.py --compare "麦克-纪录片之王,麦克阿瑟"

# 批量测试
python test_fish_speech.py --batch "云希,云野,云夏,云墨"

# 指定 API 地址
python test_fish_speech.py --api-url http://192.168.1.100:8080 \
  --voice "云希-全能配音,全网最热"
```

## 目录结构

```
fish-speech-test/
├── README.md
├── setup.sh              # 环境安装脚本
├── start_server.sh       # 服务启动脚本（pip 模式）
├── compose.yml           # Docker Compose (GPU)
├── compose.cpu.yml       # Docker Compose (CPU/Mac)
├── test_fish_speech.py   # 测试脚本
├── checkpoints/          # 模型权重（.gitignore）
├── output/               # 生成的测试音频（.gitignore）
└── .venv-fish/           # Python 虚拟环境（.gitignore）
```

## 注意事项

- **许可证**: Fish Speech 使用 Fish Audio Research License，个人非商用免费
- **不替换主项目**: 此目录是独立的测试环境，不影响 `audio_processing_module.py` 中的 Qwen3-TTS
- **macOS 限制**: CPU 模式推理速度较慢，仅用于效果评估
- **GPU 加速**: 需要 NVIDIA GPU + Docker 才能获得正常推理速度
