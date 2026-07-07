# 小说有声剧可视化工具

一个本地 Web 工具，用于管理小说剧本、试听克隆音色、批量生成有声剧音频，并对剧本逐行编辑、逐句重生成与混音。

## 启动

```bash
cd visual_tool
bash start.sh
```

浏览器打开：`http://localhost:8088`

> 必须通过 `http://localhost:8088` 访问，不能直接双击打开 `index.html`（`file://` 协议无法请求后端 API）。

## 界面布局

顶部工具栏 + 三栏主区 + 底部日志：

```
┌─────────────────────────────────────────────────────────┐
│ 顶栏: 🔄刷新  ▶生成选中  ▶▶生成全部  ⏹取消  [状态]        │
├──────────────┬──────────────────────┬───────────────────┤
│ 📁 剧本列表   │ 📄 内容预览（可编辑） │ 📻 输出文件        │
│ (多选)       │  🔬实验室  🎤音色库  │                   │
│              │                      │                   │
│ 小说→章节树  │  背景音场景层        │  章节→音频分组     │
│              │  剧本片段逐行编辑     │  (成品/混音/配音/  │
│              │                      │   音效/背景音)     │
├──────────────┴──────────────────────┴───────────────────┤
│ 生成日志面板（SSE 实时日志）                              │
└─────────────────────────────────────────────────────────┘
```

## 功能说明

### 1. 剧本列表（左栏）

- 扫描 `novel_tool/novel_scripts/` 下所有小说，按小说→章节树形展示
- 章节按章节号数字排序（支持中文数字：第一回 / 第14回 / 第100回）
- 每章前有 checkbox，可**多选**加入生成队列
- 「全选/取消」快速勾选某小说全部章节
- 点击章节名 → 中央面板加载该剧本内容
- 展开状态在刷新/预览后保持

### 2. 内容预览与编辑（中央）

点击剧本后进入可编辑视图：

**顶部**
- `💾 保存剧本`：将所有编辑写回剧本 JSON 文件（直接覆盖，不备份）

**背景音场景（soundscape）**
- 列出所有场景层，显示名称、覆盖行范围、英文提示词
- 每层 `🔄 重生成背景音` 按钮 → 调用 Stable Audio 3 重新生成，替换 `output/背景音/soundscape_layer_N.wav`

**剧本片段（逐行）**

每行可编辑字段（含 title 悬停说明）：
- 角色、音色（下拉选择/输入，来自克隆音色库）、语速、音高
- 台词文本、语气指导 instruct

行内操作按钮：
- `🔄 配音`：先自动保存，再用最新文本+音色重生成该行配音(TTS)，替换 `配音/voice_line_N.wav`
- `🎚 混音`：按原混音逻辑重新混合该行（配音+音效，遵循 mix.mode 与音效触发位置），生成 `混音/mixed_line_N.wav`

**音效区块（每行 effects）**

每个音效可编辑：音效名、触发关键词、延时、时长、`sound_en` 英文提示词、`sound_cn` 中文说明。
- `🔄 重生成`：仅重生成该音效，替换 `音效/effect_line_{名}_N.wav`

### 3. 输出文件（右栏）

- 扫描 `output/` 下所有已生成音频，按小说→章节展示
- 章节默认折叠，点击展开；分组（成品/混音/配音/音效/背景音）也默认折叠
- 每个音频独立播放器 + 文件大小 + `#行号`
- 每个音频 `🔄` 图标 → 展开重生成面板，显示对应剧本文本，可编辑后重生成
  - 配音：显示角色+音色+可编辑文本 → 走 TTS
  - 音效：显示提示词 → 走 Woosh
  - 背景音：显示场景+提示词 → 走 SA3
  - 成品音频：重新合成整章
- 重生成完成后音频原地替换（带时间戳防缓存），展开状态保持

### 4. 声音实验室（🔬）

独立生成三类音频，即时试听：
- **🗣 TTS 合成**：输入文本 + 选择克隆音色（可试听）+ 语速/音高 → 合成
- **🎵 音效生成**：英文提示词 + 时长 → Woosh 生成
- **🎼 背景音生成**：英文提示词 + 时长 → SA3 生成

三个按钮均支持生成/停止状态切换，结果自动播放。产物存 `output/_lab/`。

### 5. 音色库（🎤）

- 列出 `clone-audio/` 下所有克隆音色，支持搜索过滤、逐个试听
- `🎙 音色库编辑`：表格化编辑克隆音色的角色名、特色、场景、性别、年龄段、语言、风格标签，写回音色说明 MD（见「路径约定」）

### 6. 批量生成

- `▶ 生成选中`：对勾选章节逐个调用 `audio_processing_module.py`
- `▶▶ 生成全部`：执行 `novel_batch_manager.sh`
- 底部日志面板 SSE 实时显示 TTS/混音/切分进度，`⏹ 取消` 可中止

## 后端 API

| 端点 | 方法 | 功能 |
|---|---|---|
| `/api/scripts` | GET | 剧本树（按章节号排序） |
| `/api/raw-scripts` | GET | 原稿文件列表 |
| `/api/outputs` | GET | 输出音频树（分组+行号） |
| `/api/clone-voices` | GET | 克隆音色列表 |
| `/api/clone-voice-table` | GET | 克隆音色说明表（含性别/年龄/语言/风格） |
| `/api/char-voices-novels` | GET | 有配音表的小说列表 |
| `/api/char-voices?novel=` | GET | 指定小说的角色配音表 |
| `/api/script/line-audio?script=` | GET | 剧本逐行已生成音频信息 |
| `/api/file/{path}` | GET | 音频/JSON 文件（支持 Range 播放） |
| `/api/raw-script/{path}` | GET | 原稿内容 |
| `/api/generate` | POST | 生成选中章节（异步） |
| `/api/generate-all` | POST | 执行批量脚本（异步） |
| `/api/generate/log?task_id=` | GET | SSE 实时日志流 |
| `/api/generate/cancel` | POST | 取消任务 |
| `/api/generate/status?task_id=` | GET | 任务状态 |
| `/api/outputs/delete` | POST | 删除输出音频 |
| `/api/regen` / `/api/regen/info` | POST | 输出列表单音频重生成 |
| `/api/script/save` | POST | 保存编辑后的剧本 |
| `/api/script/regen-line` | POST | 逐行重生成配音+音效 |
| `/api/script/regen-effect` | POST | 单个音效重生成 |
| `/api/script/regen-layer` | POST | 背景音场景层重生成 |
| `/api/script/remix-line` | POST | 逐行按原逻辑重新混音 |
| `/api/char-voices/update` | POST | 更新小说角色配音表 |
| `/api/clone-voice-table/update` | POST | 更新克隆音色说明表某行 |
| `/api/lab/tts` `/api/lab/sfx` `/api/lab/bgm` | POST | 声音实验室生成 |

## 技术栈

- 后端：Python 标准库 `http.server`（多线程），零第三方依赖
- 前端：原生 HTML/CSS/JS，无构建工具
- 音频：`<audio>` 标签 + HTTP Range 支持
- 实时日志：Server-Sent Events (SSE)
- 生成执行：`subprocess.Popen` 实时读取子进程 stdout

## 路径约定

- 剧本：`novel_tool/novel_scripts/{小说名}/{章节名}.json`
- 原稿：`novel_tool/novel_scripts_raw/{小说名}/...`
- 输出：`output/{小说名}/{章节名}/{配音,音效,背景音,混音}/`
- 音色：`clone-audio/{音色名}.mp3`
- 音色说明表：`.comate/skills/novel-to-script/references/克隆音频角色列表说明.md`（唯一权威文件，音色库编辑写回此处）
- 角色配音表：`novel_tool/character_voice_tables/{小说名}角色配音表.md`

## 注意事项

- 保存剧本直接覆盖原文件，不自动备份
- 逐行/逐音效重生成前会先自动保存，确保用最新提示词
- 混音需先有对应 `voice_line_N.wav`
- Woosh/SA3 首次生成需加载模型（约 30-40 秒），非卡死
- 逐句 bgm 不参与单行混音，背景音统一走 soundscape 场景层
