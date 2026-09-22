#!/usr/bin/env python3
"""Gera relatório PDF: minutos sub-20/sub-23 na Série A (FotMob)."""

from __future__ import annotations

import json
import re
import textwrap
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "serie_a_sub20_sub23_relatorio.pdf"
CACHE_PATH = ROOT / "data" / "fotmob_player_dob_cache.json"

UA = {"User-Agent": "Mozilla/5.0"}
GK_POSITION = 11

SEASONS = {
    2019: 13680,
    2020: 15027,
    2021: 16201,
    2022: 17409,
    2023: 18982,
    2024: 22978,
    2025: 25077,
    2026: 1000000388,
}

PERIOD_A = [2019, 2020, 2021, 2022]
PERIOD_B = [2023, 2024, 2025, 2026]

PAGE_SIZE = (11.69, 8.27)  # A4 paisagem
MARGIN_L = 0.062
MARGIN_R = 0.938

INK = "#11181F"
MUTED = "#6B7682"
RULE = "#DFE4E9"
CANVAS = "#FFFFFF"
BAND = "#F4F6F8"

C_U20 = "#1F5F8B"
C_U23 = "#C1663F"
C_PERIOD_A = "#B7C6D1"
C_PERIOD_B = "#1F5F8B"
C_NEGATIVE = "#A23B2C"


# ---------------------------------------------------------------- coleta

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def fetch_json(url: str):
    return json.loads(fetch(url))


def extract_stats_data(html: str) -> list[dict]:
    start = html.find('"statsData":[')
    if start < 0:
        raise RuntimeError("statsData não encontrado na página FotMob")
    i = start + len('"statsData":')
    depth = 0
    j = i
    while j < len(html):
        ch = html[j]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    return json.loads(html[i:j])


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def get_build_id() -> str:
    home = fetch("https://www.fotmob.com/").decode("utf-8", "ignore")
    match = re.search(r'"buildId":"([^"]+)"', home)
    if not match:
        raise RuntimeError("buildId não encontrado")
    return match.group(1)


def fetch_player_dob(build_id: str, player_id: int) -> str | None:
    url = (
        f"https://www.fotmob.com/_next/data/{build_id}/en/players/{player_id}/profile.json"
        f"?playerId={player_id}"
    )
    try:
        data = fetch_json(url)
    except Exception:
        return None
    birth = (data.get("pageProps") or {}).get("data", {}).get("birthDate")
    if isinstance(birth, dict) and birth.get("utcTime"):
        return birth["utcTime"][:10]
    fallback = (data.get("pageProps") or {}).get("fallback", {})
    for key, val in fallback.items():
        if key.startswith("player:") and isinstance(val, dict):
            b = val.get("birthDate")
            if isinstance(b, dict) and b.get("utcTime"):
                return b["utcTime"][:10]
    return None


def load_or_build_dob_cache(player_ids: set[int]) -> dict[int, date]:
    cache: dict[str, str] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    dob_by_id: dict[int, date] = {}
    for pid_str, dob_str in cache.items():
        try:
            dob_by_id[int(pid_str)] = parse_iso_date(dob_str)
        except ValueError:
            pass

    league = fetch_json("https://www.fotmob.com/api/data/leagues?id=268")
    team_ids = [r["id"] for r in league["table"][0]["data"]["table"]["all"]]
    for team_id in team_ids:
        team = fetch_json(f"https://www.fotmob.com/api/data/teams?id={team_id}")
        for group in team.get("squad", {}).get("squad", []):
            for member in group.get("members", []):
                pid = member.get("id")
                dob_raw = member.get("dateOfBirth")
                if pid and dob_raw:
                    cache[str(pid)] = dob_raw
                    dob_by_id[pid] = parse_iso_date(dob_raw)

    missing = sorted(pid for pid in player_ids if pid not in dob_by_id)
    if missing:
        build_id = get_build_id()
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {pool.submit(fetch_player_dob, build_id, pid): pid for pid in missing}
            for fut in as_completed(futures):
                pid = futures[fut]
                dob_raw = fut.result()
                if dob_raw:
                    cache[str(pid)] = dob_raw
                    dob_by_id[pid] = parse_iso_date(dob_raw)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return dob_by_id


def is_sub20(birth_year: int, season_year: int) -> bool:
    return birth_year >= season_year - 20


def is_sub23(birth_year: int, season_year: int) -> bool:
    return birth_year >= season_year - 23


def collect_season_stats(dob_by_id: dict[int, date]) -> list[dict]:
    rows: list[dict] = []
    all_ids: set[int] = set()

    season_players: dict[int, list[dict]] = {}
    for year, season_id in SEASONS.items():
        url = (
            f"https://www.fotmob.com/pt-BR/leagues/268/stats/season/{season_id}"
            f"/players/mins_played"
        )
        players = extract_stats_data(fetch(url).decode("utf-8", "ignore"))
        players = [p for p in players if p.get("position") != GK_POSITION]
        season_players[year] = players
        all_ids.update(p["id"] for p in players)

    if not all_ids.issubset(dob_by_id):
        dob_by_id.update(load_or_build_dob_cache(all_ids))

    for year, players in sorted(season_players.items()):
        total_minutes = 0
        u20_minutes = 0
        u23_minutes = 0
        u20_players = 0
        u23_players = 0
        total_players = len(players)

        for player in players:
            minutes = int(player["statValue"]["value"])
            total_minutes += minutes
            dob = dob_by_id.get(player["id"])
            if not dob:
                continue
            birth_year = dob.year
            if is_sub20(birth_year, year):
                u20_minutes += minutes
                u20_players += 1
            if is_sub23(birth_year, year):
                u23_minutes += minutes
                u23_players += 1

        rows.append(
            {
                "year": year,
                "total_minutes": total_minutes,
                "u20_minutes": u20_minutes,
                "u23_minutes": u23_minutes,
                "u20_players": u20_players,
                "u23_players": u23_players,
                "u20_pct": 100 * u20_minutes / total_minutes,
                "u23_pct": 100 * u23_minutes / total_minutes,
                "u20_players_pct": 100 * u20_players / total_players,
                "u23_players_pct": 100 * u23_players / total_players,
                "total_players": total_players,
                "partial": year == 2026,
            }
        )
    return rows


def aggregate_period(rows: list[dict], years: list[int]) -> dict:
    subset = [r for r in rows if r["year"] in years]
    n = len(subset)
    return {
        "years": years,
        "label": f"{years[0]}–{years[-1]}",
        "avg_u20_pct": sum(r["u20_pct"] for r in subset) / n,
        "avg_u23_pct": sum(r["u23_pct"] for r in subset) / n,
        "avg_u20_players_pct": sum(r["u20_players_pct"] for r in subset) / n,
        "avg_u23_players_pct": sum(r["u23_players_pct"] for r in subset) / n,
    }


# ---------------------------------------------------------------- estilo

def setup_style() -> None:
    available = {f.name for f in mpl.font_manager.fontManager.ttflist}
    family = [f for f in ("Inter", "Liberation Sans", "DejaVu Sans") if f in available]
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": family or ["DejaVu Sans"],
            "figure.facecolor": CANVAS,
            "axes.facecolor": CANVAS,
            "axes.edgecolor": RULE,
            "axes.labelcolor": MUTED,
            "axes.titlecolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "axes.titlesize": 12,
            "axes.labelsize": 9.5,
            "legend.frameon": False,
            "pdf.fonttype": 42,
        }
    )


def fmt_int(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%".replace(".", ",")


def fmt_delta_pp(previous: float, current: float) -> str:
    return f"{current - previous:+.1f} p.p.".replace(".", ",")


# ---------------------------------------------------------------- página

def new_page() -> plt.Figure:
    return plt.figure(figsize=PAGE_SIZE)


def draw_header(fig: plt.Figure, eyebrow: str, title: str, subtitle: str = "") -> None:
    fig.text(MARGIN_L, 0.945, " ".join(eyebrow.upper()), fontsize=7.5,
             color=MUTED, fontweight="bold")
    fig.text(MARGIN_L, 0.897, title, fontsize=19, color=INK, fontweight="bold", va="top")
    if subtitle:
        fig.text(MARGIN_L, 0.852, subtitle, fontsize=10.5, color=MUTED, va="top")
    fig.add_artist(
        Line2D(
            [MARGIN_L, MARGIN_R], [0.905, 0.905],
            color=RULE, linewidth=0.9, transform=fig.transFigure,
        )
    )
    fig.add_artist(
        Line2D(
            [MARGIN_L, MARGIN_L + 0.055], [0.905, 0.905],
            color=C_U20, linewidth=2.6, transform=fig.transFigure,
        )
    )


def draw_footer(fig: plt.Figure, page: int, total: int) -> None:
    fig.add_artist(
        Line2D(
            [MARGIN_L, MARGIN_R], [0.062, 0.062],
            color=RULE, linewidth=0.8, transform=fig.transFigure,
        )
    )
    fig.text(
        MARGIN_L, 0.038, "Série A · Minutos sub-20 e sub-23 · Fonte: FotMob",
        fontsize=8, color=MUTED,
    )
    fig.text(
        MARGIN_R, 0.038, f"{page:02d} / {total:02d}",
        fontsize=8, color=MUTED, ha="right",
    )


def save_page(pdf: PdfPages, fig: plt.Figure) -> None:
    pdf.savefig(fig)
    plt.close(fig)


def style_axes(ax: plt.Axes, y_grid: bool = True) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(length=0, pad=6)
    if y_grid:
        ax.grid(axis="y", color=RULE, linewidth=0.8)
        ax.set_axisbelow(True)


def kpi_card(fig: plt.Figure, x: float, y: float, w: float, h: float,
             label: str, value: str, note: str, accent: str) -> None:
    fig.add_artist(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0,rounding_size=0.012",
            transform=fig.transFigure, facecolor=BAND, edgecolor="none",
        )
    )
    fig.add_artist(
        Rectangle(
            (x, y), 0.0042, h,
            transform=fig.transFigure, facecolor=accent, edgecolor="none",
        )
    )
    fig.text(x + 0.022, y + h - 0.034, label, fontsize=8.5, color=MUTED, va="top")
    fig.text(x + 0.022, y + h - 0.072, value, fontsize=21, color=INK,
             fontweight="bold", va="top")
    fig.text(x + 0.022, y + 0.022, note, fontsize=8.5, color=MUTED, va="bottom")


# ---------------------------------------------------------------- páginas

def page_cover(pdf: PdfPages, rows: list[dict], period_a: dict, period_b: dict) -> None:
    fig = new_page()
    fig.add_artist(
        Rectangle((0, 0.72), 1, 0.28, transform=fig.transFigure,
                  facecolor=BAND, edgecolor="none")
    )
    fig.add_artist(
        Rectangle((0, 0.72), 1, 0.006, transform=fig.transFigure,
                  facecolor=C_U20, edgecolor="none")
    )

    fig.text(MARGIN_L, 0.905, " ".join("RELATÓRIO ANALÍTICO"), fontsize=8,
             color=MUTED, fontweight="bold")
    fig.text(MARGIN_L, 0.845, "Minutos de sub-20 e sub-23", fontsize=33,
             color=INK, fontweight="bold", va="top")
    fig.text(MARGIN_L, 0.775, "Campeonato Brasileiro Série A · temporadas 2019 a 2026",
             fontsize=13, color=MUTED, va="top")

    fig.text(MARGIN_L, 0.645,
             "Comparativo da utilização de atletas jovens, ano a ano e em dois blocos\n"
             "de quatro temporadas. Indicadores relativos (%), sem soma de minutos totais.",
             fontsize=12, color=INK, va="top", linespacing=1.6)

    cards = [
        ("Sub-20 · participação média", fmt_pct(period_b["avg_u20_pct"]),
         f"{period_a['label']} → {period_b['label']}: "
         f"{fmt_delta_pp(period_a['avg_u20_pct'], period_b['avg_u20_pct'])}",
         C_U20),
        ("Sub-23 · participação média", fmt_pct(period_b["avg_u23_pct"]),
         f"{period_a['label']} → {period_b['label']}: "
         f"{fmt_delta_pp(period_a['avg_u23_pct'], period_b['avg_u23_pct'])}",
         C_U23),
        ("Sub-23 · share de atletas", fmt_pct(period_b["avg_u23_players_pct"]),
         f"antes: {fmt_pct(period_a['avg_u23_players_pct'])} com minutos", C_U23),
    ]
    width = 0.268
    gap = 0.021
    for idx, (label, value, note, accent) in enumerate(cards):
        kpi_card(fig, MARGIN_L + idx * (width + gap), 0.235, width, 0.18,
                 label, value, note, accent)

    fig.text(MARGIN_L, 0.155,
             "Sub-20: nascidos em Y−20 ou depois  ·  Sub-23: nascidos em Y−23 ou depois  ·  goleiros excluídos",
             fontsize=9.5, color=MUTED, va="top")
    fig.text(MARGIN_L, 0.112,
             f"Fonte: FotMob (mins_played, liga 268)  ·  Gerado em {date.today().strftime('%d/%m/%Y')}",
             fontsize=9.5, color=MUTED, va="top")
    save_page(pdf, fig)


def page_methodology(pdf: PdfPages, rows: list[dict], page: int, total: int) -> None:
    fig = new_page()
    draw_header(fig, "Metodologia", "Como os números foram apurados",
                "Critérios de recorte, fonte dos dados e limitações da amostra.")

    blocks = [
        ("Fonte", "Ranking mins_played do FotMob para a Série A (liga 268), "
                  "uma consulta por temporada, de 2019 a 2026."),
        ("Recorte de posição", "Goleiros excluídos da base. Todos os percentuais têm como "
                               "denominador apenas os minutos de jogadores de linha."),
        ("Sub-20", "No ano Y, atletas nascidos em Y−20 ou depois. Em 2019, portanto, "
                   "todos os nascidos a partir de 1999."),
        ("Sub-23", "No ano Y, atletas nascidos em Y−23 ou depois. Em 2019, "
                   "todos os nascidos a partir de 1996."),
        ("Datas de nascimento", "Obtidas nos elencos e nos perfis individuais do FotMob; "
                                "cobertura de 100% dos atletas com minutos registrados."),
        ("Comparativos", "Entre blocos de temporadas, usamos apenas médias anuais de indicadores "
                         "relativos (% de minutos e % de atletas). Nunca somamos minutos totais, "
                         "pois 2026 está incompleta."),
        ("Limitação", "A temporada 2026 ainda está em andamento. Por isso, comparações entre "
                      "períodos usam somente percentuais médios por ano."),
    ]

    y = 0.79
    for title, body in blocks:
        fig.text(MARGIN_L, y, title, fontsize=11, color=INK, fontweight="bold", va="top")
        fig.text(MARGIN_L + 0.20, y, textwrap.fill(body, width=88), fontsize=10.5,
                 color=MUTED, va="top", linespacing=1.55)
        y -= 0.108
        fig.add_artist(
            Line2D([MARGIN_L, MARGIN_R], [y + 0.042, y + 0.042],
                   color=RULE, linewidth=0.7, transform=fig.transFigure)
        )

    draw_footer(fig, page, total)
    save_page(pdf, fig)


def page_lines(pdf: PdfPages, rows: list[dict], page: int, total: int) -> None:
    fig = new_page()
    draw_header(fig, "Evolução anual", "Indicadores relativos por temporada",
                "Participação em minutos e presença no elenco com minutos, ano a ano.")

    years = [r["year"] for r in rows]
    partial_year = next((r["year"] for r in rows if r["partial"]), None)

    plot_left = MARGIN_L + 0.038
    plot_width = MARGIN_R - plot_left - 0.035
    ax1 = fig.add_axes((plot_left, 0.425, plot_width, 0.315))
    ax2 = fig.add_axes((plot_left, 0.125, plot_width, 0.185))

    for key, color, label in (("u20_players_pct", C_U20, "Sub-20"),
                              ("u23_players_pct", C_U23, "Sub-23")):
        values = [r[key] for r in rows]
        ax1.plot(years, values, color=color, linewidth=2.4, label=label,
                 marker="o", markersize=5.5, markerfacecolor=CANVAS,
                 markeredgewidth=1.8, zorder=3)
        ax1.annotate(fmt_pct(values[-1]), (years[-1], values[-1]),
                     xytext=(9, 0), textcoords="offset points", fontsize=9,
                     color=color, fontweight="bold", va="center")

    style_axes(ax1)
    ax1.set_title("Atletas jovens com minutos (% do elenco de linha)", pad=12,
                  loc="left", fontweight="bold")
    ax1.set_ylabel("% dos atletas")
    ax1.set_xlim(years[0] - 0.35, years[-1] + 0.55)
    ax1.set_xticks(years)
    ax1.yaxis.set_major_formatter(lambda v, _: fmt_pct(v, 0))

    ax2.plot(years, [r["u20_pct"] for r in rows], color=C_U20, linewidth=2.4,
             marker="o", markersize=5.5, markerfacecolor=CANVAS, markeredgewidth=1.8, zorder=3)
    ax2.plot(years, [r["u23_pct"] for r in rows], color=C_U23, linewidth=2.4,
             marker="o", markersize=5.5, markerfacecolor=CANVAS, markeredgewidth=1.8, zorder=3)
    style_axes(ax2)
    ax2.set_title("Participação no total de minutos (jogadores de linha)", pad=12,
                  loc="left", fontweight="bold")
    ax2.set_ylabel("% dos minutos")
    ax2.set_xlim(years[0] - 0.35, years[-1] + 0.55)
    ax2.set_xticks(years)
    ax2.yaxis.set_major_formatter(lambda v, _: fmt_pct(v, 0))

    if partial_year is not None:
        for ax in (ax1, ax2):
            ax.axvspan(partial_year - 0.4, years[-1] + 0.55, color=BAND, zorder=0)
            ax.text(partial_year, 0.93, "parcial", transform=ax.get_xaxis_transform(),
                    fontsize=8, color=MUTED, ha="center", va="center")

    fig.legend(
        handles=[
            Line2D([], [], color=C_U20, linewidth=2.4, marker="o", markersize=5.5,
                   markerfacecolor=CANVAS, markeredgewidth=1.8, label="Sub-20"),
            Line2D([], [], color=C_U23, linewidth=2.4, marker="o", markersize=5.5,
                   markerfacecolor=CANVAS, markeredgewidth=1.8, label="Sub-23"),
        ],
        loc="upper right", bbox_to_anchor=(MARGIN_R, 0.845), ncols=2,
        fontsize=10.5, handlelength=1.8, columnspacing=1.8,
    )

    draw_footer(fig, page, total)
    save_page(pdf, fig)


def page_period_bars(pdf: PdfPages, period_a: dict, period_b: dict,
                     page: int, total: int) -> None:
    fig = new_page()
    draw_header(
        fig, "Comparativo de blocos", f"{period_a['label']} vs {period_b['label']}",
        "Quatro temporadas contra quatro temporadas, apenas com médias anuais de percentuais.",
    )

    labels = ["Sub-20", "Sub-23"]
    x = [0, 1]
    width = 0.3

    panel_width = 0.372
    panels = [
        {
            "rect": (MARGIN_L + 0.038, 0.195, panel_width, 0.50),
            "title": "Média anual · % dos minutos (linha)",
            "a": [period_a["avg_u20_pct"], period_a["avg_u23_pct"]],
            "b": [period_b["avg_u20_pct"], period_b["avg_u23_pct"]],
            "ylabel": "% dos minutos",
        },
        {
            "rect": (MARGIN_R - panel_width, 0.195, panel_width, 0.50),
            "title": "Média anual · % dos atletas com minutos",
            "a": [period_a["avg_u20_players_pct"], period_a["avg_u23_players_pct"]],
            "b": [period_b["avg_u20_players_pct"], period_b["avg_u23_players_pct"]],
            "ylabel": "% dos atletas",
        },
    ]

    for panel in panels:
        ax = fig.add_axes(panel["rect"])
        bars_a = ax.bar([i - width / 2 for i in x], panel["a"], width,
                        color=C_PERIOD_A, label=period_a["label"], zorder=3)
        bars_b = ax.bar([i + width / 2 for i in x], panel["b"], width,
                        color=C_PERIOD_B, label=period_b["label"], zorder=3)
        style_axes(ax)
        ax.set_title(panel["title"], pad=12, loc="left", fontweight="bold")
        ax.set_ylabel(panel["ylabel"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11.5, color=INK)
        ax.set_xlim(-0.55, 1.55)
        ax.set_ylim(0, max(panel["a"] + panel["b"]) * 1.42)
        ax.yaxis.set_major_formatter(lambda v, _: fmt_pct(v, 0))

        for bars, values in ((bars_a, panel["a"]), (bars_b, panel["b"])):
            for bar, value in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        fmt_pct(value), ha="center", va="bottom",
                        fontsize=9.5, color=INK, fontweight="bold")

        for i, (prev, curr) in enumerate(zip(panel["a"], panel["b"])):
            ax.text(
                i, 0.94, fmt_delta_pp(prev, curr), transform=ax.get_xaxis_transform(),
                ha="center", va="center", fontsize=10.5, color=C_NEGATIVE,
                fontweight="bold",
                bbox={"boxstyle": "round,pad=0.4", "facecolor": BAND, "edgecolor": "none"},
            )

    fig.legend(
        handles=[
            Rectangle((0, 0), 1, 1, facecolor=C_PERIOD_A, label=period_a["label"]),
            Rectangle((0, 0), 1, 1, facecolor=C_PERIOD_B, label=period_b["label"]),
        ],
        loc="upper right", bbox_to_anchor=(MARGIN_R, 0.845), ncols=2,
        fontsize=10.5, handlelength=1.5, columnspacing=1.8,
    )

    fig.text(
        MARGIN_L, 0.125,
        "Cada barra é a média dos percentuais anuais do bloco — método seguro com a temporada 2026 parcial.\n"
        "Os rótulos em destaque indicam a variação em pontos percentuais (p.p.) entre os dois blocos.",
        fontsize=9.5, color=MUTED, va="top", linespacing=1.6,
    )
    draw_footer(fig, page, total)
    save_page(pdf, fig)


def page_table(pdf: PdfPages, rows: list[dict], period_a: dict, period_b: dict,
               page: int, total: int) -> None:
    fig = new_page()
    draw_header(fig, "Dados detalhados", "Tabela por temporada",
                "Indicadores relativos por ano — percentuais de minutos e de atletas com minutos.")

    columns = [
        ("Temporada", 0.00, "left"),
        ("% min. sub-20", 0.18, "right"),
        ("% atl. sub-20", 0.33, "right"),
        ("Nº sub-20", 0.46, "right"),
        ("% min. sub-23", 0.59, "right"),
        ("% atl. sub-23", 0.74, "right"),
        ("Nº sub-23", 0.87, "right"),
    ]

    span = MARGIN_R - MARGIN_L
    top = 0.795
    row_h = 0.062

    for name, pos, align in columns:
        fig.text(MARGIN_L + pos * span, top, name, fontsize=8.5, color=MUTED,
                 ha=align, fontweight="bold")
    fig.add_artist(
        Line2D([MARGIN_L, MARGIN_R], [top - 0.018, top - 0.018],
               color=INK, linewidth=1.1, transform=fig.transFigure)
    )

    for idx, row in enumerate(rows):
        y = top - 0.052 - idx * row_h
        if idx % 2 == 1:
            fig.add_artist(
                Rectangle((MARGIN_L - 0.012, y - 0.018), span + 0.024, row_h * 0.82,
                          transform=fig.transFigure, facecolor=BAND, edgecolor="none",
                          zorder=0)
            )
        season = f"{row['year']}" + ("  · parcial" if row["partial"] else "")
        values = [
            (season, "left", INK, "bold"),
            (fmt_pct(row["u20_pct"], 2), "right", C_U20, "bold"),
            (fmt_pct(row["u20_players_pct"], 2), "right", MUTED, "normal"),
            (fmt_int(row["u20_players"]), "right", MUTED, "normal"),
            (fmt_pct(row["u23_pct"], 2), "right", C_U23, "bold"),
            (fmt_pct(row["u23_players_pct"], 2), "right", MUTED, "normal"),
            (fmt_int(row["u23_players"]), "right", MUTED, "normal"),
        ]
        for (name, pos, _), (text, align, color, weight) in zip(columns, values):
            fig.text(MARGIN_L + pos * span, y, text, fontsize=10, color=color,
                     ha=align, fontweight=weight, zorder=1)

    summary_y = top - 0.052 - len(rows) * row_h - 0.03
    fig.add_artist(
        Line2D([MARGIN_L, MARGIN_R], [summary_y + 0.038, summary_y + 0.038],
               color=INK, linewidth=1.1, transform=fig.transFigure)
    )
    for block in (period_a, period_b):
        text = (
            f"{block['label']}   ·   média anual sub-20: {fmt_pct(block['avg_u20_pct'])} dos minutos, "
            f"{fmt_pct(block['avg_u20_players_pct'])} dos atletas   ·   "
            f"sub-23: {fmt_pct(block['avg_u23_pct'])} dos minutos, "
            f"{fmt_pct(block['avg_u23_players_pct'])} dos atletas"
        )
        fig.text(MARGIN_L, summary_y, text, fontsize=10, color=INK, va="top")
        summary_y -= 0.042

    draw_footer(fig, page, total)
    save_page(pdf, fig)


def generate_report() -> Path:
    setup_style()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    dob_by_id: dict[int, date] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        dob_by_id = {int(k): parse_iso_date(v) for k, v in cache.items()}

    rows = collect_season_stats(dob_by_id)
    period_a = aggregate_period(rows, PERIOD_A)
    period_b = aggregate_period(rows, PERIOD_B)

    total_pages = 4
    with PdfPages(REPORT_PATH) as pdf:
        pdf.infodict().update(
            {
                "Title": "Série A — Minutos sub-20 e sub-23 (2019–2026)",
                "Subject": "Comparativo de utilização de atletas jovens na Série A",
                "Creator": "scripts/generate_serie_a_relatorio.py",
            }
        )
        page_cover(pdf, rows, period_a, period_b)
        page_lines(pdf, rows, 1, total_pages)
        page_period_bars(pdf, period_a, period_b, 2, total_pages)
        page_table(pdf, rows, period_a, period_b, 3, total_pages)
        page_methodology(pdf, rows, 4, total_pages)

    meta_path = REPORT_PATH.with_suffix(".json")
    meta_path.write_text(
        json.dumps(
            {"yearly": rows, "period_a": period_a, "period_b": period_b},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return REPORT_PATH


if __name__ == "__main__":
    path = generate_report()
    print(f"Relatório gerado: {path}")
