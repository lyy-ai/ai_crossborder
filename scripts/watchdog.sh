#!/bin/bash
# 看门狗：检测 10045/10046（前后端）+ 10047-10050（本地生成服务），掉了自动拉起
# 安装: bash scripts/watchdog.sh install   (写入 crontab，每分钟检查)
# 手动: bash scripts/watchdog.sh check     (立即检查一次)
# 卸载: bash scripts/watchdog.sh uninstall

ROOT=/data/liyangyang/ai_crossborder
DRAMA=/data/liyangyang/ai_drama
MARK=$ROOT/logs/.watchdog
mkdir -p $ROOT/logs

# 冷却：某服务刚拉过 $2 分钟内不再重复拉（vLLM/TTS 加载模型要 1-3 分钟，避免重复启动）
cooldown() {
  local f=$MARK.$1 now=$(date +%s)
  if [ -f "$f" ] && [ $((now - $(cat "$f"))) -lt $(($2 * 60)) ]; then return 1; fi
  echo "$now" > "$f"
  return 0
}

up() { curl -s -m 5 -o /dev/null "$1"; }

check() {
  if ! up http://127.0.0.1:10046/api/health/services; then
    cooldown backend 2 || exit 0
    echo "$(date '+%F %T') backend down, restarting" >> $ROOT/logs/watchdog.log
    bash $ROOT/scripts/start.sh backend >> $ROOT/logs/watchdog.log 2>&1
  fi
  if ! up http://127.0.0.1:10045/; then
    cooldown frontend 2 || exit 0
    echo "$(date '+%F %T') frontend down, restarting" >> $ROOT/logs/watchdog.log
    bash $ROOT/scripts/start.sh frontend >> $ROOT/logs/watchdog.log 2>&1
  fi
  if ! up http://127.0.0.1:10048/v1/models; then
    cooldown llm 6 || exit 0
    echo "$(date '+%F %T') llm down, restarting" >> $ROOT/logs/watchdog.log
    bash $DRAMA/scripts/start_all.sh llm >> $ROOT/logs/watchdog.log 2>&1
  fi
  if ! up http://127.0.0.1:10047/system_stats; then
    cooldown comfy 3 || exit 0
    echo "$(date '+%F %T') comfy down, restarting" >> $ROOT/logs/watchdog.log
    bash $DRAMA/scripts/start_all.sh comfy >> $ROOT/logs/watchdog.log 2>&1
  fi
  if ! up http://127.0.0.1:10050/health; then
    cooldown video 3 || exit 0
    echo "$(date '+%F %T') video down, restarting" >> $ROOT/logs/watchdog.log
    bash $DRAMA/scripts/start_all.sh video >> $ROOT/logs/watchdog.log 2>&1
  fi
  if ! up http://127.0.0.1:10049/health; then
    cooldown tts 6 || exit 0
    echo "$(date '+%F %T') tts down, restarting" >> $ROOT/logs/watchdog.log
    (cd $DRAMA/services/tts && setsid env CUDA_VISIBLE_DEVICES=1 \
      ./venv/bin/uvicorn server:app --host 127.0.0.1 --port 10049 \
      > $DRAMA/logs/tts_service.log 2>&1 < /dev/null &)
  fi
}

case "${1:-check}" in
  check) check ;;
  install)
    (crontab -l 2>/dev/null | grep -v "ai_crossborder/scripts/watchdog.sh"; \
     echo "* * * * * bash $ROOT/scripts/watchdog.sh check >/dev/null 2>&1") | crontab -
    echo "已安装 crontab（每分钟检查一次）："
    crontab -l | grep watchdog
    ;;
  uninstall)
    (crontab -l 2>/dev/null | grep -v "ai_crossborder/scripts/watchdog.sh") | crontab -
    echo "已卸载"
    ;;
  *) echo "用法: $0 [check|install|uninstall]"; exit 1 ;;
esac
