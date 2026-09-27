"""Generate presentation cards from the same public event log used by the UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .events import read_events

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - exercised only when the optional extra is absent
    Image = ImageDraw = ImageFont = None


WIDTH, HEIGHT = 1920, 1080
BG = "#08111f"
PANEL = "#10233a"
TEXT = "#f4f7fb"
MUTED = "#91a4bd"
CYAN = "#59d9ff"
GREEN = "#57e39a"
YELLOW = "#ffd166"
RED = "#ff7188"


def _font(size: int, bold: bool = False):
    if ImageFont is None:
        return None
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrap(text: str, width: int = 58) -> list[str]:
    words, lines, current = str(text).split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width and current:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines or [""]


def _card(title: str, subtitle: str, accent: str = CYAN):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 15), fill=accent)
    draw.text((110, 120), "LOCAL CONSENSUS WORKSPACE", font=_font(26, True), fill=accent)
    draw.text((110, 190), title, font=_font(72, True), fill=TEXT)
    draw.text((115, 290), subtitle, font=_font(30), fill=MUTED)
    return image, draw


def _save_title(output: Path) -> str:
    image, draw = _card("Three personal agents. One shared trip.", "A privacy-preserving planning workflow powered by local Ollama.")
    draw.rounded_rectangle((110, 470, 1810, 720), radius=24, fill=PANEL, outline="#263c58", width=3)
    draw.text((160, 520), "PRIVATE MEMORY", font=_font(30, True), fill=YELLOW)
    draw.text((160, 575), "bounded proposal", font=_font(30), fill=TEXT)
    draw.text((810, 545), "→", font=_font(45, True), fill=CYAN)
    draw.text((1030, 520), "SHARED CONSENSUS", font=_font(30, True), fill=GREEN)
    draw.text((1030, 575), "approved or blocked", font=_font(30), fill=TEXT)
    target = output / "01-title.png"
    image.save(target)
    return str(target)


def _save_round(output: Path, round_number: int, proposal: dict[str, Any] | None, responses: list[dict[str, Any]]) -> str:
    destinations = proposal.get("destinations", []) if proposal else []
    itinerary = proposal.get("itinerary", []) if proposal else []
    image, draw = _card(
        f"Round {round_number} · Shared proposal",
        "Only task-relevant proposal data crosses the agent boundary.",
    )
    draw.rounded_rectangle((110, 390, 1810, 560), radius=18, fill=PANEL, outline="#263c58", width=3)
    names = ", ".join(str(item.get("name", "option")) for item in destinations[:5]) or "waiting for destinations"
    draw.text((150, 430), "OPTIONS", font=_font(25, True), fill=CYAN)
    for index, line in enumerate(_wrap(names, 95)[:2]):
        draw.text((360, 430 + index * 38), line, font=_font(26), fill=TEXT)
    draw.text((150, 500), "ITINERARY", font=_font(25, True), fill=CYAN)
    draw.text((360, 500), f"{len(itinerary)} days", font=_font(26), fill=TEXT)
    x = 110
    for response in responses:
        status = str(response.get("status", response.get("action", "unknown")))
        color = GREEN if status == "approved" else RED if status in {"blocked", "unsafe"} else YELLOW
        draw.rounded_rectangle((x, 650, x + 520, 850), radius=18, fill="#0b1728", outline=color, width=4)
        draw.text((x + 25, 685), str(response.get("agent_id", "agent")), font=_font(30, True), fill=TEXT)
        draw.text((x + 25, 735), status.upper(), font=_font(24, True), fill=color)
        reason = str(response.get("reason_code", "bounded response"))
        draw.text((x + 25, 785), " · ".join(_wrap(reason, 25)[:2]), font=_font(20), fill=MUTED)
        x += 570
    target = output / f"02-round-{round_number}.png"
    image.save(target)
    return str(target)


def _save_outcome(output: Path, proposal: dict[str, Any] | None, outcome: dict[str, Any] | None) -> str:
    reached = bool(outcome and outcome.get("type") == "consensus_reached")
    image, draw = _card(
        "Consensus reached" if reached else "Workflow blocked",
        "Every required response is explicit. Silence never counts as approval.",
        GREEN if reached else RED,
    )
    if reached:
        itinerary = proposal.get("itinerary", []) if proposal else []
        draw.text((120, 430), "FINAL FIVE-DAY ITINERARY", font=_font(30, True), fill=GREEN)
        for index, day in enumerate(itinerary[:5]):
            y = 500 + index * 72
            activities = ", ".join(str(value) for value in day.get("activities", []))
            draw.text((120, y), f"DAY {day.get('day', index + 1)}", font=_font(25, True), fill=CYAN)
            draw.text((330, y), " · ".join(_wrap(activities, 88)[:1]), font=_font(25), fill=TEXT)
    else:
        reason = str((outcome or {}).get("reason_code", "resolution required"))
        draw.rounded_rectangle((120, 440, 1800, 650), radius=18, fill="#301a27", outline=RED, width=3)
        draw.text((165, 500), "USER ACTION REQUIRED", font=_font(30, True), fill=RED)
        draw.text((165, 560), "Reason: " + reason, font=_font(27), fill=TEXT)
    target = output / "03-outcome.png"
    image.save(target)
    return str(target)


def render_assets(events_path: str | Path, output_dir: str | Path) -> list[str]:
    """Render title, round, and outcome cards from public events only."""
    if Image is None:
        raise RuntimeError("Pillow is required. Install it with: python3 -m pip install -r requirements-video.txt")
    events = read_events(events_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    files = [_save_title(output)]
    rounds = sorted({int(event["round"]) for event in events if event.get("round") is not None})
    for round_number in rounds:
        round_events = [event for event in events if int(event.get("round", 0)) == round_number]
        publication = next((event for event in round_events if event.get("type") in {"proposal_published", "proposal_created"}), None)
        responses = [event for event in round_events if event.get("type") in {"agent_contribution", "agent_decision"}]
        files.append(_save_round(output, round_number, publication.get("proposal") if publication else None, responses))
    outcome = next((event for event in reversed(events) if event.get("type") in {"consensus_reached", "consensus_blocked"}), None)
    latest = next((event for event in reversed(events) if event.get("type") in {"proposal_published", "proposal_created"}), None)
    files.append(_save_outcome(output, latest.get("proposal") if latest else None, outcome))
    (output / "manifest.json").write_text(json.dumps({"events": str(events_path), "assets": files}, indent=2), encoding="utf-8")
    return files
