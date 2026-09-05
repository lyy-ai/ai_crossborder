import asyncio
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

OUT_ROOT = "/data/liyangyang/ai_crossborder/output"
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_INDEX = 2
VIDEO_SIZE = "480x832"
FPS = 16

# 三平台字幕视觉风格差异化（ASS 颜色格式 &HAABBGGRR）
PLATFORM_SUB_STYLE = {
    # TikTok：白色粗体 + 粗黑描边，画面中部偏下，网感强
    "tiktok": {
        "overlay": dict(size=20, primary="&H00FFFFFF", back="&H80000000", bold=-1,
                        italic=0, border=1, outline=3.0, shadow=0, align=5, margin_v=330),
        "sub": dict(size=12, primary="&H00FFFFFF", back="&H80000000", bold=-1,
                    italic=0, border=1, outline=2.0, shadow=0, align=2, margin_v=28),
    },
    # YouTube Shorts：半透明深色底框包裹文字，极简干净
    "shorts": {
        "overlay": dict(size=16, primary="&H00FFFFFF", back="&H96000000", bold=-1,
                        italic=0, border=3, outline=1.2, shadow=0, align=5, margin_v=300),
        "sub": dict(size=11, primary="&H00FFFFFF", back="&H96000000", bold=0,
                    italic=0, border=3, outline=0.8, shadow=0, align=2, margin_v=24),
    },
    # Instagram Reels：琥珀色精致标题置于顶部，阴影替代描边，字幕斜体
    "reels": {
        "overlay": dict(size=16, primary="&H000B9EF5", back="&H80000000", bold=-1,
                        italic=0, border=1, outline=0.5, shadow=2, align=8, margin_v=60),
        "sub": dict(size=11, primary="&H00FFFFFF", back="&H80000000", bold=0,
                    italic=-1, border=1, outline=1.0, shadow=1, align=2, margin_v=40),
    },
}


async def run(cmd):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{err.decode(errors='ignore')[-600:]}")


async def ffprobe_duration(path):
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    return float(out.decode().strip())


async def kenburns(image, out, dur):
    frames = int(dur * FPS)
    vf = (f"scale=960:1664:force_original_aspect_ratio=decrease,"
          f"pad=960:1664:(ow-iw)/2:(oh-ih)/2:white,"
          f"zoompan=z='min(zoom+0.0018,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={VIDEO_SIZE}:fps={FPS},format=yuv420p")
    await run(["ffmpeg", "-y", "-loop", "1", "-i", image, "-vf", vf,
               "-t", f"{dur:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", out])


def _font(size):
    return ImageFont.truetype(FONT_PATH, size, index=FONT_INDEX)


def _fit_lines(d, text, max_w, size, min_size=20):
    """把 text 按像素宽度换行；若最宽的行仍超宽则整体缩字号直到适配。"""
    while True:
        font = _font(size)
        lines = []
        for para in text.split("\n"):
            cur = ""
            for ch in para:
                if d.textlength(cur + ch, font=font) > max_w and cur:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            lines.append(cur)
        lines = [ln for ln in lines if ln]
        if size <= min_size or all(d.textlength(ln, font=font) <= max_w for ln in lines):
            return font, lines
        size -= 2


def make_card_image(text, path, accent="#4f6ef7", sub=""):
    W, H = 480, 832
    img = Image.new("RGB", (W, H), (17, 19, 28))
    d = ImageDraw.Draw(img)
    d.rectangle([0, H // 2 - 130, W, H // 2 + 130], fill=(24, 27, 40))
    d.rectangle([0, H // 2 - 130, 8, H // 2 + 130], fill=accent)
    # text_card 的 zoompan z=1.05 会裁掉边缘 ~12px/侧，故留足边距
    font, lines = _fit_lines(d, text, W - 100, 44, min_size=24)
    total_h = len(lines) * int(font.size * 1.36)
    y = H // 2 - total_h // 2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=(245, 246, 250))
        y += int(font.size * 1.36)
    if sub:
        sub_font, sub_lines = _fit_lines(d, sub, W - 110, 26, min_size=16)
        y = H // 2 + 150
        for ln in sub_lines[:2]:
            w = d.textlength(ln, font=sub_font)
            d.text(((W - w) / 2, y), ln, font=sub_font, fill=(150, 158, 181))
            y += int(sub_font.size * 1.3)
    img.save(path)


async def text_card(text, out, dur, sub=""):
    if sub:
        sub = textwrap.shorten(sub, width=60, placeholder="…")
    img_path = out + ".png"
    make_card_image(text, img_path, sub=sub)
    frames = int(dur * FPS)
    vf = f"zoompan=z='1.05':d={frames}:s={VIDEO_SIZE}:fps={FPS},format=yuv420p"
    await run(["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-vf", vf,
               "-t", f"{dur:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", out])


async def concat_wavs(wavs, out, gap=0.2, head=0.15):
    parts = []
    for w in wavs:
        parts += ["-i", w]
    sil = "anullsrc=r=24000:cl=mono"
    fc, labels = [], []
    fc.append(f"{sil},atrim=duration={head}[s0]"); labels.append("[s0]")
    for i in range(len(wavs)):
        fc.append(f"[{i}:a]aresample=24000[a{i}]"); labels.append(f"[a{i}]")
        if i < len(wavs) - 1:
            fc.append(f"{sil},atrim=duration={gap}[g{i}]"); labels.append(f"[g{i}]")
    fc.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]")
    await run(["ffmpeg", "-y", *parts, "-filter_complex", ";".join(fc), "-map", "[out]", out])


async def merge_shot(clip, audio, out):
    dv = await ffprobe_duration(clip)
    da = await ffprobe_duration(audio) if audio else 0.0
    dur = max(dv, da, 1.0)
    inputs = ["-i", clip]
    fc = [f"[0:v]tpad=stop_mode=clone:stop_duration={max(dur - dv, 0):.3f},setsar=1[v]"]
    if audio:
        inputs += ["-i", audio]
        fc.append(f"[1:a]apad=whole_dur={dur:.3f},aresample=24000[a]")
    else:
        fc.append(f"anullsrc=r=24000:cl=mono,atrim=duration={dur:.3f}[a]")
    await run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-r", str(FPS), "-c:a", "aac", "-b:a", "96k", "-t", f"{dur:.3f}", out])
    return dur


def ass_time(t):
    h = int(t // 3600); t -= h * 3600
    m = int(t // 60); t -= m * 60
    return f"{h}:{m:02d}:{t:05.2f}"


def write_ass(events, path, platform):
    st = PLATFORM_SUB_STYLE.get(platform, PLATFORM_SUB_STYLE["tiktok"])

    def style_line(name, c):
        return (f"Style: {name}, Droid Sans Fallback, {c['size']}, {c['primary']}, "
                f"&H00000000, {c['back']}, {c['bold']}, {c['italic']}, 0, 0, 100, 100, "
                f"0, 0, {c['border']}, {c['outline']}, {c['shadow']}, {c['align']}, "
                f"10, 10, {c['margin_v']}, 1")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 480
PlayResY: 832

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line('Overlay', st['overlay'])}
{style_line('Sub', st['sub'])}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for ev in events:
        txt = ev["text"].replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{ass_time(ev['start'])},{ass_time(ev['end'])},{ev['style']},,0,0,0,,{txt}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines))


async def concat_and_subtitle(shot_files, ass_events, platform, out, bgm=None):
    list_file = out + ".list"
    with open(list_file, "w") as f:
        for p in shot_files:
            f.write(f"file '{p}'\n")
    ass_path = out + ".ass"
    write_ass(ass_events, ass_path, platform)
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file]
    if bgm and os.path.exists(bgm):
        cmd += ["-i", bgm]
        fc = f"[1:a]volume=0.15,aloop=loop=-1:size=2e9[bg];[0:a][bg]amix=inputs=2:duration=first[a]"
        cmd += ["-filter_complex", f"[0:v]subtitles={ass_path}[v];" + fc,
                "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-vf", f"subtitles={ass_path}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", out]
    await run(cmd)


async def zip_outputs(files, zip_path):
    cwd = os.path.dirname(zip_path)
    names = [os.path.basename(f) for f in files]
    await run(["zip", "-j", "-q", zip_path, *files])
