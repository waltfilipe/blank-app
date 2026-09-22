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

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

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

    if len(dob_by_id) < len(all_ids):
        dob_by_id.update(load_or_build_dob_cache(all_ids))

    for year, players in sorted(season_players.items()):
        total_minutes = 0
        u20_minutes = 0
        u23_minutes = 0
        u20_players = 0
        u23_players = 0

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
                "partial": year == 2026,
            }
        )
    return rows


def aggregate_period(rows: list[dict], years: list[int]) -> dict:
    subset = [r for r in rows if r["year"] in years]
    total = sum(r["total_minutes"] for r in subset)
    u20 = sum(r["u20_minutes"] for r in subset)
    u23 = sum(r["u23_minutes"] for r in subset)
    n = len(years)
    return {
        "years": years,
        "label": f"{years[0]}–{years[-1]}",
        "total_minutes": total,
        "u20_minutes": u20,
        "u23_minutes": u23,
        "u20_pct": 100 * u20 / total,
        "u23_pct": 100 * u23 / total,
        "avg_u20": u20 / n,
        "avg_u23": u23 / n,
    }


def add_text_page(pdf: PdfPages, title: str, paragraphs: list[str]) -> None:
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.axis("off")
    ax.text(0.05, 0.92, title, fontsize=20, fontweight="bold", va="top")
    y = 0.84
    for paragraph in paragraphs:
        wrapped = textwrap.fill(paragraph, width=105)
        ax.text(0.05, y, wrapped, fontsize=11, va="top")
        y -= 0.06 + 0.018 * wrapped.count("\n")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def plot_line_charts(pdf: PdfPages, rows: list[dict]) -> None:
    years = [r["year"] for r in rows]
    u20 = [r["u20_minutes"] for r in rows]
    u23 = [r["u23_minutes"] for r in rows]
    u20_pct = [r["u20_pct"] for r in rows]
    u23_pct = [r["u23_pct"] for r in rows]

    fig, axes = plt.subplots(2, 1, figsize=(11.69, 8.27), sharex=True)

    axes[0].plot(years, u20, marker="o", linewidth=2.2, label="Sub-20")
    axes[0].plot(years, u23, marker="o", linewidth=2.2, label="Sub-23")
    axes[0].set_title("Minutos jogados por ano (sem goleiros)")
    axes[0].set_ylabel("Minutos")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    if rows[-1]["partial"]:
        axes[0].annotate(
            "2026 parcial",
            xy=(years[-1], u23[-1]),
            xytext=(years[-1] - 0.7, u23[-1] + 20000),
            arrowprops={"arrowstyle": "->"},
            fontsize=9,
        )

    axes[1].plot(years, u20_pct, marker="o", linewidth=2.2, label="Sub-20 (% do total)")
    axes[1].plot(years, u23_pct, marker="o", linewidth=2.2, label="Sub-23 (% do total)")
    axes[1].set_title("Participação relativa na temporada")
    axes[1].set_xlabel("Temporada")
    axes[1].set_ylabel("% dos minutos")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def plot_period_bars(pdf: PdfPages, period_a: dict, period_b: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))

    labels = [period_a["label"], period_b["label"]]
    x = range(len(labels))
    width = 0.35

    u20_totals = [period_a["u20_minutes"], period_b["u20_minutes"]]
    u23_totals = [period_a["u23_minutes"], period_b["u23_minutes"]]
    bars_u20 = axes[0].bar([i - width / 2 for i in x], u20_totals, width, label="Sub-20")
    bars_u23 = axes[0].bar([i + width / 2 for i in x], u23_totals, width, label="Sub-23")
    axes[0].set_title("Minutos totais: 4 anos vs 4 anos")
    axes[0].set_xticks(list(x), labels)
    axes[0].set_ylabel("Minutos acumulados")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.3)
    for bars in (bars_u20, bars_u23):
        for bar in bars:
            axes[0].text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{int(bar.get_height()):,}".replace(",", "."),
                ha="center",
                va="bottom",
                fontsize=8,
            )

    u20_avg = [period_a["avg_u20"], period_b["avg_u20"]]
    u23_avg = [period_a["avg_u23"], period_b["avg_u23"]]
    u20_pct = [period_a["u20_pct"], period_b["u20_pct"]]
    u23_pct = [period_a["u23_pct"], period_b["u23_pct"]]

    bars_u20_avg = axes[1].bar([i - width / 2 for i in x], u20_avg, width, label="Sub-20 (média/ano)")
    bars_u23_avg = axes[1].bar([i + width / 2 for i in x], u23_avg, width, label="Sub-23 (média/ano)")
    axes[1].set_title("Média anual e participação percentual")
    axes[1].set_xticks(list(x), labels)
    axes[1].set_ylabel("Minutos médios por temporada")
    axes[1].legend(loc="upper left")
    axes[1].grid(axis="y", alpha=0.3)
    for bar in bars_u20_avg:
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{int(bar.get_height()):,}".replace(",", "."),
            ha="center",
            va="bottom",
            fontsize=8,
        )
    for bar in bars_u23_avg:
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{int(bar.get_height()):,}".replace(",", "."),
            ha="center",
            va="bottom",
            fontsize=8,
        )

    pct_text = (
        f"Share sub-20: {period_a['u20_pct']:.1f}% → {period_b['u20_pct']:.1f}% | "
        f"Share sub-23: {period_a['u23_pct']:.1f}% → {period_b['u23_pct']:.1f}%"
    )
    fig.suptitle("Comparativo 2019–2022 vs 2023–2026", fontsize=14, fontweight="bold")
    fig.text(0.5, 0.02, pct_text, ha="center", fontsize=10)

    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def plot_yearly_table(pdf: PdfPages, rows: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.axis("off")
    ax.set_title("Tabela anual (minutos e participação)", fontsize=14, fontweight="bold", pad=16)

    columns = [
        "Ano",
        "Total min.",
        "Sub-20 min.",
        "Sub-20 %",
        "Sub-23 min.",
        "Sub-23 %",
        "Obs.",
    ]
    table_rows = []
    for row in rows:
        table_rows.append(
            [
                str(row["year"]),
                f"{row['total_minutes']:,}".replace(",", "."),
                f"{row['u20_minutes']:,}".replace(",", "."),
                f"{row['u20_pct']:.2f}%",
                f"{row['u23_minutes']:,}".replace(",", "."),
                f"{row['u23_pct']:.2f}%",
                "Parcial" if row["partial"] else "",
            ]
        )

    table = ax.table(
        cellText=table_rows,
        colLabels=columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def generate_report() -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        dob_by_id = {int(k): parse_iso_date(v) for k, v in cache.items()}
    else:
        dob_by_id = {}

    rows = collect_season_stats(dob_by_id)
    period_a = aggregate_period(rows, PERIOD_A)
    period_b = aggregate_period(rows, PERIOD_B)

    methodology = [
        "Fonte: FotMob — estatística mins_played da Série A (liga 268), temporadas 2019 a 2026.",
        "Goleiros excluídos (posição FotMob 11). Demais jogadores de linha entram na base de minutos.",
        "Sub-20 no ano Y: atletas nascidos em Y−20 ou depois (ex.: 2019 → nascidos desde 1999).",
        "Sub-23 no ano Y: atletas nascidos em Y−23 ou depois (ex.: 2019 → nascidos desde 1996).",
        "A temporada 2026 está em andamento no FotMob; volumes absolutos desse ano são parciais.",
        "Comparativo 4×4: bloco 2019–2022 versus bloco 2023–2026, com médias anuais e percentuais.",
    ]

    with PdfPages(REPORT_PATH) as pdf:
        add_text_page(
            pdf,
            "Relatório Série A — Minutos Sub-20 e Sub-23",
            [
                "Análise comparativa de minutos jogados por atletas de categorias sub-20 e sub-23 "
                "na Série A brasileira, com recorte anual e agregação em dois blocos de quatro temporadas.",
                *methodology,
            ],
        )
        plot_line_charts(pdf, rows)
        plot_period_bars(pdf, period_a, period_b)
        plot_yearly_table(pdf, rows)

    meta_path = REPORT_PATH.with_suffix(".json")
    meta_path.write_text(
        json.dumps({"yearly": rows, "period_a": period_a, "period_b": period_b}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return REPORT_PATH


if __name__ == "__main__":
    path = generate_report()
    print(f"Relatório gerado: {path}")
