import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
import re
import random
import os
import urllib.request

def _resolve_truetype_path(preferred_names):
    """Возвращает первый найденный путь к TTF из списка имён.

    Ищем в: ./assets рядом с модулем, рядом с модулем, затем в каталоге шрифтов PIL.
    """
    base_dir = os.path.dirname(__file__)
    candidates = []
    for name in preferred_names:
        candidates.append(os.path.join(base_dir, "assets", name))
        candidates.append(os.path.join(base_dir, name))
    try:
        pil_fonts_dir = os.path.join(os.path.dirname(ImageFont.__file__), "fonts")
        for name in preferred_names:
            candidates.append(os.path.join(pil_fonts_dir, name))
    except Exception:
        pass
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def _ensure_font_downloaded(bold=False):
    """Ensure DejaVuSans TTF exists in ./assets. Download if missing.

    This avoids tiny bitmap fallback on hosts without system fonts.
    """
    base_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(base_dir, "assets")
    try:
        os.makedirs(assets_dir, exist_ok=True)
    except Exception:
        return None
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    dest = os.path.join(assets_dir, filename)
    if os.path.exists(dest):
        return dest
    # Try download from reliable mirrors
    urls = [
        f"https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/{filename}",
        f"https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/{filename}",
    ]
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            return dest
        except Exception:
            continue
    return None

def _load_font(size, bold=False):
    """Надёжная загрузка TrueType-шрифта с фоллбэками.

    Приоритет: DejaVu из проекта → DejaVu из PIL → Arial → load_default().
    """
    preferred = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    ttf_path = _resolve_truetype_path(preferred) or _ensure_font_downloaded(bold=bold)
    if ttf_path:
        try:
            return ImageFont.truetype(ttf_path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def draw_modern_banner(title, icon_emoji, subtitle=None, logo_text="PALMARON BOT", site_text="palamron-bot.com", width=1600, height=600):
    """Генерирует современный неоновый баннер максимально близко к референсу"""
    # 1. Фон: глубокий тёмно-зелёный градиент с мягким светом
    img = Image.new('RGB', (width, height), (8, 24, 12))
    draw = ImageDraw.Draw(img)
    # Градиент
    for y in range(height):
        r = int(8 + (24-8)*y/height)
        g = int(24 + (60-24)*y/height)
        b = int(12 + (32-12)*y/height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    # Лёгкий "spotlight" в левом верхнем углу
    for r in range(300, 0, -10):
        alpha = int(30 * (r/300)**2)
        draw.ellipse([0-r, 0-r, r*2, r*2], fill=(30, 120, 60, alpha))
    # 2. Сетка
    grid_color = (40, 80, 60, 60)
    step = 64
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)
    # 3. Текст включён по умолчанию. Можно выключить через BANNER_TEXT_DISABLED=1
    disable_text = os.environ.get("BANNER_TEXT_DISABLED", "0") not in ("0", "false", "False")

    # Размеры для текста/иконок, если всё же включен рендер текста
    title_size = max(84, int(width * 0.12))
    subtitle_size = max(36, int(width * 0.05))
    logo_size = max(30, int(width * 0.04))
    icon_size = max(160, int(width * 0.2))

    if not disable_text:
        title_font = _load_font(title_size, bold=True)
        subtitle_font = _load_font(subtitle_size, bold=False)
        logo_font = _load_font(logo_size, bold=False)
    else:
        title_font = subtitle_font = logo_font = None

    # Пытаемся взять emoji-шрифт, иначе используем обычный; если disable_text — иконку рисуем сферой ниже
    icon_ttf = _resolve_truetype_path(["seguiemj.ttf", "SegoeUIEmoji.ttf", "NotoColorEmoji.ttf"]) or None
    has_emoji_font = bool(icon_ttf) and not disable_text
    if has_emoji_font:
        try:
            icon_font = ImageFont.truetype(icon_ttf, icon_size)
        except Exception:
            has_emoji_font = False
            icon_font = _load_font(icon_size, bold=False)
    # Перед рендером очищаем от эмодзи, если нет emoji-шрифта
    def _strip_emojis(s: str) -> str:
        if not s:
            return s
        emoji_pattern = re.compile(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F1E6-\U0001F1FF]", flags=re.UNICODE)
        return emoji_pattern.sub("", s)

    safe_title = (_strip_emojis(title) if not has_emoji_font else title) if not disable_text else None
    safe_subtitle = (_strip_emojis(subtitle) if (subtitle and not has_emoji_font) else subtitle) if not disable_text else None

    # Обмежуємо праву область під іконку
    icon_x = width - 420
    left_pad = 80
    top_title = 80
    title_area_width = icon_x - left_pad - 40
    # Масштабування заголовка, щоб не наїжджав на іконку
    if not disable_text and safe_title:
        try:
            tf_size = title_size
            min_size = max(48, int(width * 0.06))
            while tf_size >= min_size:
                tf = _load_font(tf_size, bold=True)
                bbox = draw.textbbox((0, 0), safe_title, font=tf)
                if (bbox[2] - bbox[0]) <= title_area_width:
                    title_font = tf
                    break
                tf_size -= 6
        except Exception:
            pass
    # 4. Світіння заголовка (outer glow) + основний текст
    if not disable_text and safe_title:
        for r in range(16, 0, -2):
            draw.text((left_pad, top_title), safe_title, font=title_font, fill=(0, 140, 80, int(22/r)))
        draw.text((left_pad, top_title), safe_title, font=title_font, fill=(255,255,255))
    # 5. Підзаголовок із неоновим відтінком з переносами, щоб не заходив під іконку
    if not disable_text and safe_subtitle:
        max_sub_width = title_area_width
        # Грубий перенос за кількістю символів, потім уточнюємо по пікселях
        approx_chars = max(12, int(max_sub_width / 18))
        wrapped = []
        for line in safe_subtitle.split('\n'):
            for chunk in textwrap.wrap(line, width=approx_chars):
                # Уточнюємо: якщо надто довго — обрізаємо по словах
                while True:
                    bb = draw.textbbox((0,0), chunk, font=subtitle_font)
                    if (bb[2]-bb[0]) <= max_sub_width or len(chunk) <= 3:
                        break
                    chunk = chunk[:-1]
                wrapped.append(chunk)
        sub_y = 220
        for idx, ln in enumerate(wrapped[:3]):  # максимум 3 рядки щоб не зсувати низ
            for r in range(12, 0, -3):
                draw.text((left_pad, sub_y + idx*46), ln, font=subtitle_font, fill=(0, 200, 110, int(18/r)))
            draw.text((left_pad, sub_y + idx*46), ln, font=subtitle_font, fill=(180,255,200))
    # 6. Правая декорация: emoji если доступен шрифт, иначе неоновая сфера
    if icon_emoji and has_emoji_font and not disable_text:
        icon_y = 60
        for dx,dy in [(-8,8),(8,8),(-8,-8),(8,-8)]:
            draw.text((icon_x+dx, icon_y+dy), icon_emoji, font=icon_font, fill=(0,40,0))
        for r in range(36, 0, -2):
            draw.text((icon_x, icon_y), icon_emoji, font=icon_font, fill=(0,255,140,int(28/max(1,r))))
        draw.text((icon_x, icon_y), icon_emoji, font=icon_font, fill=(0,255,120))
    else:
        # Неоновая сфера (овальная) вместо emoji
        cx = icon_x + 120
        cy = int(height * 0.62)
        rx, ry = 220, 70
        # Глубокая тень
        for k in range(14, 0, -1):
            draw.ellipse([cx-rx-k*3, cy-ry-k*3, cx+rx+k*3, cy+ry+k*3], fill=(0, 40, 0))
        # Светящийся глоу
        for g in range(28, 0, -2):
            draw.ellipse([cx-rx-g*2, cy-ry-g, cx+rx+g*2, cy+ry+g], fill=(0, 255, 140))
        # Основная сфера
        draw.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], fill=(0, 255, 120))
    # 7. Логотип і підпис внизу з легким підсвічуванням
    if not disable_text:
        for r in range(8, 0, -2):
            draw.text((80, height-80), logo_text, font=logo_font, fill=(0, 160, 80, int(12/r)))
        draw.text((80, height-80), logo_text, font=logo_font, fill=(180,255,200))
        draw.text((80, height-40), site_text, font=logo_font, fill=(120,220,180))
    # 8. Додаткові неонові бліки (декор праворуч)
    for _ in range(3):
        x = random.randint(width-500, width-100)
        y = random.randint(40, height-100)
        w = random.randint(80,180)
        h = random.randint(20,60)
        draw.ellipse([x, y, x+w, y+h], fill=(0,255,120,30))
    # 8. Сохраняем в BytesIO
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes



# --- Pro renderer with PNG assets (closer to reference) ---
try:
    from PIL import Image as _PILImage
except Exception:
    _PILImage = None

def _ensure_default_assets(assets_dir: str):
    """Generate simple neon-styled placeholders (hand, plane, logo) if absent.
    This avoids dependency on external PNG files.
    """
    if _PILImage is None:
        return
    os.makedirs(assets_dir, exist_ok=True)
    # hand.png
    hp = os.path.join(assets_dir, 'hand.png')
    if not os.path.exists(hp):
        w, h = 720, 720
        img = _PILImage.new('RGBA', (w, h), (0,0,0,0))
        dr = ImageDraw.Draw(img)
        glow = (0, 255, 140, 40)
        core = (0, 255, 120, 255)
        # palm
        for r in range(18, 0, -2):
            dr.ellipse([120-r*2, 260-r, 560+r*2, 640+r], fill=(0, 255, 120, int(12*r)))
        dr.ellipse([140, 280, 540, 620], fill=core)
        # fingers (rounded rects)
        def finger(x, top, height):
            fw = 82
            for o in range(14, 0, -2):
                dr.rounded_rectangle([x-o, top-o*2, x+fw+o, top+height+o], radius=40+o, fill=(0,255,140,int(18)))
            dr.rounded_rectangle([x, top, x+fw, top+height], radius=44, fill=core)
        finger(160, 120, 260)
        finger(260, 90, 280)
        finger(360, 110, 270)
        finger(460, 140, 250)
        # thumb
        for o in range(14, 0, -2):
            dr.rounded_rectangle([80-o, 360-o, 210+o, 520+o], radius=50+o, fill=(0,255,140,int(18)))
        dr.rounded_rectangle([80, 360, 210, 520], radius=56, fill=core)
        img.save(hp)
    # plane.png
    pp = os.path.join(assets_dir, 'plane.png')
    if not os.path.exists(pp):
        w, h = 400, 300
        img = _PILImage.new('RGBA', (w, h), (0,0,0,0))
        dr = ImageDraw.Draw(img)
        poly = [(20,150),(380,30),(220,170),(360,270)]
        for k in range(18,0,-2):
            dr.polygon([(x-k, y-k) for x,y in poly], fill=(0,255,140,18))
        dr.polygon(poly, fill=(0,255,120,255))
        img.save(pp)
    # logo_round.png
    lp = os.path.join(assets_dir, 'logo_round.png')
    if not os.path.exists(lp):
        w, h = 260, 260
        img = _PILImage.new('RGBA', (w, h), (0,0,0,0))
        dr = ImageDraw.Draw(img)
        for r in range(18, 0, -2):
            dr.ellipse([10-r,10-r,w-10+r,h-10+r], fill=(0,255,140,18))
        dr.ellipse([18,18,w-18,h-18], fill=(0,255,120,255))
        try:
            fnt = _load_font(48, bold=True)
            text = 'PB'
            tw, th = dr.textbbox((0,0), text, font=fnt)[2:4]
            dr.text(((w-tw)//2, (h-th)//2), text, font=fnt, fill=(20,50,30,255))
        except Exception:
            pass
        img.save(lp)

def draw_pro_banner(title: str,
                    subtitle: str | None = None,
                    width: int = 1280,
                    height: int = 420,
                    assets_dir: str = None,
                    site_text: str = "palamron-bot.com",
                    logo_text: str = "PALMARON BOT"):
    """Renders a banner using PNG overlays (hand/plane/logo) if present.

    Expected assets (optional but recommended):
      - assets/hand.png (neon hand), assets/plane.png, assets/logo_round.png
    Falls back gracefully if some files missing.
    """
    base = Image.new('RGB', (width, height), (9, 25, 15))
    g = ImageDraw.Draw(base)
    # soft vignette background
    for y in range(height):
        r = int(10 + (20-10)*y/height)
        gcol = int(28 + (48-28)*y/height)
        b = int(16 + (28-16)*y/height)
        g.line([(0, y), (width, y)], fill=(r, gcol, b))
    # grid
    grid = (36, 80, 60)
    step = 46
    for x in range(0, width, step):
        g.line([(x, 0), (x, height)], fill=grid, width=1)
    for y in range(0, height, step):
        g.line([(0, y), (width, y)], fill=grid, width=1)

    # left glow cone
    for r in range(int(height*0.9), 0, -20):
        g.ellipse([-r*0.7, -r*0.7, r*1.2, r*1.2], fill=(20, 100, 60))

    # load fonts
    title_font = _load_font(int(width*0.12), bold=True)
    sub_font = _load_font(int(width*0.04))
    small_font = _load_font(int(width*0.028))

    # optional text (by default keep small/clean so it doesn't dominate)
    if title:
        tx, ty = int(width*0.06), int(height*0.20)
        small_title_font = _load_font(int(width*0.085), bold=True)
        for dx, dy in ((4,4),(2,2)):
            g.text((tx+dx, ty+dy), title, font=small_title_font, fill=(0,0,0))
        g.text((tx, ty), title, font=small_title_font, fill=(235, 250, 245), stroke_width=2, stroke_fill=(0, 200, 120))
    if subtitle:
        g.text((int(width*0.06), int(height*0.40)), subtitle, font=sub_font, fill=(210,235,230))

    # site/brand bottom-left
    g.text((tx, height-62), logo_text, font=small_font, fill=(180,240,220))
    g.text((tx, height-34), site_text, font=small_font, fill=(140,210,200))

    # overlay assets if present
    import os
    adir = assets_dir or os.path.join(os.path.dirname(__file__), 'assets')
    _ensure_default_assets(adir)
    def _open(p):
        try:
            return _PILImage.open(p).convert('RGBA') if _PILImage else None
        except Exception:
            return None
    hand = _open(os.path.join(adir, 'hand.png'))
    plane = _open(os.path.join(adir, 'plane.png'))
    logo = _open(os.path.join(adir, 'logo_round.png'))
    # neonize helper: multi-layer glow + outline to match reference
    def neonize(img_rgba, tint=(0,255,140)):
        if img_rgba is None:
            return None
        img_rgba = img_rgba.convert('RGBA')
        w, h = img_rgba.size
        alpha = img_rgba.split()[-1]
        out = _PILImage.new('RGBA', (w, h), (0,0,0,0))

        def layer(color, mask):
            lay = _PILImage.new('RGBA', (w, h), color)
            lay.putalpha(mask)
            return lay

        # Deep glow
        deep = alpha.filter(ImageFilter.GaussianBlur(max(8, int(min(w,h)*0.06))))
        out = _PILImage.alpha_composite(out, layer(tint + (90,), deep))
        # Mid glow
        mid = alpha.filter(ImageFilter.GaussianBlur(max(6, int(min(w,h)*0.035))))
        out = _PILImage.alpha_composite(out, layer(tint + (140,), mid))
        # Inner glow
        inner = alpha.filter(ImageFilter.GaussianBlur(max(3, int(min(w,h)*0.02))))
        out = _PILImage.alpha_composite(out, layer((0,255,180,180), inner))

        # Outline ring using dilate-erode difference
        try:
            dil = alpha.filter(ImageFilter.MaxFilter(7))
            ero = alpha.filter(ImageFilter.MinFilter(7))
            import PIL.ImageChops as ImageChops
            ring = ImageChops.subtract(dil, ero)
            ring = ring.filter(ImageFilter.GaussianBlur(2))
            out = _PILImage.alpha_composite(out, layer((120,255,200,220), ring))
        except Exception:
            pass

        # Core fill
        core = _PILImage.new('RGBA', (w,h), (0,255,120,255))
        core.putalpha(alpha)
        out = _PILImage.alpha_composite(out, core)
        return out
    if hand:
        hand = neonize(hand, tint=(0,255,140))
        hand = hand.resize((int(width*0.38), int(height*0.74)))
        base.paste(hand, (int(width*0.60), int(height*0.09)), hand)
    if plane:
        plane = neonize(plane, tint=(0,255,140))
        plane = plane.resize((int(width*0.11), int(height*0.16)))
        base.paste(plane, (int(width*0.77), int(height*0.06)), plane)
    if logo:
        logo = logo.resize((int(height*0.18), int(height*0.18)))
        base.paste(logo, (int(width*0.05), int(height*0.78)), logo)

    buf = io.BytesIO()
    base.save(buf, format='PNG')
    buf.seek(0)
    return buf

