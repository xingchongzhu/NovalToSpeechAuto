# 小说有声书批量生成系统

## 项目概述

本项目用于把小说章节剧本 JSON 合成为可直接交付的平台音频。当前主流程以 `Qwen3-TTS` 生成人声，结合音效、场景级 `soundscape` 背景音和自动混音，批量输出整章有声内容。

当前默认输出平台为 `ximalaya`，会在整章正文生成完成后自动拼接固定片头片尾，并导出为平台要求的 MP3 文件。

当前在制小说：《蜀山剑侠传》。

## 项目结构

```text
novel_tool/
├── novel_scripts/                         # 按小说名组织的章节 JSON 剧本
│   └── 蜀山剑侠传_json/
├── novel_scripts_raw/                     # 小说原始 TXT 文稿及 JSON 转换稿
│   └── 蜀山剑侠传/
├── character_voice_tables/                # 每部小说的正式角色配音表
│   └── 蜀山剑侠传角色配音表.md
├── scripts/
│   ├── audio_processing_module.py        # 核心音频处理与合成逻辑
│   ├── novel_batch_executor.py           # Python 批量执行入口
│   ├── novel_batch_manager.sh            # Shell 批处理管理脚本
│   ├── organize_audio_files.py           # 最终音频整理（复制到 小说音频/）
│   ├── audio_quality_checker.py          # 音频质量检查
│   ├── polyphone_processor.py            # 中文多音字处理
│   ├── woosh_generate_audio.py           # Woosh 音效生成引擎
│   ├── stable_audio3_background_generate_audio.py  # Stable Audio 3 背景音引擎
│   └── cleanup_final_audio.sh            # 清理最终合成音频（保留配音/音效中间产物）
├── output/                               # 输出目录（自动生成）
│   └── {小说名}/
│       ├── 片头片尾/                      # 固定片头片尾缓存
│       └── {章节名}/
│           ├── 配音/                      # 逐句人声 TTS 中间产物
│           ├── 音效/                      # 逐句音效中间产物
│           ├── 混音/                      # 单句混音中间产物
│           ├── 背景音/                    # 场景级背景音
│           └── stream_tmp/               # 流式 TTS 临时文件
└── README.md
```

## 核心功能

- `Qwen3-TTS` 人声合成，支持多角色配音（主引擎），备选 `fish-speech` HTTP API
- `woosh` / `stable-audio-3` 音效与背景音引擎切换
- 使用顶层 `soundscape.scene_layers` 生成场景级连续背景音
- 支持 `overlay` / `insert` 音效处理模式，当前剧本规范默认使用 `overlay`
- 按章节批量生成整章音频
- 按平台规则输出，当前内置 `default` 与 `ximalaya`
- 为每部小说缓存固定片头片尾，后续章节直接复用
- 配音与音效中间产物持久化为子目录，支持断点续传和重新合成
- `cleanup_final_audio.sh` 清理脚本：仅删除最终合成音频（.mp3 和 chunk_title），保留配音/音效/混音等中间产物

## 当前输出平台

### `ximalaya`

当前默认平台为 `ximalaya`，主要规则如下：

- 输出格式：`mp3`
- 采样率：`44100Hz`
- 码率：`192k`
- 声道：`2` 声道
- 自动拼接固定片头片尾
- 自动检查章节总时长是否落在建议区间内
- 自动压缩超长静音片段，避免大段空白

平台默认值定义在 `脚本/audio_processing_module.py` 的 `PLATFORM_PROFILES` 中。

## 剧本 JSON 结构

当前剧本结构已经更新，顶层至少包含这些字段：

```json
{
  "project": "蜀山剑侠传有声小说自动生成",
  "chapter": "第一回-月夜棹孤舟_巫峡啼猿登栈道_天涯逢知己_移家结伴隐名山",
  "片头": {
    "novel_name": "蜀山剑侠传",
    "author": "还珠楼主",
    "speaker": "AI合成",
    "role_voice": "云健-中年男性磁性声音"
  },
  "roles_definition": {},
  "data": [],
  "soundscape": {
    "scene_layers": []
  }
}
```

### 顶层字段说明

- `project`：项目名称
- `chapter`：章节名称
- `片头`：平台片头片尾使用的小说级固定元信息
- `roles_definition`：该章涉及角色的统一配音定义
- `data`：逐片段剧本数据
- `soundscape`：场景级背景音配置

### `片头` 字段说明

`片头` 用于生成并缓存每部小说固定片头片尾，当前支持：

```json
"片头": {
  "novel_name": "剑来",
  "author": "烽火戏诸侯",
  "speaker": "AI合成",
  "role_voice": "云健-中年男性磁性声音"
}
```

说明：

- `novel_name`：小说名，整部小说所有章节保持一致
- `author`：作者名，整部小说所有章节保持一致
- `speaker`：演播展示文案，当前项目通常写 `AI合成`
- `role_voice`：片头片尾播报音色；会优先用于固定片头片尾的合成

### `roles_definition`

`roles_definition` 中的角色参数是正文配音的统一来源。同一角色在整部小说中应保持：

- `role_voice` 一致
- `pitch` 一致
- `volume` 一致
- `speed` 一致

### `data`

`data` 为实际播报片段数组，每项包含：

- `id`
- `role`
- `api.voice`
- `api.effects`
- `mix`

其中：

- `id=0` 通常为章节标题
- 角色切换时分段
- 同一角色连续内容应尽量合并
- 背景音不再推荐逐句写 `api.bgm`，优先使用顶层 `soundscape`

### `soundscape`

当前推荐使用：

```json
"soundscape": {
  "scene_layers": [
    {
      "name": "街巷人物交锋",
      "start_line": 5,
      "end_line": 25,
      "prompt": "very subtle low volume cinematic background ambience, ...",
      "volume": "-22%",
      "fade_in": 2,
      "fade_out": 2,
      "target_dbfs": -30,
      "high_pass_hz": 90,
      "low_pass_hz": 4200
    }
  ]
}
```

系统会根据 `start_line / end_line` 估算时长、生成背景音并在整章尾部统一叠加。

## 片头片尾合成与拼接逻辑

片头片尾不是逐句生成时插进去的，而是在整章正文生成完成后统一处理。

流程如下：

1. 逐句生成配音、音效和单句混音
2. 合并为整章正文
3. 生成并叠加 `soundscape` 背景音
4. 进入平台导出阶段
5. 根据 `片头` 字段和平台模板生成固定片头片尾文件
6. 若 `output/{小说名}/片头片尾/` 下已存在对应文案哈希文件，则直接复用
7. 将固定片头拼到整章前，将固定片尾拼到整章后
8. 最终导出平台格式音频

因此，片头片尾目录为空时，通常说明：

- 本次没有按支持片头片尾的平台运行
- 或章节还没有真正走到最终导出阶段

## 输出目录说明

以《蜀山剑侠传》为例，输出目录通常如下：

```text
output/
└── 蜀山剑侠传_json/
    ├── 片头片尾/
    │   ├── 片头_xxxxx.mp3
    │   └── 片尾_xxxxx.mp3
    └── 第一回-月夜棹孤舟.../
        ├── 配音/
        ├── 音效/
        ├── 混音/
        ├── 背景音/
        ├── stream_tmp/
        ├── chunk_title_xxxxx.wav
        └── 第一回-月夜棹孤舟..._上.mp3    # 最终合成音频
```

最终交付文件整理后存放于：

```text
小说音频/
└── 蜀山剑侠传_json/
    └── 第一回-月夜棹孤舟..._整书免费.mp3
```

说明：

- `片头片尾/` 是按小说缓存的固定资源目录
- `配音/`、`音效/`、`混音/`、`背景音/` 是章节级中间产物，支持断点续传
- `chunk_title_*.wav` 是标题语音缓存，可跨章节复用
- 最终整章文件为 `{章节名}_{上/下/中}.mp3`（按章节长度分片）
- 中间产物可单独保留，用 `清除最终合成脚本.sh` 清理最终音频后重新合成

## 使用方法

### 1. 准备剧本

把章节 JSON 放到：

```text
novel_tool/novel_scripts/{小说名}/
```

并确保：

- `片头` 字段完整
- `roles_definition` 与对应角色配音表一致
- `soundscape.scene_layers` 使用正确的行号范围

### 2. 安装依赖

```bash
pip install pydub ffmpeg-python requests
```

并确保本机已安装 `ffmpeg`。

### 3. 运行批处理

```bash
cd novel_tool/scripts
./novel_batch_manager.sh
```

当前默认就会按 `ximalaya` 平台执行。

如需显式指定：

```bash
./novel_batch_manager.sh --platform ximalaya
```

可选参数：

- `--script-dir <目录>`
- `--output-dir <目录>`
- `--temp-dir <目录>`
- `--sfx-engine <woosh|stable-audio-3>`
- `--bgm-engine <stable-audio-3|woosh>`
- `--keep-segments`
- `--debug`

### 4. 查看结果

最终输出位于：

```text
output/{小说名}/{章节名}/{章节名}_full.mp3
```

## 核心脚本说明

### `audio_processing_module.py`

TTS 引擎选择：

- 主引擎：`qwen3-tts`（Qwen3-TTS-12Hz-1.7B-Base），支持语音克隆，自动检测 Apple MPS / CUDA / CPU 设备
- 备选引擎：`fish-speech`（通过 HTTP API 调用本地 Fish Speech 服务，默认 `localhost:8080`）

负责：

- TTS 初始化与正文合成
- 音频参数调整
- 单句混音
- `soundscape` 背景音生成与叠加
- 平台导出
- 固定片头片尾生成、缓存与拼接

### `novel_batch_executor.py`

负责：

- 扫描剧本目录
- 调用 `audio_processing_module.py` 批量处理章节
- 传递平台、引擎和输出参数

### `novel_batch_manager.sh`

负责：

- Shell 层参数管理
- 环境与依赖检查
- 统一触发批处理流程

## 维护脚本

### `cleanup_final_audio.sh`

清理每个章节下的最终合成音频，保留配音/音效/混音等中间产物。

```bash
# 在项目根目录执行
bash cleanup_final_audio.sh
```

功能：

- 删除每个章节根目录的 `.mp3` 最终音频（合成的完整章节有声书）
- 删除每个章节根目录的 `chunk_title_*.wav` 标题语音缓存
- 保留 `配音/`、`音效/`、`混音/`、`背景音/` 子目录中的所有中间产物
- 执行后打印各子目录剩余文件数供验证

适用场景：重新合成章节时，先清理旧的最终输出，但保留耗时的 TTS 人声和音效中间产物。

## 常见问题

### 1. 合成完成但没有片头片尾

优先检查：

- 是否按 `ximalaya` 平台运行
- 输出是否为 `.mp3` 而不是 `.wav`
- `output/{小说名}/片头片尾/` 是否已有缓存文件
- 章节是否真正走到了最终导出阶段

### 2. 片头片尾音色不对

检查剧本顶层 `片头.role_voice` 是否正确。
当前固定片头片尾会优先读取这个字段。

### 3. 正文角色音色不对

检查：

- `roles_definition`
- `data[].api.voice.role_voice`
- 对应小说角色配音表

三者是否一致。

### 4. 背景音没有生效

检查：

- 顶层是否存在 `soundscape.scene_layers`
- `start_line / end_line` 是否落在有效 `data.id` 范围内
- 背景音引擎是否可用

## 说明

这份 README 以当前仓库实现为准。若后续继续扩展平台规则、剧本结构或导出逻辑，应同步更新：

- `README.md`
- `audio_processing_module.py`
- `novel-to-script` skill 里的剧本规范与模板
