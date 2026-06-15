import argparse
import json
import os
import sys
import time
from pathlib import Path


def detect_environment():
    info = {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "cwd": os.getcwd(),
    }
    try:
        import torch
        info.update({
            "torch": torch.__version__,
            "mps_available": bool(torch.backends.mps.is_available()) if hasattr(torch.backends, "mps") else False,
            "cuda_available": torch.cuda.is_available(),
        })
    except Exception as exc:
        info["torch_error"] = str(exc)
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["small-music", "small-sfx"], default="small-music")
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--prompt", default="ambient background music, calm and relaxing, soft piano, gentle rain, distant forest birds, no drums, no vocals, smooth loop, seamless transition, high fidelity stereo")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    lab_dir = Path(__file__).resolve().parents[1]
    output_dir = lab_dir / "outputs"
    log_dir = lab_dir / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    env_info = detect_environment()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (log_dir / f"probe-{stamp}.json").write_text(json.dumps({"env": env_info, "args": vars(args)}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Stable Audio 3 Lab Probe ===")
    print(json.dumps(env_info, ensure_ascii=False, indent=2))
    print()
    print("This probe currently validates the isolated runtime only.")
    print("Reason: Stable Audio 3 official local inference flow is repo-driven and model-specific;")
    print("on this Mac, the practical path is to validate small models in an isolated clone next.")
    print(f"Suggested target mode: {args.mode}")
    print(f"Suggested duration: {args.seconds}s")
    print(f"Suggested prompt: {args.prompt}")

    if args.output:
        Path(args.output).write_text(json.dumps({"env": env_info, "args": vars(args)}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote summary: {args.output}")


if __name__ == "__main__":
    main()
