#!/bin/bash
# 激活 codemate conda 环境

source ~/miniconda3/etc/profile.d/conda.sh
conda activate codemate

echo "✅ 已激活 codemate 环境"
echo "📂 当前目录: $(pwd)"
echo ""
echo "运行项目:"
echo "  cd ~/Desktop/codemate-agent"
echo "  python -m codemate_agent.cli"
