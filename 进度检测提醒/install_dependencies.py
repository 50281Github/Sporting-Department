#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import sys
import os

REQUIREMENTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'requirements.txt')
PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

def read_requirements(path: str) -> list[str]:
    """读取 requirements.txt，跳过空行与注释"""
    reqs: list[str] = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                reqs.append(s)
    except FileNotFoundError:
        print(f"错误: 未找到依赖文件: {path}")
        sys.exit(1)
    return reqs

def run_and_stream(command: list[str]) -> int:
    """以流式方式运行命令，实时打印输出"""
    print("\n--- 命令 ---")
    print(' '.join(command))
    print("--------------\n")
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ''):
        if not line and proc.poll() is not None:
            break
        if line:
            print(line, end='')
    return proc.wait()

def check_python_and_pip():
    """检查 Python 和 pip 是否安装"""
    print("正在检查 Python 环境...")
    try:
        subprocess.run([sys.executable, "--version"], check=True, capture_output=True)
        print(f"Python 已安装: {sys.version.splitlines()[0]}")
    except subprocess.CalledProcessError:
        print("错误: 未检测到 Python。请先安装 Python。")
        sys.exit(1)

    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, capture_output=True)
        print("pip 已安装。")
    except subprocess.CalledProcessError:
        print("错误: 未检测到 pip。请确保 pip 已正确安装并配置到 PATH。")
        sys.exit(1)

def install_dependencies():
    """逐包安装 requirements.txt 中列出的依赖，并实时展示进度"""
    if not os.path.exists(REQUIREMENTS_FILE):
        print(f"错误: 未找到依赖文件: {REQUIREMENTS_FILE}")
        sys.exit(1)

    reqs = read_requirements(REQUIREMENTS_FILE)
    if not reqs:
        print("提示: requirements.txt 为空或无有效依赖。")
        return

    print(f"正在安装依赖 (使用清华源: {PIP_MIRROR})...\n")

    successes: list[str] = []
    failures: list[str] = []
    total = len(reqs)

    for i, spec in enumerate(reqs, start=1):
        print(f"==== [{i}/{total}] 开始安装: {spec} ====")
        cmd = [
            sys.executable, "-m", "pip", "install",
            spec,
            "-i", PIP_MIRROR,
            "--trusted-host", "pypi.tuna.tsinghua.edu.cn"
        ]
        code = run_and_stream(cmd)
        if code == 0:
            print(f"==== [{i}/{total}] 安装成功: {spec} ====")
            successes.append(spec)
        else:
            print(f"==== [{i}/{total}] 安装失败: {spec} (退出码: {code}) ====")
            failures.append(spec)

    print("\n安装完成汇总:")
    print(f"- 成功 {len(successes)}/{total}")
    if successes:
        print("  成功包: " + ", ".join(successes))
    print(f"- 失败 {len(failures)}/{total}")
    if failures:
        print("  失败包: " + ", ".join(failures))

if __name__ == "__main__":
    check_python_and_pip()
    install_dependencies()
    print("\n环境检查与依赖安装完成。")
    # 保持程序运行，等待用户手动关闭
    try:
        input("\n安装流程已结束。按 Enter 键关闭程序...")
    except KeyboardInterrupt:
        pass