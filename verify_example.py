#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_example.py
样例 GitHub 配置分析验证脚本（基于用户模板），支持 --mock 本地测试。
"""

import sys
import os
import json
import re
import base64
import argparse
from typing import Tuple, Optional, Dict, Set

try:
    import requests
except Exception:
    requests = None  # requests 不是必须（mock 模式下可以没有）

# -----------------------------
# 配置（已填充示例值）
# -----------------------------
CONFIG = {
    "ENVIRONMENT": {
        "GITHUB_TOKEN_VAR": "MCP_GITHUB_TOKEN",   # 环境变量名（放 token）
        "REPO_OWNER_VAR": "REPO_OWNER",
        "REPO_NAME_VAR": "REPO_NAME",
        "ENV_FILE_PATH": ".env"
    },
    "ANALYSIS_TARGET": {
        "TARGET_FILE_PATH": "analysis_results.json",
        "ANALYSIS_FILE_NAME": "analysis_results.json",
        "ANALYSIS_FILE_FORMAT": "json"
    },
    "PARAMETER_VALIDATION": {
        "REQUIRED_PARAMETERS": [
            "micro_batch_size_per_device_for_update",
            "micro_batch_size_per_device_for_experience"
        ],
        "VALIDATION_MODE": "exact",  # exact / any / range
        "EXPECTED_VALUES": {
            "micro_batch_size_per_device_for_update": {
                "before": 4,
                "after": 2
            },
            "micro_batch_size_per_device_for_experience": {
                "before": 8,
                "after": 4
            }
        },
        "RANGE_CONFIG": '{"micro_batch_size_per_device_for_update": {"min_before": 1, "max_before": 16}}'
    },
    "ISSUE_SEARCH": {
        "KEYWORDS": [
            "oom",
            "memory",
            "显存"
        ],
        "INCLUDE_PR": "false",
        "ALLOW_EMPTY_ISSUES": "false",
        "STRICT_ISSUE_MATCH": "true"
    },
    "VERIFICATION_CHECKS": {
        "VERIFY_COMMIT": "true",
        "VERIFY_PARAMETERS": "true",
        "VERIFY_ISSUES": "true",
        "DATE_FORMAT": r"^\d{4}-\d{2}-\d{2}$"
    }
}

# -----------------------------
# 示例（用于 mock 模式） - 一个会通过所有校验的 analysis_results.json 示例
# -----------------------------
SAMPLE_ANALYSIS = {
    "target_commit_sha": "0f4b0c1e2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d",
    "commit_author": "example-author",
    "commit_date": "2025-09-10",
    "parameter_changes": {
        "micro_batch_size_per_device_for_update": {
            "before": 4,
            "after": 2,
            "line_number": 120
        },
        "micro_batch_size_per_device_for_experience": {
            "before": 8,
            "after": 4,
            "line_number": 130
        }
    },
    "related_issue_number_list": [101, 102]
}

# -----------------------------
# 工具函数
# -----------------------------
def get_github_credentials() -> Tuple[Optional[str], str, str]:
    """获取 GitHub 认证与仓库信息（从环境变量读取）"""
    token = os.getenv(CONFIG["ENVIRONMENT"]["GITHUB_TOKEN_VAR"])
    owner = os.getenv(CONFIG["ENVIRONMENT"]["REPO_OWNER_VAR"], "example-owner")
    repo = os.getenv(CONFIG["ENVIRONMENT"]["REPO_NAME_VAR"], "example-repo")
    return token, owner, repo

def github_api_request(endpoint: str, token: Optional[str], owner: str, repo: str, mock: bool=False) -> Tuple[bool, Optional[Dict]]:
    """发送 GitHub API 请求；mock=True 时返回示例数据（不联网）"""
    if mock:
        # 模拟几个 endpoint 的返回结构以配合后续校验
        if endpoint.startswith("contents/"):
            # 返回 analysis 文件的 base64 编码内容
            payload = base64.b64encode(json.dumps(SAMPLE_ANALYSIS).encode("utf-8")).decode("utf-8")
            return True, {"content": payload}
        if endpoint.startswith("commits/"):
            # 返回 commit 详情
            return True, {
                "sha": SAMPLE_ANALYSIS["target_commit_sha"],
                "author": {"login": SAMPLE_ANALYSIS["commit_author"]},
                "commit": {"author": {"date": SAMPLE_ANALYSIS["commit_date"]}}
            }
        if endpoint.startswith("issues?"):
            # 返回 issue 列表（simulate both issues 101 and 102 exist and contain keywords）
            return True, [
                {"number": 101, "title": "oom on large batch", "body": "遇到 OOM 问题"},
                {"number": 102, "title": "显存不足", "body": "memory usage spike"}
            ]
        if endpoint.startswith("issues/"):
            num = int(endpoint.split("/")[-1])
            if num == 101:
                return True, {"number": 101, "title": "oom on large batch", "body": "遇到 OOM 问题"}
            if num == 102:
                return True, {"number": 102, "title": "显存不足", "body": "memory usage spike"}
            return False, None

        return False, None

    # 实际调用 GitHub API（需要 requests）
    if requests is None:
        print("Error: requests 模块不可用（没有 mock 模式时需要安装 requests）", file=sys.stderr)
        return False, None

    url = f"https://api.github.com/repos/{owner}/{repo}/{endpoint}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return True, resp.json()
        elif resp.status_code == 404:
            return False, None
        else:
            print(f"API error {resp.status_code} for {endpoint}: {resp.text}", file=sys.stderr)
            return False, None
    except Exception as e:
        print(f"Exception calling GitHub API: {e}", file=sys.stderr)
        return False, None

def load_analysis_results(token: Optional[str], owner: str, repo: str, mock: bool=False) -> Optional[Dict]:
    """加载 analysis file（如果 mock=True 则来自 SAMPLE_ANALYSIS）"""
    analysis_file = CONFIG["ANALYSIS_TARGET"]["ANALYSIS_FILE_NAME"]
    success, file_data = github_api_request(f"contents/{analysis_file}", token, owner, repo, mock=mock)
    if not success or not file_data:
        return None
    try:
        content_encoded = file_data.get("content", "")
        content = base64.b64decode(content_encoded).decode("utf-8")
        if CONFIG["ANALYSIS_TARGET"]["ANALYSIS_FILE_FORMAT"] == "json":
            return json.loads(content)
        else:
            # 暂不演示 yaml，直接返回 None 表示不支持
            return None
    except Exception as e:
        print(f"Error parsing {analysis_file}: {e}", file=sys.stderr)
        return None

def verify_commit_data(results: Dict, token: Optional[str], owner: str, repo: str, mock: bool=False) -> bool:
    commit_sha = results.get("target_commit_sha")
    if not isinstance(commit_sha, str) or not re.match(r"^[a-f0-9]{40}$", commit_sha, re.IGNORECASE):
        print(f"Error: Invalid commit SHA format: {commit_sha}", file=sys.stderr)
        return False

    success, commit_data = github_api_request(f"commits/{commit_sha}", token, owner, repo, mock=mock)
    if not success or not commit_data:
        print(f"Error: Commit {commit_sha} not found", file=sys.stderr)
        return False

    expected_author = results.get("commit_author")
    actual_author = commit_data.get("author", {}).get("login")
    # fallback: commit.author.name
    if not actual_author:
        actual_author = commit_data.get("commit", {}).get("author", {}).get("name")

    if expected_author != actual_author:
        print(f"Error: Author mismatch - Expected: {expected_author}, Actual: {actual_author}", file=sys.stderr)
        return False

    commit_date = results.get("commit_date", "")
    if not re.match(CONFIG["VERIFICATION_CHECKS"]["DATE_FORMAT"], commit_date):
        print(f"Error: Invalid date format: {commit_date}. Expected: {CONFIG['VERIFICATION_CHECKS']['DATE_FORMAT']}", file=sys.stderr)
        return False

    return True

def verify_parameter_changes(results: Dict) -> bool:
    param_changes = results.get("parameter_changes", {})
    required_params = CONFIG["PARAMETER_VALIDATION"]["REQUIRED_PARAMETERS"]

    for param in required_params:
        if param not in param_changes:
            print(f"Error: Missing parameter change data for: {param}", file=sys.stderr)
            return False
        change = param_changes[param]
        for field in ["before", "after", "line_number"]:
            if field not in change:
                print(f"Error: Missing {field} for parameter: {param}", file=sys.stderr)
                return False

    mode = CONFIG["PARAMETER_VALIDATION"]["VALIDATION_MODE"]
    if mode == "exact":
        for param, expected in CONFIG["PARAMETER_VALIDATION"]["EXPECTED_VALUES"].items():
            actual = param_changes.get(param, {})
            if actual.get("before") != expected["before"] or actual.get("after") != expected["after"]:
                print(f"Error: {param} value mismatch - Expected {expected['before']}→{expected['after']}, Got {actual.get('before')}→{actual.get('after')}", file=sys.stderr)
                return False
    elif mode == "any":
        for param in required_params:
            actual = param_changes.get(param, {})
            if actual.get("before") == actual.get("after"):
                print(f"Error: No change detected for {param}", file=sys.stderr)
                return False
    elif mode == "range":
        range_config = json.loads(CONFIG["PARAMETER_VALIDATION"]["RANGE_CONFIG"])
        for param, ranges in range_config.items():
            actual = param_changes.get(param, {})
            before_val = actual.get("before")
            if before_val is None or not (ranges["min_before"] <= before_val <= ranges["max_before"]):
                print(f"Error: {param} before value {before_val} not in range {ranges['min_before']}-{ranges['max_before']}", file=sys.stderr)
                return False
    else:
        print(f"Unknown validation mode: {mode}", file=sys.stderr)
        return False

    return True

def get_relevant_issues(token: Optional[str], owner: str, repo: str, mock: bool=False) -> Set[int]:
    keywords = CONFIG["ISSUE_SEARCH"]["KEYWORDS"]
    include_pr = CONFIG["ISSUE_SEARCH"]["INCLUDE_PR"].lower() == "true"
    issues = set()
    page = 1
    while True:
        success, data = github_api_request(f"issues?state=all&per_page=100&page={page}", token, owner, repo, mock=mock)
        if not success or not data:
            break
        # data expected to be a list
        for item in data:
            if not include_pr and "pull_request" in item:
                continue
            number = item.get("number")
            text = (item.get("title", "") + " " + (item.get("body") or "")).lower()
            for kw in keywords:
                if kw.lower() in text:
                    issues.add(number)
                    break
        if isinstance(data, list) and len(data) < 100:
            break
        page += 1
    return issues

def verify_issues(results: Dict, token: Optional[str], owner: str, repo: str, mock: bool=False) -> bool:
    issue_list = results.get("related_issue_number_list", [])
    if not isinstance(issue_list, list):
        print("Error: related_issue_number_list must be a list", file=sys.stderr)
        return False
    if len(issue_list) == 0 and not CONFIG["ISSUE_SEARCH"]["ALLOW_EMPTY_ISSUES"].lower() == "true":
        print("Error: related_issue_number_list cannot be empty", file=sys.stderr)
        return False

    keywords = CONFIG["ISSUE_SEARCH"]["KEYWORDS"]
    for issue_num in issue_list:
        if not isinstance(issue_num, int) or issue_num <= 0:
            print(f"Error: Invalid issue number: {issue_num}", file=sys.stderr)
            return False
        success, issue_data = github_api_request(f"issues/{issue_num}", token, owner, repo, mock=mock)
        if not success or not issue_data:
            print(f"Error: Issue #{issue_num} not found", file=sys.stderr)
            return False
        text = (issue_data.get("title", "") + " " + (issue_data.get("body") or "")).lower()
        if not any(kw.lower() in text for kw in keywords):
            print(f"Error: Issue #{issue_num} missing keywords: {keywords}", file=sys.stderr)
            return False

    expected_issues = get_relevant_issues(token, owner, repo, mock=mock)
    provided_issues = set(issue_list)
    if provided_issues != expected_issues:
        missing = expected_issues - provided_issues
        extra = provided_issues - expected_issues
        if missing:
            print(f"Error: Missing issues: {missing}", file=sys.stderr)
        if extra:
            print(f"Error: Extra issues: {extra}", file=sys.stderr)
        if CONFIG["ISSUE_SEARCH"]["STRICT_ISSUE_MATCH"].lower() == "true":
            return False

    return True

# -----------------------------
# 主流程
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="示例验证脚本（基于模板）。使用 --mock 可以本地运行（无需 GitHub token）。")
    parser.add_argument("--mock", action="store_true", help="启用 mock 模式（本地测试，不调用 GitHub）")
    args = parser.parse_args()

    mock = args.mock
    token, owner, repo = get_github_credentials()

    # 如果没有 token 且未显式指定 mock，则提示并自动切换为 mock 模式以便演示
    if not token and not mock:
        print("Warning: 未检测到 GitHub token（环境变量 MCP_GITHUB_TOKEN 未设置）。自动切换到 --mock 模式以便演示。", file=sys.stderr)
        mock = True

    if not mock and requests is None:
        print("Error: requests 模块未安装且未启用 --mock 模式。请 pip install requests 或使用 --mock。", file=sys.stderr)
        sys.exit(1)

    print("🔍 Starting GitHub configuration analysis verification...")
    all_passed = True
    results = load_analysis_results(token, owner, repo, mock=mock)
    if not results:
        print("Error: analysis file not found or invalid", file=sys.stderr)
        sys.exit(1)
    print("✅ Loaded analysis results")

    if CONFIG["VERIFICATION_CHECKS"]["VERIFY_COMMIT"].lower() == "true":
        print("2. Verifying commit data...")
        if not verify_commit_data(results, token, owner, repo, mock=mock):
            all_passed = False
        else:
            print("✅ Commit data verified")

    if CONFIG["VERIFICATION_CHECKS"]["VERIFY_PARAMETERS"].lower() == "true":
        print("3. Verifying parameter changes...")
        if not verify_parameter_changes(results):
            all_passed = False
        else:
            print("✅ Parameter changes verified")

    if CONFIG["VERIFICATION_CHECKS"]["VERIFY_ISSUES"].lower() == "true":
        print("4. Verifying related issues...")
        if not verify_issues(results, token, owner, repo, mock=mock):
            all_passed = False
        else:
            print("✅ Related issues verified")

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All verification checks passed!")
        sys.exit(0)
    else:
        print("❌ Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
