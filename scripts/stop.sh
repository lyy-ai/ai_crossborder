#!/bin/bash
# 停止本项目前后端（不动共享生成服务）
ss -tlnp 2>/dev/null | grep -E ":10045 |:10046 " | grep -oP 'pid=\K[0-9]+' | xargs -r kill -9
echo "已停止 10045/10046"
