from qwen_tts import Qwen3TTSModel
import torch

# 加载模型
model = Qwen3TTSModel.from_pretrained(
    '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model',
    device_map='auto',
    dtype=torch.bfloat16,
)

# 查看model对象的方法
print("Model methods:")
methods = [method for method in dir(model) if not method.startswith('_')]
for method in methods:
    if callable(getattr(model, method)):
        print(f"  - {method}")

# 查看generate_voice_clone方法的签名
print("\ngenerate_voice_clone method signature:")
import inspect
print(inspect.signature(model.generate_voice_clone))

# 查看create_voice_clone_prompt方法的签名
print("\ncreate_voice_clone_prompt method signature:")
print(inspect.signature(model.create_voice_clone_prompt))
