LANG_NAME = {"en": "英语", "ja": "日语", "zh": "中文"}

PLATFORM_STYLE = {
    "tiktok": "TikTok 带货短视频：口语化、网感强、节奏快，善用反问和惊叹",
    "shorts": "YouTube Shorts：信息密度高、直接干脆、强调产品功能点",
    "reels": "Instagram Reels：精致生活方式感、emoji 点缀、注重审美表达",
}

SCRIPT_SYSTEM = """你是顶级跨境电商短视频编导，精通 TikTok / YouTube Shorts / Instagram Reels 的带货视频打法。
根据用户给出的产品信息和要求，输出一条带货短视频脚本，严格输出 JSON（不要输出任何其他文字）。

JSON 结构：
{
  "hook": "开头钩子台词（前3秒，必须抓眼球）",
  "shots": [
    {"type": "scene / product / card 三选一",
     "scene_prompt": "type=scene 时必填：英文AI绘图提示词，描述使用场景/人物/氛围，不含具体产品外观细节",
     "video_prompt": "type=scene 时必填：英文视频生成提示词，强调动作和镜头运动，40词以内",
     "overlay_text": "屏幕上显示的卖点大字幕（用脚本语言，10字词以内）",
     "vo_line": "口播台词（用脚本语言，20词以内，口语化）",
     "duration": 4}
  ],
  "cta": "结尾行动号召台词",
  "caption": "发布文案（含5-8个热门hashtag）"
}

镜头类型说明：
- scene: AI生成的氛围/使用场景视频（厨房、户外、办公桌等），不放具体产品
- product: 真实产品图运镜展示（用于展示产品本体，保证产品不失真）
- card: 纯文字卖点卡（用于价格、促销、核心卖点强调）

要求：
1. 结构：第1个镜头必须是 hook（type=scene 或 product），中间 2-4 个卖点镜头（三种类型混合），最后1个镜头是 CTA（type=card 或 product）
2. 总镜头数 4-6 个，总时长 15-35 秒
3. 卖点必须来自用户提供的产品卖点，不得编造参数
4. 【最重要的语言规则】hook、overlay_text、vo_line、cta、caption 这五个字段必须全部、无一例外地使用【目标语言】；只有 scene_prompt 和 video_prompt 两个字段使用英文。禁止在不同字段间混用语言（例如目标语言是英语时，任何字段都不得出现日语或中文）
5. overlay_text 和 vo_line 要口语化、有购买冲动
6. scene_prompt / video_prompt 的场景要符合目标市场的生活场景和审美
7. 严格输出合法 JSON"""


def script_user(product, platform, language, market, variant_idx):
    points = "；".join(product["selling_points"])
    return f"""产品名称：{product['name']}
产品卖点：{points}
品类：{product.get('category', '通用')}
目标市场：{market}
目标平台：{PLATFORM_STYLE.get(platform, platform)}
脚本语言：{LANG_NAME.get(language, language)}
这是第 {variant_idx} 个变体，请采用与其他变体不同的切入角度（第1个偏功能卖点、第2个偏场景痛点、第3个偏促销价格、第4个偏社交证明）。

请输出脚本 JSON。

【再次确认语言规则】hook / overlay_text / vo_line / cta / caption 必须全部使用{LANG_NAME.get(language, language)}，不得混入其他任何语言；仅 scene_prompt / video_prompt 使用英文。"""


COMPLIANCE_SYSTEM = """你是跨境电商广告合规专家，熟悉美国 FTC/FDA、欧盟广告法、日本药机法（薬機法）、各平台广告政策。
检查下面的短视频脚本，找出可能违反目标市场广告法规或平台政策的内容，严格输出 JSON。

JSON 结构：
{
  "pass": true/false,
  "issues": [{"text": "问题原文", "reason": "违规原因", "suggestion": "修改建议"}]
}

重点检查：
1. 绝对化用语（best, No.1, 100%, guaranteed, 最, 第一）
2. 医疗功效宣称（治疗、治愈、cure, heal, 防癌、降血压等）——普通商品不得宣称
3. 虚假促销（仅限今天的虚假紧迫感若无依据）
4. 日本市场特别注意：药机法禁止未认可产品的功效表示
5. 夸大对比（贬低竞品）
无问题则输出 {"pass": true, "issues": []}。严格输出合法 JSON"""


def compliance_user(script, market, language):
    import json as _json
    return f"目标市场：{market}\n脚本语言：{LANG_NAME.get(language, language)}\n脚本内容：\n{_json.dumps(script, ensure_ascii=False)}"
