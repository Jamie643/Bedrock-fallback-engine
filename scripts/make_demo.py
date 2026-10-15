"""
Generate demo.gif for bedrock-fallback-engine README.

Run:
    pip install Pillow
    python scripts/make_demo.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

WIDTH, HEIGHT = 1000, 540
BG_DARK = (20, 22, 28)
BG_HEADER = (14, 16, 20)
PANEL = (32, 36, 44)
PANEL_BORDER = (48, 54, 64)
TEXT_WHITE = (240, 244, 248)
TEXT_GRAY = (140, 148, 158)
TEXT_DIM = (90, 98, 108)

GREEN = (58, 208, 130)
ORANGE = (240, 150, 50)
RED = (232, 78, 78)
BLUE = (72, 168, 236)

# Try to load a real font; fall back to default if not present.
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "C:/Windows/Fonts/consola.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


F_TITLE = _load_font(18, bold=True)
F_LABEL = _load_font(12)
F_BODY = _load_font(14)
F_LOG = _load_font(13)
F_MONO = _load_font(13)
F_BIG = _load_font(22, bold=True)

# --------------------------------------------------------------------------- #
# Timeline — each entry is a frame
# --------------------------------------------------------------------------- #

TIMELINE = [
    {
        "phase": "healthy",
        "time": "14:59:01",
        "event": "POST /triage",
        "status": "200 OK",
        "route": "PRIMARY",
        "region": "us-east-1",
        "model": "Claude 3.5 Sonnet",
        "latency": "142ms",
        "accent": GREEN,
        "load": [85, 0, 0],
    },
    {
        "phase": "healthy",
        "time": "14:59:02",
        "event": "POST /triage",
        "status": "200 OK",
        "route": "PRIMARY",
        "region": "us-east-1",
        "model": "Claude 3.5 Sonnet",
        "latency": "138ms",
        "accent": GREEN,
        "load": [82, 0, 0],
    },
    {
        "phase": "throttle",
        "time": "14:59:03",
        "event": "POST /triage",
        "status": "429 THROTTLE",
        "route": "FAILING",
        "region": "us-east-1",
        "model": "Claude 3.5 Sonnet",
        "latency": "850ms",
        "accent": ORANGE,
        "load": [99, 0, 0],
    },
    {
        "phase": "failover",
        "time": "14:59:04",
        "event": "→ FALLBACK",
        "status": "CIRCUIT OPEN",
        "route": "FAILOVER",
        "region": "us-west-2",
        "model": "Claude 3.5 Sonnet",
        "latency": "12ms",
        "accent": BLUE,
        "load": [0, 45, 0],
    },
    {
        "phase": "recovered",
        "time": "14:59:05",
        "event": "POST /triage",
        "status": "200 OK",
        "route": "BACKUP",
        "region": "us-west-2",
        "model": "Claude 3.5 Sonnet",
        "latency": "164ms",
        "accent": BLUE,
        "load": [0, 78, 0],
    },
    {
        "phase": "recovered",
        "time": "14:59:06",
        "event": "POST /triage",
        "status": "200 OK",
        "route": "BACKUP",
        "region": "us-west-2",
        "model": "Claude 3.5 Sonnet",
        "latency": "159ms",
        "accent": BLUE,
        "load": [0, 75, 0],
    },
]

# Each frame lingers this long (ms). Throttle is a flash.
FRAME_DURATIONS = [1200, 1000, 700, 700, 1300, 2200]


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #

def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int] | None = None,
    outline: tuple[int, int, int] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_header(img: Image.Image, draw: ImageDraw.ImageDraw, state: dict) -> None:
    draw.rectangle([(0, 0), (WIDTH, 64)], fill=BG_HEADER)
    draw.text((28, 22), "AWS BEDROCK RESILIENCE ENGINE", fill=TEXT_WHITE, font=F_TITLE)

    # Status pill on the right
    accent = state["accent"]
    dim = (accent[0] // 4, accent[1] // 4, accent[2] // 4)
    draw_rounded_rect(draw, (WIDTH - 240, 18, WIDTH - 28, 46), 6, fill=dim, outline=accent)
    label = f"ENGINE: {state['route']}"
    draw.text((WIDTH - 228, 25), label, fill=accent, font=F_BODY)


def draw_left_panel(draw: ImageDraw.ImageDraw, state: dict) -> None:
    x0, y0, x1, y1 = 28, 88, 470, 500
    draw_rounded_rect(draw, (x0, y0, x1, y1), 8, fill=PANEL, outline=PANEL_BORDER)
    draw.text((x0 + 20, y0 + 18), "ACTIVE SYSTEM PROFILES", fill=TEXT_DIM, font=F_LABEL)

    # ---- Region 01 (primary) ----
    card_x0, card_y0, card_x1, card_y1 = x0 + 20, y0 + 50, x1 - 20, y0 + 210
    primary_active = state["route"] in ("PRIMARY", "FAILING")
    primary_throttled = state["route"] == "FAILING"
    primary_border = ORANGE if primary_throttled else (GREEN if primary_active else PANEL_BORDER)
    draw_rounded_rect(draw, (card_x0, card_y0, card_x1, card_y1), 6,
                      fill=BG_DARK, outline=primary_border)

    draw.text((card_x0 + 16, card_y0 + 14), "REGION 01  ·  PRIMARY", fill=TEXT_WHITE, font=F_BODY)
    draw.text((card_x0 + 16, card_y0 + 42), "us-east-1  ·  Claude 3.5 Sonnet", fill=TEXT_GRAY, font=F_MONO)

    if primary_throttled:
        p_status, p_color = "STATUS  ·  THROTTLED (429)", ORANGE
    elif primary_active:
        p_status, p_color = "STATUS  ·  ACTIVE", GREEN
    else:
        p_status, p_color = "STATUS  ·  STANDBY", TEXT_DIM
    draw.text((card_x0 + 16, card_y0 + 76), p_status, fill=p_color, font=F_MONO)

    # ---- Region 02 (backup) ----
    card2_y0 = y0 + 235
    card2_y1 = y0 + 395
    backup_active = state["route"] in ("BACKUP", "FAILOVER")
    backup_border = BLUE if backup_active else PANEL_BORDER
    draw_rounded_rect(draw, (card_x0, card2_y0, card_x1, card2_y1), 6,
                      fill=BG_DARK, outline=backup_border)

    draw.text((card_x0 + 16, card2_y0 + 14), "REGION 02  ·  CROSS-REGION BACKUP", fill=TEXT_WHITE, font=F_BODY)
    draw.text((card_x0 + 16, card2_y0 + 42), "us-west-2  ·  Claude 3.5 Sonnet", fill=TEXT_GRAY, font=F_MONO)

    if state["route"] == "BACKUP":
        b_status, b_color = "STATUS  ·  ACTIVE PATH", BLUE
    elif state["route"] == "FAILOVER":
        b_status, b_color = "STATUS  ·  ROUTING INITIATED", BLUE
    else:
        b_status, b_color = "STATUS  ·  READY", TEXT_DIM
    draw.text((card_x0 + 16, card2_y0 + 76), b_status, fill=b_color, font=F_MONO)


def draw_right_panel(draw: ImageDraw.ImageDraw, state: dict, frame_index: int) -> None:
    x0, y0, x1, y1 = 490, 88, WIDTH - 28, 500
    draw_rounded_rect(draw, (x0, y0, x1, y1), 8, fill=PANEL, outline=PANEL_BORDER)
    draw.text((x0 + 20, y0 + 18), "LIVE TELEMETRY  ·  X-ROUTE INVOCATIONS", fill=TEXT_DIM, font=F_LABEL)

    # ---- Log stream ----
    log_y = y0 + 55
    for i in range(frame_index + 1):
        entry = TIMELINE[i]
        accent = entry["accent"]
        # Highlight the throttle and failover lines
        emphasize = entry["phase"] in ("throttle", "failover")
        prefix = "⚠ " if entry["phase"] == "throttle" else ("→ " if entry["phase"] == "failover" else "· ")
        line = f"[{entry['time']}]  {prefix}{entry['event']:<14} {entry['region']:<12} {entry['latency']:>6}"
        font = F_MONO
        draw.text((x0 + 20, log_y), line, fill=accent if emphasize else TEXT_GRAY, font=font)
        log_y += 22

    # ---- Load chart ----
    chart_x0, chart_y0 = x0 + 20, y0 + 320
    chart_x1, chart_y1 = x1 - 20, y0 + 405
    draw.text((chart_x0, chart_y0 - 22), "REGIONAL PIPELINE COMPUTE LOAD", fill=TEXT_DIM, font=F_LABEL)
    draw.rounded_rect = getattr(draw, "rounded_rectangle", None)
    draw.rectangle([(chart_x0, chart_y0), (chart_x1, chart_y1)], fill=BG_DARK, outline=PANEL_BORDER)

    # 80% threshold line
    threshold_y = chart_y1 - int(((chart_y1 - chart_y0) * 0.8))
    for tx in range(chart_x0, chart_x1, 6):
        draw.line([(tx, threshold_y), (tx + 3, threshold_y)], fill=(80, 40, 40), width=1)

    bar_x = chart_x0 + 30
    labels = ["us-east-1", "us-west-2", "eu-west-1"]
    for idx, load_val in enumerate(state["load"]):
        bar_h = int(((chart_y1 - chart_y0 - 20) * load_val) / 100.0)
        if load_val == 0:
            bar_color = (55, 60, 70)
        elif load_val >= 80:
            bar_color = ORANGE if state["phase"] != "throttle" else RED
        else:
            bar_color = state["accent"]

        bar_top = chart_y1 - bar_h - 2
        draw.rectangle([(bar_x, bar_top), (bar_x + 70, chart_y1 - 2)], fill=bar_color)

        draw.text((bar_x + 2, chart_y1 + 4), labels[idx], fill=TEXT_GRAY, font=F_LABEL)
        pct_color = TEXT_WHITE if load_val > 0 else TEXT_DIM
        draw.text((bar_x + 2, bar_top - 16), f"{load_val}%", fill=pct_color, font=F_MONO)
        bar_x += 120

    # ---- Footer ----
    draw.text((x0 + 20, y1 - 26), "github.com/Jamie643/bedrock-fallback-engine",
              fill=TEXT_DIM, font=F_LABEL)


def draw_alert_overlay(draw: ImageDraw.ImageDraw, state: dict) -> None:
    """Extra visual punch on the throttle frame."""
    if state["phase"] != "throttle":
        return
    # Red border pulse
    draw.rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], outline=RED, width=4)
    # Big warning text centered in the header
    draw.text((WIDTH // 2 - 130, 22), "⚠  FALLBACK TRIGGERED", fill=ORANGE, font=F_TITLE)


# --------------------------------------------------------------------------- #
# Generate frames
# --------------------------------------------------------------------------- #

def main() -> None:
    frames = []

    for i, state in enumerate(TIMELINE):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
        draw = ImageDraw.Draw(img)

        draw_header(img, draw, state)
        draw_left_panel(draw, state)
        draw_right_panel(draw, state, i)
        draw_alert_overlay(draw, state)

        frames.append(img)

    out_path = Path("demo.gif")
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATIONS,
        loop=0,
        optimize=True,
    )
    print(f"🎉 Saved {out_path.resolve()}")
    print(f"   {len(frames)} frames, {sum(FRAME_DURATIONS) / 1000:.1f}s loop")


if __name__ == "__main__":
    main()
