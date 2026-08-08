#!/bin/bash
# 启动共享生成服务（LLM/ComfyUI/TTS/Video，10047-10050）
# 这些服务与 /data/liyangyang/ai_drama 短剧平台共享，只需启动一次
bash /data/liyangyang/ai_drama/scripts/start_all.sh llm
bash /data/liyangyang/ai_drama/scripts/start_all.sh comfy
bash /data/liyangyang/ai_drama/scripts/start_all.sh tts
bash /data/liyangyang/ai_drama/scripts/start_all.sh video
echo "生成服务已启动（LLM/TTS 模型加载需 1-3 分钟）"
