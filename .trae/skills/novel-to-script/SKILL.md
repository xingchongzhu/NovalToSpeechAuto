---
name: novel-to-script
description: >
  将《剑来》小说章节 TXT 原稿转换为有声剧本 JSON 文件。
  当用户提供小说章节 .txt 文件并要求"生成剧本"、"转换剧本"、"制作有声剧本"、
  "生成 JSON 剧本"、"剑来第X章 转剧本"时应使用此 Skill。
  即使只提到"把小说原稿生成剧本"、"制作配音脚本"，也应触发此 Skill。
---

# 小说 → 有声剧本生成器

## 概述

此 Skill 将《剑来》小说章节的 TXT 原稿转换为标准化的有声剧本 JSON 文件，
用于自动化语音合成流水线。

## 重要路径

| 用途 | 路径 |
|------|------|
| TXT 原稿 | `小说批量工具/小说剧本原稿/剑来/剑来第X章-章节名.txt` |
| **JSON 剧本输出** | `小说批量工具/小说剧本原稿/剑来json稿/剑来第X章-章节名.json` |
| 角色配音表 | `小说批量工具/剧本生成skill/剑来角色配配音表.md` |
| 克隆音色库 | `小说批量工具/剧本生成skill/克隆音频角色列表说明.md` |
| 格式规范文档 | `小说批量工具/剧本生成skill/剧本格式参考文档.md` |
| JSON 模板 | `小说批量工具/剧本生成skill/剧本模版.json` |
| 已有 JSON 参考 | `小说批量工具/小说剧本/剑来/剑来第1章-惊蛰.json` 等 |

**输出 JSON 必须写入 `小说批量工具/小说剧本原稿/剑来json稿/` 目录，文件名格式 `剑来第X章-章节名.json`。**

在开始处理前，**必须**通读上述角色配音表、格式规范文档和 JSON 模板，
同时**必须**阅读至少一个已有 JSON 完整参考文件来确定当前已存在的角色定义。

---

## 工作流程

### 第〇步：检查是否已有对应剧本（跳过生成）

在读取任何参考文件之前，**首先检查**目标输出路径是否已存在对应的 JSON 剧本文件：

- 根据 TXT 原稿文件名推断输出 JSON 文件名（`剑来第X章-章节名.txt` → `剑来第X章-章节名.json`）
- 检查 `小说批量工具/小说剧本原稿/剑来json稿/` 目录下是否已有同名 `.json` 文件
- **如果已存在**：跳过生成，直接告知用户该章节剧本已存在，无需重复生成
- **如果不存在**：继续执行后续步骤

### 第一步：阅读输入与参考文件

1. **读取 TXT 原稿** — 用户提供的章节文本
2. **读取 `剑来角色配配音表.md`** — 获取已有角色的标准配音定义
3. **读取 `克隆音频角色列表说明.md`** — 作为新角色音色来源
4. **读取 `剧本格式参考文档.md`** — 确认格式规范
5. **读取所有已有 JSON**（`小说批量工具/小说剧本原稿/剑来json稿/` 和 `小说批量工具/小说剧本/剑来/` 下所有 `.json` 文件）— 从中提取已定义角色的 `role_voice`、`pitch`、`volume`、`speed`，确保跨章节一致

### 第二步：提取章节信息与角色

从 TXT 内容中识别：
- **章节标题** — 如「第四章 黄鸟」
- **出场角色** — 所有有台词的角色名，以及旁白
- 对于每个角色，按以下优先级查找配音：
  1. 已有 JSON 文件中出现过的定义（最高优先级，保证一致性）
  2. `剑来角色配配音表.md` 中的定义
  3. `克隆音频角色列表说明.md` 中匹配性格相近的音色

### 第三步：分析场景与情绪

将章节内容按以下维度分段：
- **场景变化**（室内→室外、小巷→街市、白天→夜晚）
- **时间变化**（回忆、现在、未来）
- **情绪转折**（平静→紧张、悲伤→欢快）
- **角色切换**（旁白↔角色对话）

### 第四步：生成 JSON 剧本

严格按照现有 JSON 格式输出，每个片段包含 `id`、`role`、`api`（含 `voice`、`bgm`、`effects`）、`mix`。

---

## JSON 结构规范（严格遵循）

### 顶层结构

```json
{
  "project": "剑来有声小说自动生成",
  "chapter": "剑来第X章-章节名",
  "global": { ... },
  "roles_definition": { ... },
  "data": [ ... ]
}
```

### global（固定不变）

```json
{
  "pitch": "+0Hz",
  "channels": 1,
  "voice_volume": "+0%",
  "bgm_volume": "-18%",
  "effect_volume": "-10%"
}
```

### roles_definition

`roles_definition` 中每个角色使用**扁平格式**（与已有 JSON 保持一致）：

```json
"角色名": {
  "role_voice": "音色名",
  "pitch": "值",
  "volume": "值",
  "speed": "值"
}
```

**角色配音一致性原则（极其重要）**：
- 同一角色在整部小说的所有章节中 `role_voice`/`pitch`/`volume`/`speed` 必须**完全一致**
- 首先查阅所有已有 JSON 文件的 `roles_definition`，复用已有角色的定义
- 只为本章节中**首次出现**的新角色创建新的配音定义
- 所有音色名必须来自 `克隆音频角色列表说明.md` 中存在的真实音色

### data 数组

每个片段格式：

```json
{
  "id": 从0开始的连续整数,
  "role": "角色名",
  "api": {
    "voice": { ... },
    "bgm": { ... },
    "effects": [ ... ]
  },
  "mix": { "mode": "模式名" }
}
```

#### voice 字段

```json
{
  "text": "台词或旁白原文",
  "role": "角色名",
  "role_voice": "音色名",
  "speed": "语速",
  "volume": "音量",
  "pitch": "音调",
  "instruct": "语气指导"
}
```

- `text`：**100% 还原原著原文**，不增删、不改写任何字句
  - **多音字标注**：当遇到多音字容易读错时，在汉字后用方括号标注拼音，格式：`汉字[pinyin]`
  - 标注示例：
    - "他在银行[háng]工作，行[xíng]事低调。"
    - "这件事情很重[zhòng]要，不要重[chóng]复。"
    - "长[cháng]城很长[cháng]，他慢慢长[zhǎng]大了。"
  - 常见多音字参考：行(háng/xíng)、重(zhòng/chóng)、长(cháng/zhǎng)、当(dāng/dàng)、曾(céng/zēng)、便(biàn/pián)、朝(cháo/zhāo)、处(chǔ/chù)、禁(jīn/jìn)、提(tí/dī)、应(yīng/yìng)等
  - 标注原则：只标注**容易读错**的多音字，不必标注所有多音字；不确定的可以不标注
  - **声调易错提醒（极其重要）**：
    - 差：差不多→**chā（第一声）**，差劲→chà（第四声），出差→chāi（第一声）
    - 藏：躲藏/收藏/库藏→**cáng（第二声）**，宝藏/西藏→zàng（第四声）
    - 似：似乎/相似→**sì（第四声）**，似的→shì（第四声）
    - 更：更加/更是→**gèng（第四声）**，更改/五更→gēng（第一声）
    - 为：成为/沦为→**wéi（第二声）**，因为/为了→wèi（第四声）
    - 间：人间/之间/时间→**jiān（第一声）**，间隔/间接→jiàn（第四声）
    - 看：看见/观看→**kàn（第四声）**，看管/看守→kān（第一声）
    - 还：还是/还有→**hái（第二声）**，归还/还乡→huán（第二声）
    - 行：行走/修行→**xíng（第二声）**，银行/行列→háng（第二声）
    - 只：只是/只有→**zhǐ（第三声）**，一只→zhī（第一声）
    - 当：当时/充当→**dāng（第一声）**，恰当/当铺→dàng（第四声）
    - 朝：朝廷/朝代→**cháo（第二声）**，朝阳/朝夕→zhāo（第一声）
    - 分：时分/分开→**fēn（第一声）**，本分/过分→fèn（第四声）
    - 角：牛角/角落→**jiǎo（第三声）**，角色/角斗→jué（第二声）
- `instruct`：描述当前片段的语气，如「平静叙述」「生动描述」「庄重开场」「略带紧张」「感慨」「神秘神秘」

#### bgm 字段

```json
{
  "play_mode": "keep / switch / lower / fade",
  "scene": "场景标识（英文标识符）",
  "scene_cn": "中文场景描述",
  "scene_en": "英文场景描述",
  "fade_in": 0~2,
  "fade_out": 0~2,
  "volume": "典型 -18% ~ -28%",
  "pitch": "+0Hz"
}
```

**BGM 使用规则**：
- 场景变化用 `switch`，同一场景延续用 `keep`
- 对话时 BGM 降低用 `lower`
- 章节结束/大段过渡用 `fade`
- **不压人声**，BGM 音量始终低于人声

**BGM Scene 标识参考**：

| scene | scene_cn | 适用场景 |
|-------|----------|----------|
| 小镇暮色 | 古风小镇白天/夜晚 | 泥瓶巷、小镇日常 |
| 静夜星空 | 古风静夜 | 夜晚独处、内心独白 |
| 街市喧嚣 | 古风街市热闹 | 集市、街巷人群 |
| 悬念氛围 | 神秘古风 | 神秘事件、悬念 |
| 回忆往事 | 淡淡忧伤回忆 | 回忆片段 |
| 轻松日常 | 轻松乡村日常 | 日常交谈、温馨片段 |
| 热血武斗 | 热血激昂 | 打斗、展示武功 |
| 街巷对峙 | 紧张氛围 | 冲突、对峙 |
| 希望微光 | 悠远希望 | 温暖、治愈 |

#### effects 数组

```json
{
  "trigger_delay": 触发前等待秒数,
  "duration": 持续秒数,
  "process_mode": "insert",
  "name": "音效名称",
  "sound_cn": "中文描述",
  "sound_en": "英文详细描述（必须详细，见下方规范）",
  "volume": "典型 -20% ~ -28%",
  "pitch": "+0Hz"
}
```

**音效触发延迟估算**：
- 旁白语速 ≈ 3字/秒（speed -10%）
- `trigger_delay` = 动作在 text 中的字数位置 ÷ 3

**`sound_en` 提示词增强规范（极其重要）**：

音效由 **Woosh-DFlow** 模型生成（替代原 stable-audio-open），该模型特点：
- 单次生成固定约 5 秒音频，48kHz 高质量
- 对简短提示词理解力差，会导致生成内容与预期不符
- **复合音效只能生成其中一种**（如"雨声+雷声"只会生成雨声），必须拆分

因此 `sound_en` **禁止**使用简短描述，**必须**使用详细描述，且复合音效必须拆分为多个独立 effects 条目：

| 要素 | 说明 | 示例 |
|------|------|------|
| 动作 | 发生了什么 | opening, hitting, scattering |
| 材质 | 涉及什么材质 | wooden, metal, stone, paper |
| 力度/速度 | 动作特征 | soft, heavy, rapid, gentle |
| 环境/场景 | 发生在什么环境中 | on stone floor, in quiet room |
| 音色特征 | 声音听起来怎样 | creaking, clinking, thud, whoosh |

**错误 vs 正确示例**：

| 错误（太简短） | 正确（详细描述） |
|------|------|
| `"Door Opening"` | `"old wooden door creaking open slowly, rusty hinges squeaking, traditional Chinese door, heavy wood swinging"` |
| `"Fighting Sounds"` | `"physical fighting sounds, punching and kicking, body impacts, scuffling on ground, combat brawl"` |
| `"Footsteps"` | `"light footsteps with straw sandals on stone alley, soft tapping, walking pace, dry surface"` |
| `"Bird Wings"` | `"large bird wings flapping rapidly, feathers rustling, wing beats descending, bird swooping down, powerful flapping"` |
| `"Coin"` | `"metal coin tossed in air and caught, coin spinning, metallic clink, copper coin jingling"` |
| `"Wood Breaking"` | `"wooden board cracking and breaking, sharp snap, splintering wood, plank giving way, structural failure crack"` |
| `"Wind"` | `"strong howling wind in snowstorm, blizzard gusting, fierce cold wind, whistling gale, winter storm raging"` |

**`sound_en` 编写公式**：

```
[动作] + [材质/物体] + [声音特征词] + [环境/场景] + [细节修饰]
```

例如：`"soft cautious tiptoe footsteps on wooden floor, creaking wood, careful sneaking, quiet light steps"`

**复合音效拆分规则（极其重要）**：

当一个场景需要多种不同类型音效同时存在时，**必须拆分为多个独立 effects 条目**，分别生成后由混音引擎叠加。严禁在一个 `sound_en` 中用"and"连接多个不同音效。

| 错误（复合描述，只会生成其中一种） | 正确（拆分为独立条目） |
|------|------|
| `"rain and thunder, storm with lightning"` | 效果1: `"heavy rain pouring down continuously, steady rainfall on surface"`<br>效果2: `"loud thunder crash and deep rumble, storm thunder rolling"` |
| `"wind and birds chirping in forest"` | 效果1: `"strong wind blowing through trees, leaves rustling, branch swaying"`<br>效果2: `"small birds chirping and singing in trees, bird calls, distant tweets"` |
| `"sword clash and footsteps running"` | 效果1: `"metal swords clashing and ringing, blade strike, steel impact"`<br>效果2: `"rapid running footsteps on gravel, urgent pace, heavy steps"` |

拆分后的多个 effects 条目通过 `trigger_delay` 错开触发时间，模拟真实声学时序。例如：
- 闪电劈裂声 trigger_delay=0.5，雷声 trigger_delay=1.5（闪电先于雷声）
- 碰撞声 trigger_delay=0，脚步声 trigger_delay=0.3（碰撞后跑动）

**音效音量增强规则**：

Woosh 生成的不同类型音效音量差异大（雷声/闪电比雨声低 10-19 dB），混音时需按类型调整：
- 环境持续音（雨声、风声、流水）：基准音量（volume 保持 `-20%` ~ `-28%`）
- 突发冲击音（雷声、闪电、爆炸、碰撞）：增强 +10% ~ +18%（volume 设为 `-8%` ~ `-15%`）
- 轻微动作音（脚步、纸张、敲打）：保持基准

**允许使用的音效**（仅非人声、环境/动作类）：
- 烛火摇曳、桃枝敲打、吹灭蜡烛、开门声、关门声、脚步声（各种）、跳下墙头
- 抛掷钱袋/铜钱、拍桌声、床板断裂、倒地声响、竹签散落
- 鸟翼扑腾、鸟啄声、鸟飞远去、风吹声、雨声、雷声、闪电、风雪声
- 纸张燃烧、拳风破空、踢腿声、街市背景声、水流声

**音效生成优先级**：

1. **预置音效库**（优先）：系统自动从 `小说批量工具/音效库/` 匹配真实录制的 Foley 音效
2. **Woosh AI 生成**（降级）：音效库中未找到时，使用 Woosh-DFlow 模型生成

**预置音效库使用说明**：

- 音效库目录：`小说批量工具/音效库/`
- 索引文件：`小说批量工具/音效库/index.json`
- 匹配策略：effect_name 精确匹配 → 关键词模糊匹配 → sound_cn 中文关键词匹配
- 如需添加新音效，将 wav/mp3 文件放入音效库目录，并在 index.json 中添加对应条目

**严格禁止的音效**（人声/拟人发声）：
- 笑声（哈哈大笑、轻笑、嗤笑）
- 哭声、抽泣
- 叹气、冷哼、喘息
- 惊呼、嘶吼
- 吹气（轻吹气、吹一口气等人物口部动作）
- **以上所有拟人发声和人物声音动作必须由人声通过 `instruct` 演绎，禁止添加音效**

#### mix 字段

| mode | 说明 | 何时使用 |
|------|------|----------|
| `voice_only` | 仅人声 | 章节标题(id=0)、结尾独白、重点台词 |
| `voice_on_bgm` | 人声+BMG | 角色对话 |
| `mix` | 人声+BGM+音效 | 带音效的旁白叙述 |
| `effect_only` | 仅音效 | 纯环境过渡（极少使用） |

**注意**：章节第一段（id=0）必须不包含 bgm，`mix.mode` 为 `voice_only`。

---

## 分段强制规则

以下情况**必须**创建新的 data 片段：

1. **角色切换** — 旁白→角色、角色A→角色B
2. **BGM 切换或模式变更** — switch、lower、fade 时
3. **场景/时间/地点变化** — 屋内→屋外、回忆→现在
4. **情绪明显转折** — 平静→紧张、悲伤→高兴
5. **需要插入动作音效** — 开门、打斗、物品掉落
6. **单段 text 过长** — 旁白 text 超过约100字应考虑拆分，保持可读节奏

---

## 生成后校验

完成 JSON 写入后，**必须**执行以下校验：

1. **语法校验**：`python3 -c "import json; json.load(open('输出文件路径'))"` — 确保 JSON 合法
2. **角色一致性**：对比已有 JSON，确认已有角色的 `role_voice`/`pitch`/`volume`/`speed` 与之前章节完全一致
3. **音色合法性**：所有 `role_voice` 值在 `克隆音频角色列表说明.md` 中存在
4. **人声音效检查**：`effects` 中不包含任何人声类音效（笑/哭/叹/哼/喘息）
5. **id 连续性**：`data` 中 `id` 从 0 开始连续递增，不重复、不跳号
6. **音量层级**：人声 ≈ 0% > 音效 ≈ -20%~-28% > BGM ≈ -18%~-28%
7. **音效提示词质量检查**：所有 `sound_en` 必须是详细描述（至少8个英文单词），禁止简短提示词如 `"Door Opening"`、`"Footsteps"`、`"Wind"` 等2-3词描述。如发现简短提示词，必须按照 `[动作]+[材质/物体]+[声音特征词]+[环境/场景]+[细节修饰]` 公式扩展
8. **复合音效拆分检查**：`sound_en` 中禁止用"and"连接多个不同类型音效（如 `"rain and thunder"`），必须拆分为多个独立 effects 条目，通过 `trigger_delay` 错开触发

如校验失败，自动修复问题后重新校验。
