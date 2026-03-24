# Novel Audio Synthesizer Migration Plan

## 1. 当前状态分析

### 1.1 novel_audio_synthesizer.sh 主要功能
- 环境检测和准备
- 启动Docker容器服务
- 处理命令行参数
- 处理单个小说或所有小说
- 生成背景音
- 智能分析对话内容，推荐音效
- 生成配音
- 混合背景音和音效（传统方式和基于字幕的段落混合）
- 清理临时文件

### 1.2 audio_processing_module.py 已实现功能
- 定义了音频参数的数据结构
- 实现了音频引擎接口（text_to_speech, text_to_audio, mix_audio）
- 实现了音频处理工具函数
- 实现了音频混音功能
- 实现了剧本解析功能（AudioGenerator类）
- 实现了单句音频生成功能

## 2. 迁移计划

### 2.1 新增 NovelAudioSynthesizer 类
在 audio_processing_module.py 中新增 NovelAudioSynthesizer 类，实现以下功能：

#### 2.1.1 环境检测和准备
- 检测 Python 环境
- 检测 FFmpeg 安装
- 创建必要的目录结构

#### 2.1.2 Docker 服务管理
- 检查并停止旧的 Docker 容器
- 启动 easyVoice Docker 容器
- 检查服务是否正常运行

#### 2.1.3 命令行参数处理
- 支持处理单个 JSON 文件
- 支持处理所有小说的 JSON 文件

#### 2.1.4 小说处理流程
- 遍历小说目录
- 加载小说 JSON 配置
- 生成背景音
- 生成音效
- 生成配音
- 混合音频
- 保存最终音频文件

#### 2.1.5 智能音效推荐
- 实现对话内容分析功能
- 基于关键词匹配推荐合适的音效

#### 2.1.6 混合音频功能
- 实现基于字幕的段落混合功能
- 支持背景音、音效和配音的混合

#### 2.1.7 临时文件管理
- 创建和清理临时文件
- 支持保留或删除临时文件

### 2.2 集成现有功能
- 复用 AudioEngine 类的音频合成功能
- 复用 AudioGenerator 类的剧本解析功能
- 复用现有的音频混音功能

### 2.3 主函数实现
- 实现命令行接口
- 支持配置参数
- 提供帮助信息

## 3. 文件结构调整

```
audio_processing_module.py
├── 数据结构定义
│   ├── VoiceParams
│   ├── BGMAudioParams
│   ├── EffectAudioParams
│   └── MixConfig
├── AudioEngine 类
│   ├── text_to_speech
│   ├── text_to_audio
│   └── mix_audio
├── AudioGenerator 类
│   ├── 剧本解析
│   └── 单句音频生成
├── NovelAudioSynthesizer 类
│   ├── 环境检测
│   ├── Docker 服务管理
│   ├── 命令行参数处理
│   ├── 小说处理流程
│   ├── 智能音效推荐
│   └── 临时文件管理
└── 主函数
```

## 4. 迁移步骤

1. 新增 NovelAudioSynthesizer 类的基础结构
2. 实现环境检测和准备功能
3. 实现 Docker 服务管理功能
4. 实现命令行参数处理功能
5. 实现智能音效推荐功能
6. 实现基于字幕的段落混合功能
7. 实现临时文件管理功能
8. 实现主函数
9. 测试整体功能
10. 更新文档

## 5. 测试计划

1. 测试环境检测功能
2. 测试 Docker 服务管理功能
3. 测试命令行参数处理功能
4. 测试单个小说处理功能
5. 测试所有小说处理功能
6. 测试背景音生成功能
7. 测试音效生成功能
8. 测试配音生成功能
9. 测试混合音频功能
10. 测试临时文件管理功能
