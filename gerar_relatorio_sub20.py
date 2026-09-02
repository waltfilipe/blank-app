"""Gera relatório PDF com gráficos de jogadores sub-20 nas Séries B e C."""

from __future__ import annotations

import io
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import matplotlib.patheffects as pe
from matplotlib.patches import Circle, FancyBboxPatch
from PIL import Image

SERIE_B_FILE = Path("serie b sub 20.xlsx")
SERIE_C_FILE = Path("serie c sub 20.xlsx")
OUTPUT_FILE = Path("relatorio_sub20_serie_b_c.pdf")
LOGO_CACHE_DIR = Path(".cache/logos")

COLORS = {
    "serie_b": "#0D3B1E",
    "serie_b_light": "#1B6B3A",
    "serie_c": "#2E7D32",
    "serie_c_light": "#66BB6A",
    "accent": "#43A047",
    "highlight": "#A5D6A7",
    "bg": "#F4F7F5",
    "card": "#FFFFFF",
    "text": "#1B4332",
    "muted": "#5F6F65",
}

WIKI_NAMES = {
    "AO Itabaiana": "Associação Olímpica de Itabaiana",
    "Amazonas FC": "Amazonas Futebol Clube",
    "América Mineiro": "América Futebol Clube (Minas Gerais)",
    "Anápolis FC": "Anápolis Futebol Clube",
    "Athletic Club": "Athletic Club (Minas Gerais)",
    "Atlético Goianiense": "Atlético Clube Goianiense",
    "Avaí": "Avaí Futebol Clube",
    "Barra FC": "Barra Futebol Clube (Santa Catarina)",
    "Botafogo-SP": "Botafogo Futebol Clube (SP)",
    "Caxias": "Sociedade Esportiva e Recreativa Caxias do Sul",
    "Ceará": "Ceará Sporting Club",
    "Clube De Regatas Brasil": "Clube de Regatas Brasil",
    "Criciúma": "Criciúma Esporte Clube",
    "Cuiabá": "Cuiabá Esporte Clube",
    "Ferroviária": "Associação Ferroviária de Esportes",
    "Figueirense": "Figueirense Futebol Clube",
    "Fortaleza": "Fortaleza Esporte Clube",
    "Goiás": "Goiás Esporte Clube",
    "Grêmio Novorizontino": "Grêmio Novorizontino",
    "Guarani": "Guarani Futebol Clube",
    "Ituano": "Ituano Futebol Clube",
    "Juventude": "Esporte Clube Juventude",
    "Londrina": "Londrina Esporte Clube",
    "Maringá FC": "Maringá Futebol Clube",
    "Náutico": "Clube Náutico Capibaribe",
    "Paysandu SC": "Paysandu Sport Club",
    "Ponte Preta": "Associação Atlética Ponte Preta",
    "Sport Recife": "Sport Club do Recife",
    "Vila Nova FC": "Vila Nova Futebol Clube",
    "Volta Redonda": "Volta Redonda Futebol Clube",
}


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df_b = pd.read_excel(SERIE_B_FILE)
    df_c = pd.read_excel(SERIE_C_FILE)
    df_b["Divisão"] = "Série B"
    df_c["Divisão"] = "Série C"
    return df_b, df_c, pd.concat([df_b, df_c])


def club_stats(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("Team")
        .agg(
            jogadores=("Name", "count"),
            media_minutos=("Minutes played", "mean"),
            minutos_total=("Minutes played", "sum"),
        )
        .sort_values("jogadores", ascending=False)
        .reset_index()
    )


def minute_distribution(df: pd.DataFrame) -> pd.Series:
    bins = [0, 90, 450, 900, 1350, 99999]
    labels = ["< 90", "90-450", "451-900", "901-1350", "> 1350"]
    return pd.cut(df["Minutes played"], bins=bins, labels=labels, right=True).value_counts().sort_index()


def _slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


def _fetch_logo_url(team: str) -> str | None:
    title = WIKI_NAMES.get(team, team)
    url = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
    response = requests.get(url, timeout=12, headers={"User-Agent": "sub20-report/1.0"})
    if response.status_code != 200:
        return None
    return response.json().get("thumbnail", {}).get("source")


def get_team_logo(team: str) -> Image.Image | None:
    LOGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = LOGO_CACHE_DIR / f"{_slugify(team)}.png"

    if cache_path.exists():
        return Image.open(cache_path).convert("RGBA")

    logo_url = _fetch_logo_url(team)
    if not logo_url:
        return None

    response = requests.get(logo_url, timeout=15, headers={"User-Agent": "sub20-report/1.0"})
    if response.status_code != 200:
        return None

    image = Image.open(io.BytesIO(response.content)).convert("RGBA")
    image.save(cache_path)
    return image


def _style_page(fig: plt.Figure, title: str, subtitle: str | None = None) -> None:
    fig.patch.set_facecolor(COLORS["bg"])
    fig.suptitle(title, fontsize=16, fontweight="bold", color="#1B4332", y=0.98)
    if subtitle:
        fig.text(0.5, 0.93, subtitle, ha="center", fontsize=10, color="#555555")


def _add_logo_below_bar(ax, x: float, team: str, logo: Image.Image | None, zoom: float = 0.16) -> None:
    if logo is not None:
        image = OffsetImage(logo, zoom=zoom)
        ab = AnnotationBbox(image, (x, 0), xycoords=("data", "axes fraction"), frameon=False, box_alignment=(0.5, 1.0))
        ax.add_artist(ab)
        return

    initials = "".join(part[0].upper() for part in team.split()[:2])
    circle = Circle((x, -0.08), 0.06, transform=ax.get_xaxis_transform(), color="#E8F5E9", ec="#2E7D32", lw=1.2, zorder=3)
    ax.add_patch(circle)
    ax.text(x, -0.08, initials, transform=ax.get_xaxis_transform(), ha="center", va="center", fontsize=7, fontweight="bold", color="#1B5E20", zorder=4)


def chart_player_quantity_pie(df_b: pd.DataFrame, df_c: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor(COLORS["bg"])
    _style_page(fig, "1. Quantidade de jogadores sub-20", "Distribuição por divisão")

    ax = fig.add_axes([0.12, 0.28, 0.76, 0.58])
    ax.set_facecolor(COLORS["bg"])

    values = [len(df_b), len(df_c)]
    total = sum(values)
    pct_b = values[0] / total * 100
    pct_c = values[1] / total * 100

    palette = [COLORS["serie_b"], COLORS["serie_c_light"]]
    explode = (0.05, 0.05)

    wedges, _ = ax.pie(
        values,
        colors=palette,
        startangle=92,
        explode=explode,
        wedgeprops={
            "width": 0.44,
            "edgecolor": COLORS["card"],
            "linewidth": 3.5,
            "joinstyle": "round",
        },
    )

    for wedge in wedges:
        wedge.set_path_effects([pe.withSimplePatchShadow(offset=(2, -2), shadow_rgbFace="#90A4AE", alpha=0.28)])

    center = Circle((0, 0), 0.56, fc=COLORS["card"], ec="#DDE8E0", lw=2.2, zorder=5)
    ax.add_patch(center)

    ax.text(0, 0.14, "TOTAL", ha="center", va="center", fontsize=11, fontweight="bold", color=COLORS["muted"], zorder=6)
    ax.text(0, -0.06, str(total), ha="center", va="center", fontsize=36, fontweight="bold", color=COLORS["text"], zorder=6)
    ax.text(0, -0.27, "jogadores sub-20", ha="center", va="center", fontsize=10, color=COLORS["muted"], zorder=6)

    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.15, 1.15)
    ax.set_aspect("equal")
    ax.axis("off")

    meta = [
        ("Série B", values[0], pct_b, palette[0]),
        ("Série C", values[1], pct_c, palette[1]),
    ]

    legend_ax = fig.add_axes([0.08, 0.08, 0.84, 0.14])
    legend_ax.set_facecolor(COLORS["bg"])
    legend_ax.axis("off")

    for idx, (label, count, pct, color) in enumerate(meta):
        x0 = 0.04 + idx * 0.5
        legend_ax.add_patch(
            FancyBboxPatch(
                (x0, 0.08),
                0.44,
                0.84,
                transform=legend_ax.transAxes,
                boxstyle="round,pad=0.015,rounding_size=0.02",
                facecolor=COLORS["card"],
                edgecolor="#DDE8E0",
                linewidth=1.4,
            )
        )
        legend_ax.add_patch(
            FancyBboxPatch(
                (x0 + 0.03, 0.2),
                0.035,
                0.6,
                transform=legend_ax.transAxes,
                boxstyle="square,pad=0",
                facecolor=color,
                edgecolor="none",
            )
        )
        legend_ax.text(x0 + 0.08, 0.72, label, ha="left", va="center", fontsize=12, fontweight="bold", color=COLORS["text"], transform=legend_ax.transAxes)
        legend_ax.text(x0 + 0.08, 0.48, f"{count} jogadores", ha="left", va="center", fontsize=10.5, color=COLORS["muted"], transform=legend_ax.transAxes)
        legend_ax.text(x0 + 0.08, 0.24, f"{pct:.1f}% do total", ha="left", va="center", fontsize=10, color=color, fontweight="bold", transform=legend_ax.transAxes)
        legend_ax.text(x0 + 0.38, 0.5, f"{pct:.1f}%", ha="center", va="center", fontsize=22, fontweight="bold", color=color, transform=legend_ax.transAxes)

    legend_ax.text(
        0.5,
        -0.02,
        f"Diferença de {abs(values[0] - values[1])} jogadores entre as divisões (Série B com maior volume)",
        ha="center",
        va="top",
        fontsize=9.5,
        color=COLORS["muted"],
        transform=legend_ax.transAxes,
    )

    return fig


def chart_clubs_with_logos(stats: pd.DataFrame, title: str, subtitle: str, color: str, top_n: int = 10) -> plt.Figure:
    data = stats.head(top_n).iloc[::-1]
    teams = data["Team"].tolist()
    values = data["jogadores"].tolist()

    fig, ax = plt.subplots(figsize=(11, 8.5))
    _style_page(fig, title, subtitle)

    bars = ax.barh(teams, values, color=color, edgecolor="white", height=0.65)
    ax.set_xlabel("Quantidade de jogadores sub-20", fontsize=11)
    ax.set_xlim(0, max(values) * 1.25)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)

    for bar, value in zip(bars, values):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2, str(int(value)), va="center", fontsize=10, fontweight="bold", color="#1B4332")

    logos = [get_team_logo(team) for team in teams]
    for idx, (team, logo) in enumerate(zip(teams, logos)):
        y = idx
        if logo is not None:
            image = OffsetImage(logo, zoom=0.11)
            ab = AnnotationBbox(image, (-0.55, y), xycoords=("data", "data"), frameon=False, box_alignment=(1.0, 0.5))
            ax.add_artist(ab)
        else:
            initials = "".join(part[0].upper() for part in team.split()[:2])
            ax.text(-0.35, y, initials, ha="center", va="center", fontsize=8, fontweight="bold", color="#1B5E20", bbox=dict(boxstyle="circle,pad=0.25", facecolor="#E8F5E9", edgecolor="#2E7D32"))

    ax.set_xlim(-0.8, max(values) * 1.25)
    fig.subplots_adjust(top=0.86, left=0.22, right=0.96, bottom=0.08)
    return fig


def chart_clubs_column_with_logos(stats: pd.DataFrame, title: str, subtitle: str, color: str, top_n: int = 10) -> plt.Figure:
    data = stats.head(top_n)
    teams = data["Team"].tolist()
    values = data["jogadores"].tolist()
    x = range(len(teams))

    fig, ax = plt.subplots(figsize=(11, 8.5))
    _style_page(fig, title, subtitle)

    bars = ax.bar(x, values, color=color, edgecolor="white", width=0.72)
    ax.set_ylabel("Quantidade de jogadores sub-20", fontsize=11)
    ax.set_xticks(list(x))
    ax.set_xticklabels([])
    ax.set_ylim(0, max(values) * 1.28)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)

    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, str(int(value)), ha="center", fontsize=10, fontweight="bold", color="#1B4332")

    logos = [get_team_logo(team) for team in teams]
    for idx, (team, logo) in enumerate(zip(teams, logos)):
        _add_logo_below_bar(ax, idx, team, logo, zoom=0.11)

    ax.tick_params(axis="x", length=0)
    fig.subplots_adjust(top=0.86, bottom=0.18)
    return fig


def chart_minute_distribution(df_b: pd.DataFrame, df_c: pd.DataFrame) -> plt.Figure:
    dist_b = minute_distribution(df_b)
    dist_c = minute_distribution(df_c)
    labels = [str(label) for label in dist_b.index]
    x = range(len(labels))
    width = 0.36

    fig, ax = plt.subplots(figsize=(11, 8.5))
    _style_page(fig, "3.1 Distribuição por faixa de minutos", "Comparativo Série B x Série C")

    bars_b = ax.bar([i - width / 2 for i in x], dist_b.values, width=width, label="Série B", color=COLORS["serie_b"], edgecolor="white")
    bars_c = ax.bar([i + width / 2 for i in x], dist_c.values, width=width, label="Série C", color=COLORS["serie_c"], edgecolor="white")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Quantidade de jogadores", fontsize=11)
    ax.set_xlabel("Faixa de minutos jogados", fontsize=11)
    ax.legend(loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.spines[["top", "right"]].set_visible(False)

    for bars in (bars_b, bars_c):
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, height + 0.6, str(int(height)), ha="center", fontsize=9, fontweight="bold", color="#1B4332")

    fig.subplots_adjust(top=0.86, bottom=0.12)
    return fig


def chart_team_tables(stats: pd.DataFrame, title: str, subtitle: str, rows_per_page: int = 22) -> list[plt.Figure]:
    headers = ["#", "Clube", "Jogadores", "Média min", "Total min"]
    figures: list[plt.Figure] = []

    for page_start in range(0, len(stats), rows_per_page):
        page_data = stats.iloc[page_start : page_start + rows_per_page]
        page_num = page_start // rows_per_page + 1
        total_pages = (len(stats) + rows_per_page - 1) // rows_per_page

        fig, ax = plt.subplots(figsize=(11, 8.5))
        _style_page(fig, title, f"{subtitle} — página {page_num}/{total_pages}")
        ax.axis("off")

        rows = []
        for rank, row in enumerate(page_data.itertuples(), start=page_start + 1):
            rows.append(
                [
                    str(rank),
                    row.Team,
                    str(int(row.jogadores)),
                    f"{row.media_minutos:.1f}",
                    str(int(row.minutos_total)),
                ]
            )

        table = ax.table(
            cellText=rows,
            colLabels=headers,
            loc="center",
            cellLoc="center",
            colWidths=[0.06, 0.44, 0.14, 0.16, 0.16],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9.5)
        table.scale(1, 1.55)

        for (row_idx, col_idx), cell in table.get_celld().items():
            cell.set_edgecolor("#DDE8E0")
            if row_idx == 0:
                cell.set_facecolor(COLORS["serie_b"])
                cell.set_text_props(color="white", fontweight="bold")
            elif row_idx % 2 == 0:
                cell.set_facecolor("#F1F8F4")
            else:
                cell.set_facecolor(COLORS["card"])
            if col_idx == 1 and row_idx > 0:
                cell.get_text().set_ha("left")
                cell.PAD = 0.04

        fig.subplots_adjust(top=0.86, bottom=0.06, left=0.06, right=0.94)
        figures.append(fig)

    return figures


def build_pdf(df_b: pd.DataFrame, df_c: pd.DataFrame, df_all: pd.DataFrame) -> Path:
    stats_b = club_stats(df_b)
    stats_c = club_stats(df_c)
    stats_all = club_stats(df_all)

    charts = [
        chart_player_quantity_pie(df_b, df_c),
        chart_clubs_column_with_logos(stats_b, "2. Clubes que mais utilizam jogadores sub-20", "Série B — Top 10", COLORS["serie_b"]),
        chart_clubs_column_with_logos(stats_c, "2. Clubes que mais utilizam jogadores sub-20", "Série C — Top 10", COLORS["serie_c"]),
        chart_clubs_column_with_logos(stats_all, "2.1 Destaque geral (Séries B e C)", "Top 10 combinado", COLORS["accent"]),
        chart_minute_distribution(df_b, df_c),
    ]
    tables = [
        *chart_team_tables(stats_b, "4. Tabelas por clube", "Série B — todos os times"),
        *chart_team_tables(stats_c, "4. Tabelas por clube", "Série C — todos os times"),
        *chart_team_tables(stats_all, "4. Tabelas por clube", "Geral (Séries B e C) — todos os times"),
    ]

    cover, ax_cover = plt.subplots(figsize=(11, 8.5))
    cover.patch.set_facecolor(COLORS["bg"])
    ax_cover.axis("off")
    cover.text(0.5, 0.62, "Relatório de Jogadores Sub-20", ha="center", fontsize=24, fontweight="bold", color="#1B4332", transform=ax_cover.transAxes)
    cover.text(0.5, 0.54, "Séries B e C — Campeonato Brasileiro", ha="center", fontsize=14, color="#555555", transform=ax_cover.transAxes)
    cover.text(
        0.5,
        0.34,
        "Gráficos: quantidade por divisão, clubes com maior uso de sub-20\ne distribuição por faixa de minutos.",
        ha="center",
        fontsize=11,
        color="#444444",
        transform=ax_cover.transAxes,
    )

    with PdfPages(OUTPUT_FILE) as pdf:
        pdf.savefig(cover, facecolor=COLORS["bg"])
        for chart in charts:
            pdf.savefig(chart, facecolor=COLORS["bg"])
        for table in tables:
            pdf.savefig(table, facecolor=COLORS["bg"])
        plt.close(cover)
        for chart in charts:
            plt.close(chart)
        for table in tables:
            plt.close(table)

    return OUTPUT_FILE


def main() -> None:
    if not SERIE_B_FILE.exists() or not SERIE_C_FILE.exists():
        raise FileNotFoundError("Arquivos Excel das Séries B e C não encontrados.")

    df_b, df_c, df_all = load_data()
    output = build_pdf(df_b, df_c, df_all)
    print(f"PDF gerado: {output.resolve()}")


if __name__ == "__main__":
    main()
