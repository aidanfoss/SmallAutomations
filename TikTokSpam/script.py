# script.py
# TikTok "Top 5" spammer with tags, ledger, MoviePy v1/v2 compat
# Layout: Subtitle at top-center, numbered list left-aligned below it, video fills bottom half

import os, re, json, hashlib, random
from pathlib import Path
from typing import List, Dict, Set, Optional
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
from moviepy import ImageClip
import moviepy.video.fx as vfx
from PIL import Image, ImageFilter
import numpy as np




from PIL import Image, ImageDraw, ImageFont
import numpy as np


# ------------------- CONFIG -------------------
INPUT_ROOT = Path("videos")
OUTPUT_DIR = Path("outputs")
LEDGER_FILE = OUTPUT_DIR / "ledger.json"

TIKTOK_SIZE = (1080, 1920)
SLOTS = 5
NUM_RENDITIONS = 10   # keep 1 when testing

TEST_MODE = False     # <<< set to False for full output
TEST_FRAMES = 20      # number of frames to render in test mode
FPS = 30

QUERY_TAGS_ALL: Set[str] = set()
QUERY_TAGS_ANY: Set[str] = set()
MAX_CLIPS_POOL = 80

NUM_COL_W = 90   # width reserved for "1."
NUM_GAP   = 16   # gap between number column and title column


FONT_CHOICES = ["Impact", "Arial Black", "Arial", "Verdana", "Tahoma",
                "Trebuchet MS", "Calibri", "Consolas"]

# Layout constants
SIDE_MARGIN = 60
SUBTITLE_MARGIN_TOP = 40
LIST_MARGIN_TOP = 160
FONT_SIZE_MAIN = 55
FONT_SIZE_SUBTITLE = 72
TOP_PANEL_OPACITY = 0.6
EXCLUDE_COMMON = {"untagged", "chosen"}

# Layout tweaks
VIDEO_BOTTOM_OFFSET = 80   # <— lift the bottom video up by this many pixels
FONT_SIZE_MAIN = 48        # was 55; slightly smaller to reduce overlap
LIST_MARGIN_TOP = 170      # push list a bit lower under the subtitle


# ============================================================
# COMPAT / HELPERS
# ============================================================
def _on_color(clip, size, color=None, pos=('left','center'), col_opacity=0):
    # adds a transparent (or colored) background canvas around a clip
    fn = getattr(clip, "on_color", None) or getattr(clip, "on_background", None)
    if fn:
        return fn(size=size, color=color, pos=pos, col_opacity=col_opacity)
    # fallback: just return the original if not available
    return clip

def _fl_image(clip, func):
    """
    Apply a per-frame transform `func(frame) -> frame` across MoviePy v1/v2.
    Tries: fl_image (v1), image_transform (some v2 builds), then fl(...) fallback.
    """
    if hasattr(clip, "fl_image"):
        return clip.fl_image(func)
    if hasattr(clip, "image_transform"):
        return clip.image_transform(func)
    if hasattr(clip, "fl"):
        return clip.fl(lambda gf, t: func(gf(t)))
    # If nothing available, just return the clip unchanged
    return clip

def _resize(clip, **kw):
    fn = getattr(clip, "resized", None) or getattr(clip, "resize")
    return fn(**kw)

def _crop(clip, **kw):
    fn = getattr(clip, "cropped", None) or getattr(clip, "crop")
    return fn(**kw)

def _with_start(clip, t):
    fn = getattr(clip, "with_start", None) or getattr(clip, "set_start")
    return fn(t)

def _with_duration(clip, d):
    fn = getattr(clip, "with_duration", None) or getattr(clip, "set_duration")
    return fn(d)

def _with_position(clip, pos):
    fn = getattr(clip, "with_position", None) or getattr(clip, "set_position")
    return fn(pos)

def _with_opacity(clip, alpha):
    fn = getattr(clip, "with_opacity", None) or getattr(clip, "set_opacity")
    return fn(alpha)

def rgb_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)
    
def _subclip(clip, t0, t1):
    fn = getattr(clip, "subclipped", None) or getattr(clip, "subclip")
    return fn(t0, t1)
    
def _with_margin(clip, left=6, right=6, top=3, bottom=3):
    fn = getattr(clip, "with_margin", None) or getattr(clip, "margin", None)
    if fn:
        return fn(left=left, right=right, top=top, bottom=bottom, color=None)
    return clip
    
def _subclip(clip, t0, t1):
    fn = getattr(clip, "subclipped", None) or getattr(clip, "subclip")
    return fn(t0, t1)


def make_textclip(text, **kw):
    """
    Very compatible TextClip wrapper: uses PIL 'label' mode only,
    maps fontsize<->font_size, avoids unsupported args.
    """
    kw.pop("align", None)       # not supported in your build
    kw.pop("size", None)        # ignored in 'label' mode
    kw["method"] = "label"      # stable across versions

    try:
        if "fontsize" in kw and "font_size" not in kw:
            kw["font_size"] = kw.pop("fontsize")
        return TextClip(text=text, **kw)
    except TypeError:
        # try v1-style names
        try:
            if "font_size" in kw and "fontsize" not in kw:
                kw["fontsize"] = kw.pop("font_size")
            return TextClip(text=text, **kw)  # keep text=... (v2 accepts it)
        except TypeError:
            # last resort: drop font
            kw.pop("font", None)
            return TextClip(text=text, **kw)


WINDOWS_FONTS_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
FONT_ALIASES = {
    "Impact": ["impact.ttf"],
    "Arial Black": ["ariblk.ttf"],
    "Arial": ["arial.ttf", "arialbd.ttf"],
    "Verdana": ["verdana.ttf", "verdanab.ttf"],
    "Tahoma": ["tahoma.ttf", "tahomabd.ttf"],
    "Trebuchet MS": ["trebuc.ttf", "trebucbd.ttf"],
    "Calibri": ["calibri.ttf", "calibrib.ttf"],
    "Consolas": ["consola.ttf", "consolab.ttf"],
}
def resolve_font_path(family: str) -> Optional[str]:
    candidates = FONT_ALIASES.get(family, [])
    for fname in candidates:
        p = WINDOWS_FONTS_DIR / fname
        if p.exists():
            return str(p)
    direct = WINDOWS_FONTS_DIR / family
    if direct.exists():
        return str(direct)
    return None

def fast_sha1(file: Path, chunk=1024*1024) -> str:
    h = hashlib.sha1()
    with file.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def short_sig(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

def contrasting_text_color(bg_rgb):
    """
    Choose black or white text depending on panel background brightness.
    Uses luminance (perceived brightness).
    """
    r, g, b = bg_rgb
    luminance = 0.299*r + 0.587*g + 0.114*b
    return (0, 0, 0) if luminance > 160 else (255, 255, 255)


def random_rgb(minc=90, maxc=255):
    return (random.randint(minc,maxc), random.randint(minc,maxc), random.randint(minc,maxc))

# ============================================================
# TAGS
# ============================================================
TAG_PTRN = re.compile(r"\[(.*?)\]")
BRACKET_TAGS_RE = re.compile(r"\[.*?\]")

def parse_tags_from_name(name: str) -> Set[str]:
    tags = set()
    for m in TAG_PTRN.findall(name):
        parts = re.split(r"[;, ]+", m.strip())
        tags.update(t.lower() for t in parts if t.strip())
    return tags

def parse_tags_from_path(path: Path) -> Set[str]:
    return {p.name.lower() for p in path.parents if p != INPUT_ROOT and p.name}

def parse_tags_sidecar(mp4: Path) -> Set[str]:
    js = mp4.with_suffix(".json")
    if js.exists():
        try:
            data = json.loads(js.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tags"), list):
                return {str(t).lower() for t in data["tags"]}
        except Exception:
            pass
    return set()

def visible_title(title: str) -> str:
    return BRACKET_TAGS_RE.sub("", title).strip()

# ============================================================
# LIBRARY / LEDGER
# ============================================================
def index_library() -> List[Dict]:
    items = []
    for mp4 in INPUT_ROOT.rglob("*.mp4"):
        name = mp4.stem
        tags = set()
        tags |= parse_tags_from_name(mp4.name)
        tags |= parse_tags_from_path(mp4)
        tags |= parse_tags_sidecar(mp4)
        media_id = fast_sha1(mp4)
        items.append({"path": str(mp4), "title": name, "tags": sorted(tags), "media_id": media_id})
    return items

def filter_by_tags(items: List[Dict]) -> List[Dict]:
    if not QUERY_TAGS_ALL and not QUERY_TAGS_ANY:
        return items
    res = []
    for it in items:
        tset = set(it["tags"])
        if QUERY_TAGS_ALL and not QUERY_TAGS_ALL.issubset(tset): continue
        if QUERY_TAGS_ANY and tset.isdisjoint(QUERY_TAGS_ANY): continue
        res.append(it)
    return res

def load_ledger() -> Set[str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if LEDGER_FILE.exists():
        try:
            data = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
            return set(data.get("signatures", []))
        except Exception:
            return set()
    return set()

def save_ledger(sigs: Set[str]):
    LEDGER_FILE.write_text(json.dumps({"signatures": sorted(sigs)}, indent=2), encoding="utf-8")

# ============================================================
# LAYOUT
# ============================================================
def resize_for_bottom_half(clip):
    """Fill bottom half vertically, crop horizontally if needed, then lift off bottom by VIDEO_BOTTOM_OFFSET."""
    target_h = TIKTOK_SIZE[1] // 2
    c = _resize(clip, height=target_h)
    if c.w > TIKTOK_SIZE[0]:
        x1 = int((c.w - TIKTOK_SIZE[0]) // 2)
        c = _crop(c, x1=x1, y1=0, x2=x1 + TIKTOK_SIZE[0], y2=c.h)

    # Position using explicit pixel coords (top-left origin):
    # y = total_height - clip_height - bottom_margin
    x = int((TIKTOK_SIZE[0] - c.w) // 2)
    y = int(TIKTOK_SIZE[1] - c.h - VIDEO_BOTTOM_OFFSET)
    return _with_position(c, (x, y))

def make_blurred_bg(base_clip):
    """
    Build a full-frame, *smoothly blurred* background from base_clip:
    - Scale & center-crop to 1080x1920 (cover-fit)
    - Apply strong Gaussian blur using Pillow (no pixelation)
    - Slightly darken for readability
    """
    # Cover-fit scale, then crop to TikTok size
    scale = max(TIKTOK_SIZE[0] / base_clip.w, TIKTOK_SIZE[1] / base_clip.h)
    c = _resize(base_clip, width=int(base_clip.w * scale))
    c = _crop(
        c,
        width=TIKTOK_SIZE[0],
        height=TIKTOK_SIZE[1],
        x_center=c.w / 2,
        y_center=c.h / 2,
    )

    # True Gaussian blur via Pillow on every frame
    RADIUS = 28  # increase for stronger blur (e.g., 35–40)
    def _blur_frame(frame):
        return np.array(Image.fromarray(frame).filter(ImageFilter.GaussianBlur(radius=RADIUS)))

    blurred = _fl_image(c, _blur_frame)

    # Slight darken so text pops; fall back to per-frame multiply if needed
    try:
        blurred = blurred.fx(vfx.colorx, 0.75)
    except Exception:
        def _darken(frame):
            arr = frame.astype(np.float32) * 0.75
            return np.clip(arr, 0, 255).astype(np.uint8)
        blurred = _fl_image(blurred, _darken)

    return blurred




from moviepy import ImageClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np

def list_panel_overlay(slots_text: List[str], start_t: float, dur: float,
                       font_path_or_none, color_rgb, panel_rgb):
    """
    Transparent top-half overlay that ONLY contains the numbered list text.
    No colored panel. Renders with Pillow into one RGBA image, then to ImageClip.
    """
    overlays = []

    w = TIKTOK_SIZE[0]
    panel_h = TIKTOK_SIZE[1] // 2

    # Transparent canvas (no colored box)
    img = Image.new("RGBA", (w, panel_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Load font (fallback-safe)
    try:
        if font_path_or_none:
            font_main = ImageFont.truetype(font_path_or_none, FONT_SIZE_MAIN)
        else:
            font_main = ImageFont.truetype("arial.ttf", FONT_SIZE_MAIN)
    except Exception:
        font_main = ImageFont.load_default()

    # Columns & spacing
    NUM_COL_W = 90   # width reserved for "1."
    NUM_GAP   = 16   # gap between number col and title col
    x_num     = SIDE_MARGIN
    x_title   = SIDE_MARGIN + NUM_COL_W + NUM_GAP

    # Vertical distribution below the subtitle area
    space_available = panel_h - (LIST_MARGIN_TOP + 40)
    line_spacing = max(int(space_available // SLOTS), int(FONT_SIZE_MAIN * 1.35))
    line_h = int(FONT_SIZE_MAIN * 1.45)

    stroke_w   = 2
    stroke_fill = (0, 0, 0, 255)
    text_fill   = (color_rgb[0], color_rgb[1], color_rgb[2], 255)

    def draw_text_left(x, y_center, text):
        if not text:
            return
        bbox = draw.textbbox((0, 0), text, font=font_main, stroke_width=stroke_w)
        th = bbox[3] - bbox[1]
        y = int(y_center - th / 2)
        draw.text((x, y), text, font=font_main, fill=text_fill,
                  stroke_width=stroke_w, stroke_fill=stroke_fill)

    def draw_text_right(x_right, y_center, text):
        if not text:
            return
        bbox = draw.textbbox((0, 0), text, font=font_main, stroke_width=stroke_w)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = int(x_right - tw)
        y = int(y_center - th / 2)
        draw.text((x, y), text, font=font_main, fill=text_fill,
                  stroke_width=stroke_w, stroke_fill=stroke_fill)

    # Draw lines (number right-aligned in its column; title left-aligned)
    for i in range(SLOTS):
        y_center = LIST_MARGIN_TOP + i * line_spacing + line_h // 2
        num_text   = f"{i+1}."
        title_text = slots_text[i] if slots_text[i] else ""
        draw_text_right(x_num + NUM_COL_W, y_center, num_text)
        draw_text_left(x_title,            y_center, title_text)

    # Convert to a timed overlay clip
    arr = np.array(img)  # RGBA
    panel_clip = ImageClip(arr)
    panel_clip = _with_duration(panel_clip, dur)
    panel_clip = _with_position(panel_clip, ("center", "top"))
    panel_clip = _with_start(panel_clip, start_t)

    overlays.append(panel_clip)
    return overlays






def common_tag(order_items):
    tag_sets = [set(it["tags"]) - EXCLUDE_COMMON for it in order_items]
    if not tag_sets: return None
    common = set.intersection(*tag_sets)
    if not common: return None
    return sorted(common, key=lambda s:(len(s), s))[0]

# ============================================================
# RENDER
# ============================================================
def render_one(order_items: List[Dict], style, out_name_base: str):
    font_family = style["font_family"]
    font_path = style["font_path"]
    text_rgb, panel_rgb = style["text_rgb"], style["panel_rgb"]

    # Derive both the foreground (bottom-half video) and a blurred background per segment
    opened = []
    bgs = []
    for it in order_items:
        base = VideoFileClip(it["path"])
        # foreground bottom clip
        fg = resize_for_bottom_half(base)
        opened.append(fg)
        # blurred, full-frame background from same base
        bg = make_blurred_bg(base)
        bgs.append(bg)

    overlays = []
    slots_text = [""] * SLOTS
    t = 0.0
    for i, (fg_clip, item) in enumerate(zip(opened, order_items)):
        # build/update list overlay for this segment
        slots_text[i] = visible_title(item["title"])
        overlays += list_panel_overlay(slots_text, t, fg_clip.duration, font_path, text_rgb, panel_rgb)

        # time the fg clip + matching bg
        opened[i] = _with_start(fg_clip, t)
        bgs[i]    = _with_start(_with_duration(bgs[i], fg_clip.duration), t)

        t += fg_clip.duration

    total_dur = t if not TEST_MODE else TEST_FRAMES / FPS

    # Optional subtitle stays the same
    com = common_tag(order_items)
    subtitle_clip = None
    if com:
        sub_kw = dict(
            fontsize=FONT_SIZE_SUBTITLE,
            color="white",
            stroke_color="black",
            stroke_width=5,
            method="label",
        )
        if font_path:
            sub_kw["font"] = font_path
        subtitle_clip = make_textclip(f"Top 5 {com} clips", **sub_kw)
        subtitle_clip = _with_position(subtitle_clip, ("center", SUBTITLE_MARGIN_TOP))
        subtitle_clip = _with_start(subtitle_clip, 0)
        subtitle_clip = _with_duration(subtitle_clip, total_dur)

    # Compose: blurred backgrounds behind everything
    layers = bgs + opened + overlays
    if subtitle_clip:
        layers.append(subtitle_clip)

    final = CompositeVideoClip(layers, size=TIKTOK_SIZE)

    out_file = OUTPUT_DIR / f"{out_name_base}.mp4"
    print(f"  -> font: {font_family} ({font_path or 'PIL default'})")

    if TEST_MODE:
        test_seconds = TEST_FRAMES / FPS
        final_short = _subclip(final, 0, test_seconds)
        final_short.write_videofile(str(out_file), fps=FPS, codec="libx264", audio_codec="aac")
        final_short.close()
    else:
        final.write_videofile(str(out_file), fps=FPS, codec="libx264", audio_codec="aac")

    # Close all derivative clips
    for c in opened + bgs:
        try: c.close()
        except Exception: pass
    final.close()


# ============================================================
# MAIN
# ============================================================
def main():
    lib = index_library()
    if not lib: raise SystemExit("No .mp4 files found under videos/")
    pool = filter_by_tags(lib)
    if not pool: raise SystemExit("No videos matched tag filter.")
    if len(pool) > MAX_CLIPS_POOL:
        pool = random.sample(pool, MAX_CLIPS_POOL)

    used = load_ledger()
    made, attempts = 0, 0
    max_attempts = NUM_RENDITIONS * 50

    while made < NUM_RENDITIONS and attempts < max_attempts:
        attempts += 1
        selection = random.sample(pool, SLOTS)
        order = selection[:]
        random.shuffle(order)

        sig_basis = "|".join([it["media_id"] for it in order]) + "|slots=1..5"
        sig = short_sig(sig_basis)
        if sig in used:
            continue

        family = random.choice(FONT_CHOICES)
        fpath = resolve_font_path(family)
        panel_rgb = random_rgb()
        text_rgb = contrasting_text_color(panel_rgb)

        style = {
            "font_family": family,
            "font_path": fpath,
            "text_rgb": text_rgb,
            "panel_rgb": panel_rgb,
        }


        tag_union = sorted(set(t for it in order for t in it["tags"]))
        tag_bucket = "+".join(tag_union[:4]) if tag_union else "untagged"
        out_base = f"top5__{tag_bucket}__{sig}"

        print(f"Rendering {out_base} ...")
        render_one(order, style, out_base)

        used.add(sig)
        save_ledger(used)
        made += 1

    print(f"Done. Created {made} rendition(s). Ledger has {len(used)} entries.")

if __name__ == "__main__":
    while True:
        main()
        ans = input("\nGenerate more renditions? (Y/n): ").strip().lower()
        if ans.startswith("n"):
            print("Exiting generator.")
            break
