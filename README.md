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
| 10047-10050 | 生成服务（ComfyUI/vLLM/CosyVoice/Wan2.1） | 127.0.0.1，**与短剧平台共享** |

生成服务复用自 `/data/liyangyang/ai_drama`，启动一次即可供两项目用：

```bash
bash scripts/start_gen_services.sh   # 启动 4 个生成服务
bash scripts/start.sh                # 启动本项目前后端
bash scripts/status.sh               # 健康检查
bash scripts/stop.sh                 # 停止本项目（不动生成服务）
```

## 使用流程

1. 「产品档案」→ 新建产品：名称 + 卖点（；分隔）+ 目标市场 + 上传产品图
2. 点「批量生成视频」→ 选平台/语言/变体数/音色 → 建议选"先审脚本再制作"
3. 「脚本审阅」→ 检查 hook/台词/大字幕，查看合规标记，可改可重写
4. 点「开始制作全部」→「生产监控」看实时进度
5. 「成片库」播放/单条下载/整包 zip

## 流水线

```
产品卖点 → LLM批量脚本(JSON) → 合规预检(LLM)
  → 素材: scene=SDXL场景图+Wan2.1视频 / product=产品图Ken Burns / card=文字卡
  → CosyVoice 多语言配音(英/日)
  → FFmpeg: 音画对齐+大字幕+口播字幕烧录 → 成片 + zip
```

## 环境

- 后端：`/data/liyangyang/qwen35_env`（复用，fastapi/uvicorn/httpx/Pillow）
- 前端：node18 + vite，dist 由 python http.server 托管
- 生成服务环境见 `/data/liyangyang/ai_drama/README.md`

## 耗时参考（实测）

| 项 | 耗时 |
|---|---|
| 单条脚本（含合规） | ~2 分钟（4 并发） |
| SDXL 场景图 | ~10 秒/张 |
| Wan2.1 场景片段（4s） | ~8-9 分钟/个（GPU0） |
| 配音 | ~5 秒/句 |
| 1 条 6 镜头成片（含 2-3 个 AI 场景） | ~25-35 分钟 |

## 双引擎规划

当前全部走本地模型（Wan2.1/Qwen3.5-9B/SDXL/CosyVoice）。百炼 Model Router Key 发放后，后端将抽象 Provider：LLM→qwen3.7-max、视频→wan2.7-t2v、配音→qwen3-tts，一行配置切换，满足"核心 AI 能力调用百炼"的赛事要求。

## 样品计划

蓝牙耳机（3C）/ 保温杯（家居）/ 宠物用品 —— 每品类产出 英语+日语 × TikTok/Shorts 多条成片，用于 Idea 文档附件和演示视频。

## 百炼 Provider 切换（Key 发放后操作）

切换层已预留好，Key 到手后**二选一**操作：

### 方式一：改配置文件（推荐）
编辑 `/data/liyangyang/crossborder_video/backend/providers.json`：
```json
{
  "bailian_api_key": "填你的Key",
  "providers": { "llm": "bailian", "image": "bailian", "video": "bailian", "tts": "bailian" }
}
```
重启后端：`bash scripts/stop.sh && bash scripts/start.sh backend`

### 方式二：调 API（免重启）
```bash
curl -X POST http://127.0.0.1:10046/api/config/providers \
  -H "Content-Type: application/json" \
  -d '{"bailian_api_key":"填你的Key","providers":{"llm":"bailian","video":"bailian","image":"bailian","tts":"bailian"}}'
```

- 可按模块混合：例如只切 `"video":"bailian"`（wan2.7-t2v），其余保持本地
- 查看当前配置：`curl http://127.0.0.1:10046/api/config/providers`
- 模型名在 providers.json 的 `bailian_models` 里改（默认 qwen3.7-max / wan2.7-image-pro / wan2.7-t2v / qwen3-tts-instruct-flash）
- ⚠️ 百炼的视频/语音端点按 OpenAI 兼容惯例预写（`backend/app/providers.py` 的 `bailian_video`/`bailian_tts`），Key 到手后请对照《Model Router API 完整文档》核对一次端点路径与字段

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

## 运维操作手册（2026-07-19 更新）

### 停止全部服务并释放显存

```bash
# 1. 按端口杀进程（10045-10050）
ss -tlnp | grep -E ":1004[5-9]|:10050" | grep -oP 'pid=\K[0-9]+' | sort -u | xargs -r kill -9

# 2. 补杀可能残留的生成进程
ps aux | grep "[g]enerate.py" | awk '{print $2}' | xargs -r kill -9

# 3. 检查是否有 vLLM 引擎子进程残留（杀父进程后 EngineCore 可能存活）
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
# 若有大显存进程属于我们（vLLM ~21G），单独 kill -9 <pid>
```

或使用现成脚本：
```bash
bash /data/liyangyang/crossborder_video/scripts/stop.sh          # 只停本项目前后端(10045/10046)
bash /data/liyangyang/ai_drama/scripts/stop_all.sh               # 停全部含生成服务
```

### 重启全部服务

```bash
# 1. 先起生成服务（LLM/TTS 模型加载需 1-3 分钟）
bash /data/liyangyang/crossborder_video/scripts/start_gen_services.sh

# 2. 再起本项目前后端
bash /data/liyangyang/crossborder_video/scripts/start.sh

# 3. 健康检查（llm/comfy/video/tts 全 true 才算就绪）
bash /data/liyangyang/crossborder_video/scripts/status.sh
```

### 端口与显存分布速查

| 端口 | 服务 | GPU | 显存 |
|---|---|---|---|
| 10045 | 前端静态站 | - | - |
| 10046 | 业务后端 | - | - |
| 10047 | ComfyUI SDXL | GPU1 | ~7G（按需加载） |
| 10048 | vLLM Qwen3.5-9B | GPU1 | ~21G 常驻 |
| 10049 | CosyVoice TTS | GPU1 | ~4G（按需） |
| 10050 | Wan2.1 视频服务 | 生成跑 GPU0 | ~10G/任务 |

### 注意事项

1. **vLLM 引擎残留**：杀 10048 监听进程后，其 EngineCore 子进程（占 ~21G）可能存活，需用 nvidia-smi 确认后单独 kill
2. **GPU0 勿动他人进程**：GPU0 上的 veyforge（~12.8G）和 isaac-sim（~9.5G）是其他项目的，不要 kill
3. **pkill 自杀陷阱**：`pkill -f "xxx"` 与启动命令写在同一条命令里时，若命令串包含匹配文本会杀掉自身——pkill 和启动必须分开执行
4. **后台进程防杀**：所有服务必须用 `setsid ... &` 启动，否则终端会话结束时会被连带杀掉
5. **视频生成断点**：任务中途被杀后，重新 `POST /api/jobs/{jid}/produce` 即可续跑（已完成的视频/镜头会跳过，未完成的镜头会重新生成）
