import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import StringIO
import yfinance as yf
from datetime import datetime

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

        nome = info.get("shortName") or info.get("longName") or ticker
        return {
            "ticker": ticker,
            "nome": nome,
            "preco_usd": preco_usd,
            "moeda_mercado": moeda_mercado,
            "variacao_pct": variacao_pct,
            "info": info,
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "nome": ticker,
            "preco_usd": None,
            "moeda_mercado": "USD",
            "variacao_pct": None,
            "info": {},
            "erro": str(e),
        }


def parse_sheet_ativos(content):
    """Lê a aba de ativos e retorna DataFrame."""
    try:
        df = pd.read_csv(StringIO(content))
        df.columns = [c.strip() for c in df.columns]
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def parse_sheet_metas(content):
    """Lê a aba de metas e retorna DataFrame."""
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


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.title("⚙️ Configurações")

spreadsheet_id = st.sidebar.text_input(
    "ID da Planilha Google",
    value=SPREADSHEET_ID,
    help="O ID da sua planilha pública do Google Sheets",
)

gid_ativos = st.sidebar.text_input(
    "GID da aba 'Ativos'",
    value=GID_PADRAO,
    help="O GID da aba que contém os ativos (número na URL)",
)

meta_mensal_usd = st.sidebar.number_input(
    "Meta mensal (USD)",
    min_value=0.0,
    value=META_MENSAL_USD_PADRAO,
    step=100.0,
    format="%.2f",
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Dados de mercado: Yahoo Finance · Câmbio em tempo real")

# ─────────────────────────────────────────────
#  TÍTULO
# ─────────────────────────────────────────────
st.title("📊 Dashboard de Aposentadoria")
st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

# ─────────────────────────────────────────────
#  CARREGAR DADOS
# ─────────────────────────────────────────────
with st.spinner("Carregando dados da planilha..."):
    content_ativos, erro_ativos, url_ativos = load_sheet_raw(spreadsheet_id, gid_ativos)

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

# Mapeamento flexível de colunas
def encontrar_coluna(possiveis, colunas):
    for p in possiveis:
        for c in colunas:
            if p.lower() == c.lower():
                return c
    return None

col_ticker   = encontrar_coluna(["Ticker", "ticker", "TICKER", "Ativo", "ativo"], colunas)
col_qtd      = encontrar_coluna(["Quantidade", "quantidade", "Qtd", "qtd", "QTD", "Shares", "shares"], colunas)
col_preco_m  = encontrar_coluna(["Preço Médio", "preco_medio", "PrecoMedio", "Preco Medio", "Avg Price", "avg_price"], colunas)
col_moeda    = encontrar_coluna(["Moeda", "moeda", "MOEDA", "Currency", "currency"], colunas)
col_classe   = encontrar_coluna(["Classe", "classe", "CLASSE", "Class", "class", "Tipo", "tipo"], colunas)
col_pais     = encontrar_coluna(["País", "pais", "PAIS", "Pais", "Country", "country"], colunas)

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

    rows.append({
        "Ticker":         ticker,
        "Nome":           nome,
        "Classe":         classe,
        "País":           pais,
        "Qtd":            qtd,
        "Preço Atual (USD)":  preco_usd_atual,
        "Var. Dia (%)":       variacao_pct,
        "Preço Médio (USD)":  preco_medio_usd,
        "Valor Atual (USD)":  valor_atual_usd,
        "Custo Total (USD)":  custo_total_usd,
        "L/P (USD)":          lucro_prejuizo,
        "L/P (%)":            lucro_pct,
    })

df = pd.DataFrame(rows)

# ─────────────────────────────────────────────
#  KPIs PRINCIPAIS
# ─────────────────────────────────────────────
total_carteira   = df["Valor Atual (USD)"].sum(skipna=True)
total_custo      = df["Custo Total (USD)"].sum(skipna=True)
total_lp         = total_carteira - total_custo if (total_carteira and total_custo) else None
total_lp_pct     = (total_lp / total_custo * 100) if (total_lp is not None and total_custo and total_custo > 0) else None
renda_mensal_est = total_carteira * 0.004  # SWR ~0.4% ao mês (≈4.8% aa)
progresso_meta   = (renda_mensal_est / meta_mensal_usd * 100) if meta_mensal_usd > 0 else 0

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("💰 Carteira Total", formatar_usd(total_carteira))

with col2:
    delta_str = f"{formatar_pct(total_lp_pct)}" if total_lp_pct is not None else None
    st.metric("📈 L/P Total", formatar_usd(total_lp), delta=delta_str)

with col3:
    st.metric("💵 Renda Mensal Est.", formatar_usd(renda_mensal_est),
              help="Estimativa baseada em 4.8% a.a. (0.4% ao mês)")

with col4:
    st.metric("🎯 Meta Mensal", formatar_usd(meta_mensal_usd))

with col5:
    st.metric("🏁 Progresso Meta", f"{progresso_meta:.1f}%")

st.markdown("---")

# ─────────────────────────────────────────────
#  BARRA DE PROGRESSO DA META
# ─────────────────────────────────────────────
prog_clamped = min(progresso_meta, 100)
cor_prog = "#16a34a" if progresso_meta >= 100 else "#3b82f6"

st.markdown(f"""
<div style="background:#e2e8f0;border-radius:8px;height:24px;width:100%;margin-bottom:8px;">
  <div style="background:{cor_prog};width:{prog_clamped:.1f}%;height:100%;border-radius:8px;
              display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;font-size:13px;">
    {progresso_meta:.1f}%
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────
#  TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📋 Carteira", "🥧 Alocação", "📈 Desempenho", "🔍 Detalhes"])

# ── TAB 1: CARTEIRA ──────────────────────────
with tab1:
    st.subheader("Posições da Carteira")

    # Filtros
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

    # Formatar para exibição
    df_show = df_filtrado.copy()
    df_show["Preço Atual (USD)"] = df_show["Preço Atual (USD)"].apply(formatar_usd)
    df_show["Var. Dia (%)"]      = df_show["Var. Dia (%)"].apply(formatar_pct)
    df_show["Preço Médio (USD)"] = df_show["Preço Médio (USD)"].apply(formatar_usd)
    df_show["Valor Atual (USD)"] = df_show["Valor Atual (USD)"].apply(formatar_usd)
    df_show["Custo Total (USD)"] = df_show["Custo Total (USD)"].apply(formatar_usd)
    df_show["L/P (USD)"]         = df_show["L/P (USD)"].apply(formatar_usd)
    df_show["L/P (%)"]           = df_show["L/P (%)"].apply(formatar_pct)
    df_show["Qtd"]               = df_show["Qtd"].apply(lambda x: f"{x:,.4f}" if pd.notna(x) else "—")

    st.dataframe(df_show, use_container_width=True, height=400)

    total_filtrado = df_filtrado["Valor Atual (USD)"].sum(skipna=True)
    st.caption(f"Total filtrado: {formatar_usd(total_filtrado)} | {len(df_filtrado)} ativos")

# ── TAB 2: ALOCAÇÃO ──────────────────────────
with tab2:
    st.subheader("Alocação da Carteira")

    c1, c2 = st.columns(2)

    with c1:
        # Por Classe
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
        # Por País
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

    # Barras por ativo (top 20)
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

# ── TAB 3: DESEMPENHO ──────────────────────────
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

# ── TAB 4: DETALHES ──────────────────────────
with tab4:
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
            mkt_cap = info_raw.get("marketCap")
            st.metric("Market Cap", formatar_usd(mkt_cap) if mkt_cap else "—")

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
    "Câmbio atualizado em tempo real · As informações são meramente informativas."
)