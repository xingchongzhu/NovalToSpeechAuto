---
name: novel-to-script
description: >
  将小说章节 TXT 原稿转换为有声剧本 JSON 文件。用户要求生成剧本、转换剧本、制作有声剧、生成 JSON 剧本、某部小说第X章转剧本，或提供小说章节 txt/json 原稿并希望产出可合成的配音脚本时，必须使用此 Skill。此 Skill 内置剧本完整格式规范、克隆音色库、JSON 模板和小说角色配音表模板；每部小说的正式角色配音表统一维护在项目的小说角色配音关系表目录。
---

# 小说 → 有声剧本生成器

## 目标

把小说章节原稿转换为可直接进入批量音频合成流程的 JSON 剧本。

生成时优先保证：
- 原文 100% 保留，不改写、不删减、不添加剧情。
- 每部小说严格按对应小说角色配音表生成，角色配音跨章节一致。
- 章节标题单独分段，其余只按配音角色切换分段。
- 背景音使用顶层 `soundscape.scene_layers`，不使用逐句 `api.bgm`。
- 音效可包含动作、环境声和必要的人声类发声，但人声音效必须短促自然、音量低于角色配音。
- 禁止使用脚本批量化、模板批处理或正则一键扫全书的方式直接生成剧本成品；每一章都必须基于具体上下文做智能场景识别、角色识别、对白归属和音效判断，逐章单独处理，保证结果合理、自然、可听。

## 内置资源和项目路径

本 Skill 的完整剧本格式规范就在本文件中，生成剧本时不再读取单独的格式参考文档。

| 用途 | Skill 内路径 | 何时读取 |
|------|-------------|----------|
| 克隆音色全集 | `references/克隆音频角色列表说明.md` | 为新角色选择真实存在的音色时 |
| JSON 模板 | `references/剧本模版.json` | 需要确认字段结构时读取 |
| 角色配音表模板 | `references/小说角色配音表模板.md` | 某部小说还没有正式角色配音表时复制使用 |

每部小说的正式角色配音表不放在 `references/`，统一放在项目目录：
- 角色配音关系表目录：`小说批量工具/小说角色配音关系表/`
- 命名规则：`小说批量工具/小说角色配音关系表/{小说名}角色配音表.md`
- 示例：`小说批量工具/小说角色配音关系表/剑来角色配音表.md`

项目中的原稿和输出路径按小说名分目录维护：
- TXT 原稿：`小说批量工具/小说剧本原稿/{小说名}/{小说名}第X章-章节名.txt`
- 后续 TXT 原稿：`小说批量工具/小说剧本原稿/{小说名}后续/{小说名}第X章-章节名.txt`
- JSON 输出：`小说批量工具/小说剧本原稿/{小说名}json稿/{小说名}第X章-章节名.json`
- 已生成 JSON 参考：`小说批量工具/小说剧本原稿/{小说名}json稿/*.json`、`小说批量工具/小说剧本/{小说名}/*.json`

## 工作流程

### 1. 检查是否已有输出

先根据章节原稿文件名推断小说名、章节号、章节名和目标 JSON 文件名。

如果 `小说批量工具/小说剧本原稿/{小说名}json稿/` 已存在同名 JSON：
- 不重复生成。
- 告知用户文件已存在，除非用户明确要求覆盖或重新优化。

默认执行策略：
- 只要用户发起“生成某章剧本 / 继续生成下一章 / 优化某章剧本”，默认应一次性完成：读取原稿 → 生成/修正 JSON → 自动校验 → 自动修正明显问题 → 输出结果总结。
- 除非遇到真实阻塞（如原稿缺失、角色配音表缺失且无法合理补齐、关键信息冲突无法判断），否则不要在生成完初稿后停下来等待用户确认“下一步要不要继续校验/修正”。
- 校验、对白复核、音效复核、角色一致性检查，属于剧本生成的默认组成部分，不是额外可选步骤。

### 2. 读取输入和资源

生成前必须读取：
1. 当前章节 TXT 原稿。
2. 对应小说角色配音表：`小说批量工具/小说角色配音关系表/{小说名}角色配音表.md`。
3. `references/克隆音频角色列表说明.md`（至少确认新增音色存在）。
4. 已生成 JSON 参考文件中的 `roles_definition`，用于发现历史冲突，但不能覆盖角色配音表。
5. 必要时读取 `references/剧本模版.json` 确认字段结构。

如果没有找到对应小说角色配音表：
- 读取 `references/小说角色配音表模板.md`。
- 结合整部小说的已知角色设定、当前章节出场角色、已有 JSON 的 `roles_definition` 和克隆音色库，为旁白和主要角色选择合适配音。
- 新建 `小说批量工具/小说角色配音关系表/{小说名}角色配音表.md`，再按这份新表生成剧本。
- 不能只在单章 JSON 中临时设置角色配音而不落表。

### 3. 提取章节和角色

从原稿识别：
- 章节标题。
- 有台词的角色。
- 旁白。
- 场景段落，用于生成 `soundscape.scene_layers`。
- 动作、环境音和必要的人声类发声，用于生成 `effects`。

强制处理方式：
- 不允许把章节原稿先交给批量脚本做粗分段，再事后少量修补。
- 不允许依赖统一正则批量扫整批章节后直接落盘交付。
- 必须以“单章智能处理”为单位，逐段理解场景、人物关系、说话人、隐含主语、情绪和动作点，再写入最终 JSON。
- 如果某章内容复杂、多人连续对话密集，宁可人工逐段处理，也不要为了效率退回批量脚本方案。

角色定义优先级：
1. 对应小说角色配音表。
2. 已有 JSON 的 `roles_definition`，仅用于补充历史信息和发现冲突。
3. `references/克隆音频角色列表说明.md` 中匹配性格的新音色；选定后必须先补充到对应小说角色配音表。

同一角色在所有章节中 `role_voice`、`pitch`、`volume`、`speed` 必须一致；如果历史 JSON 与小说角色配音表冲突，以小说角色配音表为准。

### 4. 分段和对白归属

核心原则：
- `id=0` 为章节标题，单独分段，`mix.mode=voice_only`。
- 其余只在配音角色切换时分段。
- 同一角色连续内容必须合并，即使场景、情绪、动作或音效变化也不额外切片。
- `某人道：“台词”` 拆成旁白动作和角色台词，例如 `某人道。` 属于旁白，`台词` 属于对应角色配音。
- 动作和音效不触发分段，放到当前片段 `effects`，并按动作在合并后文本中的实际位置计算 `trigger_delay`；默认全部使用 `overlay` 混音叠加，避免打断播报。
- 除非用户明确要求做插入式音效表现，否则禁止使用 `insert`；常规小说剧本中的音效一律按混音叠加处理。
- 背景音不触发分段，背景场景变化写入顶层 `soundscape.scene_layers`，通过 `start_line/end_line` 覆盖合并后的片段范围。
- 拟人发声（笑/叹/哭）可根据剧情需要写入 `effects`，也可写进 `text` 与 `instruct`；如果作为音效，必须短促自然且不盖过配音。
- 剧本生成完成后，必须逐条复核所有 `effects` 是否与文本动作点对齐，不能只生成字段后直接交付。

角色对白拆分系统规则：
- 先判断一句文本里是否同时包含旁白叙述、说话提示词和直引号对白；若同时存在，必须拆分，不能整句挂到同一个 `role`。
- 说话提示词包括但不限于：`说道`、`问道`、`笑道`、`气笑道`、`答道`、`骂道`、`喊道`、`低声道`、`心声道`、`说道：`、`问道：` 等；出现这些模式时，要主动寻找后续对应对白。
- 旁白片段允许保留动作、表情、姿态、语气描写，例如 `陈平安收回视线，双手笼袖，深呼吸一口气，乐不可支。`；但不允许把角色直引语 `“……”` 留在旁白 `text` 里。
- 角色直引语必须归到对应角色片段；只要出现完整引号对白，默认优先判断为角色配音内容，而不是旁白内容。
- `某人说道：` 这类提示词如果服务于后面一句台词，应拆成独立旁白片段，或并入前一条旁白动作；不能和其他角色对白串在同一个片段里。
- 如果出现 `甲说一句，乙回一句` 的连续对话，必须拆成至少两个角色片段；不能把甲的台词留在旁白里、只给乙单独成句。
- 如果一句长旁白结尾带出角色发言，常见安全拆法是：`旁白叙述` → `角色A台词` → `旁白提示词` → `角色B台词`；宁可多一条短旁白，也不要把对白揉进叙述。
- 同一角色连续说多句且中间没有换人时可以合并；一旦说话人切换，必须立刻分段。
- 引号内如果只是旁白转述、书名号内引文、他人复述的内容，要结合上下文判断；但只要最终会被“谁在说”真实朗读，就应拆到对应角色。
- 还要识别“无引号的隐式角色台词 / 内心独白”：如果一句前半段明确写了某角色的动作、神态、身体反应，后半段突然转成强烈主观口吻、口语、腹诽、第一人称表达，则默认后半段属于该角色，而不是旁白。
- 强角色口吻的典型信号包括但不限于：`他娘的`、`老子`、`老娘`、`我忍了`、`换个人看看`、`行吧`、`真要`、`不好跟你掰扯`、`我怎么`、`不然我真要` 这类明显带人物情绪和口语习惯的表达。
- 如果前文主语明确是某角色，后文又出现 `我`、`老子`、`本官`、`属下` 等第一人称，而叙述视角没有切换，应优先判断为该角色的台词或内心独白，而不是旁白。
- 这类隐式角色台词的安全拆法通常是：`角色动作/神态旁白` → `该角色内心话或口语化台词`。不要因为缺少引号，就把整句都归给旁白。
- 拆分后必须再次检查：每条 `text` 是否只对应一个明确朗读角色，不能同时承担旁白和两位角色对白。

## JSON 格式规范

### 顶层结构

JSON 顶层必须包含：
- `project`：项目名称，如 `{小说名}有声小说自动生成`。
- `chapter`：章节名称，如 `第1章 惊蛰`。
- `global`：全局配置。
- `roles_definition`：角色定义（全书统一）。
- `data`：剧本片段数组（按顺序播放）。
- `soundscape`：场景级连续背景音配置，替代逐句 `bgm`。

### 全局配置 `global`

```json
{
  "pitch": "+0Hz",
  "channels": 1,
  "voice_volume": "+0%",
  "bgm_volume": "-18%",
  "effect_volume": "-10%"
}
```

字段说明：
- `pitch`：全局音调偏移，默认 `+0Hz`。
- `channels`：音频通道数，默认 `1`。
- `voice_volume`：人声基准音量，默认 `+0%`。
- `bgm_volume`：背景音基准音量，默认 `-18%`。
- `effect_volume`：音效基准音量，默认 `-10%`。

### 角色定义 `roles_definition`

核心规则：
- 同一个角色在整部小说中，`role_voice`、`pitch`、`volume`、`speed` 必须完全一致。
- 优先使用 `小说批量工具/小说角色配音关系表/{小说名}角色配音表.md` 中的角色定义保证前后统一。
- 如果角色不在表中，先结合整部小说角色设定和 `references/克隆音频角色列表说明.md` 选择配音，并补充到该小说角色配音表后再生成剧本。
- 所有 `role_voice` 必须来自 `references/克隆音频角色列表说明.md`，禁止自定义音色。
- 新角色不能只写入单章 JSON，必须先进入对应小说角色配音表，后续章节继续复用。
- 笑声、哭声、叹气、惊呼、喘息、冷哼等拟人发声可根据剧情需要保留为人声音效；如使用音效，应短促、低干扰，并避免盖过角色配音。

### 剧本片段 `data[]`

每个片段固定结构：

```json
{
  "id": 0,
  "role": "角色名",
  "api": {
    "voice": {},
    "effects": []
  },
  "mix": { "mode": "voice_only" }
}
```

要求：
- `id` 从 0 开始连续递增，不重复、不跳号。
- `role` 使用全称，不缩写、不简写、无错别字。
- 新剧本不在 `data[].api` 中写逐句 `bgm` 字段。
- `voice.text` 100% 还原原著，不增删、不改写、不添加注释。
- `text` 中遇到易读错的多音字时，可在汉字后用方括号标注拼音，如 `行[háng]`、`重[zhòng]`。
- 多音字只标注容易读错的，不确定的可不标注。

常见多音字参考：
- 差：差不多 `chā`，差劲 `chà`。
- 藏：收藏 `cáng`，宝藏 `zàng`。
- 似：似乎 `sì`，似的 `shì`。
- 更：更加 `gèng`，更改 `gēng`。
- 为：沦为 `wéi`，因为 `wèi`。
- 间：人间 `jiān`，间隔 `jiàn`。
- 看：看管 `kān`，看见 `kàn`。
- 还：还是 `hái`，归还 `huán`。
- 行：修行 `xíng`，银行 `háng`。
- 只：只是 `zhǐ`，一只 `zhī`。
- 当：充当 `dāng`，恰当 `dàng`。
- 朝：朝廷 `cháo`，朝阳 `zhāo`。
- 分：时分 `fēn`，本分 `fèn`。
- 角：牛角 `jiǎo`，角色 `jué`。

### 语音配置 `voice`

```json
{
  "text": "台词原文",
  "role": "角色名",
  "role_voice": "音色名",
  "speed": "",
  "volume": "",
  "pitch": "",
  "instruct": "语气指导"
}
```

要求：
- `role_voice` 与 `roles_definition` 和小说角色配音表一致。
- `speed`、`volume`、`pitch` 对同一角色保持全书一致。
- `instruct` 描述语气、情绪、说话状态，不改写正文。

### 背景音配置 `soundscape`

背景音统一使用顶层 `soundscape.scene_layers`，生成场景级连续背景音；点状动作声写入 `effects`。

```json
"soundscape": {
  "scene_layers": [
    {
      "name": "场景名",
      "start_line": 1,
      "end_line": 8,
      "prompt": "very subtle low volume cinematic background ambience, [time and weather], [specific location materials], [distant natural texture], [subtle indoor or street tone], [emotional atmosphere], slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
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

编写规则：
- `scene_layers` 按场景氛围覆盖连续片段，`start_line/end_line` 指向合并后的 `data.id`。
- `soundscape` 顶层不要再写 `version`、`strategy`、`engine`、`description` 这类模板性元信息，默认只保留真正参与生成的 `scene_layers`。
- 背景音不再手写 `duration` 字段，默认交给系统根据场景覆盖范围、段落文字量和语速自动估算时长。
- `prompt` 必须丰富到能支撑连续场景背景音生成，不能只写 `quiet alley`、`soft wind` 这类单调短提示词。
- 推荐结构：低音量连续背景 + 时间天气 + 具体地点材质 + 远处自然纹理 + 近处空间底色 + 情绪氛围 + 负面约束。
- 必须把场景写具体，至少交代清楚“什么时候、什么地方、空气/天气如何、有什么自然或环境纹理、整体情绪是什么”，不要只给抽象氛围词。
- 推荐优先写出的具体维度包括：昼夜（清晨/午后/黄昏/深夜）、天气（微风/闷热/潮湿/薄雾/细雨/寒意）、空间材质（土路/石板路/木窗/屋檐/院墙/竹林/水井）、自然声源（树叶轻响/夏夜虫鸣/远处鸟声/河水流动/风穿过檐角），以及这些元素的远近、强弱和连续性。
- 例如不要只写 `night ambience`，应写成类似：`quiet summer night under starry sky, faint breeze moving through tree leaves, sparse insects chirping far away, old village courtyard with wooden eaves, calm and lonely atmosphere`。
- 例如不要只写 `mysterious town`，应写成类似：`late night ancient town alley, thin cold wind brushing bluestone street, distant loose shutters and subtle leaf rustle, restrained suspense, no foreground events`。
- 必须包含低音量与连续性：`very subtle low volume cinematic background ambience`、`smooth continuous ambience bed`。
- 必须包含缓慢变化，避免循环感：`slow evolving layered soundscape`、`gentle variation over time`、`no repetitive loop feeling`。
- 可以写入轻微、远处、非突出的环境纹理，如 `distant soft wind through old wooden eaves`、`faint morning air over bluestone street`、`subtle room tone of clay walls and old timber`、`soft summer insects far away under starry night`、`gentle leaves rustling in night breeze`，但不要写成前景事件。
- 禁止突出事件、人声、旋律、脚步、尖锐音、噪声爆点：使用 `no sharp foreground sounds, no prominent events, no voices, no music, no melody, no noise bursts`。

- 默认 `volume` 可用 `-22%`；干扰人声时降到 `-28%~-32%`，太小时调到 `-18%~-22%`。
- 默认 `target_dbfs=-30`、`high_pass_hz=90`、`low_pass_hz=3800~4200`。
- 如果旧剧本或历史模板里存在 `scene_layers[].duration`，优化时默认应删除，改为使用自动时长估算；除非用户明确要求手动锁定背景音时长。

### 音效配置 `effects`

允许使用：烛火摇曳、桃枝敲打、吹灭蜡烛、关门声、脚步声、跳下墙头、抛掷钱袋、窑炉熄火、劈竹声、水流声、风吹声、鸟声、风声、雨声、笑声、哭声、叹气、冷哼、喘息、嘶吼等。

人声/拟人发声音效可以保留，但需要符合剧情和画面：
- 适合作为环境或动作补充时才添加，不强行添加。
- 音量应低于角色配音，避免抢台词。
- 时长应短促自然，避免重复、突兀或像另一条对白。
- `sound_en` 需要明确声音距离、强弱、情绪和空间感。

音效字段：

```json
{
  "trigger_delay": 0,
  "duration": 2,
  "process_mode": "overlay",
  "name": "动作+材质",
  "sound_cn": "中文描述",
  "sound_en": "英文详细描述（必须≥8个英文单词）",
  "volume": "-20%",
  "pitch": "+0Hz"
}
```

`sound_en` 编写规则：
- 音效由 Woosh-DFlow 模型生成，单次生成固定约 5 秒音频，48kHz 高质量。
- Woosh 对简短提示词理解力差，会导致生成不稳定、效果不符。
- `sound_en` 禁止使用 2-3 个单词的简短描述，必须使用详细描述。
- 编写公式：动作 + 材质/物体 + 声音特征词 + 环境/场景 + 细节修饰。
- 示例：`old wooden door creaking open slowly, rusty hinges squeaking, heavy wood swinging`。
- 示例：`light footsteps with straw sandals on stone alley, soft tapping, walking pace`。
- 示例：`metal coin tossed in air and caught, coin spinning, metallic clink, copper coin jingling`。

复合音效拆分规则：
- 当一个场景需要多种不同类型音效同时存在时，必须拆分为多个独立 `effects` 条目，分别生成后由混音引擎叠加。
- 严禁在一个 `sound_en` 中用 `and` 连接多个不同音效。
- `rain and thunder` 应拆成 `heavy rain pouring down continuously, steady rainfall` 和 `loud thunder crash and deep rumble, storm thunder rolling`。
- `wind and birds chirping` 应拆成 `strong wind blowing through trees, leaves rustling` 和 `small birds chirping in trees, bird calls, distant tweets`。
- `sword clash and footsteps` 应拆成 `metal swords clashing, blade strike, steel impact` 和 `rapid running footsteps on gravel, urgent pace`。

触发延迟计算：
- 音效不作为分段理由，应放入当前角色片段的 `effects` 数组。
- 合并片段后，`trigger_delay` 必须按动作在合并后 `text` 中的实际位置重新估算。
- 旁白语速可按约 3~5 字/秒估算；延迟时间（秒）≈ 动作前字数 ÷ 语速。
- 对话短句内动作音效通常使用 `0~2` 秒；长旁白中的动作音效要结合动作出现位置，不能全部写 `0`。
- `process_mode` 默认使用 `overlay`，让音效与配音做叠加混音；不要使用会打断播报的插入式播放。
- 如果历史 JSON、旧模板或示例中出现 `insert`，在生成新剧本或优化旧剧本时，默认应改回 `overlay`，除非用户明确要求保留插入式表现。
- 明显不合理的时间必须主动修正，例如动作词在文本前段，却把 `trigger_delay` 写到句尾附近；这种情况不能交付。

生成后音效校验：
- 剧本写完后，必须扫描整章所有带 `effects` 的片段，逐条检查音效名、动作词、`trigger_delay`、`duration`、`process_mode` 是否匹配文本语义。
- 重点检查长旁白中的动作音效，确认触发时间是否落在动作词附近，而不是滑到句尾。
- 重点检查所有音效都使用 `overlay` 叠加混音，确认不会打断配音播报。
- 如果发现 `effects[].process_mode` 不是 `overlay`，应视为默认校验失败项，除非用户明确说明该音效需要插入式处理。
- 像风声、云雾、水流、虫鸣这类持续环境纹理，优先考虑放入顶层 `soundscape.scene_layers`，不要滥用逐句 `effects`。
- 交付前要输出一份简短音效校验结论：本章共有几处 `effects`，哪些已确认对齐，哪些做过时间修正。

音量建议：
- 环境持续音（雨声、风声、流水）：`-20%~-28%`。
- 突发冲击音（雷声、闪电、爆炸、碰撞）：`-8%~-15%`。
- 轻微动作音（脚步、纸张、敲打）：保持基准。
- 人声类音效：低于角色配音，避免像另一条对白。

### 混音模式 `mix`

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `mix` | 人声 + 背景音 + 音效 | 正常场景 |
| `voice_on_bgm` | 人声 + 背景音，关闭音效 | 对话、纯叙述场景 |
| `voice_only` | 仅人声 | 开场标题、结尾独白、重点台词 |
| `effect_only` | 仅音效 | 转场、空镜过渡 |

## 写入和校验

输出到：
`小说批量工具/小说剧本原稿/{小说名}json稿/{小说名}第X章-章节名.json`

写入后必须自动校验并修复；这一步默认立即执行，不需要再次征求用户是否继续：
- JSON 语法合法。
- `data[].id` 从 0 开始连续递增，不重复、不跳号。
- 除 `id=0` 标题外，不存在连续两个相同 `role` 的片段。
- 分段符合标题单独分段、角色切换分段、同角色连续内容合并规则。
- 旁白中不残留应拆分的角色引号对白，`某人道：“台词”` 已拆成旁白动作 + 角色台词。
- 不存在“旁白片段中混入角色直引语、下一句却直接变成另一角色回应”的错位结构。
- 不存在“角色A台词被旁白念出，但角色B回应被单独拆出”的结构错误。
- `某人说道：`、`某人问道：`、`某人气笑道：` 这类提示词后，必须能在相邻片段中找到对应角色台词，不能丢句、串句或错挂到旁白。
- 不存在“角色动作描写后直接接强口语、第一人称、腹诽内容，但整句仍挂在旁白下”的隐式台词错挂。
- 对旁白片段要额外检查：若同时出现明确人物动作主语 + 强主观口吻（如 `我`、`老子` 等），应判为疑似角色内心独白，必须拆出对应角色配音。
- `data[].api` 不包含逐句 `bgm` 字段，背景音统一使用顶层 `soundscape`。
- `soundscape.scene_layers[].start_line/end_line` 指向存在的 `data.id`。
- `soundscape.scene_layers` 默认不应包含 `duration` 字段；如出现旧字段，需在交付前删除并改用自动时长估算。
- 角色 voice 配置与 `roles_definition` 一致。
- `roles_definition` 严格匹配对应小说角色配音表。
- 新角色已先补充到对应小说角色配音表，不能只存在于单章 JSON。
- 历史 JSON 与角色配音表冲突时，以角色配音表为准。
- 所有 `role_voice` 来自已知音色。
- 人声类音效如存在，需符合剧情、短促自然、音量低于角色配音。
- 所有 `sound_en` 为详细描述（≥8 个英文单词），无简短提示词。
- 复合音效已拆分为独立 `effects` 条目，`sound_en` 中无 `and` 连接不同类型音效。
- 突发冲击音（雷声/闪电/碰撞）的 `volume` 已增强至 `-8%~-15%`。
- 音量遵循：人声 > 音效 > soundscape 背景音。
- 所有 `effects` 已做生成后音效校验，`trigger_delay` 与文本动作点基本对齐。
- 所有 `effects[].process_mode` 默认必须为 `overlay`；若不是 `overlay`，必须有用户明确授权或场景理由。
- 明显不适合作为逐句 `effects` 的持续环境声，已回收为 `soundscape.scene_layers` 或重新调整。
- 文本 100% 还原原著无修改。

校验通过后，向用户报告输出路径、片段数、角色列表、soundscape 场景数和关键校验结果。
- 报告时默认直接给出：本章已完成哪些自动校验、修正了哪些明显问题、还剩哪些需要后续继续精修的点。
- 如果用户连续要求“继续生成/继续优化”，默认按同样流程继续处理下一目标，不要在每完成一章后都停下来单独询问是否继续下一步。
- 只有在出现真实阻塞、信息缺失或存在多种高影响分歧方案时，才中断流程向用户提问。

## 禁止事项

- 禁止为了追求速度，使用批量脚本一次性生成多章剧本后再抽样检查。
- 禁止把“可被正则匹配”当作“已经理解剧情和说话人”。
- 禁止在未逐章审阅的情况下，把批处理结果直接作为最终交付。
- 禁止默认使用 `insert` 作为音效 `process_mode`；除非用户明确提出需要插入式表现，否则所有音效都应使用 `overlay` 混音模式。
- 若用户要求生成某章剧本，默认应采用单章智能处理；若用户要求继续多章，也应按章逐个处理，而不是脚本批量扫出成品。
