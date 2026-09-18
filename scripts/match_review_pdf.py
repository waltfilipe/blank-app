#!/usr/bin/env python3
"""Landscape match / session review PDFs for player development."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

from fpdf import FPDF

ARTIFACTS_DIR = Path("/opt/cursor/artifacts")
REPO_DIR = Path("/workspace/docs/reviews")

FONT_DIR = Path("/usr/share/fonts/truetype/noto")
FONT_FAMILY = "NotoSans"

INK = (14, 17, 22)
INK_SOFT = (34, 40, 49)
CLUB_RED = (218, 41, 28)
CLUB_NAVY = (35, 50, 106)
WHITE = (255, 255, 255)
TEXT_BODY = (48, 54, 64)
TEXT_MUTED = (122, 130, 142)
CARD_BG = (247, 248, 250)
CARD_BORDER = (225, 228, 234)
RULE = (228, 231, 237)

RATINGS = {
    "green": {"color": (37, 158, 78), "label": "Good play", "accent": (37, 158, 78)},
    "yellow": {"color": (233, 168, 45), "label": "Mixed - strengths and errors", "accent": (233, 168, 45)},
    "red": {"color": (214, 62, 51), "label": "Errors / missed opportunity", "accent": (214, 62, 51)},
    "white": {
        "color": (255, 255, 255),
        "label": "Teammate clip - not rated",
        "accent": (176, 182, 192),
    },
}

TALLY_RATINGS = ("green", "yellow", "red")

PAGE_W, PAGE_H = 297.0, 210.0
MARGIN = 20.0
BAND_H = 40.0
FOOTER_Y = 194.0

REPORTS: dict[str, dict[str, Any]] = {
    "ali_sakr_session_041": {
        "filename": "Ali_Sakr_New_York_Red_Bulls_Session_041_Review.pdf",
        "pdf_title": "Ali Sakr - New York Red Bulls - Session 041 Review",
        "pdf_author": "New York Red Bulls",
        "player": "Ali Sakr",
        "club": "New York Red Bulls",
        "review_title": "Session 041 Review",
        "cover_blurb": "Clip-by-clip analysis across the four key phases of the session.",
        "footer_brand": "NEW YORK RED BULLS  |  INDIVIDUAL DEVELOPMENT PROGRAMME",
        "topics": [
            {
                "title": "Final Third",
                "subtitle": "Attacking the last line: 1v1s, crossing, finishing and penetration.",
                "tag": "Crossing  |  Finishing  |  Penetration",
                "plays": [
                    ("1", "Execution: poor first-time cross.", "red"),
                    ("2", "Left-foot control, good 1v1; poor finishing execution.", "yellow"),
                    (
                        "3",
                        "Left-foot control, still clears the situation. Poor finish - the far side offered stronger options.",
                        "red",
                    ),
                    (
                        "4",
                        "Space to drive and a teammate in a potential overload. Right-foot control sets up a good 1v1.",
                        "yellow",
                    ),
                    (
                        "5",
                        "Ball too far from the body; the left back is ball-watching - good chance to run in behind.",
                        "red",
                    ),
                    ("6", "Again too far from the left back - no option to penetrate.", "red"),
                    (
                        "7",
                        "Poor control, but escapes the press. Could have carried further, although the pass was not a bad decision.",
                        "red",
                    ),
                    ("8", "Play through the inside channel - keep the ball closer to the foot.", "red"),
                ],
            },
            {
                "title": "Attacking Transition",
                "subtitle": "Decisions and ball security in the moments right after winning possession.",
                "tag": "Runs in behind  |  Carrying  |  Ball security",
                "plays": [
                    ("1", "Chance to run into the space in behind the left back.", "red"),
                    ("2", "Why not switch the play wide? A numerical advantage was available.", "red"),
                    ("3", "Left-foot control.", "red"),
                    (
                        "4",
                        "Could carry longer to commit the defender and delay, allowing a teammate's run in behind.",
                        "red",
                    ),
                    (
                        "5",
                        "Good tackle; carrying the ball too far from the foot invited the challenge.",
                        "red",
                    ),
                    (
                        "6 & 7",
                        "More examples of teammates carrying the ball away from the foot and being dispossessed.",
                        "white",
                    ),
                ],
            },
            {
                "title": "Build-Up",
                "subtitle": "Second-phase build-up - progressing the ball into the final third.",
                "tag": "Between the lines  |  Third man  |  Wide channels",
                "plays": [
                    (
                        "1",
                        "Recognise the teammate already in space; the left back is ball-watching - chance to penetrate.",
                        "red",
                    ),
                    (
                        "2",
                        "Play to feet? Identify the teammate with the advantage and use it to create an outside-to-inside "
                        "option - but the space between the lines was not occupied.",
                        "red",
                    ),
                    (
                        "3",
                        "Dropping deep to build. Chance to break in between the lines or to set up a third-man combination - "
                        "offered neither.",
                        "red",
                    ),
                    (
                        "4",
                        "Teammate with a potential advantage out wide. Why not use the wide channel?",
                        "red",
                    ),
                ],
            },
            {
                "title": "Defensive Phase",
                "subtitle": "Counter-pressing, pressing decisions and 1v1 defending.",
                "tag": "Counter-press  |  Space protection  |  1v1",
                "plays": [
                    ("1", "Aggressive press to block the pass - beaten on the dribble.", "red"),
                    ("2", "Poor counter-press after the turnover - beaten on the dribble.", "red"),
                    (
                        "3",
                        "Protect the space instead of over-committing onto the opponent's body. Good effort to stay in the "
                        "play until the end.",
                        "yellow",
                    ),
                    ("4", "Good counter-press - aggressive block of the passing lane.", "green"),
                    ("5", "Good counter-press - delays and disrupts the opponent's transition.", "green"),
                    ("6", "Good effort - chases and presses the opponent, forcing the mistake.", "green"),
                ],
            },
        ],
    },
    "ben_dezalovski_toronto_fc": {
        "filename": "Ben_Dezalovski_Club_Ohio_vs_Toronto_FC_Review.pdf",
        "pdf_title": "Ben Dezalovski - Club Ohio - Match Review vs Toronto FC",
        "pdf_author": "Club Ohio",
        "player": "Ben Dezalovski",
        "club": "Club Ohio",
        "review_title": "Match Review vs Toronto FC",
        "cover_blurb": "Clip-by-clip analysis from the match against Toronto FC.",
        "footer_brand": "CLUB OHIO  |  INDIVIDUAL DEVELOPMENT PROGRAMME",
        "topics": [
            {
                "title": "Build-Up",
                "subtitle": "First touch, body shape, disguise and using space to release the right back.",
                "tag": "Body shape  |  Disguise  |  Right back",
                "plays": [
                    (
                        "1",
                        "First touch turned inside, inviting the opponent's press jump. The pass is easy to read from body shape.",
                        "red",
                    ),
                    ("2", "First touch turned inside again; pass played across the six-yard box.", "red"),
                    (
                        "3",
                        "Body shape makes it easy for the defence to read the pass. Work on disguising and hiding passing intention.",
                        "red",
                    ),
                    ("4", "First touch turned inside prevents accessing the right back.", "red"),
                    (
                        "5",
                        "Space will open on the side the press comes from - use that to your advantage at times.",
                        "red",
                    ),
                    (
                        "6",
                        "Pass to a pressed teammate. Disguise intention to play into space for the right back.",
                        "red",
                    ),
                    ("7", "Identify the advantage in the central channel.", "red"),
                    ("8", "Goalkeeper did not help, but body shape was poorly adjusted.", "red"),
                    ("9", "Good pass and good communication, indicating the advantage.", "green"),
                    (
                        "10",
                        "Good, more open control and deceiving the opponent who jumped the press.",
                        "green",
                    ),
                    ("11", "Again using space to release the right back.", "green"),
                    ("12", "Better body adjustment, good pass between the lines.", "green"),
                ],
            },
            {
                "title": "Defensive Phase",
                "subtitle": "Chasing, line communication, hip position and depth defending.",
                "tag": "Depth  |  Communication  |  1v1",
                "plays": [
                    (
                        "1",
                        "Long chase - communicate to adjust the defensive line; free man in behind.",
                        "red",
                    ),
                    ("2", "Long chase - do not allow the opponent to turn and have space.", "red"),
                    (
                        "3",
                        "Improve hip positioning; keep them open towards the opponent entering the box.",
                        "red",
                    ),
                    (
                        "4",
                        "Identify if the opponent tends to dribble and offer closer cover to the right back.",
                        "red",
                    ),
                    (
                        "5",
                        "Disadvantaged situation - perhaps step closer. Was in a difficult moment.",
                        "red",
                    ),
                    ("6", "Good reading and depth defending.", "green"),
                    ("7", "Good reading and depth defending, good block on the shot.", "green"),
                    (
                        "8",
                        "Good engagement, using the arms and not mistiming the tackle.",
                        "green",
                    ),
                    ("9", "Good recovery and clearance.", "green"),
                    (
                        "10",
                        "Good read, no threat in the box, jumps to intercept.",
                        "green",
                    ),
                ],
            },
            {
                "title": "Defensive Transition",
                "subtitle": "Box defending, depth, scanning and 1v1 duels in transition.",
                "tag": "Box defending  |  1v1  |  Scanning",
                "plays": [
                    ("1", "Improve positioning in transition when defending the box.", "red"),
                    (
                        "2",
                        "Good depth defending in transition, hips turned towards the opponent's side.",
                        "green",
                    ),
                    (
                        "3",
                        "Good scanning and transition defending, preventing the pass in behind to the opponent.",
                        "green",
                    ),
                    (
                        "4",
                        "Good 1v1 in transition and open field, directing the opponent to the byline (opponent is "
                        "right-footed). Good use of the arm in the duel. Good distance from the ball, preventing a "
                        "shot or cross.",
                        "green",
                    ),
                ],
            },
            {
                "title": "Cross Defending",
                "subtitle": "Reference points, scanning and cutting out crosses.",
                "tag": "Scanning  |  Reference  |  Interceptions",
                "plays": [
                    ("1", "Be careful not to rely only on the opponent as your reference.", "red"),
                    ("2", "Again, uses only the opponent as reference.", "red"),
                    ("3", "Split attention between space and opponent to cut out crosses.", "red"),
                    ("4", "Good scanning and positioning.", "green"),
                    (
                        "5",
                        "Good use of the opponent as reference, good use of the arm to mark the reference.",
                        "green",
                    ),
                    (
                        "6",
                        "Good scanning and reading of the cross, disrupting the opponent's jump.",
                        "green",
                    ),
                ],
            },
        ],
    },
}


class ReviewPDF(FPDF):
    def __init__(self, cfg: dict[str, Any]) -> None:
        super().__init__(orientation="L", unit="mm", format="A4")
        self.cfg = cfg
        self.topics: list[dict] = cfg["topics"]
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(False)
        self.set_title(cfg["pdf_title"])
        self.set_author(cfg["pdf_author"])
        self._register_fonts()
        self.show_footer = False

    def _register_fonts(self) -> None:
        self.add_font(FONT_FAMILY, "", FONT_DIR / "NotoSans-Regular.ttf")
        self.add_font(FONT_FAMILY, "B", FONT_DIR / "NotoSans-Bold.ttf")
        self.add_font(FONT_FAMILY, "I", FONT_DIR / "NotoSans-Italic.ttf")

    def _footer_line(self) -> str:
        return f"{self.cfg['player']}  |  {self.cfg['club']}  |  {self.cfg['review_title']}"

    def tracked_text(self, x: float, y: float, text: str, tracking: float = 1.4) -> None:
        cursor = x
        for char in text:
            self.set_xy(cursor, y)
            self.cell(self.get_string_width(char), 4, char)
            cursor += self.get_string_width(char) + tracking

    def dot(self, cx: float, cy: float, rating: str, diameter: float = 4.2) -> None:
        color = RATINGS[rating]["color"]
        if rating == "white":
            self.set_fill_color(120, 128, 140)
            self.ellipse(
                cx - diameter / 2 - 1.0, cy - diameter / 2 - 1.0, diameter + 2.0, diameter + 2.0, style="F"
            )
            self.set_fill_color(*color)
            self.set_draw_color(160, 168, 180)
            self.set_line_width(0.35)
            self.ellipse(cx - diameter / 2, cy - diameter / 2, diameter, diameter, style="DF")
            return
        halo = tuple(min(255, c + 150) for c in color)
        self.set_fill_color(*halo)
        self.ellipse(
            cx - diameter / 2 - 1.1, cy - diameter / 2 - 1.1, diameter + 2.2, diameter + 2.2, style="F"
        )
        self.set_fill_color(*color)
        self.ellipse(cx - diameter / 2, cy - diameter / 2, diameter, diameter, style="F")

    def panel(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: tuple[int, int, int],
        border: tuple[int, int, int] | None = None,
        radius: float = 2.2,
    ) -> None:
        self.set_fill_color(*fill)
        style = "F"
        if border:
            self.set_draw_color(*border)
            self.set_line_width(0.25)
            style = "DF"
        try:
            self.rect(x, y, w, h, style=style, round_corners=True, corner_radius=radius)
        except TypeError:
            self.rect(x, y, w, h, style=style)

    def footer(self) -> None:
        if not self.show_footer or self.page_no() == 1:
            return
        self.set_draw_color(*RULE)
        self.set_line_width(0.25)
        self.line(MARGIN, FOOTER_Y, PAGE_W - MARGIN, FOOTER_Y)
        self.set_fill_color(*CLUB_RED)
        self.rect(MARGIN, FOOTER_Y + 3.6, 2.4, 2.4, style="F")
        self.set_font(FONT_FAMILY, "", 7.5)
        self.set_text_color(*TEXT_MUTED)
        self.set_xy(MARGIN + 5, FOOTER_Y + 2.4)
        self.cell(140, 5, self._footer_line())
        self.set_xy(PAGE_W - MARGIN - 60, FOOTER_Y + 2.4)
        self.cell(60, 5, f"{self.page_no() - 1} / {len(self.topics)}", align="R")

    def cover(self) -> None:
        self.add_page()
        self.set_fill_color(*INK)
        self.rect(0, 0, PAGE_W, PAGE_H, style="F")
        self.set_fill_color(*CLUB_RED)
        self.rect(0, 0, 7, PAGE_H, style="F")
        self.set_fill_color(*CLUB_NAVY)
        self.rect(7, 0, 1.6, PAGE_H, style="F")

        left = 26.0
        self.set_font(FONT_FAMILY, "B", 8)
        self.set_text_color(*CLUB_RED)
        self.tracked_text(left, 40, "PLAYER DEVELOPMENT REVIEW", tracking=2.2)

        self.set_font(FONT_FAMILY, "B", 46)
        self.set_text_color(*WHITE)
        self.set_xy(left, 52)
        self.cell(0, 20, self.cfg["player"])

        self.set_font(FONT_FAMILY, "", 16)
        self.set_text_color(214, 219, 226)
        self.set_xy(left, 76)
        self.cell(0, 8, self.cfg["club"])

        self.set_draw_color(70, 78, 90)
        self.set_line_width(0.4)
        self.line(left, 94, left + 78, 94)

        self.set_font(FONT_FAMILY, "B", 22)
        self.set_text_color(*WHITE)
        self.set_xy(left, 102)
        self.cell(0, 12, self.cfg["review_title"])

        self.set_font(FONT_FAMILY, "", 10)
        self.set_text_color(*TEXT_MUTED)
        self.set_xy(left, 118)
        self.multi_cell(112, 5.4, self.cfg["cover_blurb"])

        self._cover_legend(left, 140)
        self._cover_contents(PAGE_W - MARGIN - 112, 40, 112, 130)
        self._cover_baseline(left, 186)

    def _cover_baseline(self, x: float, y: float) -> None:
        self.set_draw_color(52, 59, 69)
        self.set_line_width(0.3)
        self.line(x, y, PAGE_W - MARGIN, y)
        self.set_fill_color(*CLUB_RED)
        self.rect(x, y + 4.2, 2.4, 2.4, style="F")
        self.set_font(FONT_FAMILY, "B", 7)
        self.set_text_color(120, 128, 140)
        self.tracked_text(x + 5.6, y + 3.4, self.cfg["footer_brand"], tracking=1.6)

    def _cover_legend(self, x: float, y: float) -> None:
        self.set_font(FONT_FAMILY, "B", 8)
        self.set_text_color(150, 158, 170)
        self.tracked_text(x, y, "RATING KEY", tracking=2.0)
        row = y + 9
        for rating, meta in RATINGS.items():
            self.dot(x + 2.4, row + 3.1, rating, diameter=4.0)
            self.set_font(FONT_FAMILY, "", 9)
            self.set_text_color(222, 226, 232)
            self.set_xy(x + 8, row)
            self.cell(100, 6.2, meta["label"])
            row += 8.2

    def _cover_contents(self, x: float, y: float, w: float, h: float) -> None:
        self.panel(x, y, w, h, fill=(24, 29, 36), border=(46, 53, 63), radius=3)
        pad = 11.0
        self.set_font(FONT_FAMILY, "B", 8)
        self.set_text_color(150, 158, 170)
        self.tracked_text(x + pad, y + 11, "CONTENTS", tracking=2.0)
        self.set_draw_color(46, 53, 63)
        self.set_line_width(0.3)
        self.line(x + pad, y + 20, x + w - pad, y + 20)

        top = y + 25.0
        row_h = (y + h - 9.0 - top) / len(self.topics)
        for index, topic in enumerate(self.topics, start=1):
            row = top + (index - 1) * row_h
            center = row + row_h / 2

            self.set_font(FONT_FAMILY, "B", 16)
            self.set_text_color(*CLUB_RED)
            self.set_xy(x + pad, center - 8.6)
            self.cell(14, 9, f"{index:02d}")

            self.set_font(FONT_FAMILY, "B", 12)
            self.set_text_color(*WHITE)
            self.set_xy(x + pad + 16, center - 8.4)
            self.cell(62, 8, topic["title"])

            self.set_font(FONT_FAMILY, "", 7.6)
            self.set_text_color(*TEXT_MUTED)
            self.set_xy(x + pad + 16, center + 0.2)
            self.cell(70, 5, topic["tag"])

            count = sum(2 if "&" in num else 1 for num, _, _ in topic["plays"])
            self.set_font(FONT_FAMILY, "B", 8.4)
            self.set_text_color(180, 186, 196)
            self.set_xy(x + w - pad - 24, center - 4.2)
            self.cell(24, 8, f"{count} plays", align="R")

            if index < len(self.topics):
                self.set_draw_color(40, 46, 55)
                self.line(x + pad, row + row_h, x + w - pad, row + row_h)

    def topic_page(self, index: int, topic: dict) -> None:
        self.show_footer = True
        self.add_page()
        self._topic_band(index, topic)
        self._topic_cards(topic["plays"])

    def _topic_band(self, index: int, topic: dict) -> None:
        self.set_fill_color(*INK)
        self.rect(0, 0, PAGE_W, BAND_H, style="F")
        self.set_fill_color(*CLUB_RED)
        self.rect(0, BAND_H, PAGE_W, 1.6, style="F")

        self.set_font(FONT_FAMILY, "B", 7.5)
        self.set_text_color(*CLUB_RED)
        self.tracked_text(MARGIN, 8.5, f"TOPIC {index:02d}", tracking=2.0)

        self.set_font(FONT_FAMILY, "B", 21)
        self.set_text_color(*WHITE)
        self.set_xy(MARGIN, 13.4)
        self.cell(170, 12, topic["title"])

        self._band_tally(topic["plays"])

        if topic.get("subtitle"):
            self.set_font(FONT_FAMILY, "", 8.6)
            self.set_text_color(148, 156, 168)
            self.set_xy(MARGIN, 27.6)
            self.cell(190, 5, topic["subtitle"])

    def _band_tally(self, plays: list[tuple[str, str, str]]) -> None:
        counts = {key: sum(1 for _, _, r in plays if r == key) for key in TALLY_RATINGS}
        chip_w, chip_h, gap = 17.0, 9.0, 4.0
        visible = [(k, v) for k, v in counts.items() if v]
        total_w = len(visible) * chip_w + (len(visible) - 1) * gap
        x = PAGE_W - MARGIN - total_w
        y = 16.0
        for rating, value in visible:
            self.panel(x, y, chip_w, chip_h, fill=(30, 36, 44), border=(54, 61, 72), radius=1.8)
            self.dot(x + 5.2, y + chip_h / 2, rating, diameter=3.6)
            self.set_font(FONT_FAMILY, "B", 9)
            self.set_text_color(*WHITE)
            self.set_xy(x + 8.4, y + 1.2)
            self.cell(chip_w - 11, chip_h - 2.4, str(value))
            x += chip_w + gap

    def _topic_cards(self, plays: list[tuple[str, str, str]]) -> None:
        top = BAND_H + 11.0
        available = FOOTER_Y - 7.0 - top
        accent_w, pad_x, dot_w = 3.2, 7.0, 8.4
        min_gap, max_gap, max_card_h = 3.0, 12.0, 30.0
        count = len(plays)

        for font_size, line_h, pad_y in ((10.0, 5.0, 4.6), (9.4, 4.7, 4.0), (8.8, 4.4, 3.6), (8.2, 4.1, 3.2)):
            self.set_font(FONT_FAMILY, "B", font_size - 0.6)
            label_w = dot_w + max(self.get_string_width(f"Play {num}") for num, _, _ in plays) + 6.0
            text_x = MARGIN + accent_w + pad_x + label_w
            text_w = PAGE_W - MARGIN - text_x - pad_x
            self.set_font(FONT_FAMILY, "", font_size)
            base = [
                max(len(self.multi_cell(text_w, line_h, t, dry_run=True, output="LINES")) * line_h + pad_y * 2, 14.0)
                for _, t, _ in plays
            ]
            if sum(base) + min_gap * (count - 1) <= available:
                break

        slack = available - sum(base) - min_gap * (count - 1)
        grow = min(slack * 0.55 / count, max(0.0, max_card_h - max(base)))
        heights = [h + grow for h in base]
        leftover = available - sum(heights) - min_gap * (count - 1)
        gap = min_gap + (min(leftover / (count - 1), max_gap - min_gap) if count > 1 else 0.0)
        block_h = sum(heights) + gap * (count - 1)

        y = top + max(0.0, (available - block_h) / 2)
        card_w = PAGE_W - 2 * MARGIN
        for (num, text, rating), height in zip(plays, heights):
            self.panel(MARGIN, y, card_w, height, fill=CARD_BG, border=CARD_BORDER, radius=2.2)
            self.set_fill_color(*RATINGS[rating]["accent"])
            try:
                self.rect(MARGIN, y, accent_w, height, style="F", round_corners=("TOP_LEFT", "BOTTOM_LEFT"), corner_radius=2.2)
            except TypeError:
                self.rect(MARGIN, y, accent_w, height, style="F")

            self.dot(MARGIN + accent_w + pad_x + 2.4, y + height / 2, rating)

            self.set_font(FONT_FAMILY, "B", font_size - 0.6)
            self.set_text_color(*INK_SOFT)
            self.set_xy(MARGIN + accent_w + pad_x + dot_w, y + height / 2 - line_h / 2)
            self.cell(label_w - dot_w, line_h, f"Play {num}")

            self.set_font(FONT_FAMILY, "", font_size)
            self.set_text_color(*TEXT_BODY)
            text_x = MARGIN + accent_w + pad_x + label_w
            text_w = PAGE_W - MARGIN - text_x - pad_x
            lines = self.multi_cell(text_w, line_h, text, dry_run=True, output="LINES")
            text_h = len(lines) * line_h
            self.set_xy(text_x, y + (height - text_h) / 2)
            self.multi_cell(text_w, line_h, text, align="L")

            y += height + gap


def build_pdf(report_id: str) -> Path:
    if report_id not in REPORTS:
        raise KeyError(f"Unknown report: {report_id}. Choose from: {', '.join(REPORTS)}")
    cfg = REPORTS[report_id]
    pdf = ReviewPDF(cfg)
    pdf.cover()
    for index, topic in enumerate(cfg["topics"], start=1):
        pdf.topic_page(index, topic)

    repo_path = REPO_DIR / cfg["filename"]
    artifact_path = ARTIFACTS_DIR / cfg["filename"]
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(repo_path))
    shutil.copy(repo_path, artifact_path)
    return repo_path


def main(argv: list[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    report_id = argv[0] if argv else "ali_sakr_session_041"
    print(build_pdf(report_id))


if __name__ == "__main__":
    main()
