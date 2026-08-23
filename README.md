# 跨境爆品短视频工厂

AI+跨境黑客松参赛作品（场景二 · AI 社媒营销 → AI 短视频批量生产）。

**一句话**：输入产品卖点和目标市场，一键批量产出适配 TikTok / YouTube Shorts / Reels 的带货短视频（脚本+配音+字幕+成片）。

**访问地址**：`http://36.212.51.4:10045`（API：`http://36.212.51.4:10046/docs`）

## 核心功能

1. **批量脚本**：每产品一次产出 N 条不同切入角度的脚本（功能卖点/场景痛点/促销/社交证明），按平台语气区分
2. **多语言本地化**：英语/日语脚本+配音+字幕同步生成（本地化重写而非翻译）
3. **产品保真混合剪辑**：AI 生成氛围场景 + 卖家真实产品图运镜（Ken Burns）+ 卖点字幕卡，杜绝 AI"货不对板"
4. **合规预检**：LLM 扫描脚本违禁词（绝对化用语/医疗宣称/日本药机法等）并给改写建议
5. **平台适配**：9:16 竖屏，按 TikTok/Shorts/Reels 输出不同字幕样式与发布文案

## 架构与端口

| 端口 | 服务 | 绑定 |
|---|---|---|
| 10045 | 前端 | 0.0.0.0 |
| 10046 | 业务后端 | 0.0.0.0 |

**当前为纯云端模式**：全部 AI 能力走阿里云百炼 Token Plan（菜鸟黑客松专属），无需本地 GPU 生成服务：

| 能力 | 模型 | 端点 |
|---|---|---|
| 脚本/合规 LLM | qwen3.7-plus | OpenAI 兼容 `/compatible-mode/v1/chat/completions` |
| 场景图 | qwen-image-2.0 | `/api/v1/services/aigc/multimodal-generation/generation` |
| 场景视频 | happyhorse-1.1-t2v | `/api/v1/services/aigc/video-generation/video-synthesis`（异步轮询） |
| 多语言配音 | qwen-audio-3.0-tts-plus | `/api/v1/services/audio/tts/SpeechSynthesizer` |

启动：

```bash
bash scripts/start.sh                # 启动本项目前后端（10045/10046）
bash scripts/status.sh               # 健康检查（bailian: true 即云端就绪）
bash scripts/stop.sh                 # 停止本项目
```

如需切回本地模型（vLLM/ComfyUI/Wan2.1/CosyVoice，与短剧平台共享 10047-10050），见下文「Provider 切换」。

## 使用流程

1. 「产品档案」→ 新建产品：名称 + 卖点（；分隔）+ 目标市场 + 上传产品图
2. 点「批量生成视频」→ 选平台/语言/变体数/音色 → 建议选"先审脚本再制作"
3. 「脚本审阅」→ 检查 hook/台词/大字幕，查看合规标记，可改可重写
4. 点「开始制作全部」→「生产监控」看实时进度
5. 「成片库」播放/单条下载/整包 zip

## 流水线

```
产品卖点 → LLM批量脚本(JSON) → 合规预检(LLM)          [Token Plan qwen3.7-plus]
  → 素材: scene=qwen-image-2.0场景图+happyhorse-1.1-t2v视频 / product=产品图Ken Burns / card=文字卡
  → qwen-audio-3.0-tts-plus 多语言配音(英/日)
  → FFmpeg: 音画对齐+大字幕+口播字幕烧录 → 成片 + zip
```

## 环境

- 后端：`/data/liyangyang/qwen35_env`（复用，fastapi/uvicorn/httpx/Pillow）
- 前端：node18 + vite，dist 由 python http.server 托管
- AI 能力：百炼 Token Plan 专属 API Key（配置见下文）

## 耗时参考（Token Plan 云端实测）

| 项 | 耗时 |
|---|---|
| 单条脚本（含合规） | ~1-2 分钟 |
| qwen-image-2.0 场景图 | ~30-60 秒/张 |
| happyhorse-1.1-t2v 场景片段（5s） | ~90 秒/个 |
| 配音 | ~3 秒/句 |
| 1 条 5 镜头成片（含 2 个 AI 场景） | ~4-6 分钟 |

## Token Plan 配置（当前模式）

Token Plan 专属 API Key（`sk-sp-` 开头）已配置在 `backend/providers.json`：

```json
{
  "bailian_api_key": "sk-sp-***",
  "bailian_base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
  "providers": { "llm": "bailian", "image": "bailian", "video": "bailian", "tts": "bailian" },
  "bailian_models": {
    "llm": "qwen3.7-plus",
    "image": "qwen-image-2.0",
    "video": "happyhorse-1.1-t2v",
    "tts": "qwen-audio-3.0-tts-plus"
  }
}
```

说明：
- LLM 走 OpenAI 兼容 `/chat/completions`；图像/视频/语音走同域名 `/api/v1` 原生端点（`providers.py` 自动推导，无需另配）
- 模型可换成 Token Plan 支持的其他模型：qwen3.8-max / deepseek-v4-pro / kimi-k2.6 / glm-5.2 / wan2.7-image-pro / happyhorse-1.1-i2v 等
- ⚠️ Token Plan Key 必须配专属基地址（`token-plan.cn-beijing.maas.aliyuncs.com`），用百炼通用地址不抵扣套餐额度
- ⚠️ Key 已写入 `providers.json`，请勿提交到公开仓库

## Provider 切换（云端/本地混合）

`backend/providers.json` 中 `providers` 的每一项可独立设 `"bailian"` 或 `"local"`，改完重启后端生效；也可免重启热切换：

```bash
curl -X POST http://127.0.0.1:10046/api/config/providers \
  -H "Content-Type: application/json" \
  -d '{"providers":{"llm":"local","video":"bailian"}}'
curl http://127.0.0.1:10046/api/config/providers   # 查看当前配置
```

切回本地需先启动生成服务：`bash scripts/start_gen_services.sh`（10047-10050，与短剧平台共享）。

## 样品计划

蓝牙耳机（3C）/ 保温杯（家居）/ 宠物用品 —— 每品类产出 英语+日语 × TikTok/Shorts 多条成片，用于 Idea 文档附件和演示视频。

## 样片清单（Idea 文档演示材料）

| 品类 | 语言 | 时长 | 路径 |
|---|---|---|---|
| 蓝牙耳机 | 英语 | 26.2s | output/jobs/078ff3e9b5/078ff3e9b5_tien1/final.mp4 |
| 蓝牙耳机 | 日语 | 22.0s | output/jobs/078ff3e9b5/078ff3e9b5_tija1/final.mp4 |
| 蓝牙耳机 v2 | 英语 | 23.3s / 18.4s | output/jobs/f4fa24bb58/*/final.mp4 |
| 保温杯 | 英语 | 21.2s | output/jobs/4c5e25b4b4/4c5e25b4b4_tien1/final.mp4 |
| 保温杯 | 日语 | 18.2s | output/jobs/4c5e25b4b4/4c5e25b4b4_tija1/final.mp4 |
| 宠物梳 | 英语 | 18.5s | output/jobs/1f8c4c78f0/1f8c4c78f0_tien1/final.mp4 |
| 宠物梳 | 日语 | 16.2s | output/jobs/1f8c4c78f0/1f8c4c78f0_tija1/final.mp4 |

在线播放：前端「批量任务」→ 对应任务 →「成片库」。

---

## 运维操作手册（2026-08-23 更新：纯云端模式）

### 停止 / 重启

```bash
bash /data/liyangyang/ai_crossborder/scripts/stop.sh    # 停前后端(10045/10046)
bash /data/liyangyang/ai_crossborder/scripts/start.sh   # 起前后端
bash /data/liyangyang/ai_crossborder/scripts/status.sh  # 健康检查（bailian: true 即云端就绪）
```

纯云端模式下无需本地 GPU 服务。若切回 local 模式，旧本地生成服务（ComfyUI:10047 / vLLM:10048 / CosyVoice:10049 / Wan2.1:10050，与短剧平台共享）由 `/data/liyangyang/ai_drama/scripts/start_all.sh` 管理；杀 vLLM 后需用 `nvidia-smi` 确认 EngineCore 子进程已退出（否则 ~21G 显存残留）。

### 注意事项

1. **GPU0 勿动他人进程**：GPU0 上的 veyforge（~12.8G）和 isaac-sim（~9.5G）是其他项目的，不要 kill
2. **pkill 自杀陷阱**：`pkill -f "xxx"` 与启动命令写在同一条命令里时，若命令串包含匹配文本会杀掉自身——pkill 和启动必须分开执行
3. **后台进程防杀**：所有服务必须用 `setsid ... &` 启动，否则终端会话结束时会被连带杀掉
4. **视频生成断点**：任务中途被杀后，重新 `POST /api/jobs/{jid}/produce` 即可续跑（已完成的视频/镜头会跳过，未完成的镜头会重新生成）
5. **Token Plan 额度**：图像/视频按次扣 Credits，重度调试前先小量验证；Key 泄露需立即在控制台重置
