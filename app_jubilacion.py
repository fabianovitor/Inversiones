import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import StringIO
import yfinance as yf
from datetime import datetime
import numpy as np

st.set_page_config(
    page_title="Dashboard — Aposentadoria",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

META_MENSAL_USD_PADRAO = 2300.0
SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"

LAYOUT_BASE = dict(
    plot_bgcolor="#f8fafc",
    paper_bgcolor="white",
    font=dict(color="#1e293b", size=13),
    margin=dict(t=60, b=60, l=60, r=60),
)

def layout_eixos(xaxis_title="", yaxis_title=""):
    return dict(
        **LAYOUT_BASE,
        xaxis=dict(
            title=dict(text=xaxis_title, font=dict(color="#1e293b", size=14)),
            tickfont=dict(color="#1e293b", size=12),
            linecolor="#94a3b8", gridcolor="#e2e8f0",
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(color="#1e293b", size=14)),
            tickfont=dict(color="#1e293b", size=12),
            linecolor="#94a3b8", gridcolor="#e2e8f0",
        ),
    )


def build_csv_url(spreadsheet_id, gid):
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )


@st.cache_data(ttl=300)
def load_sheet_raw(spreadsheet_id, gid):
    url = build_csv_url(spreadsheet_id, gid)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=15, headers=headers)
        if response.status_code != 200:
            return "", f"HTTP_{response.status_code}", url
        content = response.text
        if content.strip().startswith("<!DOCTYPE") or content.strip().startswith("<html"):
            return "", "HTML_RESPONSE", url
        return content, None, url
    except Exception as e:
        return "", f"ERROR: {str(e)}", url


@st.cache_data(ttl=300)
def get_exchange_rate(from_currency, to_currency="USD"):
    if from_currency.upper() == to_currency.upper():
        return 1.0
    try:
        pair = f"{from_currency.upper()}{to_currency.upper()}=X"
        ticker = yf.Ticker(pair)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 1.0


@st.cache_data(ttl=300)
def get_all_rates():
    moedas = ["SEK", "EUR", "GBP", "BRL", "CAD", "CHF", "JPY", "NOK", "DKK"]
    rates = {"USD": 1.0}
    for moeda in moedas:
        rates[moeda] = get_exchange_rate(moeda, "USD")
    return rates


@st.cache_data(ttl=300)
def get_ticker_info(ticker, rates):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="2d")
        moeda_mercado = info.get("currency", "USD").upper()
        preco_raw = info.get("currentPrice") or info.get("regularMarketPrice", None)
        preco_usd = None
        if preco_raw:
            if moeda_mercado == "USD":
                preco_usd = float(preco_raw)
            else:
                taxa = rates.get(moeda_mercado, None)
                if taxa:
                    preco_usd = float(preco_raw) * taxa
                else:
                    preco_usd = float(preco_raw)

        variacao_pct = None
        if hist is not None and len(hist) >= 2:
            try:
                preco_ontem = float(hist["Close"].iloc[-2])
                preco_hoje = float(hist["Close"].iloc[-1])
                if preco_ontem > 0:
                    variacao_pct = ((preco_hoje - preco_ontem) / preco_ontem) * 100
            except Exception:
                pass
        elif hist is not None and len(hist) == 1:
            try:
                preco_hoje = float(hist["Close"].iloc[-1])
                preco_ontem_raw = info.get("previousClose") or info.get("regularMarketPreviousClose")
                if preco_ontem_raw:
                    preco_ontem = float(preco_ontem_raw)
                    if preco_ontem > 0:
                        variacao_pct = ((preco_hoje - preco_ontem) / preco_ontem) * 100
            except Exception:
                pass

        # Dividendos anuais estimados
        div_yield = info.get("dividendYield", None)
        div_anual_usd = None
        if div_yield and preco_usd:
            div_anual_usd = preco_usd * div_yield

        nome = info.get("shortName") or info.get("longName") or ticker
        return {
            "ticker": ticker,
            "nome": nome,
            "preco_usd": preco_usd,
            "moeda_mercado": moeda_mercado,
            "variacao_pct": variacao_pct,
            "div_yield": div_yield,
            "div_anual_usd": div_anual_usd,
            "info": info,
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "nome": ticker,
            "preco_usd": None,
            "moeda_mercado": "USD",
            "variacao_pct": None,
            "div_yield": None,
            "div_anual_usd": None,
            "info": {},
            "erro": str(e),
        }


def parse_sheet_ativos(content):
    try:
        df = pd.read_csv(StringIO(content))
        df.columns = [c.strip() for c in df.columns]
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def formatar_usd(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    return f"${valor:,.2f}"


def formatar_pct(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    sinal = "+" if valor > 0 else ""
    return f"{sinal}{valor:.2f}%"


def cor_variacao(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "#64748b"
    if valor > 0:
        return "#16a34a"
    if valor < 0:
        return "#dc2626"
    return "#64748b"


def calcular_projecao_patrimonial(patrimonio_atual, aporte_mensal, anos, taxa_anual=0.07):
    """Calcula projeção de patrimônio com aportes mensais."""
    taxa_mensal = (1 + taxa_anual) ** (1/12) - 1
    meses = anos * 12
    resultados = []
    saldo = patrimonio_atual
    for m in range(1, meses + 1):
        saldo = saldo * (1 + taxa_mensal) + aporte_mensal
        if m % 12 == 0:
            resultados.append({
                "Ano": datetime.now().year + m // 12,
                "Patrimônio (USD)": saldo,
                "Renda Mensal Est. (USD)": saldo * 0.004,
            })
    return pd.DataFrame(resultados)


def anos_para_meta(patrimonio_atual, aporte_mensal, meta_renda_mensal, taxa_anual=0.07):
    """Calcula quantos anos para atingir a renda mensal desejada."""
    meta_patrimonio = meta_renda_mensal / 0.004
    taxa_mensal = (1 + taxa_anual) ** (1/12) - 1
    saldo = patrimonio_atual
    meses = 0
    max_meses = 600  # 50 anos máx
    while saldo < meta_patrimonio and meses < max_meses:
        saldo = saldo * (1 + taxa_mensal) + aporte_mensal
        meses += 1
    if meses >= max_meses:
        return None
    return meses / 12


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Painel de Controle")

    st.markdown("### 🎯 Meus Objetivos")

    idade_atual = st.number_input(
        "Minha idade atual",
        min_value=18, max_value=80, value=48, step=1,
    )

    idade_aposentadoria = st.number_input(
        "Idade desejada para aposentadoria",
        min_value=idade_atual + 1, max_value=90, value=65, step=1,
    )

    meta_mensal_usd = st.number_input(
        "Meta de renda mensal passiva (USD)",
        min_value=0.0,
        value=META_MENSAL_USD_PADRAO,
        step=100.0,
        format="%.2f",
    )

    aporte_mensal_usd = st.number_input(
        "Aporte mensal planejado (USD)",
        min_value=0.0,
        value=500.0,
        step=50.0,
        format="%.2f",
    )

    taxa_retorno_anual = st.slider(
        "Taxa de retorno anual estimada (%)",
        min_value=3.0, max_value=15.0, value=7.0, step=0.5,
    ) / 100

    st.markdown("---")
    st.markdown("### 📊 Dados da Planilha")
    st.caption(f"ID: `{SPREADSHEET_ID[:20]}...`")
    st.caption(f"GID: `{GID_PADRAO}`")

    st.markdown("---")
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.caption("Dados: Yahoo Finance · Câmbio em tempo real")

anos_restantes = idade_aposentadoria - idade_atual

# ─────────────────────────────────────────────
#  TÍTULO
# ─────────────────────────────────────────────
st.title("📊 Dashboard de Aposentadoria")
st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · {idade_atual} anos · Meta: aposentar aos {idade_aposentadoria} anos ({anos_restantes} anos restantes)")

# ─────────────────────────────────────────────
#  CARREGAR DADOS
# ─────────────────────────────────────────────
with st.spinner("Carregando dados da planilha..."):
    content_ativos, erro_ativos, url_ativos = load_sheet_raw(SPREADSHEET_ID, GID_PADRAO)

if erro_ativos:
    st.error(f"❌ Erro ao carregar aba de ativos: {erro_ativos}")
    st.info(f"URL tentada: {url_ativos}")
    st.stop()

df_ativos, erro_parse = parse_sheet_ativos(content_ativos)
if erro_parse or df_ativos.empty:
    st.error(f"❌ Erro ao interpretar dados de ativos: {erro_parse}")
    with st.expander("Conteúdo bruto recebido"):
        st.text(content_ativos[:2000])
    st.stop()

# ─────────────────────────────────────────────
#  DETECÇÃO DE COLUNAS
# ─────────────────────────────────────────────
colunas = list(df_ativos.columns)


def encontrar_coluna(possiveis, colunas):
    for p in possiveis:
        for c in colunas:
            if p.lower() == c.lower():
                return c
    return None


col_ticker  = encontrar_coluna(["Ticker", "ticker", "TICKER", "Ativo", "ativo"], colunas)
col_qtd     = encontrar_coluna(["Quantidade", "quantidade", "Qtd", "qtd", "QTD", "Shares", "shares"], colunas)
col_preco_m = encontrar_coluna(["Preço Médio", "preco_medio", "PrecoMedio", "Preco Medio", "Avg Price", "avg_price"], colunas)
col_moeda   = encontrar_coluna(["Moeda", "moeda", "MOEDA", "Currency", "currency"], colunas)
col_classe  = encontrar_coluna(["Classe", "classe", "CLASSE", "Class", "class", "Tipo", "tipo"], colunas)
col_pais    = encontrar_coluna(["País", "pais", "PAIS", "Pais", "Country", "country"], colunas)

if not col_ticker:
    st.error("❌ Coluna 'Ticker' não encontrada na planilha.")
    st.write("Colunas disponíveis:", colunas)
    st.stop()

if not col_qtd:
    st.error("❌ Coluna 'Quantidade' não encontrada na planilha.")
    st.write("Colunas disponíveis:", colunas)
    st.stop()

# ─────────────────────────────────────────────
#  COTAÇÕES
# ─────────────────────────────────────────────
with st.spinner("Buscando cotações..."):
    rates = get_all_rates()

tickers_lista = df_ativos[col_ticker].dropna().unique().tolist()

cotacoes = {}
progress = st.progress(0)
for i, tk in enumerate(tickers_lista):
    cotacoes[tk] = get_ticker_info(str(tk).strip(), rates)
    progress.progress((i + 1) / len(tickers_lista))
progress.empty()

# ─────────────────────────────────────────────
#  MONTAR DATAFRAME ENRIQUECIDO
# ─────────────────────────────────────────────
rows = []
for _, row in df_ativos.iterrows():
    ticker = str(row[col_ticker]).strip()
    try:
        qtd = float(str(row[col_qtd]).replace(",", "."))
    except Exception:
        qtd = 0.0

    preco_medio_orig = None
    if col_preco_m:
        try:
            preco_medio_orig = float(str(row[col_preco_m]).replace(",", "."))
        except Exception:
            pass

    moeda_orig = str(row[col_moeda]).strip().upper() if col_moeda else "USD"
    classe     = str(row[col_classe]).strip() if col_classe else "N/A"
    pais       = str(row[col_pais]).strip() if col_pais else "N/A"

    info_cot = cotacoes.get(ticker, {})
    preco_usd_atual = info_cot.get("preco_usd")
    variacao_pct    = info_cot.get("variacao_pct")
    nome            = info_cot.get("nome", ticker)
    div_yield       = info_cot.get("div_yield")
    div_anual_usd   = info_cot.get("div_anual_usd")

    # Converter preço médio para USD
    preco_medio_usd = None
    if preco_medio_orig is not None:
        if moeda_orig == "USD":
            preco_medio_usd = preco_medio_orig
        else:
            taxa = rates.get(moeda_orig, None)
            if taxa:
                preco_medio_usd = preco_medio_orig * taxa
            else:
                preco_medio_usd = preco_medio_orig

    valor_atual_usd = (preco_usd_atual * qtd) if preco_usd_atual is not None else None
    custo_total_usd = (preco_medio_usd * qtd) if preco_medio_usd is not None else None
    lucro_prejuizo  = None
    lucro_pct       = None
    if valor_atual_usd is not None and custo_total_usd is not None and custo_total_usd > 0:
        lucro_prejuizo = valor_atual_usd - custo_total_usd
        lucro_pct      = (lucro_prejuizo / custo_total_usd) * 100

    # Dividendos estimados por posição
    div_pos_anual = None
    if div_anual_usd is not None:
        div_pos_anual = div_anual_usd * qtd

    rows.append({
        "Ticker":              ticker,
        "Nome":                nome,
        "Classe":              classe,
        "País":                pais,
        "Qtd":                 qtd,
        "Preço Atual (USD)":   preco_usd_atual,
        "Var. Dia (%)":        variacao_pct,
        "Preço Médio (USD)":   preco_medio_usd,
        "Valor Atual (USD)":   valor_atual_usd,
        "Custo Total (USD)":   custo_total_usd,
        "L/P (USD)":           lucro_prejuizo,
        "L/P (%)":             lucro_pct,
        "Div. Yield (%)":      (div_yield * 100) if div_yield else None,
        "Div. Anual/Pos (USD)": div_pos_anual,
    })

df = pd.DataFrame(rows)

# ─────────────────────────────────────────────
#  MÉTRICAS GERAIS
# ─────────────────────────────────────────────
total_carteira   = df["Valor Atual (USD)"].sum(skipna=True)
total_custo      = df["Custo Total (USD)"].sum(skipna=True)
total_lp         = total_carteira - total_custo if (total_carteira and total_custo) else None
total_lp_pct     = (total_lp / total_custo * 100) if (total_lp is not None and total_custo and total_custo > 0) else None

# Renda passiva estimada
renda_mensal_swr   = total_carteira * 0.004   # SWR 4.8% aa
div_mensal_estimado = df["Div. Anual/Pos (USD)"].sum(skipna=True) / 12 if "Div. Anual/Pos (USD)" in df.columns else 0
renda_mensal_total = max(renda_mensal_swr, div_mensal_estimado if div_mensal_estimado > 0 else renda_mensal_swr)

progresso_meta = (renda_mensal_swr / meta_mensal_usd * 100) if meta_mensal_usd > 0 else 0

# Cálculo de anos para meta
anos_para_atingir = anos_para_meta(total_carteira, aporte_mensal_usd, meta_mensal_usd, taxa_retorno_anual)
idade_prevista = idade_atual + anos_para_atingir if anos_para_atingir else None

# ─────────────────────────────────────────────
#  KPIs PRINCIPAIS — LINHA 1
# ─────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("💰 Patrimônio Total", formatar_usd(total_carteira))

with col2:
    delta_str = f"{formatar_pct(total_lp_pct)}" if total_lp_pct is not None else None
    st.metric("📈 L/P Total", formatar_usd(total_lp), delta=delta_str)

with col3:
    st.metric("💵 Renda Mensal Est.", formatar_usd(renda_mensal_swr),
              help="Estimativa baseada em 4.8% a.a. (SWR 0.4%/mês)")

with col4:
    st.metric("🎯 Meta Mensal", formatar_usd(meta_mensal_usd))

with col5:
    st.metric("🏁 Progresso Meta", f"{progresso_meta:.1f}%")

# ─────────────────────────────────────────────
#  KPIs APOSENTADORIA — LINHA 2
# ─────────────────────────────────────────────
col_a, col_b, col_c, col_d = st.columns(4)

meta_patrimonio_necessario = meta_mensal_usd / 0.004

with col_a:
    st.metric(
        "🏦 Patrimônio Necessário",
        formatar_usd(meta_patrimonio_necessario),
        help=f"Para gerar {formatar_usd(meta_mensal_usd)}/mês via SWR 4.8%",
    )

with col_b:
    faltam = meta_patrimonio_necessario - total_carteira
    st.metric(
        "📉 Falta Acumular",
        formatar_usd(max(0, faltam)),
        delta=f"{(total_carteira/meta_patrimonio_necessario*100):.1f}% acumulado",
    )

with col_c:
    if anos_para_atingir is not None:
        st.metric(
            "⏳ Anos p/ Atingir Meta",
            f"{anos_para_atingir:.1f} anos",
            delta=f"Aposentadoria ~{idade_prevista:.0f} anos" if idade_prevista else None,
        )
    else:
        st.metric("⏳ Anos p/ Atingir Meta", "Meta muito distante")

with col_d:
    st.metric(
        "📅 Prazo Disponível",
        f"{anos_restantes} anos",
        delta=f"Até os {idade_aposentadoria} anos",
    )

st.markdown("---")

# ─────────────────────────────────────────────
#  BARRA DE PROGRESSO
# ─────────────────────────────────────────────
prog_clamped = min(progresso_meta, 100)
cor_prog = "#16a34a" if progresso_meta >= 100 else ("#f59e0b" if progresso_meta >= 50 else "#3b82f6")

st.markdown("**Progresso em direção à renda mensal desejada:**")
st.markdown(f"""
<div style="background:#e2e8f0;border-radius:8px;height:28px;width:100%;margin-bottom:8px;">
  <div style="background:{cor_prog};width:{prog_clamped:.1f}%;height:100%;border-radius:8px;
              display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;font-size:14px;">
    {progresso_meta:.1f}%
  </div>
</div>
<p style="color:#64748b;font-size:12px;margin-top:4px;">
  {formatar_usd(renda_mensal_swr)} / {formatar_usd(meta_mensal_usd)} por mês
  &nbsp;|&nbsp; Patrimônio: {formatar_usd(total_carteira)} / {formatar_usd(meta_patrimonio_necessario)}
</p>
""", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────
#  TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Carteira",
    "🥧 Alocação",
    "📈 Desempenho",
    "🔮 Projeção",
    "🔍 Detalhes",
])

# ── TAB 1: CARTEIRA ──────────────────────────
with tab1:
    st.subheader("Posições da Carteira")

    c1, c2, c3 = st.columns(3)
    with c1:
        classes_disp = sorted(df["Classe"].dropna().unique().tolist())
        classe_sel = st.multiselect("Filtrar por Classe", classes_disp, default=classes_disp)
    with c2:
        paises_disp = sorted(df["País"].dropna().unique().tolist())
        pais_sel = st.multiselect("Filtrar por País", paises_disp, default=paises_disp)
    with c3:
        busca = st.text_input("Buscar Ticker / Nome", "")

    df_filtrado = df[
        df["Classe"].isin(classe_sel) &
        df["País"].isin(pais_sel)
    ]
    if busca:
        mask = (
            df_filtrado["Ticker"].str.contains(busca, case=False, na=False) |
            df_filtrado["Nome"].str.contains(busca, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]

    df_show = df_filtrado.copy()
    df_show["Preço Atual (USD)"]  = df_show["Preço Atual (USD)"].apply(formatar_usd)
    df_show["Var. Dia (%)"]       = df_show["Var. Dia (%)"].apply(formatar_pct)
    df_show["Preço Médio (USD)"]  = df_show["Preço Médio (USD)"].apply(formatar_usd)
    df_show["Valor Atual (USD)"]  = df_show["Valor Atual (USD)"].apply(formatar_usd)
    df_show["Custo Total (USD)"]  = df_show["Custo Total (USD)"].apply(formatar_usd)
    df_show["L/P (USD)"]          = df_show["L/P (USD)"].apply(formatar_usd)
    df_show["L/P (%)"]            = df_show["L/P (%)"].apply(formatar_pct)
    df_show["Div. Yield (%)"]     = df_show["Div. Yield (%)"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
    df_show["Div. Anual/Pos (USD)"] = df_show["Div. Anual/Pos (USD)"].apply(formatar_usd)
    df_show["Qtd"]                = df_show["Qtd"].apply(lambda x: f"{x:,.4f}" if pd.notna(x) else "—")

    st.dataframe(df_show, use_container_width=True, height=400)

    total_filtrado = df_filtrado["Valor Atual (USD)"].sum(skipna=True)
    div_filtrado = df_filtrado["Div. Anual/Pos (USD)"].sum(skipna=True) / 12
    st.caption(
        f"Total filtrado: {formatar_usd(total_filtrado)} | "
        f"Renda mensal estimada (div.): {formatar_usd(div_filtrado)} | "
        f"{len(df_filtrado)} ativos"
    )

# ── TAB 2: ALOCAÇÃO ──────────────────────────
with tab2:
    st.subheader("Alocação da Carteira")

    c1, c2 = st.columns(2)

    with c1:
        df_classe = (
            df.groupby("Classe", dropna=False)["Valor Atual (USD)"]
            .sum()
            .reset_index()
            .dropna(subset=["Valor Atual (USD)"])
            .sort_values("Valor Atual (USD)", ascending=False)
        )
        if not df_classe.empty:
            fig_classe = px.pie(
                df_classe,
                names="Classe",
                values="Valor Atual (USD)",
                title="Por Classe de Ativo",
                hole=0.4,
            )
            fig_classe.update_layout(**LAYOUT_BASE)
            fig_classe.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_classe, use_container_width=True)

    with c2:
        df_pais = (
            df.groupby("País", dropna=False)["Valor Atual (USD)"]
            .sum()
            .reset_index()
            .dropna(subset=["Valor Atual (USD)"])
            .sort_values("Valor Atual (USD)", ascending=False)
        )
        if not df_pais.empty:
            fig_pais = px.pie(
                df_pais,
                names="País",
                values="Valor Atual (USD)",
                title="Por País",
                hole=0.4,
            )
            fig_pais.update_layout(**LAYOUT_BASE)
            fig_pais.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_pais, use_container_width=True)

    # Top 20 por valor
    df_top = (
        df.dropna(subset=["Valor Atual (USD)"])
        .sort_values("Valor Atual (USD)", ascending=False)
        .head(20)
    )
    if not df_top.empty:
        fig_bar = px.bar(
            df_top,
            x="Ticker",
            y="Valor Atual (USD)",
            color="Classe",
            title="Top 20 Ativos por Valor",
            text_auto=".2s",
        )
        fig_bar.update_layout(**layout_eixos("Ativo", "Valor (USD)"))
        st.plotly_chart(fig_bar, use_container_width=True)

# ── TAB 3: DESEMPENHO ────────────────────────
with tab3:
    st.subheader("Desempenho dos Ativos")

    df_desemp = df.dropna(subset=["L/P (%)"]).sort_values("L/P (%)", ascending=False)

    if not df_desemp.empty:
        cores = ["#16a34a" if v >= 0 else "#dc2626" for v in df_desemp["L/P (%)"]]
        fig_lp = go.Figure(go.Bar(
            x=df_desemp["Ticker"],
            y=df_desemp["L/P (%)"],
            marker_color=cores,
            text=df_desemp["L/P (%)"].apply(lambda v: f"{v:+.1f}%"),
            textposition="outside",
        ))
        fig_lp.update_layout(
            **layout_eixos("Ativo", "L/P (%)"),
            title="Lucro/Prejuízo por Ativo (%)",
        )
        st.plotly_chart(fig_lp, use_container_width=True)

    # Variação do dia
    df_var = df.dropna(subset=["Var. Dia (%)"]).sort_values("Var. Dia (%)", ascending=False)
    if not df_var.empty:
        cores2 = ["#16a34a" if v >= 0 else "#dc2626" for v in df_var["Var. Dia (%)"]]
        fig_var = go.Figure(go.Bar(
            x=df_var["Ticker"],
            y=df_var["Var. Dia (%)"],
            marker_color=cores2,
            text=df_var["Var. Dia (%)"].apply(lambda v: f"{v:+.2f}%"),
            textposition="outside",
        ))
        fig_var.update_layout(
            **layout_eixos("Ativo", "Variação (%)"),
            title="Variação do Dia (%)",
        )
        st.plotly_chart(fig_var, use_container_width=True)

    # Dividend Yield
    df_div = df.dropna(subset=["Div. Yield (%)"]).sort_values("Div. Yield (%)", ascending=False)
    if not df_div.empty:
        fig_div = px.bar(
            df_div,
            x="Ticker",
            y="Div. Yield (%)",
            color="Classe",
            title="Dividend Yield por Ativo (%)",
            text_auto=".2f",
        )
        fig_div.update_layout(**layout_eixos("Ativo", "Yield (%)"))
        st.plotly_chart(fig_div, use_container_width=True)

# ── TAB 4: PROJEÇÃO ──────────────────────────
with tab4:
    st.subheader("🔮 Projeção Patrimonial para Aposentadoria")

    col_p1, col_p2 = st.columns([2, 1])

    with col_p1:
        anos_proj = max(anos_restantes + 10, 30)
        df_proj = calcular_projecao_patrimonial(
            total_carteira, aporte_mensal_usd, anos_proj, taxa_retorno_anual
        )

        # Linha de meta patrimônio
        meta_pat = meta_mensal_usd / 0.004

        fig_proj = go.Figure()
        fig_proj.add_trace(go.Scatter(
            x=df_proj["Ano"],
            y=df_proj["Patrimônio (USD)"],
            mode="lines+markers",
            name="Patrimônio Projetado",
            line=dict(color="#3b82f6", width=3),
        ))
        fig_proj.add_hline(
            y=meta_pat,
            line_dash="dash",
            line_color="#dc2626",
            annotation_text=f"Meta: {formatar_usd(meta_pat)}",
            annotation_position="top right",
        )
        if idade_prevista and idade_prevista <= 90:
            ano_meta = int(datetime.now().year + (idade_prevista - idade_atual))
            fig_proj.add_vline(
                x=ano_meta,
                line_dash="dot",
                line_color="#16a34a",
                annotation_text=f"Meta atingida ({int(idade_prevista)} anos)",
                annotation_position="top left",
            )
        # Linha da aposentadoria desejada
        ano_apos = datetime.now().year + anos_restantes
        fig_proj.add_vline(
            x=ano_apos,
            line_dash="dash",
            line_color="#f59e0b",
            annotation_text=f"Aposentadoria desejada ({idade_aposentadoria} anos)",
            annotation_position="top right",
        )

        fig_proj.update_layout(
            **layout_eixos("Ano", "Patrimônio (USD)"),
            title=f"Projeção Patrimonial — Taxa {taxa_retorno_anual*100:.1f}% a.a. | Aporte {formatar_usd(aporte_mensal_usd)}/mês",
        )
        st.plotly_chart(fig_proj, use_container_width=True)

        # Renda mensal projetada
        fig_renda = go.Figure()
        fig_renda.add_trace(go.Scatter(
            x=df_proj["Ano"],
            y=df_proj["Renda Mensal Est. (USD)"],
            mode="lines",
            name="Renda Mensal Est.",
            line=dict(color="#16a34a", width=3),
            fill="tozeroy",
            fillcolor="rgba(22,163,74,0.15)",
        ))
        fig_renda.add_hline(
            y=meta_mensal_usd,
            line_dash="dash",
            line_color="#dc2626",
            annotation_text=f"Meta: {formatar_usd(meta_mensal_usd)}/mês",
        )
        fig_renda.update_layout(
            **layout_eixos("Ano", "Renda Mensal (USD)"),
            title="Renda Mensal Passiva Estimada ao Longo do Tempo",
        )
        st.plotly_chart(fig_renda, use_container_width=True)

    with col_p2:
        st.markdown("### 📊 Resumo da Projeção")

        # Patrimônio na aposentadoria desejada
        df_apos = df_proj[df_proj["Ano"] <= ano_apos]
        pat_na_apos = df_apos["Patrimônio (USD)"].iloc[-1] if not df_apos.empty else total_carteira
        renda_na_apos = pat_na_apos * 0.004

        st.metric(
            f"Patrimônio aos {idade_aposentadoria} anos",
            formatar_usd(pat_na_apos),
        )
        st.metric(
            f"Renda mensal aos {idade_aposentadoria} anos",
            formatar_usd(renda_na_apos),
            delta=f"{(renda_na_apos/meta_mensal_usd*100):.0f}% da meta" if meta_mensal_usd > 0 else None,
        )

        st.markdown("---")

        if anos_para_atingir is not None:
            st.success(f"✅ Com aporte de {formatar_usd(aporte_mensal_usd)}/mês e retorno de {taxa_retorno_anual*100:.1f}% a.a., você deve atingir a meta em **{anos_para_atingir:.1f} anos** (aos ~{int(idade_prevista)} anos).")
        else:
            patrimonio_apos = pat_na_apos
            pct_meta = (patrimonio_apos / meta_patrimonio_necessario * 100) if meta_patrimonio_necessario > 0 else 0
            st.warning(f"⚠️ Com os parâmetros atuais, aos {idade_aposentadoria} anos você terá {pct_meta:.0f}% da meta. Considere aumentar o aporte ou a taxa de retorno.")

        st.markdown("---")
        st.markdown("**Premissas:**")
        st.markdown(f"- Patrimônio atual: {formatar_usd(total_carteira)}")
        st.markdown(f"- Aporte mensal: {formatar_usd(aporte_mensal_usd)}")
        st.markdown(f"- Taxa retorno: {taxa_retorno_anual*100:.1f}% a.a.")
        st.markdown(f"- Regra SWR: 4.8% ao ano (0.4%/mês)")
        st.markdown(f"- Meta renda: {formatar_usd(meta_mensal_usd)}/mês")
        st.markdown(f"- Patrimônio necessário: {formatar_usd(meta_patrimonio_necessario)}")

        # Sensibilidade — impacto do aporte
        st.markdown("---")
        st.markdown("**📐 Análise de Sensibilidade — Aportes:**")
        aportes_test = [0, 250, 500, 1000, 2000]
        sens_rows = []
        for ap in aportes_test:
            a = anos_para_meta(total_carteira, ap, meta_mensal_usd, taxa_retorno_anual)
            sens_rows.append({
                "Aporte/mês": formatar_usd(ap),
                "Anos p/ meta": f"{a:.1f}" if a else ">50",
                "Idade": f"{int(idade_atual + a)}" if a else "—",
            })
        st.dataframe(pd.DataFrame(sens_rows), use_container_width=True, hide_index=True)

# ── TAB 5: DETALHES ──────────────────────────
with tab5:
    st.subheader("Detalhes por Ativo")

    ticker_sel = st.selectbox("Selecione um ativo", sorted(tickers_lista))

    if ticker_sel:
        info_sel = cotacoes.get(ticker_sel, {})
        info_raw = info_sel.get("info", {})

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Preço Atual (USD)", formatar_usd(info_sel.get("preco_usd")))
        with c2:
            st.metric("Var. Dia", formatar_pct(info_sel.get("variacao_pct")))
        with c3:
            st.metric("Moeda Original", info_sel.get("moeda_mercado", "—"))
        with c4:
            dy = info_sel.get("div_yield")
            st.metric("Dividend Yield", f"{dy*100:.2f}%" if dy else "—")

        c5, c6 = st.columns(2)
        with c5:
            mkt_cap = info_raw.get("marketCap")
            st.metric("Market Cap", formatar_usd(mkt_cap) if mkt_cap else "—")
        with c6:
            pe = info_raw.get("trailingPE")
            st.metric("P/E Ratio", f"{pe:.1f}x" if pe else "—")

        with st.expander("Dados completos do Yahoo Finance"):
            st.json({k: v for k, v in info_raw.items() if not isinstance(v, (list, dict))})

        # Histórico de preços
        with st.spinner("Carregando histórico..."):
            try:
                hist_longo = yf.Ticker(ticker_sel).history(period="1y")
                if not hist_longo.empty:
                    fig_hist = px.line(
                        hist_longo.reset_index(),
                        x="Date",
                        y="Close",
                        title=f"Histórico 1 Ano — {ticker_sel}",
                    )
                    fig_hist.update_layout(**layout_eixos("Data", "Preço"))
                    st.plotly_chart(fig_hist, use_container_width=True)
            except Exception as e:
                st.warning(f"Não foi possível carregar o histórico: {e}")

# ─────────────────────────────────────────────
#  RODAPÉ
# ─────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Dashboard de Aposentadoria · Dados via Yahoo Finance · "
    "Câmbio atualizado em tempo real · As informações são meramente informativas. "
    "Não constitui recomendação de investimento."
)