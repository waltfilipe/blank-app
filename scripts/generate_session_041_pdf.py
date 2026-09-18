#!/usr/bin/env python3
"""Generate Session 041 review PDF for Ali Sakr — NY Red Bulls."""

from fpdf import FPDF
from pathlib import Path

OUTPUT = Path("/opt/cursor/artifacts/Ali_Sakr_New_York_Red_Bulls_Session_041_Review.pdf")
REPO_OUTPUT = Path(
    "/workspace/docs/reviews/Ali_Sakr_New_York_Red_Bulls_Session_041_Review.pdf"
)

Rating = str  # "green" | "yellow" | "red"

RATING_COLORS = {
    "green": (34, 139, 34),
    "yellow": (218, 165, 32),
    "red": (200, 40, 40),
}


def ascii_safe(text: str) -> str:
    return (
        text.replace("\u2014", " - ")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u2022", "-")
    )


class ReviewPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def title_page(self):
        self.add_page()
        self.ln(48)
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 12, "Ali Sakr", align="C")
        self.ln(4)
        self.set_font("Helvetica", "", 18)
        self.set_text_color(186, 12, 47)
        self.multi_cell(0, 10, "New York Red Bulls", align="C")
        self.ln(8)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 10, "Session 041 Review", align="C")
        self.ln(24)
        self.set_draw_color(200, 200, 200)
        self.line(40, self.get_y(), 170, self.get_y())
        self.ln(14)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(60, 60, 60)
        self.cell(0, 8, "Rating key", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        for rating, label in (
            ("green", "Good play"),
            ("yellow", "Mixed - strengths and errors"),
            ("red", "Errors / missed opportunities"),
        ):
            self._rating_dot(rating, self.l_margin + 52)
            self.set_font("Helvetica", "", 10)
            self.set_text_color(50, 50, 50)
            self.set_x(self.l_margin + 60)
            self.cell(0, 8, label)
            self.ln(10)

    def _rating_dot(self, rating: Rating, x: float | None = None):
        r, g, b = RATING_COLORS[rating]
        self.set_fill_color(r, g, b)
        self.set_draw_color(r, g, b)
        cx = x if x is not None else self.l_margin + 2
        cy = self.get_y() + 3
        self.ellipse(cx, cy - 2, cx + 4, cy + 2, style="F")

    def topic_page(self, title: str, subtitle: str | None, plays: list[tuple[str, str, Rating]]):
        self.add_page()
        self.set_fill_color(30, 30, 30)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 12, f"  {ascii_safe(title)}", fill=True, new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            self.ln(3)
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(100, 100, 100)
            self.multi_cell(0, 5, ascii_safe(subtitle))
        self.ln(6)
        self.set_text_color(30, 30, 30)

        for num, text, rating in plays:
            self.set_x(self.l_margin)
            y0 = self.get_y()
            self._rating_dot(rating)
            self.set_xy(self.l_margin + 10, y0)
            self.set_font("Helvetica", "B", 9)
            self.cell(16, 5, f"Play {num}")
            self.set_font("Helvetica", "", 9)
            self.multi_cell(0, 5, ascii_safe(text))
            self.ln(3)

        if self.get_y() > 260:
            pass  # allow auto page break if needed; topic title stays on first page of section


def build_pdf():
    pdf = ReviewPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf.title_page()

    pdf.topic_page(
        "Final Third",
        None,
        [
            ("1", "Execution: poor first-time cross.", "red"),
            ("2", "Left-foot control, good 1v1; poor finishing execution.", "yellow"),
            (
                "3",
                "Left-foot control, still gets out of trouble. Poor finish. Far side had stronger options.",
                "yellow",
            ),
            (
                "4",
                "Space to drive; teammate in a potential overload. Right-foot control sets up a good 1v1.",
                "green",
            ),
            (
                "5",
                "Ball too far from the body; LB ball-watching - good chance to penetrate in behind.",
                "yellow",
            ),
            ("6", "Again too far from the LB - no penetration option.", "red"),
            (
                "7",
                "Poor control, but escapes the press. Could have carried further; the pass was not necessarily wrong.",
                "yellow",
            ),
            ("8", "Inside channel - keep the ball closer on the dribble.", "red"),
        ],
    )

    pdf.topic_page(
        "Attacking Transition",
        None,
        [
            ("1", "Opportunity to run in behind the LB.", "red"),
            ("2", "Why not go wide? Possible numerical advantage on that side.", "red"),
            ("3", "Left-foot control.", "yellow"),
            (
                "4",
                "Could carry longer, commit the defender, and delay to allow a teammate's run in behind.",
                "yellow",
            ),
            ("5", "Good tackle; ball carried too far from the foot invites dispossession.", "yellow"),
            (
                "6 & 7",
                "Teammates driving with the ball away from the foot and being dispossessed.",
                "red",
            ),
        ],
    )

    pdf.topic_page(
        "Build-Up",
        "Second-phase build-up - progressing into the final third.",
        [
            (
                "1",
                "Spot the teammate already in space; LB ball-watching - penetration opportunity.",
                "yellow",
            ),
            (
                "2",
                "Feet or space? Teammate advantaged - use that for outside-to-inside; did not occupy between the lines.",
                "yellow",
            ),
            (
                "3",
                "Dropping deep to build. Chance to break between the lines or use third-man movement - offered neither.",
                "red",
            ),
            ("4", "Teammate advantaged wide. Why not use the wide channel?", "red"),
        ],
    )

    pdf.topic_page(
        "Defensive Phase",
        None,
        [
            ("1", "Aggressive press to block the pass - beaten on the dribble.", "red"),
            ("2", "Poor counter-press after turnover - beaten on the dribble.", "red"),
            (
                "3",
                "Protect space rather than over-committing on the opponent's body; good effort to stay in the play to the end.",
                "yellow",
            ),
            ("4", "Good counter-press - aggressive block of the passing lane.", "green"),
            ("5", "Good counter-press - delay and disrupt the opponent's transition.", "green"),
            ("6", "Good effort - chase and press to force the mistake.", "green"),
        ],
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    REPO_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(REPO_OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(path)
