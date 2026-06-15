# Stable Audio 3 Lab

这是一个放在项目根目录下的隔离验证环境，用来评估 `Stable Audio 3 Small` 是否适合当前小说配音项目的背景音/环境音需求。

## 目标
- 不修改原有项目依赖和脚本
- 不接入现有背景音链路
- 单独验证本机是否适合运行 `Stable Audio 3` 小模型
- 单独记录实验输出和日志

## 目录结构
- `scripts/setup_lab.sh`：创建独立虚拟环境并安装基础依赖
- `scripts/run_smoke.sh`：运行最小探测脚本
- `scripts/run_probe.py`：输出当前 Python / Torch / MPS / CUDA 环境信息
- `scripts/clone_official_repo.sh`：克隆官方 `stable-audio-3` 仓库到本目录
- `outputs/`：后续音频验证输出
- `logs/`：探测日志与实验记录
- `models/`：预留模型目录

## 建议执行顺序
1. `zsh stable-audio3-lab/scripts/setup_lab.sh`
2. `zsh stable-audio3-lab/scripts/run_smoke.sh`
3. `zsh stable-audio3-lab/scripts/clone_official_repo.sh`

## 当前判断
- 这台机器更适合先验证 `small-music` / `small-sfx`
- 不建议直接把它视作现有章节级背景音方案的替代品
- 如果后续要接项目，建议先验证 60-120 秒环境底床的质感、循环感和拼接痕迹
