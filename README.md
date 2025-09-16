# GitHub Configuration Analysis Verifier (example)

## 内容说明
此仓库包含一个示例验证脚本 `verify_example.py`，用于验证仓库根目录的 `analysis_results.json`（或 yaml）内容是否满足预期规范（commit、参数变更、issue 关联等）。脚本支持 `--mock` 模式用于离线测试。

## 必要文件
- `verify_example.py`：主验证脚本（请确保可执行权限）。
- `analysis_results.json`：放在仓库根目录，遵循模板（参见 `analysis_results.json.sample`）。
- `.env`：把 `.env.example` 复制为 `.env` 并填入真实值（仅在真实模式下需要）。
- `project_docs/`：脚本会将验证报告写入该目录（默认）。示例提供 `.gitkeep`。

## 快速开始（离线演示）
1. 在本地克隆仓库并进入目录。
2. 运行（无需安装任何依赖）：
```bash
python3 verify_example.py --mock
