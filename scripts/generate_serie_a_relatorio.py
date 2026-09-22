#!/usr/bin/env python3
"""Gera relatório PDF: minutos sub-20/sub-23 na Série A (FotMob)."""

from __future__ import annotations

import json
import re
import statistics
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
SALES_CACHE_PATH = ROOT / "data" / "transfermarkt_vendas_exterior.json"

UA = {"User-Agent": "Mozilla/5.0"}
GK_POSITION = 11

TM_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TM_MARKER = '<th class="spieler-transfer-cell">Saídas</th>'
TM_BRAZIL = {"Brasil", "Brazil"}
TM_NON_COUNTRY = {"Sem clube", "Without Club", "-", ""}

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

# Vendas: 2026 tem janela incompleta, então o bloco recente usa só temporadas fechadas.
SALES_PERIOD_A = [2019, 2020, 2021, 2022]
SALES_PERIOD_B = [2023, 2024, 2025]

PAGE_SIZE = (11.69, 8.27)  # A4 paisagem
MARGIN_L = 0.062
MARGIN_R = 0.938

INK = "#11181F"
MUTED = "#6B7682"
RULE = "#DFE4E9"
CANVAS = "#FFFFFF"
BAND = "#F4F6F8"
NAVY = "#0F2A3D"

REPORT_TITLE = "Análise de Minutos e Vendas - Atletas Sub-20 e Sub-23"
ON_NAVY_MUTED = "#A9BCCB"

C_U20 = "#1F5F8B"
C_U23 = "#C1663F"
C_PERIOD_A = "#B7C6D1"
C_PERIOD_B = "#1F5F8B"
C_NEGATIVE = "#A23B2C"
C_POSITIVE = "#2E7D5B"


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


def tm_fetch_season(year: int) -> str:
    url = (
        "https://www.transfermarkt.com.br/campeonato-brasileiro-serie-a/transfers/"
        f"wettbewerb/BRA1/saison_id/{year}"
    )
    req = urllib.request.Request(url, headers=TM_UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", "ignore")


def tm_destination_country(row_html: str) -> str | None:
    match = re.search(r'verein-flagge-transfer-cell">.*?title="([^"]+)"', row_html, re.S)
    return match.group(1).strip() if match else None


def tm_parse_departures(html: str) -> list[dict]:
    departures = []
    for part in html.split(TM_MARKER)[1:]:
        start = part.find("<tbody>")
        end = part.find("</tbody>", start)
        if start < 0 or end < 0:
            continue
        for row in re.findall(r"<tr>(.*?)</tr>", part[start + 7 : end], re.S):
            age_match = re.search(r'alter-transfer-cell">(\d+)</td>', row)
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if not age_match or not cells:
                continue
            fee = " ".join(re.sub(r"<[^>]+>", " ", cells[-1]).split())
            departures.append(
                {
                    "age": int(age_match.group(1)),
                    "fee": fee,
                    "dest": tm_destination_country(row),
                }
            )
    return departures


def tm_is_sale(fee: str) -> bool:
    text = fee.lower()
    if "empréstimo" in text or "emprestimo" in text:
        return False
    if "fim do" in text or "custo zero" in text or "sem custo" in text:
        return False
    if text in {"-", "?", ""}:
        return False
    return "€" in fee


def tm_is_abroad(destination: str | None) -> bool:
    if not destination or destination in TM_NON_COUNTRY:
        return False
    return destination not in TM_BRAZIL


def collect_sales_stats(refresh: bool = False) -> list[dict]:
    if not refresh and SALES_CACHE_PATH.exists():
        return json.loads(SALES_CACHE_PATH.read_text(encoding="utf-8"))

    rows = []
    for year in sorted(SEASONS):
        departures = tm_parse_departures(tm_fetch_season(year))
        sales = [d for d in departures if tm_is_sale(d["fee"])]
        abroad = [s for s in sales if tm_is_abroad(s["dest"])]
        rows.append(
            {
                "year": year,
                "departures": len(departures),
                "sales": len(sales),
                "sales_abroad": len(abroad),
                "sales_abroad_u20": sum(1 for s in abroad if s["age"] <= 20),
                "sales_abroad_u23": sum(1 for s in abroad if s["age"] <= 23),
                "partial": year == 2026,
            }
        )

    SALES_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SALES_CACHE_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def aggregate_sales_period(rows: list[dict], years: list[int]) -> dict:
    subset = [r for r in rows if r["year"] in years]
    n = len(subset)
    u20 = [r["sales_abroad_u20"] for r in subset]
    u23 = [r["sales_abroad_u23"] for r in subset]
    return {
        "years": years,
        "label": f"{years[0]}–{years[-1]}",
        "seasons": n,
        "avg_u20": sum(u20) / n,
        "avg_u23": sum(u23) / n,
        "med_u20": statistics.median(u20),
        "med_u23": statistics.median(u23),
    }


def aggregate_period(rows: list[dict], years: list[int]) -> dict:
    subset = [r for r in rows if r["year"] in years]
    n = len(subset)
    u20_series = [r["u20_pct"] for r in subset]
    u23_series = [r["u23_pct"] for r in subset]
    return {
        "years": years,
        "label": f"{years[0]}–{years[-1]}",
        "avg_u20_pct": sum(u20_series) / n,
        "avg_u23_pct": sum(u23_series) / n,
        "med_u20_pct": statistics.median(u20_series),
        "med_u23_pct": statistics.median(u23_series),
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


def fmt_num(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def fmt_delta_pp(previous: float, current: float) -> str:
    return f"{current - previous:+.1f}".replace(".", ",") + " p.p."


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

def page_intro(pdf: PdfPages) -> None:
    fig = new_page()
    fig.add_artist(Rectangle((0, 0), 1, 1, transform=fig.transFigure,
                             facecolor=NAVY, edgecolor="none"))
    fig.add_artist(Rectangle((0.986, 0.5), 0.014, 0.5, transform=fig.transFigure,
                             facecolor=C_U20, edgecolor="none"))
    fig.add_artist(Rectangle((0.986, 0), 0.014, 0.5, transform=fig.transFigure,
                             facecolor=C_U23, edgecolor="none"))

    fig.text(MARGIN_L, 0.885, " ".join("RELATÓRIO ANALÍTICO"), fontsize=8,
             color=ON_NAVY_MUTED, fontweight="bold")
    fig.add_artist(Line2D([MARGIN_L, MARGIN_R], [0.855, 0.855], color=ON_NAVY_MUTED,
                          alpha=0.35, linewidth=0.8, transform=fig.transFigure))

    fig.add_artist(Rectangle((MARGIN_L, 0.655), 0.06, 0.006, transform=fig.transFigure,
                             facecolor=C_U23, edgecolor="none"))
    title_main, title_sub = (part.strip() for part in REPORT_TITLE.split(" - "))
    fig.text(MARGIN_L, 0.625, title_main, fontsize=38, color=CANVAS,
             fontweight="bold", va="top")
    fig.text(MARGIN_L, 0.528, title_sub, fontsize=38, color=ON_NAVY_MUTED, va="top")
    fig.text(MARGIN_L, 0.405, "Série A do Campeonato Brasileiro · temporadas 2019 a 2026",
             fontsize=13, color=ON_NAVY_MUTED, va="top")

    fig.add_artist(Line2D([MARGIN_L, MARGIN_R], [0.255, 0.255], color=ON_NAVY_MUTED,
                          alpha=0.35, linewidth=0.8, transform=fig.transFigure))
    fig.text(MARGIN_L, 0.205, " ".join("INSIGHT"), fontsize=8, color=C_U23,
             fontweight="bold", va="top")
    fig.text(
        MARGIN_L + 0.16, 0.212,
        "Os números mostram uma queda na utilização desses atletas, mas será\n"
        "pelo aumento de estrangeiros ou por vendas cada vez mais precoces?",
        fontsize=15, color=CANVAS, va="top", linespacing=1.55,
    )

    save_page(pdf, fig)


def page_methodology(pdf: PdfPages) -> None:
    fig = new_page()
    draw_header(fig, "Metodologia", "Como os números foram apurados",
                "Fontes, critérios de recorte e limitações da amostra.")

    blocks = [
        ("Fontes", "Minutos: ranking mins_played do FotMob para a Série A, uma consulta por "
                   "temporada, de 2019 a 2026. Vendas: página de transferências da Série A no "
                   "Transfermarkt, por temporada, de 2019 a 2025."),
        ("Sub-20 e sub-23", "No ano Y, atletas nascidos em Y−20 ou depois (sub-20) e em Y−23 "
                            "ou depois (sub-23). Em 2019: nascidos desde 1999 e desde 1996."),
        ("Goleiros", "Goleiros ficam fora da análise de minutos: os percentuais consideram apenas "
                     "os minutos jogados por atletas de linha."),
        ("Vendas", "Conta saídas com valor de transferência registrado e clube de destino fora "
                   "do Brasil; empréstimos e saídas sem custo ficam de fora. A idade é a "
                   "registrada pelo Transfermarkt no momento da transferência."),
        ("Temporada 2026", "Nos minutos, 2026 entra como temporada parcial e é comparada apenas "
                           "por percentuais. Nas vendas, 2026 fica de fora porque a janela segue "
                           "aberta: o bloco recente cobre as três janelas completas de 2023 a 2025."),
        ("Comparativos", "Blocos comparados por média e mediana: dos percentuais anuais de minutos "
                         "e do número de vendas por janela, com a variação das vendas em % sobre "
                         "o bloco anterior."),
    ]

    y = 0.80
    line_h = 0.029
    for title, body in blocks:
        wrapped = textwrap.fill(body, width=86)
        fig.text(MARGIN_L, y, title, fontsize=11, color=INK, fontweight="bold", va="top")
        fig.text(MARGIN_L + 0.20, y, wrapped, fontsize=10.5,
                 color=MUTED, va="top", linespacing=1.55)
        rule_y = y - wrapped.count("\n") * line_h - 0.038
        fig.add_artist(
            Line2D([MARGIN_L, MARGIN_R], [rule_y, rule_y],
                   color=RULE, linewidth=0.7, transform=fig.transFigure)
        )
        y = rule_y - 0.030

    save_page(pdf, fig)


def page_lines(pdf: PdfPages, rows: list[dict]) -> None:
    fig = new_page()
    draw_header(fig, "Evolução anual", "Participação em minutos",
                "Percentual dos minutos de linha jogados por atletas sub-20 e sub-23, ano a ano.")

    years = [r["year"] for r in rows]
    partial_year = next((r["year"] for r in rows if r["partial"]), None)

    plot_left = MARGIN_L + 0.038
    plot_width = MARGIN_R - plot_left - 0.035
    ax = fig.add_axes((plot_left, 0.165, plot_width, 0.58))

    for key, color, label in (("u20_pct", C_U20, "Sub-20"), ("u23_pct", C_U23, "Sub-23")):
        values = [r[key] for r in rows]
        ax.plot(years, values, color=color, linewidth=2.6, label=label,
                marker="o", markersize=6, markerfacecolor=CANVAS,
                markeredgewidth=1.8, zorder=3)
        ax.annotate(fmt_pct(values[-1]), (years[-1], values[-1]),
                    xytext=(10, 0), textcoords="offset points", fontsize=10,
                    color=color, fontweight="bold", va="center")

    style_axes(ax)
    ax.set_title("Participação no total de minutos (jogadores de linha)", pad=14,
                 loc="left", fontweight="bold")
    ax.set_ylabel("% dos minutos")
    ax.set_xlabel("Temporada")
    ax.set_xlim(years[0] - 0.35, years[-1] + 0.55)
    ax.set_xticks(years)
    ax.yaxis.set_major_formatter(lambda v, _: fmt_pct(v, 0))

    if partial_year is not None:
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

    save_page(pdf, fig)


def page_period_bars(pdf: PdfPages, period_a: dict, period_b: dict) -> None:
    fig = new_page()
    draw_header(
        fig, "Comparativo de blocos", f"{period_a['label']} vs {period_b['label']}",
        "Quatro temporadas contra quatro temporadas — média e mediana dos % anuais de minutos.",
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
        },
        {
            "rect": (MARGIN_R - panel_width, 0.195, panel_width, 0.50),
            "title": "Mediana anual · % dos minutos (linha)",
            "a": [period_a["med_u20_pct"], period_a["med_u23_pct"]],
            "b": [period_b["med_u20_pct"], period_b["med_u23_pct"]],
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
        ax.set_ylabel("% dos minutos")
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
        "Cada barra resume os percentuais anuais do bloco (média ou mediana) — seguro com 2026 parcial.\n"
        "Os rótulos em destaque indicam a variação em pontos percentuais (p.p.) entre os dois blocos.",
        fontsize=9.5, color=MUTED, va="top", linespacing=1.6,
    )
    save_page(pdf, fig)


def draw_season_table(
    fig: plt.Figure,
    rows: list[dict],
    *,
    title: str | None,
    accent: str,
    top: float,
    highlight_header: str,
    highlight_values: list[str],
    side_header: str | None = None,
    side_values: list[str] | None = None,
    x0: float = MARGIN_L,
    x1: float = MARGIN_R,
    row_h: float = 0.052,
) -> float:
    """Desenha tabela de uma categoria. Retorna y final abaixo da tabela."""
    span = x1 - x0
    season_x = x0
    has_side = bool(side_header and side_values)
    highlight_x = x0 + (0.46 if has_side else 0.72) * span
    side_x = x1
    band_width = (0.3 if has_side else 0.45) * span

    if title:
        fig.text(season_x, top, title, fontsize=12, color=accent,
                 fontweight="bold", va="top")
        header_y = top - 0.062
    else:
        header_y = top - 0.012

    fig.add_artist(
        Rectangle(
            (highlight_x - band_width / 2, header_y - 0.016), band_width, 0.03,
            transform=fig.transFigure, facecolor=accent, alpha=0.14, edgecolor="none",
            zorder=0,
        )
    )
    fig.text(season_x, header_y, "Temporada", fontsize=8.5, color=MUTED,
             ha="left", fontweight="bold", zorder=1)
    fig.text(highlight_x, header_y, highlight_header, fontsize=8.5, color=accent,
             ha="center", fontweight="bold", zorder=1)
    if side_header:
        fig.text(side_x, header_y, side_header, fontsize=8.5, color=MUTED,
                 ha="right", fontweight="bold", zorder=1)
    fig.add_artist(
        Line2D([x0, x1], [header_y - 0.021, header_y - 0.021],
               color=accent, linewidth=1.4, transform=fig.transFigure)
    )

    for idx, row in enumerate(rows):
        y = header_y - 0.055 - idx * row_h
        band_bottom = y - 0.016
        band_height = row_h * 0.8
        if idx % 2 == 1:
            fig.add_artist(
                Rectangle(
                    (x0 - 0.012, band_bottom), span + 0.024, band_height,
                    transform=fig.transFigure, facecolor=BAND, edgecolor="none", zorder=-1,
                )
            )
        fig.add_artist(
            Rectangle(
                (highlight_x - band_width / 2, band_bottom), band_width, band_height,
                transform=fig.transFigure, facecolor=accent, alpha=0.09, edgecolor="none",
                zorder=0,
            )
        )
        season = f"{row['year']}" + (" · parcial" if row["partial"] else "")
        fig.text(season_x, y, season, fontsize=10, color=INK,
                 ha="left", fontweight="bold", zorder=1)
        fig.text(highlight_x, y, highlight_values[idx], fontsize=11.5, color=accent,
                 ha="center", fontweight="bold", zorder=1)
        if side_values:
            fig.text(side_x, y, side_values[idx], fontsize=10, color=MUTED,
                     ha="right", zorder=1)

    return header_y - 0.055 - len(rows) * row_h - 0.028


def page_table_category(
    pdf: PdfPages,
    rows: list[dict],
    period_a: dict,
    period_b: dict,
    *,
    category: str,
    pct_key: str,
    players_key: str,
    accent: str,
    avg_key: str,
    med_key: str,
) -> None:
    fig = new_page()
    draw_header(
        fig, "Dados detalhados", f"Tabela por temporada · {category}",
        "Destaque para o percentual de minutos de linha jogados por atletas da categoria.",
    )

    bottom = draw_season_table(
        fig, rows,
        title=None,
        accent=accent,
        top=0.78,
        highlight_header="% dos minutos",
        highlight_values=[fmt_pct(r[pct_key], 2) for r in rows],
        side_header="Atletas com minutos",
        side_values=[fmt_int(r[players_key]) for r in rows],
    )

    fig.add_artist(
        Line2D([MARGIN_L, MARGIN_R], [bottom + 0.012, bottom + 0.012],
               color=RULE, linewidth=0.9, transform=fig.transFigure)
    )
    fig.text(
        MARGIN_L, bottom - 0.018,
        f"{period_a['label']}: média {fmt_pct(period_a[avg_key])} · "
        f"mediana {fmt_pct(period_a[med_key])}",
        fontsize=10.5, color=INK, va="top",
    )
    fig.text(
        MARGIN_L, bottom - 0.052,
        f"{period_b['label']}: média {fmt_pct(period_b[avg_key])} · "
        f"mediana {fmt_pct(period_b[med_key])} · "
        f"variação {fmt_delta_pp(period_a[avg_key], period_b[avg_key])} (média)",
        fontsize=10.5, color=MUTED, va="top",
    )

    save_page(pdf, fig)


def page_sales_lines(pdf: PdfPages, sales: list[dict]) -> None:
    fig = new_page()
    draw_header(fig, "Vendas por janela", "Vendas ao exterior",
                "Atletas sub-20 e sub-23 vendidos por clubes da Série A para clubes de fora do Brasil.")

    years = [r["year"] for r in sales]

    plot_left = MARGIN_L + 0.038
    plot_width = MARGIN_R - plot_left - 0.035
    ax = fig.add_axes((plot_left, 0.215, plot_width, 0.53))

    for key, color, label in (("sales_abroad_u20", C_U20, "Sub-20"),
                              ("sales_abroad_u23", C_U23, "Sub-23")):
        values = [r[key] for r in sales]
        ax.plot(years, values, color=color, linewidth=2.6, label=label,
                marker="o", markersize=6, markerfacecolor=CANVAS,
                markeredgewidth=1.8, zorder=3)
        ax.annotate(fmt_int(values[-1]), (years[-1], values[-1]),
                    xytext=(10, 0), textcoords="offset points", fontsize=10,
                    color=color, fontweight="bold", va="center")

    style_axes(ax)
    ax.set_title("Total de vendas para clubes do exterior", pad=14,
                 loc="left", fontweight="bold")
    ax.set_ylabel("Atletas vendidos")
    ax.set_xlabel("Janela (temporada)")
    ax.set_xlim(years[0] - 0.35, years[-1] + 0.55)
    ax.set_xticks(years)
    ax.set_ylim(0, max(r["sales_abroad_u23"] for r in sales) * 1.25)

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

    fig.text(
        MARGIN_L, 0.135,
        "Considera apenas saídas registradas com valor de transferência e clube de destino fora do Brasil.\n"
        "A janela de 2026 segue aberta e ficou fora desta seção.",
        fontsize=9.5, color=MUTED, va="top", linespacing=1.6,
    )

    save_page(pdf, fig)


def page_sales_bars(pdf: PdfPages, block_a: dict, block_b: dict) -> None:
    fig = new_page()
    draw_header(
        fig, "Vendas por janela", f"{block_a['label']} vs {block_b['label']}",
        "Quadriênio contra triênio de janelas completas — média e mediana de vendas ao exterior.",
    )

    labels = ["Sub-20", "Sub-23"]
    x = [0, 1]
    width = 0.3
    panel_width = 0.372

    panels = [
        {
            "rect": (MARGIN_L + 0.038, 0.195, panel_width, 0.50),
            "title": "Média por janela · vendas ao exterior",
            "a": [block_a["avg_u20"], block_a["avg_u23"]],
            "b": [block_b["avg_u20"], block_b["avg_u23"]],
        },
        {
            "rect": (MARGIN_R - panel_width, 0.195, panel_width, 0.50),
            "title": "Mediana por janela · vendas ao exterior",
            "a": [block_a["med_u20"], block_a["med_u23"]],
            "b": [block_b["med_u20"], block_b["med_u23"]],
        },
    ]

    for panel in panels:
        ax = fig.add_axes(panel["rect"])
        bars_a = ax.bar([i - width / 2 for i in x], panel["a"], width,
                        color=C_PERIOD_A, label=block_a["label"], zorder=3)
        bars_b = ax.bar([i + width / 2 for i in x], panel["b"], width,
                        color=C_PERIOD_B, label=block_b["label"], zorder=3)
        style_axes(ax)
        ax.set_title(panel["title"], pad=12, loc="left", fontweight="bold")
        ax.set_ylabel("Atletas por janela")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11.5, color=INK)
        ax.set_xlim(-0.55, 1.55)
        ax.set_ylim(0, max(panel["a"] + panel["b"]) * 1.42)

        for bars, values in ((bars_a, panel["a"]), (bars_b, panel["b"])):
            for bar, value in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        fmt_num(value), ha="center", va="bottom",
                        fontsize=9.5, color=INK, fontweight="bold")

        for i, (prev, curr) in enumerate(zip(panel["a"], panel["b"])):
            change = 100 * (curr - prev) / prev if prev else 0.0
            color = C_NEGATIVE if change < 0 else C_POSITIVE
            ax.text(
                i, 0.94, f"{change:+.1f}".replace(".", ",") + "%",
                transform=ax.get_xaxis_transform(),
                ha="center", va="center", fontsize=10.5, color=color, fontweight="bold",
                bbox={"boxstyle": "round,pad=0.4", "facecolor": BAND, "edgecolor": "none"},
            )

    fig.legend(
        handles=[
            Rectangle((0, 0), 1, 1, facecolor=C_PERIOD_A, label=block_a["label"]),
            Rectangle((0, 0), 1, 1, facecolor=C_PERIOD_B, label=block_b["label"]),
        ],
        loc="upper right", bbox_to_anchor=(MARGIN_R, 0.845), ncols=2,
        fontsize=10.5, handlelength=1.5, columnspacing=1.8,
    )

    fig.text(
        MARGIN_L, 0.125,
        f"Média e mediana de atletas vendidos ao exterior por janela: {block_a['seasons']} temporadas "
        f"({block_a['label']}) contra {block_b['seasons']} ({block_b['label']}).\n"
        "Os rótulos em destaque mostram quanto o triênio recente ficou acima do quadriênio anterior, em %.",
        fontsize=9.5, color=MUTED, va="top", linespacing=1.6,
    )
    save_page(pdf, fig)


def page_sales_tables(pdf: PdfPages, sales: list[dict]) -> None:
    fig = new_page()
    draw_header(fig, "Vendas por janela", "Tabelas por temporada",
                "Atletas vendidos para clubes de fora do Brasil, por categoria e por janela.")

    column_width = 0.325
    draw_season_table(
        fig, sales,
        title="Sub-20",
        accent=C_U20,
        top=0.78,
        highlight_header="Vendas ao exterior",
        highlight_values=[fmt_int(r["sales_abroad_u20"]) for r in sales],
        x0=MARGIN_L,
        x1=MARGIN_L + column_width,
    )
    draw_season_table(
        fig, sales,
        title="Sub-23",
        accent=C_U23,
        top=0.78,
        highlight_header="Vendas ao exterior",
        highlight_values=[fmt_int(r["sales_abroad_u23"]) for r in sales],
        x0=MARGIN_R - column_width,
        x1=MARGIN_R,
    )

    fig.text(
        MARGIN_L, 0.135,
        "Apenas saídas com valor de transferência registrado e clube de destino fora do Brasil.\n"
        "A janela de 2026 ainda está aberta e não entra na contagem.",
        fontsize=9.5, color=MUTED, va="top", linespacing=1.6,
    )

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

    sales_years = SALES_PERIOD_A + SALES_PERIOD_B
    sales = [r for r in collect_sales_stats() if r["year"] in sales_years]
    sales_a = aggregate_sales_period(sales, SALES_PERIOD_A)
    sales_b = aggregate_sales_period(sales, SALES_PERIOD_B)

    with PdfPages(REPORT_PATH) as pdf:
        pdf.infodict().update(
            {
                "Title": REPORT_TITLE,
                "Subject": "Minutos de sub-20/sub-23 e vendas ao exterior na Série A",
                "Creator": "scripts/generate_serie_a_relatorio.py",
            }
        )
        page_intro(pdf)
        page_lines(pdf, rows)
        page_period_bars(pdf, period_a, period_b)
        page_table_category(
            pdf, rows, period_a, period_b,
            category="Sub-20", pct_key="u20_pct", players_key="u20_players",
            accent=C_U20, avg_key="avg_u20_pct", med_key="med_u20_pct",
        )
        page_table_category(
            pdf, rows, period_a, period_b,
            category="Sub-23", pct_key="u23_pct", players_key="u23_players",
            accent=C_U23, avg_key="avg_u23_pct", med_key="med_u23_pct",
        )
        page_sales_lines(pdf, sales)
        page_sales_bars(pdf, sales_a, sales_b)
        page_sales_tables(pdf, sales)
        page_methodology(pdf)

    meta_path = REPORT_PATH.with_suffix(".json")
    meta_path.write_text(
        json.dumps(
            {
                "yearly": rows,
                "period_a": period_a,
                "period_b": period_b,
                "sales_yearly": sales,
                "sales_period_a": sales_a,
                "sales_period_b": sales_b,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return REPORT_PATH


if __name__ == "__main__":
    path = generate_report()
    print(f"Relatório gerado: {path}")
