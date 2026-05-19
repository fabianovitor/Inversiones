# ============================================================
# app.py - Dashboard Principal
# ============================================================

import streamlit as st
import pandas as pd

# ── Configuração da página ────────────────────────────────
st.set_page_config(
    page_title="📊 Inversiones FCV",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Imports internos (após set_page_config) ───────────────
try:
    from config import (
        GOOGLE_SHEETS_URL,
        MAPEAMENTO_COLUNAS_GS,
        TICKER_ERICSSON,
        CACHE_TTL_PLANILHA,
        CACHE_TTL_MERCADO,
        BRL_USD if hasattr(__import__('config'), 'BRL_USD') else None,
    )
except Exception:
    pass

from config import GOOGLE_SHEETS_URL, MAPEAMENTO_COLUNAS_GS, TICKER_ERICSSON
from utils import (
    formatar_moeda, formatar_pct, formatar_compacto,
    safe_float, emoji_tendencia
)

# BRL_USD pode não estar no config.py atual
try:
    from config import BRL_USD
except ImportError:
    BRL_USD = 5.0

# ── Constantes ───────────────────────────────────────────
CACHE_TTL = 300   # 5 minutos

# ============================================================
# CARREGAMENTO DE DADOS
# ============================================================

@st.cache_data(ttl=CACHE_TTL)
def carregar_planilha() -> pd.DataFrame:
    """Carrega dados do Google Sheets."""
    try:
        df = pd.read_csv(GOOGLE_SHEETS_URL)
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Renomear colunas
        mapa = {k.lower(): v for k, v in MAPEAMENTO_COLUNAS_GS.items()}
        df = df.rename(columns=mapa)
        
        # Colunas numéricas
        numericas = [
            "qtd", "pm_usd", "div_anual", "yoc_planilha",
            "preco_atual_planilha", "valor_total_planilha",
            "peso_planilha", "objetivo_pct"
        ]
        for col in numericas:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str)
                    .str.replace(",", ".")
                    .str.replace("%", "")
                    .str.strip(),
                    errors="coerce"
                ).fillna(0)
        
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar planilha: {e}")
        return pd.DataFrame()


def separar_carteiras(df: pd.DataFrame):
    """Separa carteira principal e Ericsson."""
    if df.empty:
        return df, pd.DataFrame()
    
    if "ticker" not in df.columns:
        return df, pd.DataFrame()
    
    mask_eric = df["ticker"].astype(str).str.upper() == TICKER_ERICSSON.upper()
    df_ericsson  = df[mask_eric].copy().reset_index(drop=True)
    df_principal = df[~mask_eric].copy().reset_index(drop=True)
    
    return df_principal, df_ericsson


@st.cache_data(ttl=300)
def enriquecer_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Enriquece DataFrame com cálculos derivados."""
    if df.empty:
        return df
    
    df = df.copy()
    
    # Usar preço da planilha como preço atual
    if "preco_atual_planilha" in df.columns:
        df["preco_atual"] = df["preco_atual_planilha"]
    elif "pm_usd" in df.columns:
        df["preco_atual"] = df["pm_usd"]
    else:
        df["preco_atual"] = 0.0
    
    # Valor atual
    if "valor_total_planilha" in df.columns:
        df["valor_atual"] = df["valor_total_planilha"]
    elif "qtd" in df.columns and "preco_atual" in df.columns:
        df["valor_atual"] = df["qtd"] * df["preco_atual"]
    else:
        df["valor_atual"] = 0.0
    
    # Custo total
    if "qtd" in df.columns and "pm_usd" in df.columns:
        df["custo_total"] = df["qtd"] * df["pm_usd"]
    else:
        df["custo_total"] = df.get("valor_atual", pd.Series([0.0] * len(df)))
    
    # Lucro
    df["lucro_usd"] = df["valor_atual"] - df["custo_total"]
    df["lucro_pct"] = df.apply(
        lambda r: (r["lucro_usd"] / r["custo_total"] * 100)
        if r.get("custo_total", 0) > 0 else 0,
        axis=1
    )
    
    # Renda mensal
    if "div_anual" in df.columns and "qtd" in df.columns:
        df["renda_mensal"] = df["qtd"] * df["div_anual"] / 12
    else:
        df["renda_mensal"] = 0.0
    
    # YoC
    if "yoc_planilha" in df.columns:
        df["yoc"] = df["yoc_planilha"]
    elif "div_anual" in df.columns and "pm_usd" in df.columns:
        df["yoc"] = df.apply(
            lambda r: (r["div_anual"] / r["pm_usd"] * 100)
            if r.get("pm_usd", 0) > 0 else 0,
            axis=1
        )
    else:
        df["yoc"] = 0.0
    
    # Peso %
    total = df["valor_atual"].sum()
    df["peso_pct"] = df["valor_atual"].apply(
        lambda v: (v / total * 100) if total > 0 else 0
    )
    
    return df


def resumo_carteira(df: pd.DataFrame) -> dict:
    """Calcula resumo da carteira."""
    if df is None or df.empty:
        return {}
    
    patrimonio    = safe_float(df["valor_atual"].sum()) if "valor_atual" in df.columns else 0
    custo_total   = safe_float(df["custo_total"].sum()) if "custo_total" in df.columns else 0
    lucro_usd     = patrimonio - custo_total
    lucro_pct     = (lucro_usd / custo_total * 100) if custo_total > 0 else 0
    renda_mensal  = safe_float(df["renda_mensal"].sum()) if "renda_mensal" in df.columns else 0
    renda_anual   = renda_mensal * 12
    yoc_medio     = safe_float(df["yoc"].mean()) if "yoc" in df.columns else 0
    dy_medio      = (renda_anual / patrimonio * 100) if patrimonio > 0 else 0
    num_ativos    = df["ticker"].nunique() if "ticker" in df.columns else 0
    
    return {
        "patrimonio_total" : patrimonio,
        "custo_total"      : custo_total,
        "lucro_total_usd"  : lucro_usd,
        "lucro_total_pct"  : lucro_pct,
        "renda_mensal"     : renda_mensal,
        "renda_anual"      : renda_anual,
        "yoc_medio"        : yoc_medio,
        "dy_medio"         : dy_medio,
        "num_ativos"       : num_ativos,
    }


# ============================================================
# TABS
# ============================================================

def render_tab_visao_geral(df_principal, df_ericsson):
    """Aba Visão Geral."""
    st.markdown("## 📊 Visão Geral do Portfólio")
    
    resumo_p = resumo_carteira(df_principal)
    resumo_e = resumo_carteira(df_ericsson) if df_ericsson is not None and not df_ericsson.empty else {}
    
    patrimonio_total = resumo_p.get("patrimonio_total", 0) + resumo_e.get("patrimonio_total", 0)
    renda_mensal     = resumo_p.get("renda_mensal", 0) + resumo_e.get("renda_mensal", 0)
    lucro_total      = resumo_p.get("lucro_total_usd", 0) + resumo_e.get("lucro_total_usd", 0)
    custo_total      = resumo_p.get("custo_total", 0) + resumo_e.get("custo_total", 0)
    lucro_pct        = (lucro_total / custo_total * 100) if custo_total > 0 else 0
    
    # Métricas principais
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💼 Patrimônio Total",  formatar_compacto(patrimonio_total))
    c2.metric("📈 Lucro/Prejuízo",    formatar_moeda(lucro_total),
              delta=formatar_pct(lucro_pct), delta_color="normal")
    c3.metric("💰 Renda Mensal",      formatar_moeda(renda_mensal))
    c4.metric("🏦 Renda Anual",       formatar_moeda(renda_mensal * 12))
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Carteira Principal")
        r = resumo_p
        st.metric("Patrimônio",   formatar_compacto(r.get("patrimonio_total", 0)))
        st.metric("Renda Mensal", formatar_moeda(r.get("renda_mensal", 0)))
        st.metric("YoC Médio",    formatar_pct(r.get("yoc_medio", 0)))
        st.metric("Ativos",       r.get("num_ativos", 0))
    
    with col2:
        st.markdown("### 🔵 Carteira Ericsson")
        e = resumo_e
        if e:
            st.metric("Patrimônio",   formatar_compacto(e.get("patrimonio_total", 0)))
            st.metric("Renda Mensal", formatar_moeda(e.get("renda_mensal", 0)))
            st.metric("YoC Médio",    formatar_pct(e.get("yoc_medio", 0)))
        else:
            st.info("Sem dados Ericsson")


def render_tab_carteira(df):
    """Aba Carteira Principal."""
    st.markdown("## 📊 Carteira Principal")
    
    if df is None or df.empty:
        st.warning("⚠️ Nenhum dado encontrado.")
        return
    
    resumo = resumo_carteira(df)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💼 Patrimônio",    formatar_compacto(resumo.get("patrimonio_total", 0)))
    c2.metric("📈 Lucro/Prejuízo", formatar_moeda(resumo.get("lucro_total_usd", 0)),
              delta=formatar_pct(resumo.get("lucro_total_pct", 0)), delta_color="normal")
    c3.metric("💰 Renda Mensal",  formatar_moeda(resumo.get("renda_mensal", 0)))
    c4.metric("🏦 YoC Médio",     formatar_pct(resumo.get("yoc_medio", 0)))
    
    st.divider()
    st.markdown("### 📋 Posições")
    
    colunas_map = {
        "ticker"      : "Ticker",
        "nome"        : "Nome",
        "categoria"   : "Categoria",
        "qtd"         : "Qtd",
        "pm_usd"      : "PM (USD)",
        "preco_atual" : "Preço Atual",
        "valor_atual" : "Valor",
        "lucro_usd"   : "Lucro USD",
        "lucro_pct"   : "Lucro %",
        "renda_mensal": "Renda/Mês",
        "yoc"         : "YoC %",
        "peso_pct"    : "Peso %",
    }
    
    cols_disp = [c for c in colunas_map if c in df.columns]
    df_exib = (
        df[cols_disp]
        .copy()
        .rename(columns={c: colunas_map[c] for c in cols_disp})
        .sort_values("Valor", ascending=False)
        if "valor_atual" in df.columns
        else df[cols_disp].copy().rename(columns={c: colunas_map[c] for c in cols_disp})
    )
    
    st.dataframe(
        df_exib,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PM (USD)"  : st.column_config.NumberColumn(format="$%.2f"),
            "Preço Atual": st.column_config.NumberColumn(format="$%.2f"),
            "Valor"     : st.column_config.NumberColumn(format="$%.2f"),
            "Lucro USD" : st.column_config.NumberColumn(format="$%.2f"),
            "Lucro %"   : st.column_config.NumberColumn(format="%.2f%%"),
            "Renda/Mês" : st.column_config.NumberColumn(format="$%.2f"),
            "YoC %"     : st.column_config.NumberColumn(format="%.2f%%"),
            "Peso %"    : st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=100
            ),
        },
    )


def render_tab_ericsson(df):
    """Aba Ericsson."""
    st.markdown("## 🔵 Carteira Ericsson (ERIC)")
    
    if df is None or df.empty:
        st.info("ℹ️ Nenhum dado encontrado para ERIC.")
        return
    
    render_tab_carteira(df)


def render_tab_projecao(df_principal, df_ericsson):
    """Aba Projeção de Renda."""
    st.markdown("## 🎯 Projeção de Renda por Dividendos")
    
    resumo_p = resumo_carteira(df_principal)
    resumo_e = resumo_carteira(df_ericsson) if df_ericsson is not None and not df_ericsson.empty else {}
    
    renda_atual   = resumo_p.get("renda_mensal", 0) + resumo_e.get("renda_mensal", 0)
    patrimonio    = resumo_p.get("patrimonio_total", 0) + resumo_e.get("patrimonio_total", 0)
    
    st.markdown("### ⚙️ Parâmetros")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        aporte = st.number_input("💵 Aporte Mensal (USD)", 0.0, 100_000.0, 500.0, 100.0)
    with col2:
        anos = st.slider("📅 Horizonte (anos)", 1, 30, 10)
    with col3:
        yield_est = st.number_input("🏦 Yield estimado (%)", 0.1, 30.0, 6.0, 0.5)
    
    reinvestir = st.checkbox("🔄 Reinvestir dividendos?", value=True)
    
    st.divider()
    
    # Simulação
    registros = []
    pat = patrimonio
    renda = renda_atual
    aporte_acum = 0.0
    
    for ano in range(1, anos + 1):
        aporte_acum += aporte * 12
        renda_anual  = renda * 12
        
        if reinvestir:
            pat = pat + aporte * 12 + renda_anual
        else:
            pat = pat + aporte * 12
        
        renda_anual = pat * (yield_est / 100)
        renda       = renda_anual / 12
        
        registros.append({
            "Ano"              : ano,
            "Patrimônio (USD)" : pat,
            "Patrimônio (BRL)" : pat * BRL_USD,
            "Renda Mensal (USD)": renda,
            "Renda Mensal (BRL)": renda * BRL_USD,
            "Aporte Acumulado" : aporte_acum,
            "Yield Real %"     : (renda_anual / pat * 100) if pat > 0 else 0,
        })
    
    df_proj = pd.DataFrame(registros)
    
    st.markdown("### 📊 Projeção Ano a Ano")
    st.dataframe(
        df_proj,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Patrimônio (USD)" : st.column_config.NumberColumn(format="$%.2f"),
            "Patrimônio (BRL)" : st.column_config.NumberColumn(format="R$ %.2f"),
            "Renda Mensal (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Renda Mensal (BRL)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Aporte Acumulado" : st.column_config.NumberColumn(format="$%.2f"),
            "Yield Real %"     : st.column_config.NumberColumn(format="%.2f%%"),
        },
    )
    
    st.divider()
    st.markdown("### 📌 Situação Atual")
    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimônio Total",  formatar_compacto(patrimonio))
    c2.metric("Renda Mensal USD",  formatar_moeda(renda_atual))
    c3.metric("Renda Mensal BRL",  f"R$ {renda_atual * BRL_USD:,.2f}")


def render_tab_analises(df_principal, df_ericsson):
    """Aba Análises."""
    st.markdown("## 🔍 Análises do Portfólio")
    
    frames = []
    if df_principal is not None and not df_principal.empty:
        frames.append(df_principal)
    if df_ericsson is not None and not df_ericsson.empty:
        frames.append(df_ericsson)
    
    if not frames:
        st.warning("⚠️ Sem dados para análise.")
        return
    
    df_total = pd.concat(frames, ignore_index=True)
    
    # Diversificação por categoria
    st.markdown("### 📊 Diversificação por Categoria")
    if "categoria" in df_total.columns and "valor_atual" in df_total.columns:
        cat = (
            df_total.groupby("categoria")["valor_atual"]
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
                "Valor": st.column_config.NumberColumn(format="$%.2f"),
                "Peso %": st.column_config.ProgressColumn(
                    format="%.1f%%", min_value=0, max_value=100
                ),
            },
        )
    else:
        st.info("Coluna 'categoria' não encontrada.")
    
    st.divider()
    
    # Top ativos por renda
    st.markdown("### 💸 Top 10 por Renda Mensal")
    if "ticker" in df_total.columns and "renda_mensal" in df_total.columns:
        top = (
            df_total[["ticker", "renda_mensal"]]
            .sort_values("renda_mensal", ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        top.index += 1
        st.dataframe(
            top,
            use_container_width=True,
            column_config={
                "renda_mensal": st.column_config.NumberColumn("Renda/Mês", format="$%.2f"),
            },
        )


# ============================================================
# MAIN
# ============================================================

def main():
    st.title("📊 Dashboard de Inversiones FCV")
    st.caption("Portfólio de dividendos | Dados ao vivo via Google Sheets")
    
    # Carrega dados
    with st.spinner("Carregando dados da planilha..."):
        df_raw = carregar_planilha()
    
    if df_raw.empty:
        st.error("❌ Não foi possível carregar os dados. Verifique a planilha.")
        st.info("URL configurada: " + GOOGLE_SHEETS_URL)
        st.stop()
    
    # Enriquece e separa
    df_enriquecido = enriquecer_dados(df_raw)
    df_principal, df_ericsson = separar_carteiras(df_enriquecido)
    
    # Abas
    tabs = st.tabs([
        "🏠 Visão Geral",
        "📊 Carteira",
        "🔵 Ericsson",
        "🎯 Projeção",
        "🔍 Análises",
    ])
    
    with tabs[0]:
        render_tab_visao_geral(df_principal, df_ericsson)
    
    with tabs[1]:
        render_tab_carteira(df_principal)
    
    with tabs[2]:
        render_tab_ericsson(df_ericsson)
    
    with tabs[3]:
        render_tab_projecao(df_principal, df_ericsson)
    
    with tabs[4]:
        render_tab_analises(df_principal, df_ericsson)
    
    # Rodapé
    st.divider()
    st.caption("⚡ Dashboard atualiza automaticamente a cada 5 minutos")


if __name__ == "__main__":
    main()
