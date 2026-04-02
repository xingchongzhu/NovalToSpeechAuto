import sys

# 添加脚本目录到Python路径
sys.path.append('/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/脚本')

# 从正确的模块导入
from audio_processing_module import AudioGenerator

# 设置路径
chapter_path = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本/剑来/剑来第一章-入山门青峰山.json'

# 初始化音频生成器
audio_generator = AudioGenerator(chapter_path, tts_engine='qwen3-tts', qwen_model_path='/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model')

# 只生成第2句（陈平安的台词）
line_config = audio_generator._parse_line_config(audio_generator.config['data'][2])
audio_generator.generate_single_line(line_config)
print("测试完成！")
