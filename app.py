import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("Player Evaluation")

# -------------------------
# Colunas
# -------------------------

columns = [
    "Player",
    "Defensive 1v1",
    "Aerial Duels",
    "Cover",
    "Crosses",
    "Speed",
    "Strenght",
    "CoD",
    "Jump",
    "Aggressiveness",
    "Awareness",
    "Maturity",
    "Creativity"
]

grades = [
    "A+","A","A-",
    "B+","B","B-",
    "C+","C","C-",
    "D+","D","D-",
    "F"
]

# -------------------------
# Escala Numérica
# -------------------------

grade_to_score = {
    "A+": 13, "A": 12, "A-": 11,
    "B+": 10, "B": 9,  "B-": 8,
    "C+": 7,  "C": 6,  "C-": 5,
    "D+": 4,  "D": 3,  "D-": 2,
    "F": 1
}

# -------------------------
# DataFrame Inicial
# -------------------------

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(
        [[""] + ["A"] * (len(columns)-1)],
        columns=columns
    )

# -------------------------
# Editor
# -------------------------

edited_df = st.data_editor(
    st.session_state.data,
    column_config={
        "Player": st.column_config.TextColumn("Player"),
        **{
            col: st.column_config.SelectboxColumn(
                col,
                options=grades
            )
            for col in columns if col != "Player"
        }
    },
    num_rows="dynamic",
    use_container_width=True
)

st.session_state.data = edited_df

# -------------------------
# Gradiente de Cor
# -------------------------

def color_scale(val):
    score = grade_to_score.get(val, 1)

    # Verde escuro → vermelho
    green = int(255 * (score / 13))
    red = 255 - green

    return f'background-color: rgb({red},{green},0); color: black'

styled_df = edited_df.style.map(color_scale, subset=columns[1:])

st.dataframe(styled_df, use_container_width=True)
