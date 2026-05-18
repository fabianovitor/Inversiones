# app.py - Dashboard de Aposentadoria
# ============================================================
# PARTE 1/8: Imports e Configurações Iniciais
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
import time
import io
import json
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Dashboard Aposentadoria",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CONSTANTES
# ============================================================
CACHE_TTL = 600  # 10 minutos
ARQUIVO_PADRAO = "carteira.xlsx"

TOOLTIPS = {
    "patrimonio": "Soma do valor atual de todos os ativos da carteira principal (excluindo Ericsson).",
    "renda_mensal": "Estimativa de renda mensal baseada no Dividend Yield atual de cada ativo.",
    "ericsson": "Carteira paralela tratada separadamente (ações da empresa empregadora).",
    "meta": "Meta de renda mensal definida na sidebar.",
}
# ============================================================
# PARTE 2/8: Funções de Formatação
# ============================================================

def fmt_usd(valor):
    """Formata valor em USD."""
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        return f"US$ {float(valor):,.2f}"
    except (ValueError, TypeError):
        return "-"


def fmt_pct(valor):
    """Formata percentual (valor já em %)."""
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        return f"{float(valor):+.2f}%"
    except (ValueError, TypeError):
        return "-"


def fmt_pct_dy(valor):
    """Formata DY (valor decimal: 0.05 = 5%)."""
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        return f"{float(valor)*100:.2f}%"
    except (ValueError, TypeError):
        return "-"


def safe_float(valor, default=0.0):
    """Converte para float com segurança."""
    if pd.isna(valor) or valor is None:
        return default
    try:
        return float(valor)
    except (ValueError, TypeError):
        return default
# ============================================================
# PARTE 3/8: Funções de Carregamento de Dados
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def buscar_dados_yfinance(ticker):
    """Busca dados de um ticker no Yahoo Finance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        preco = (
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
        )

        nome = info.get("longName") or info.get("shortName") or ticker
        setor = info.get("sector") or "Outros"

        # Dividend yield (vem como decimal: 0.05 = 5%)
        dy = info.get("dividendYield") or 0
        if dy and dy > 1:  # Se vier como percentual (5.0), converte
            dy = dy / 100

        # Variação do dia
        var_pct = info.get("regularMarketChangePercent") or 0

        return {
            "preco": safe_float(preco),
            "nome": nome,
            "setor": setor,
            "div_yield": safe_float(dy),
            "var_pct": safe_float(var_pct),
            "erro": None,
        }
    except Exception as e:
        return {
            "preco": 0,
            "nome": ticker,
            "setor": "Outros",
            "div_yield": 0,
            "var_pct": 0,
            "erro": str(e),
        }


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def carregar_planilha(arquivo):
    """Carrega a planilha Excel e retorna DataFrame."""
    try:
        df = pd.read_excel(arquivo)
        df.columns = [c.strip().lower() for c in df.columns]
        return df, None
    except Exception as e:
        return None, str(e)
# ============================================================
# PARTE 4/8: Processamento da Carteira
# ============================================================

def processar_carteira(df_raw):
    """Processa a planilha e enriquece com dados do Yahoo Finance."""
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Mapeamento de colunas (flexível)
    col_map = {
        "ticker": ["ticker", "papel", "ativo", "symbol"],
        "qtd": ["qtd", "quantidade", "qty", "shares"],
        "pm_usd": ["pm_usd", "preco_medio", "pm", "preço médio", "preco medio"],
        "tipo": ["tipo", "categoria", "carteira"],
    }

    # Renomeia colunas
    rename_dict = {}
    for col_padrao, alternativas in col_map.items():
        for alt in alternativas:
            if alt in df_raw.columns:
                rename_dict[alt] = col_padrao
                break

    df = df_raw.rename(columns=rename_dict).copy()

    # Garante colunas essenciais
    for col in ["ticker", "qtd", "pm_usd"]:
        if col not in df.columns:
            df[col] = np.nan

    if "tipo" not in df.columns:
        df["tipo"] = "principal"

    # Limpa tickers
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df = df[df["ticker"].notna() & (df["ticker"] != "") & (df["ticker"] != "NAN")]

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Busca dados do Yahoo Finance
    dados_yf = []
    progress = st.progress(0, text="Buscando cotações...")
    total = len(df)

    for i, ticker in enumerate(df["ticker"].tolist()):
        dados = buscar_dados_yfinance(ticker)
        dados["ticker"] = ticker
        dados_yf.append(dados)
        progress.progress((i + 1) / total, text=f"Buscando {ticker} ({i+1}/{total})")

    progress.empty()

    df_yf = pd.DataFrame(dados_yf)
    df = df.merge(df_yf, on="ticker", how="left")

    # Renomeia preco -> preco_usd
    df = df.rename(columns={"preco": "preco_usd"})

    # Cálculos
    df["qtd"] = df["qtd"].apply(safe_float)
    df["pm_usd"] = df["pm_usd"].apply(safe_float)
    df["preco_usd"] = df["preco_usd"].apply(safe_float)
    df["div_yield"] = df["div_yield"].apply(safe_float)
    df["var_pct"] = df["var_pct"].apply(safe_float)

    df["valor_atual"] = df["qtd"] * df["preco_usd"]
    df["custo_total"] = df["qtd"] * df["pm_usd"]
    df["lucro"] = df["valor_atual"] - df["custo_total"]
    df["lucro_pct"] = np.where(
        df["custo_total"] > 0,
        (df["lucro"] / df["custo_total"]) * 100,
        np.nan,
    )
    df["renda_mensal"] = (df["valor_atual"] * df["div_yield"]) / 12
    df["yoc"] = np.where(
        df["pm_usd"] > 0,
        (df["preco_usd"] * df["div_yield"]) / df["pm_usd"],
        np.nan,
    )

    # Separa carteira principal e Ericsson
    df["tipo"] = df["tipo"].astype(str).str.strip().str.lower()
    df_eric = df[df["tipo"].str.contains("eric", na=False)].copy()
    df_principal = df[~df["tipo"].str.contains("eric", na=False)].copy()

    return df_principal, df_eric
# ============================================================
# PARTE 5/8: Sidebar - Configurações
# ============================================================

st.sidebar.title("⚙️ Configurações")

# Upload ou arquivo padrão
st.sidebar.markdown("### 📁 Fonte de Dados")
arquivo_upload = st.sidebar.file_uploader(
    "Carregar planilha Excel",
    type=["xlsx", "xls"],
    help="Colunas esperadas: ticker, qtd, pm_usd, tipo (opcional)",
)

usar_padrao = st.sidebar.checkbox(
    f"Usar arquivo padrão ({ARQUIVO_PADRAO})",
    value=True,
    help=f"Tenta carregar {ARQUIVO_PADRAO} da pasta do projeto.",
)

st.sidebar.markdown("---")

# Parâmetros financeiros
st.sidebar.markdown("### 💰 Parâmetros")

meta_mensal = st.sidebar.number_input(
    "Meta de renda mensal (USD)",
    min_value=0.0,
    value=5000.0,
    step=100.0,
    help="Quanto você quer receber de renda passiva por mês.",
)

aporte_mensal = st.sidebar.number_input(
    "Aporte mensal (USD)",
    min_value=0.0,
    value=1000.0,
    step=100.0,
    help="Quanto você consegue investir por mês.",
)

taxa_retorno = st.sidebar.slider(
    "Retorno anual estimado (%)",
    min_value=1.0,
    max_value=20.0,
    value=8.0,
    step=0.5,
    help="Taxa anual média esperada (juros + dividendos reinvestidos).",
) / 100

st.sidebar.markdown("---")

# Debug
st.sidebar.markdown("### 🔧 Debug")
debug = st.sidebar.checkbox("Modo debug", value=False)
# ============================================================
# PARTE 6/8: Carregamento de Dados e Cálculos Globais
# ============================================================

st.title("💰 Dashboard de Aposentadoria")

# Decide fonte de dados
df_raw = None
erro_carregamento = None

if arquivo_upload is not None:
    df_raw, erro_carregamento = carregar_planilha(arquivo_upload)
    if df_raw is not None:
        st.sidebar.success(f"✅ Arquivo carregado: {arquivo_upload.name}")
elif usar_padrao:
    if Path(ARQUIVO_PADRAO).exists():
        df_raw, erro_carregamento = carregar_planilha(ARQUIVO_PADRAO)
        if df_raw is not None:
            st.sidebar.success(f"✅ Usando: {ARQUIVO_PADRAO}")
    else:
        erro_carregamento = f"Arquivo {ARQUIVO_PADRAO} não encontrado."

if erro_carregamento:
    st.error(f"❌ Erro ao carregar planilha: {erro_carregamento}")
    st.info("📋 **Formato esperado da planilha:**\n\n"
            "| ticker | qtd | pm_usd | tipo |\n"
            "|--------|-----|--------|------|\n"
            "| AAPL | 10 | 150.00 | principal |\n"
            "| ERIC | 100 | 5.50 | ericsson |")
    st.stop()

if df_raw is None or df_raw.empty:
    st.warning("⚠️ Nenhum dado carregado. Faça upload de uma planilha ou habilite o arquivo padrão.")
    st.stop()

# Debug: mostra dados brutos
if debug:
    with st.sidebar.expander("🔍 Dados brutos (debug)"):
        st.dataframe(df_raw)

    # Botão de download dos dados brutos
    csv_raw = df_raw.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        "⬇️ Baixar dados brutos (CSV)",
        data=csv_raw,
        file_name="dados_brutos.csv",
        mime="text/csv",
    )

# Processa carteira
with st.spinner("⏳ Processando carteira e buscando cotações..."):
    df_principal, df_eric = processar_carteira(df_raw)

# Debug: dados processados
if debug:
    with st.sidebar.expander("🔍 Dados processados (debug)"):
        st.markdown("**Carteira Principal:**")
        st.dataframe(df_principal)
        st.markdown("**Ericsson:**")
        st.dataframe(df_eric)

    csv_proc = df_principal.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        "⬇️ Baixar dados processados (CSV)",
        data=csv_proc,
        file_name="dados_processados.csv",
        mime="text/csv",
    )

# ============================================================
# CÁLCULOS GLOBAIS
# ============================================================
patrimonio = df_principal["valor_atual"].sum(skipna=True) if not df_principal.empty else 0
custo_tot = df_principal["custo_total"].sum(skipna=True) if not df_principal.empty else 0
lucro_tot = df_principal["lucro"].sum(skipna=True) if not df_principal.empty else 0
lucro_pct_tot = (lucro_tot / custo_tot * 100) if custo_tot else 0
renda_tot = df_principal["renda_mensal"].sum(skipna=True) if not df_principal.empty else 0

patr_eric = df_eric["valor_atual"].sum(skipna=True) if not df_eric.empty else 0
renda_eric = df_eric["renda_mensal"].sum(skipna=True) if not df_eric.empty else 0
            "Lucro %": lambda x: fmt_pct(x) if pd.notna(x) else "-",
            "DY": lambda x: fmt_pct_dy(x),
            "YOC": lambda x: fmt_pct_dy(x),
            "Renda/Mês": lambda x: fmt_usd(x),
        })

        styled_eric = aplicar_estilo_df(styled_eric, ["Var %", "Lucro/Prej.", "Lucro %"])
        st.dataframe(styled_eric, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.info(
            "💡 **Regra de rebalanceamento:** Quando o valor da Ericsson ultrapassar "
            "**25% do valor da carteira principal**, considere vender parte das ações "
            "e realocar nos demais ativos da carteira principal."
        )
    else:
        st.info("Nenhuma ação da Ericsson encontrada na planilha. Adicione linhas com `tipo = ericsson`.")
# ============================================================
# PARTE 8/8: Aba Projeção + Aba Análises + Rodapé
# ============================================================

# ============================================================
# ABA 3: PROJEÇÃO
# ============================================================
with tab_projecao:
    st.subheader("📈 Projeção de Patrimônio e Renda")
    st.caption(
        "Simulação considerando aporte mensal constante e taxa de retorno anual estimada "
        "(juros compostos, dividendos reinvestidos)."
    )

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        anos_proj = st.slider(
            "Horizonte de projeção (anos)",
            min_value=1,
            max_value=40,
            value=17,
            step=1,
            help="Anos até a aposentadoria. Padrão: 17 anos (idade 48 → 65).",
        )
    with col_p2:
        taxa_saque = st.slider(
            "Taxa de saque anual (regra dos 4%)",
            min_value=2.0,
            max_value=8.0,
            value=4.0,
            step=0.5,
            help="Percentual anual seguro para retirada na aposentadoria.",
        ) / 100

    # Simulação mês a mês
    meses = anos_proj * 12
    taxa_mensal = (1 + taxa_retorno) ** (1/12) - 1

    saldo = patrimonio
    historico = []
    for m in range(meses + 1):
        ano_atual = m / 12
        historico.append({
            "Mês": m,
            "Ano": ano_atual,
            "Patrimônio": saldo,
            "Renda Mensal (4%)": saldo * taxa_saque / 12,
        })
        saldo = saldo * (1 + taxa_mensal) + aporte_mensal

    df_proj = pd.DataFrame(historico)

    # Métricas finais
    patr_final = df_proj["Patrimônio"].iloc[-1]
    renda_final = patr_final * taxa_saque / 12
    total_aportado = aporte_mensal * meses
    juros_ganhos = patr_final - patrimonio - total_aportado

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("💼 Patrimônio Final", fmt_usd(patr_final))
    with col_m2:
        st.metric("💵 Renda Mensal Estimada", fmt_usd(renda_final))
    with col_m3:
        st.metric("📥 Total Aportado", fmt_usd(total_aportado))
    with col_m4:
        st.metric("📈 Juros Ganhos", fmt_usd(juros_ganhos))

    # Gráfico de evolução do patrimônio
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(
        x=df_proj["Ano"],
        y=df_proj["Patrimônio"],
        mode="lines",
        name="Patrimônio",
        line=dict(color="#1f77b4", width=3),
        fill="tozeroy",
        fillcolor="rgba(31, 119, 180, 0.1)",
    ))
    fig_proj.update_layout(
        title="📊 Evolução do Patrimônio ao Longo do Tempo",
        xaxis_title="Anos",
        yaxis_title="Patrimônio (USD)",
        height=400,
        hovermode="x unified",
    )
    st.plotly_chart(fig_proj, use_container_width=True, key="proj_patrimonio")

    # Gráfico de renda mensal projetada
    fig_renda_proj = go.Figure()
    fig_renda_proj.add_trace(go.Scatter(
        x=df_proj["Ano"],
        y=df_proj["Renda Mensal (4%)"],
        mode="lines",
        name="Renda Mensal",
        line=dict(color="#00C853", width=3),
        fill="tozeroy",
        fillcolor="rgba(0, 200, 83, 0.1)",
    ))
    fig_renda_proj.add_hline(
        y=meta_mensal,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Meta: {fmt_usd(meta_mensal)}",
        annotation_position="top right",
    )
    fig_renda_proj.update_layout(
        title=f"💰 Projeção de Renda Mensal (regra dos {taxa_saque*100:.1f}%)",
        xaxis_title="Anos",
        yaxis_title="Renda Mensal (USD)",
        height=400,
        hovermode="x unified",
    )
    st.plotly_chart(fig_renda_proj, use_container_width=True, key="proj_renda")

    # Quando atinge a meta?
    df_meta = df_proj[df_proj["Renda Mensal (4%)"] >= meta_mensal]
    if not df_meta.empty:
        anos_meta = df_meta.iloc[0]["Ano"]
        st.success(
            f"🎯 **Meta de {fmt_usd(meta_mensal)}/mês atingida em {anos_meta:.1f} anos** "
            f"(patrimônio necessário: {fmt_usd(meta_mensal * 12 / taxa_saque)})"
        )
    else:
        patr_necessario = meta_mensal * 12 / taxa_saque
        falta = patr_necessario - patr_final
        st.warning(
            f"⚠️ **Meta não atingida** no horizonte de {anos_proj} anos. "
            f"Patrimônio necessário: {fmt_usd(patr_necessario)} "
            f"(faltam {fmt_usd(falta)})"
        )