from huggingface_hub import login

# 登录 Hugging Face
print("正在登录 Hugging Face...")
try:
    # 使用交互式登录
    login()
    print("登录成功！")
except Exception as e:
    print(f"登录失败: {e}")
