#!/bin/bash
# 跨境爆品短视频工厂 一键启动（setsid 脱离进程组）
# 用法: bash /data/liyangyang/crossborder_video/scripts/start.sh [backend|frontend|all]
# 注意: 生成服务(10047-10050)由 scripts/start_gen_services.sh 管理（与短剧平台共享）

ROOT=/data/liyangyang/crossborder_video
QWEN_ENV=/data/liyangyang/qwen35_env
LOGS=$ROOT/logs
mkdir -p $LOGS

start_backend() {
  echo "[start] 业务后端 0.0.0.0:10046"
  cd $ROOT/backend
  setsid $QWEN_ENV/bin/uvicorn app.main:app --host 0.0.0.0 --port 10046 \
    > $LOGS/backend.log 2>&1 < /dev/null &
}

start_frontend() {
  echo "[start] 前端 0.0.0.0:10045"
  setsid $QWEN_ENV/bin/python -m http.server 10045 --bind 0.0.0.0 \
    --directory $ROOT/frontend/dist > $LOGS/frontend.log 2>&1 < /dev/null &
}

case "${1:-all}" in
  backend) start_backend ;;
  frontend) start_frontend ;;
  all) start_backend; start_frontend ;;
  *) echo "未知: $1"; exit 1 ;;
esac
