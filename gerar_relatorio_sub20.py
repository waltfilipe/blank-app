"""Gera relatório PDF com estatísticas de jogadores sub-20 nas Séries B e C."""

from datetime import datetime
from pathlib import Path

import pandas as pd
from fpdf import FPDF


SERIE_B_FILE = Path("serie b sub 20.xlsx")
SERIE_C_FILE = Path("serie c sub 20.xlsx")
OUTPUT_FILE = Path("relatorio_sub20_serie_b_c.pdf")


class RelatorioPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20, 60, 40)
        self.cell(0, 10, "Relatório de Jogadores Sub-20", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, "Séries B e C do Campeonato Brasileiro", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(20, 80, 50)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(20, 80, 50)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def add_table(self, headers: list[str], rows: list[list], col_widths: list[float] | None = None):
        if col_widths is None:
            col_widths = [self.epw / len(headers)] * len(headers)

        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(230, 245, 235)
        self.set_text_color(20, 60, 40)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
        self.ln()

        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        fill = False
        for row in rows:
            if self.get_y() > 270:
                self.add_page()
                self.set_font("Helvetica", "B", 9)
                self.set_fill_color(230, 245, 235)
                self.set_text_color(20, 60, 40)
                for i, header in enumerate(headers):
                    self.cell(col_widths[i], 8, header, border=1, align="C", fill=True)
                self.ln()
                self.set_font("Helvetica", "", 9)
                self.set_text_color(30, 30, 30)

            if fill:
                self.set_fill_color(248, 252, 249)
            else:
                self.set_fill_color(255, 255, 255)

            for i, value in enumerate(row):
                align = "L" if i == 0 else "C"
                self.cell(col_widths[i], 7, str(value), border=1, align=align, fill=True)
            self.ln()
            fill = not fill
        self.ln(3)


def load_data():
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
            minutos_total=("Minutes played", "sum"),
            media_minutos=("Minutes played", "mean"),
        )
        .sort_values("jogadores", ascending=False)
        .reset_index()
    )


def minute_distribution(df: pd.DataFrame) -> pd.Series:
    bins = [0, 90, 450, 900, 1350, 99999]
    labels = ["< 90 min", "90-450 min", "451-900 min", "901-1350 min", "> 1350 min"]
    return pd.cut(df["Minutes played"], bins=bins, labels=labels, right=True).value_counts().sort_index()


def build_pdf(df_b: pd.DataFrame, df_c: pd.DataFrame, df_all: pd.DataFrame) -> Path:
    pdf = RelatorioPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.body_text(f"Gerado em: {generated_at}")
    pdf.body_text(
        "Este relatório apresenta a quantidade de jogadores sub-20, os clubes que mais "
        "utilizam essa categoria e a média de minutos jogados nas Séries B e C."
    )

    pdf.section_title("1. Quantidade de jogadores sub-20")
    pdf.add_table(
        ["Divisão", "Jogadores"],
        [
            ["Série B", str(len(df_b))],
            ["Série C", str(len(df_c))],
            ["Total (B + C)", str(len(df_all))],
        ],
        col_widths=[120, 60],
    )

    pdf.section_title("2. Clubes que mais utilizam jogadores sub-20")

    for title, df in [("Série B", df_b), ("Série C", df_c)]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        stats = club_stats(df).head(10)
        pdf.add_table(
            ["Clube", "Jogadores", "Média min", "Total min"],
            [
                [
                    row.Team,
                    str(int(row.jogadores)),
                    f"{row.media_minutos:.1f}",
                    str(int(row.minutos_total)),
                ]
                for row in stats.itertuples()
            ],
            col_widths=[75, 30, 35, 35],
        )

    pdf.section_title("2.1 Destaque geral (Séries B e C)")
    stats_all = club_stats(df_all).head(10)
    pdf.add_table(
        ["Clube", "Jogadores", "Média min", "Total min"],
        [
            [
                row.Team,
                str(int(row.jogadores)),
                f"{row.media_minutos:.1f}",
                str(int(row.minutos_total)),
            ]
            for row in stats_all.itertuples()
        ],
        col_widths=[75, 30, 35, 35],
    )

    pdf.section_title("3. Média de minutos dos jogadores sub-20")
    pdf.add_table(
        ["Divisão", "Média", "Mediana"],
        [
            ["Série B", f"{df_b['Minutes played'].mean():.1f} min", f"{df_b['Minutes played'].median():.0f} min"],
            ["Série C", f"{df_c['Minutes played'].mean():.1f} min", f"{df_c['Minutes played'].median():.0f} min"],
            [
                "Geral (B + C)",
                f"{df_all['Minutes played'].mean():.1f} min",
                f"{df_all['Minutes played'].median():.0f} min",
            ],
        ],
        col_widths=[70, 55, 55],
    )

    pdf.body_text(
        "A mediana abaixo da média indica que poucos jogadores concentram muitos minutos, "
        "enquanto a maioria atua com pouca minutagem."
    )

    pdf.section_title("3.1 Distribuição por faixa de minutos")
    for title, df in [("Série B", df_b), ("Série C", df_c)]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        dist = minute_distribution(df)
        pdf.add_table(
            ["Faixa de minutos", "Jogadores"],
            [[str(idx), str(val)] for idx, val in dist.items()],
            col_widths=[100, 50],
        )

    pdf.section_title("Observações")
    pdf.body_text(
        "- Na Série B, Ponte Preta lidera em volume (11 jogadores), mas com baixa média de minutos (~194 min/jogador).\n"
        "- Ceará e Avaí combinam volume alto com uso mais consistente (médias de 424 e 460 min).\n"
        "- Na Série C, Paysandu SC se destaca pelo equilíbrio entre quantidade (7) e minutagem (400 min de média).\n"
        "- A Série B apresenta média de minutos superior à Série C (302 vs 193 min)."
    )

    pdf.output(OUTPUT_FILE)
    return OUTPUT_FILE


def main():
    if not SERIE_B_FILE.exists() or not SERIE_C_FILE.exists():
        raise FileNotFoundError("Arquivos Excel das Séries B e C não encontrados.")

    df_b, df_c, df_all = load_data()
    output = build_pdf(df_b, df_c, df_all)
    print(f"PDF gerado: {output.resolve()}")


if __name__ == "__main__":
    main()
