# ============================================================
# app.py - Aplicação principal do dashboard
# ============================================================

import streamlit as st
import pandas as pd

from config import (
    APP_TITULO,
    APP_ICONE,
    APP_LAYOUT,
    MOSTRAR_ERICSSON,
    BRL_USD,
)
from data_loader import carregar_carteira, separar_carteiras, resumo_carteira
from utils import formatar_moeda, formatar_pct, formatar_compacto, emoji_tendencia


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title=APP_TITULO,
    page_icon=APP_ICONE,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS GLOBAL
# ============================================================

st.markdown("""
<style>
    /* Métricas */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem;
        font-weight: 700;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.9rem;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        padding: 0 20px;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
    }

    /* Cards de métricas */
    .metric-card {
        background: #1E1E2E;
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #2D2D3F;
        margin-bottom: 8px;
    }

    /* Esconde rodapé do Streamlit */
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar(df_principal: pd.DataFrame,
                   df_ericsson: pd.DataFrame) -> None:
    """Renderiza a barra lateral com resumo e controles."""

    with st.sidebar:
        st.markdown(f"## {APP_ICONE} {APP_TITULO}")
        st.divider()

        # --- Resumo geral ---
        resumo_p = resumo_carteira(df_principal)
        resumo_e = resumo_carteira(df_ericsson) if MOSTRAR_ERICSSON else {}

        patrimonio_total = (
            resumo_p.get("patrimonio_total", 0)
            + resumo_e.get("patrimonio_total", 0)
        )
        renda_mensal = (
            resumo_p.get("renda_mensal", 0)
            + resumo_e.get("renda_mensal", 0)
        )

        st.markdown("### 💼 Portfólio Total")
        st.metric(
            "Patrimônio",
            formatar_compacto(patrimonio_total),
            delta=None,
        )
        st.metric(
            "Renda Mensal",
            formatar_moeda(renda_mensal),
            delta=None,
        )

        st.divider()

        # --- Carteira Principal ---
        st.markdown("### 📊 Carteira Principal")
        col1, col2 = st.columns(2)
        col1.metric("Ativos", resumo_p.get("num_ativos", 0))
        col2.metric("YoC", formatar_pct(resumo_p.get("yoc_medio", 0)))

        lucro_p = resumo_p.get("lucro_total_usd", 0)
        st.metric(
            "Lucro/Prejuízo",
            formatar_moeda(lucro_p),
            delta=formatar_pct(resumo_p.get("lucro_total_pct", 0)),
            delta_color="normal",
        )

        # --- Carteira Ericsson ---
        if MOSTRAR_ERICSSON and not df_ericsson.empty:
            st.divider()
            st.markdown("### 🔵 Ericsson (ERIC)")
            lucro_e = resumo_e.get("lucro_total_usd", 0)
            st.metric(
                "Patrimônio",
                formatar_compacto(resumo_e.get("patrimonio_total", 0)),
            )
            st.metric(
                "Lucro/Prejuízo",
                formatar_moeda(lucro_e),
                delta=formatar_pct(resumo_e.get("lucro_total_pct", 0)),
                delta_color="normal",
            )

        st.divider()

        # --- Câmbio ---
        st.markdown(f"💱 **USD/BRL:** R$ {BRL_USD:.2f}")

        # --- Botão de atualizar ---
        st.divider()
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption("Dados: Google Sheets + yfinance")


# ============================================================
# TABS PRINCIPAIS
# ============================================================

def render_tabs(df_principal: pd.DataFrame,
                df_ericsson: pd.DataFrame) -> None:
    """Renderiza as tabs do dashboard."""

    tabs = st.tabs([
        "📊 Visão Geral",
        "📈 Performance",
        "💰 Dividendos",
        "🎯 Alocação",
        "🔵 Ericsson",
        "🔍 Detalhes",
    ])

    # --- Tab 1: Visão Geral ---
    with tabs[0]:
        _render_visao_geral(df_principal, df_ericsson)

    # --- Tab 2: Performance ---
    with tabs[1]:
        _render_performance(df_principal)

    # --- Tab 3: Dividendos ---
    with tabs[2]:
        _render_dividendos(df_principal)

    # --- Tab 4: Alocação ---
    with tabs[3]:
        _render_alocacao(df_principal)

    # --- Tab 5: Ericsson ---
    with tabs[4]:
        _render_ericsson(df_ericsson)

    # --- Tab 6: Detalhes ---
    with tabs[5]:
        _render_detalhes(df_principal, df_ericsson)


# ============================================================
# TAB 1: VISÃO GERAL
# ============================================================

def _render_visao_geral(df_principal: pd.DataFrame,
                         df_ericsson: pd.DataFrame) -> None:
    """Tab de visão geral do portfólio."""

    st.markdown("## 📊 Visão Geral do Portfólio")

    resumo_p = resumo_carteira(df_principal)
    resumo_e = resumo_carteira(df_ericsson) if MOSTRAR_ERICSSON else {}

    # --- Métricas principais ---
    patrimonio_total = (
        resumo_p.get("patrimonio_total", 0)
        + resumo_e.get("patrimonio_total", 0)
    )
    renda_anual = (
        resumo_p.get("renda_anual", 0)
        + resumo_e.get("renda_anual", 0)
    )
    renda_mensal = renda_anual / 12
    lucro_total  = (
        resumo_p.get("lucro_total_usd", 0)
        + resumo_e.get("lucro_total_usd", 0)
    )
    custo_total  = (
        resumo_p.get("custo_total", 0)
        + resumo_e.get("custo_total", 0)
    )
    lucro_pct = (lucro_total / custo_total * 100) if custo_total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "💼 Patrimônio Total",
        formatar_compacto(patrimonio_total),
        delta=f"R$ {patrimonio_total * BRL_USD:,.0f}",
        delta_color="off",
    )
    col2.metric(
        "📈 Lucro/Prejuízo",
        formatar_moeda(lucro_total),
        delta=formatar_pct(lucro_pct),
        delta_color="normal",
    )
    col3.metric(
        "💰 Renda Mensal",
        formatar_moeda(renda_mensal),
        delta=f"Anual: {formatar_moeda(renda_anual)}",
        delta_color="off",
    )
    col4.metric(
        "🏦 YoC Médio",
        formatar_pct(resumo_p.get("yoc_medio", 0)),
        delta=f"DY: {formatar_pct(resumo_p.get('dy_medio', 0))}",
        delta_color="off",
    )

    st.divider()

    # --- Tabela resumo por carteira ---
    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.markdown("### 📋 Posições Principais")
        if not df_principal.empty:
            _tabela_posicoes(df_principal)

    with col_b:
        st.markdown("### 🏷️ Por Categoria")
        if not df_principal.empty:
            _resumo_por_categoria(df_principal)


def _tabela_posicoes(df: pd.DataFrame) -> None:
    """Exibe tabela de posições formatada."""

    colunas = {
        "ticker"      : "Ticker",
        "nome"        : "Nome",
        "qtd"         : "Qtd",
        "preco_atual" : "Preço",
        "valor_atual" : "Valor",
        "lucro_pct"   : "Lucro %",
        "yoc"         : "YoC %",
        "peso_pct"    : "Peso %",
    }

    # Seleciona e renomeia colunas disponíveis
    cols_disp = [c for c in colunas.keys() if c in df.columns]
    df_exib = df[cols_disp].copy()
    df_exib = df_exib.rename(columns={c: colunas[c] for c in cols_disp})

    # Ordena por valor
    if "Valor" in df_exib.columns:
        df_exib = df_exib.sort_values("Valor", ascending=False)

    st.dataframe(
        df_exib,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Preço"   : st.column_config.NumberColumn(format="$%.2f"),
            "Valor"   : st.column_config.NumberColumn(format="$%.2f"),
            "Lucro %" : st.column_config.NumberColumn(format="%.2f%%"),
            "YoC %"   : st.column_config.NumberColumn(format="%.2f%%"),
            "Peso %"  : st.column_config.ProgressColumn(
                            format="%.1f%%", min_value=0, max_value=100
                        ),
        },
    )


def _resumo_por_categoria(df: pd.DataFrame) -> None:
    """Exibe resumo de valor por categoria."""

    if "categoria" not in df.columns or "valor_atual" not in df.columns:
        return

    resumo = (
        df.groupby("categoria")["valor_atual"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    resumo.columns = ["Categoria", "Valor"]

    total = resumo["Valor"].sum()
    resumo["Peso %"] = resumo["Valor"] / total * 100

    st.dataframe(
        resumo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor"  : st.column_config.NumberColumn(format="$%.2f"),
            "Peso %" : st.column_config.ProgressColumn(
                           format="%.1f%%", min_value=0, max_value=100
                       ),
        },
    )


# ============================================================
# TAB 2: PERFORMANCE
# ============================================================

def _render_performance(df: pd.DataFrame) -> None:
    """Tab de performance dos ativos."""

    st.markdown("## 📈 Performance dos Ativos")

    if df.empty:
        st.info("Sem dados de performance disponíveis.")
        return

    # --- Métricas ---
    resumo = resumo_carteira(df)
    col1, col2, col3 = st.columns(3)
    col1.metric("Custo Total",     formatar_moeda(resumo.get("custo_total", 0)))
    col2.metric("Valor Atual",     formatar_compacto(resumo.get("patrimonio_total", 0)))
    col3.metric(
        "Lucro/Prejuízo",
        formatar_moeda(resumo.get("lucro_total_usd", 0)),
        delta=formatar_pct(resumo.get("lucro_total_pct", 0)),
    )

    st.divider()

    # --- Tabela de performance ---
    st.markdown("### 🏆 Performance por Ativo")
    if not df.empty:
        colunas = {
            "ticker"      : "Ticker",
            "nome"        : "Nome",
            "pm_usd"      : "PM (USD)",
            "preco_atual" : "Preço Atual",
            "lucro_usd"   : "Lucro USD",
            "lucro_pct"   : "Lucro %",
            "variacao_pct": "Var. Dia %",
        }
        cols_disp = [c for c in colunas.keys() if c in df.columns]
        df_perf = df[cols_disp].copy().rename(
            columns={c: colunas[c] for c in cols_disp}
        )

        if "Lucro %" in df_perf.columns:
            df_perf = df_perf.sort_values("Lucro %", ascending=False)

        st.dataframe(
            df_perf,
            use_container_width=True,
            hide_index=True,
            column_config={
                "PM (USD)"    : st.column_config.NumberColumn(format="$%.2f"),
                "Preço Atual" : st.column_config.NumberColumn(format="$%.2f"),
                "Lucro USD"   : st.column_config.NumberColumn(format="$%.2f"),
                "Lucro %"     : st.column_config.NumberColumn(format="%.2f%%"),
                "Var. Dia %"  : st.column_config.NumberColumn(format="%.2f%%"),
            },
        )


# ============================================================
# TAB 3: DIVIDENDOS
# ============================================================

def _render_dividendos(df: pd.DataFrame) -> None:
    """Tab de análise de dividendos."""

    st.markdown("## 💰 Análise de Dividendos")

    if df.empty:
        st.info("Sem dados de dividendos disponíveis.")
        return

    resumo = resumo_carteira(df)

    # --- Métricas ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Renda Anual",  formatar_moeda(resumo.get("renda_anual", 0)))
    col2.metric("Renda Mensal", formatar_moeda(resumo.get("renda_mensal", 0)))
    col3.metric("YoC Médio",    formatar_pct(resumo.get("yoc_medio", 0)))
    col4.metric("DY Médio",     formatar_pct(resumo.get("dy_medio", 0)))

    st.divider()

    # --- Renda em BRL ---
    renda_mensal_brl = resumo.get("renda_mensal", 0) * BRL_USD
    st.info(
        f"💱 Renda mensal em BRL: **R$ {renda_mensal_brl:,.2f}** "
        f"(câmbio: R$ {BRL_USD:.2f})"
    )

    # --- Tabela de dividendos ---
    st.markdown("### 📋 Dividendos por Ativo")
    colunas = {
        "ticker"             : "Ticker",
        "nome"               : "Nome",
        "qtd"                : "Qtd",
        "div_anual"          : "Div/Ação (ano)",
        "div_recebido_anual" : "Total Anual",
        "renda_mensal"       : "Renda Mensal",
        "yoc"                : "YoC %",
        "dy_atual"           : "DY Atual %",
    }
    cols_disp = [c for c in colunas.keys() if c in df.columns]
    df_div = df[cols_disp].copy().rename(
        columns={c: colunas[c] for c in cols_disp}
    )

    if "Total Anual" in df_div.columns:
        df_div = df_div.sort_values("Total Anual", ascending=False)

    st.dataframe(
        df_div,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Div/Ação (ano)" : st.column_config.NumberColumn(format="$%.4f"),
            "Total Anual"    : st.column_config.NumberColumn(format="$%.2f"),
            "Renda Mensal"   : st.column_config.NumberColumn(format="$%.2f"),
            "YoC %"          : st.column_config.NumberColumn(format="%.2f%%"),
            "DY Atual %"     : st.column_config.NumberColumn(format="%.2f%%"),
        },
    )


# ============================================================
# TAB 4: ALOCAÇÃO
# ============================================================

def _render_alocacao(df: pd.DataFrame) -> None:
    """Tab de análise de alocação."""

    st.markdown("## 🎯 Análise de Alocação")

    if df.empty:
        st.info("Sem dados de alocação disponíveis.")
        return

    # --- Tabela de alocação vs objetivo ---
    st.markdown("### ⚖️ Alocação Atual vs Objetivo")
    colunas = {
        "ticker"      : "Ticker",
        "categoria"   : "Categoria",
        "valor_atual" : "Valor Atual",
        "peso_pct"    : "Peso Atual %",
        "objetivo_pct": "Objetivo %",
        "gap_objetivo": "Gap %",
    }
    cols_disp = [c for c in colunas.keys() if c in df.columns]
    df_aloc = df[cols_disp].copy().rename(
        columns={c: colunas[c] for c in cols_disp}
    )

    if "Valor Atual" in df_aloc.columns:
        df_aloc = df_aloc.sort_values("Valor Atual", ascending=False)

    st.dataframe(
        df_aloc,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor Atual" : st.column_config.NumberColumn(format="$%.2f"),
            "Peso Atual %" : st.column_config.ProgressColumn(
                                format="%.1f%%", min_value=0, max_value=100
                            ),
            "Objetivo %"  : st.column_config.NumberColumn(format="%.1f%%"),
            "Gap %"       : st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    st.divider()

    # --- Alocação por categoria ---
    st.markdown("### 🏷️ Alocação por Categoria")
    if "categoria" in df.columns and "valor_atual" in df.columns:
        cat = (
            df.groupby("categoria")["valor_atual"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        cat.columns = ["Categoria", "Valor"]
        total = cat["Valor"].sum()
        cat["Peso %"] = cat["Valor"] / total * 100

        st.dataframe(
            cat,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valor"  : st.column_config.NumberColumn(format="$%.2f"),
                "Peso %" : st.column_config.ProgressColumn(
                               format="%.1f%%", min_value=0, max_value=100
                           ),
            },
        )


# ============================================================
# TAB 5: ERICSSON
# ============================================================

def _render_ericsson(df_ericsson: pd.DataFrame) -> None:
    """Tab dedicada à carteira Ericsson."""

    st.markdown("## 🔵 Carteira Ericsson (ERIC)")

    if not MOSTRAR_ERICSSON:
        st.info("Carteira Ericsson desabilitada no config.py")
        return

    if df_ericsson.empty:
        st.info("Sem dados da carteira Ericsson.")
        return

    resumo = resumo_carteira(df_ericsson)

    # --- Métricas ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Patrimônio",  formatar_compacto(resumo.get("patrimonio_total", 0)))
    col2.metric(
        "Lucro/Prejuízo",
        formatar_moeda(resumo.get("lucro_total_usd", 0)),
        delta=formatar_pct(resumo.get("lucro_total_pct", 0)),
    )
    col3.metric("Renda Mensal", formatar_moeda(resumo.get("renda_mensal", 0)))

    st.divider()

    # --- Detalhes ---
    st.dataframe(
        df_ericsson,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# TAB 6: DETALHES
# ============================================================

def _render_detalhes(df_principal: pd.DataFrame,
                      df_ericsson: pd.DataFrame) -> None:
    """Tab com tabela completa e detalhada."""

    st.markdown("## 🔍 Dados Completos")

    opcao = st.radio(
        "Exibir carteira:",
        ["Principal", "Ericsson", "Todas"],
        horizontal=True,
    )

    if opcao == "Principal":
        df = df_principal
    elif opcao == "Ericsson":
        df = df_ericsson
    else:
        df = pd.concat([df_principal, df_ericsson], ignore_index=True)

    if df.empty:
        st.info("Sem dados para exibir.")
        return

    # Filtro de busca
    busca = st.text_input("🔍 Filtrar por ticker ou nome:", "")
    if busca:
        mask = (
            df["ticker"].str.upper().str.contains(busca.upper(), na=False)
            | df["nome"].str.upper().str.contains(busca.upper(), na=False)
        )
        df = df[mask]

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Total: {len(df)} ativos")


# ============================================================
# MAIN
# ============================================================

def main():
    """Função principal do dashboard."""

    # Carrega dados
    df = carregar_carteira()

    if df is None or df.empty:
        st.error(
            "❌ Não foi possível carregar os dados.\n\n"
            "Verifique o `config.py` e tente novamente."
        )
        st.stop()

    # Separa carteiras
    df_principal, df_ericsson = separar_carteiras(df)

    # Sidebar
    render_sidebar(df_principal, df_ericsson)

    # Título principal
    st.markdown(f"# {APP_ICONE} {APP_TITULO}")

    # Tabs
    render_tabs(df_principal, df_ericsson)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
