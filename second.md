**作品要求：** 作品需具备可演示的核心功能，能够呈现完整或基本完整的业务流程。不一定需要达到正式商业产品标准，但应能够证明方案可实现、可使用、具有业务价值。

**📁 需提交：**

* 可运行的产品 Demo 或核心功能原型
* 产品功能与使用说明
* 技术架构及调用模型的使用说明
* GitCode 等可访问的代码仓库地址
* 产品演示视频
* 测试账号或体验地址（如适用）
* 项目开发及阶段成果说明

---

# 跨境爆品短视频工厂 · 复赛提交材料

## 一、可运行的产品 Demo

- **产品体验地址**：http://36.212.51.4:10045 （浏览器直接打开，无需登录）
- **API 接口文档**：http://36.212.51.4:10046/docs （FastAPI 自动生成的 Swagger 交互式文档，可在线调试）

Demo 已实现「产品录入 → AI 批量生成脚本 → 合规预检 → AI 素材生成 → 自动剪辑合成 → 成片下载」的完整业务闭环，全部 AI 能力均通过菜鸟黑客松 Token Plan 专属 API Key 调用阿里云百炼云端大模型完成，可直接在线体验全流程。

## 二、产品功能与使用说明

**一句话介绍**：输入产品卖点和目标市场，一键批量产出适配 TikTok / YouTube Shorts / Instagram Reels 的多语言带货短视频（脚本 + 配音 + 字幕 + 成片）。

**核心功能**：

1. **批量脚本生成**：每个产品一次产出 N 条不同切入角度的脚本（功能卖点/场景痛点/促销/社交证明），按平台语气差异化
2. **多语言本地化**：英语/日语脚本、配音、字幕同步生成（本地化重写而非直译）
3. **产品保真混合剪辑**：AI 生成氛围场景视频 + 卖家真实产品图运镜（Ken Burns）+ 卖点字幕卡，杜绝 AI「货不对板」
4. **合规预检**：LLM 自动扫描脚本违禁词（绝对化用语/医疗宣称/日本药机法等）并给出改写建议
5. **平台适配**：9:16 竖屏，按 TikTok / Shorts / Reels 输出不同字幕样式与发布文案
6. **生产监控**：WebSocket 实时推送每条视频每个镜头的生成进度

**使用流程**（约 5 分钟出一批成片）：

1. 「产品档案」→ 新建产品：填写名称 + 卖点（；分隔）+ 目标市场 + 上传产品图
2. 点「批量生成视频」→ 选平台/语言/变体数/音色 → 可选「先审脚本再制作」或「全自动一键出片」
3. 「脚本审阅」→ 检查 hook/台词/大字幕，查看合规标记，可手动修改或让 AI 重写
4. 点「开始制作全部」→「生产监控」看实时进度
5. 「成片库」在线播放 / 单条下载 / 整包 zip 下载

## 三、技术架构及调用模型的使用说明

**整体架构**：Vue 3 + Vite 前端（10045 端口） ↔ FastAPI 业务后端（10046 端口，SQLite 存储，FFmpeg 合成） ↔ 阿里云百炼 Token Plan 云端模型。

**AI 能力调用说明（全部走菜鸟黑客松 Token Plan 专属通道）**：

| 能力环节 | 调用模型 | 接入方式 |
|---|---|---|
| 短视频脚本生成 + 广告合规预检 | qwen3.7-plus | OpenAI 兼容协议 `POST /compatible-mode/v1/chat/completions`（JSON 结构化输出） |
| AI 场景图生成 | qwen-image-2.0 | 原生端点 `POST /api/v1/services/aigc/multimodal-generation/generation` |
| AI 场景视频生成（文生视频） | happyhorse-1.1-t2v | 原生异步端点 `POST /api/v1/services/aigc/video-generation/video-synthesis`，轮询 `/api/v1/tasks/{task_id}` 取回成片片段 |
| 多语言配音（英/日/中） | qwen-audio-3.0-tts-plus | 原生端点 `POST /api/v1/services/audio/tts/SpeechSynthesizer` |

- 专属基地址：`https://token-plan.cn-beijing.maas.aliyuncs.com`，请求头 `Authorization: Bearer <Token Plan API Key>`
- 后端设计了 Provider 抽象层（`backend/app/providers.py`），每项能力可在「云端百炼 / 本地模型」间按模块独立切换，配置见 `backend/providers.json`
- 视频合成：FFmpeg 完成音画对齐、大字幕与口播字幕烧录、多片段拼接，最终输出 9:16 成片与打包 zip

**流水线**：

```
产品卖点 → LLM批量脚本(JSON) → 合规预检(LLM)          [qwen3.7-plus]
  → 素材: scene=qwen-image-2.0场景图 + happyhorse-1.1-t2v场景视频 / product=产品图Ken Burns运镜 / card=文字卡
  → qwen-audio-3.0-tts-plus 多语言配音
  → FFmpeg: 音画对齐 + 大字幕 + 口播字幕烧录 → 成片 + zip
```

## 四、代码仓库地址

- GitCode（评委可访问的脱敏镜像）：**见下方附录说明**
- GitHub 主仓库：https://github.com/lyy-ai/ai_crossborder
- 说明：仓库结构为 `backend/`（FastAPI 后端）、`frontend/`（Vue 3 前端）、`scripts/`（一键启动/停止/健康检查脚本）、`workflows/`（本地绘图工作流模板），完整部署与运维说明见仓库 `README.md`。

## 五、产品演示视频

- 演示视频文件：`/data/liyangyang/ai_crossborder/output/jobs/48ccbed021/48ccbed021_tien1/final.mp4`（29.7 秒，TikTok 英文版保温杯带货成片，AI 全自动生成）
- 在线观看：打开 http://36.212.51.4:10045 →「批量任务」→ 对应任务 →「成片库」直接播放；同任务下还有变体 2（`48ccbed021_tien2`）可对比不同切入角度

## 六、测试账号 / 体验地址

- 体验地址：http://36.212.51.4:10045
- **无需账号**，开放访问，直接创建产品即可体验全流程

## 七、项目开发及阶段成果说明

**开发过程**：

1. **初赛阶段**：完成 FastAPI + Vue 3 全栈骨架、Provider 双引擎抽象层、FFmpeg 自动剪辑合成管线，打通「脚本→素材→成片」全流程
2. **云端切换**：获得 Token Plan 专属 API Key 后，将 LLM / 文生图 / 文生视频 / 语音合成四项核心 AI 能力全部切换至百炼云端（实测验证 OpenAI 兼容对话、原生多模态生成、异步视频任务轮询、TTS 语音合成四类端点），摆脱本地 GPU 依赖
3. **端到端实测**：用 AI 生成的产品图创建测试产品（蓝牙耳机/保温杯），完成多轮「产品录入 → 脚本+合规 → 场景视频 → 配音 → 成片」全流程验证，单条 5 镜头成片约 4-6 分钟产出

**阶段成果**：

- 可在线体验的完整产品 Demo（http://36.212.51.4:10045）
- 多条 AI 全自动生成的带货成片（英文/日语 × TikTok，单条约 25-30 秒）
- 全部核心 AI 能力调用百炼 Token Plan 大模型，满足赛事要求
- 支持批量、多平台、多语言、多变体并行生产，具备真实跨境电商营销业务价值

---

## 附：代码仓库可访问性说明

GitHub 主仓库 https://github.com/lyy-ai/ai_crossborder 当前为 private（内含 Token Plan API Key，不宜直接公开）。为保证评委可访问代码，已在 GitCode 建立**脱敏镜像仓库**（剔除含密钥的 `providers.json` 配置文件，仅保留 `providers.example.json` 模板），提交材料以 GitCode 地址为准。
