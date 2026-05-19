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

from debug_manager import debug, renderizar_sidebar_debug
from data_loader import carregar_planilha, separar_carteiras, enriquecer_dados, resumo_carteira
from tabs import tab_carteira, tab_ericsson, tab_projecao, tab_analises
from tabs.tab_visao_geral import renderizar as render_visao_geral


def main():
    # Sidebar debug (sempre visível para erros)
    renderizar_sidebar_debug()

    st.title("Dashboard de Inversiones FCV")
    st.caption("Portfólio de dividendos | Dados ao vivo via Google Sheets")

    with st.spinner("Carregando dados da planilha..."):
        try:
            df_raw = carregar_planilha()
            debug.log("app", "planilha_carregada", f"{len(df_raw)} linhas")
            debug.log_df("app", "df_raw", df_raw)
        except Exception as e:
            debug.log_erro("app", e)
            df_raw = None

    if df_raw is None or df_raw.empty:
        st.error("❌ Não foi possível carregar os dados.")
        st.info("Ative o Modo Debug na sidebar e baixe o arquivo para diagnóstico.")
        st.stop()

    try:
        df = enriquecer_dados(df_raw)
        debug.log_df("app", "df_enriquecido", df)
    except Exception as e:
        debug.log_erro("app", e)
        st.error(f"❌ Erro ao enriquecer dados: {e}")
        st.stop()

    try:
        df_principal, df_ericsson = separar_carteiras(df)
        debug.log("app", "df_principal_linhas", len(df_principal))
        debug.log("app", "df_ericsson_linhas", len(df_ericsson))
        debug.log_resumo("app_principal", resumo_carteira(df_principal))
        debug.log_resumo("app_ericsson", resumo_carteira(df_ericsson))
    except Exception as e:
        debug.log_erro("app", e)
        st.error(f"❌ Erro ao separar carteiras: {e}")
        st.stop()

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
