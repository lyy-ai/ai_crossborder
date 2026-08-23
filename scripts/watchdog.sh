#!/bin/bash
# 看门狗：检测 10045/10046，掉了自动拉起
# 安装: bash scripts/watchdog.sh install   (写入 crontab，每分钟检查)
# 手动: bash scripts/watchdog.sh check     (立即检查一次)
# 卸载: bash scripts/watchdog.sh uninstall

ROOT=/data/liyangyang/ai_crossborder
MARK=$ROOT/logs/.watchdog

check() {
  if ! curl -s -m 5 -o /dev/null http://127.0.0.1:10046/api/health/services; then
    echo "$(date '+%F %T') backend down, restarting" >> $ROOT/logs/watchdog.log
    bash $ROOT/scripts/start.sh backend >> $ROOT/logs/watchdog.log 2>&1
  fi
  if ! curl -s -m 5 -o /dev/null http://127.0.0.1:10045/; then
    echo "$(date '+%F %T') frontend down, restarting" >> $ROOT/logs/watchdog.log
    bash $ROOT/scripts/start.sh frontend >> $ROOT/logs/watchdog.log 2>&1
  fi
}

case "${1:-check}" in
  check) check ;;
  install)
    mkdir -p $ROOT/logs
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
