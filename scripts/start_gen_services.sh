#!/bin/bash
# 启动共享生成服务（LLM/ComfyUI/TTS/Video，10047-10050）
# 这些服务与 /data/liyangyang/ai_drama 短剧平台共享，只需启动一次
bash /data/liyangyang/ai_drama/scripts/start_all.sh llm
bash /data/liyangyang/ai_drama/scripts/start_all.sh comfy
bash /data/liyangyang/ai_drama/scripts/start_all.sh video
# TTS (CosyVoice)：ai_drama start_all.sh 无此项，单独启动
cd /data/liyangyang/ai_drama/services/tts
setsid env CUDA_VISIBLE_DEVICES=1 \
  ./venv/bin/uvicorn server:app --host 127.0.0.1 --port 10049 \
  > /data/liyangyang/ai_drama/logs/tts_service.log 2>&1 < /dev/null &
echo "生成服务已启动（LLM/TTS 模型加载需 1-3 分钟）"
