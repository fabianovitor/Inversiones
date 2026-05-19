# ============================================================
# app.py - Dashboard Principal
# ============================================================

import streamlit as st

st.set_page_config(
    page_title="Inversiones FCV",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from data_loader import carregar_planilha, separar_carteiras, enriquecer_dados
from tabs import tab_carteira, tab_ericsson, tab_projecao, tab_analises
from tabs.tab_visao_geral import renderizar as render_visao_geral


def main():
    st.title("📊 Dashboard de Inversiones FCV")
    st.caption("Portfólio de dividendos | Dados ao vivo via Google Sheets")

    with st.spinner("Carregando dados da planilha..."):
        df_raw = carregar_planilha()

    if df_raw.empty:
        st.error("❌ Não foi possível carregar os dados.")
        st.stop()

    df = enriquecer_dados(df_raw)
    df_principal, df_ericsson = separar_carteiras(df)

    tabs = st.tabs([
        "🏠 Visão Geral",
        "📊 Carteira",
        "🔵 Ericsson",
        "🎯 Projeção",
        "🔍 Análises",
    ])

    with tabs[0]:
        render_visao_geral(df_principal, df_ericsson)
    with tabs[1]:
        tab_carteira.renderizar(df_principal)
    with tabs[2]:
        tab_ericsson.renderizar(df_ericsson)
    with tabs[3]:
        tab_projecao.renderizar(df_principal, df_ericsson)
    with tabs[4]:
        tab_analises.renderizar(df_principal, df_ericsson)

    st.divider()
    st.caption("⚡ Dashboard atualiza automaticamente a cada 5 minutos")


if __name__ == "__main__":
    main()
