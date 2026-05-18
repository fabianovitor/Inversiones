# dashboard_aposentadoria.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import StringIO
import yfinance as yf
from datetime import datetime
import numpy as np
import unicodedata

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
def get_ticker_info(ticker, rates_tuple):
    rates = dict(rates_tuple)
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


def normalizar_str(s):
    """Normaliza string: lowercase, sem acentos, sem espaços extras."""
    s = str(s).strip().lower()
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def parse_sheet(content):
    """
    Lê o CSV e retorna:
    - df com colunas NORMALIZADAS (sem acentos, lowercase)
    - erro (None se OK)
    - mapa: nome_normalizado -> nome_original
    """
    try:
        df = pd.read_csv(StringIO(content))
        orig_cols = {normalizar_str(c): str(c).strip() for c in df.columns}
        df.columns = [normalizar_str(c) for c in df.columns]
        df = df.dropna(how="all")
        return df, None, orig_cols
    except Exception as e:
        return pd.DataFrame(), str(e), {}


def encontrar_coluna(df_cols_norm, candidatos):
    """
    Encontra coluna normalizada no DataFrame.
    Retorna o nome normalizado ou None.
    """
    cols_set = set(df_cols_norm)
    for cand in candidatos:
        cand_norm = normalizar_str(cand)
        if cand_norm in cols_set:
            return cand_norm
    return None


def formatar_usd(valor):
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    try:
        return f"${float(valor):,.2f}"
    except Exception:
        return "—"


def formatar_pct(valor):
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    try:
        sinal = "+" if float(valor) > 0 else ""
        return f"{sinal}{float(valor):.2f}%"
    except Exception:
        return "—"


def calcular_projecao_patrimonial(patrimonio_atual, aporte_mensal, anos, taxa_anual=0.07):
    taxa_mensal = (1 + taxa_anual) ** (1/12) - 1
    meses = int(anos * 12)
    resultados = []
    saldo = float(patrimonio_atual)
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
    meta_patrimonio = meta_renda_mensal / 0.004
    taxa_mensal = (1 + taxa_anual) ** (1/12) - 1
    saldo = float(patrimonio_atual)
    meses = 0
    max_meses = 600
    while saldo < meta_patrimonio and meses < max_meses:
        saldo = saldo * (1 + taxa_mensal) + aporte_mensal
        meses += 1
    if meses >= max_meses:
        return None
    return meses / 12


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Painel de Controle")
    st.markdown("### 🎯 Meus Objetivos")

    idade_atual = st.number_input(
        "Minha idade atual",
        min_value=18, max_value=80, value=48, step=1,
    )
    idade_aposentadoria = st.number_input(
        "Idade desejada para aposentadoria",
        min_value=int(idade_atual) + 1, max_value=90, value=65, step=1,
    )
    meta_mensal_usd = st.number_input(
        "Meta de renda mensal passiva (USD)",
        min_value=0.0, value=META_MENSAL_USD_PADRAO, step=100.0, format="%.2f",
    )
    aporte_mensal_usd = st.number_input(
        "Aporte mensal planejado (USD)",
        min_value=0.0, value=500.0, step=50.0, format="%.2f",
    )
    taxa_retorno_anual = st.slider(
        "Taxa de retorno anual estimada (%)",
        min_value=3.0, max_value=15.0, value=7.0, step=0.5,
    ) / 100

    st.markdown("---")
    st.markdown("### 📊 Planilha")
    st.caption(f"ID fixo: `{SPREADSHEET_ID[:22]}...`")
    st.caption(f"GID fixo: `{GID_PADRAO}`")

    st.markdown("---")
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    mostrar_debug = st.checkbox("🔧 Modo debug (diagnóstico)", value=False)
    st.caption("Dados: Yahoo Finance · Câmbio em tempo real")

anos_restantes = int(idade_aposentadoria) - int(idade_atual)

# ─────────────────────────────────────────────────────────────────────────────
#  TÍTULO
# ─────────────────────────────────────────────────────────────────────────────
st.title("📊 Dashboard de Aposentadoria")
st.caption(
    f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · "
    f"{int(idade_atual)} anos · Meta: aposentar aos {int(idade_aposentadoria)} anos "
    f"({anos_restantes} anos restantes)"
)

# ─────────────────────────────────────────────────────────────────────────────
#  CARREGAR DADOS
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Carregando dados da planilha..."):
    content_raw, erro_load, url_usada = load_sheet_raw(SPREADSHEET_ID, GID_PADRAO)

if erro_load:
    st.error(f"❌ Erro ao carregar planilha: {erro_load}")
    st.info(f"URL: {url_usada}")
    st.stop()

df_raw, erro_parse, orig_cols_map = parse_sheet(content_raw)

if mostrar_debug:
    with st.expander("🔧 DEBUG — Conteúdo bruto (primeiros 3000 chars)"):
        st.text(content_raw[:3000])
    with st.expander("🔧 DEBUG — DataFrame bruto (colunas normalizadas)"):
        st.dataframe(df_raw)
    with st.expander("🔧 DEBUG — Mapa de colunas"):
        st.write("Colunas normalizadas:", list(df_raw.columns))
        st.write("Mapa normalizado→original:", orig_cols_map)

if erro_parse or df_raw.empty:
    st.error(f"❌ Erro ao interpretar planilha: {erro_parse}")
    with st.expander("Conteúdo bruto"):
        st.text(content_raw[:3000])
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
#  MAPEAMENTO DE COLUNAS (usando nomes NORMALIZADOS)
#  Planilha esperada: Ticker | Qtd | Preco Medio | Moeda | Classe | Pais | Setor
# ─────────────────────────────────────────────────────────────────────────────
colunas_norm = list(df_raw.columns)

CANDIDATOS = {
    "ticker":      ["Ticker", "ticker", "Ativo", "Symbol", "Simbolo", "simbolo", "Code", "Codigo"],
    "quantidade":  ["Qtd", "qtd", "Quantidade", "quantidade", "Qty", "Shares", "Cotas"],
    "preco_medio": [
        "Preco Medio", "Preco_Medio", "PrecoMedio", "preco medio", "preco_medio",
        "Avg Price", "avg_price", "PM", "Custo Medio", "custo_medio",
        "Preco de Custo", "preco de custo",
        "Preço Médio", "Custo Médio", "Preço de Custo",
    ],
    "moeda":       ["Moeda", "moeda", "Currency", "currency", "Moeda Orig"],
    "classe":      ["Classe", "classe", "Class", "Tipo", "tipo", "Categoria", "Asset Class"],
    "pais":        ["Pais", "pais", "Pays", "Country", "country", "Mercado", "Regiao",
                    "País", "Região"],
    "setor":       ["Setor", "setor", "Sector", "sector", "Segmento"],
}

col_ticker   = encontrar_coluna(colunas_norm, CANDIDATOS["ticker"])
col_qtd      = encontrar_coluna(colunas_norm, CANDIDATOS["quantidade"])
col_pm       = encontrar_coluna(colunas_norm, CANDIDATOS["preco_medio"])
col_moeda    = encontrar_coluna(colunas_norm, CANDIDATOS["moeda"])
col_classe   = encontrar_coluna(colunas_norm, CANDIDATOS["classe"])
col_pais     = encontrar_coluna(colunas_norm, CANDIDATOS["pais"])
col_setor    = encontrar_coluna(colunas_norm, CANDIDATOS["setor"])

if mostrar_debug:
    with st.expander("🔧 DEBUG — Mapeamento de colunas encontradas"):
        st.write({
            "ticker":      col_ticker,
            "quantidade":  col_qtd,
            "preco_medio": col_pm,
            "moeda":       col_moeda,
            "classe":      col_classe,
            "pais":        col_pais,
            "setor":       col_setor,
        })

if not col_ticker:
    st.warning("⚠️ Coluna 'Ticker' não detectada. Selecione abaixo:")
    col_ticker = st.selectbox("Coluna com os tickers:", colunas_norm)
if not col_qtd:
    st.warning("⚠️ Coluna 'Quantidade' não detectada. Selecione abaixo:")
    col_qtd = st.selectbox("Coluna com as quantidades:", colunas_norm)

# ─────────────────────────────────────────────────────────────────────────────
#  FILTRAR LINHAS VÁLIDAS
# ─────────────────────────────────────────────────────────────────────────────
df_ativos = df_raw.copy()
df_ativos = df_ativos[df_ativos[col_ticker].notna()]
df_ativos = df_ativos[df_ativos[col_ticker].astype(str).str.strip() != ""]
df_ativos = df_ativos[~df_ativos[col_ticker].astype(str).str.lower().str.startswith("ticker")]
df_ativos = df_ativos.reset_index(drop=True)

if df_ativos.empty:
    st.error("❌ Nenhum ativo encontrado na planilha após filtros.")
    st.dataframe(df_raw)
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
#  COTAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Buscando taxas de câmbio..."):
    rates = get_all_rates()
    rates_tuple = tuple(sorted(rates.items()))

tickers_lista = df_ativos[col_ticker].astype(str).str.strip().unique().tolist()

cotacoes = {}
progress_bar = st.progress(0)
status_text = st.empty()
for i, tk in enumerate(tickers_lista):
    status_text.text(f"Buscando cotação: {tk} ({i+1}/{len(tickers_lista)})")
    cotacoes[tk] = get_ticker_info(str(tk).strip(), rates_tuple)
    progress_bar.progress((i + 1) / len(tickers_lista))
progress_bar.empty()
status_text.empty()

# ─────────────────────────────────────────────────────────────────────────────
#  MONTAR DATAFRAME ENRIQUECIDO
#  IMPORTANTE: todas as chaves do dict usam nomes SEM acentos
# ─────────────────────────────────────────────────────────────────────────────
rows = []
for _, row in df_ativos.iterrows():
    ticker = str(row[col_ticker]).strip()

    # Quantidade
    try:
        qtd_raw = str(row[col_qtd]).replace(",", ".").strip() if col_qtd else "0"
        qtd = float(qtd_raw) if qtd_raw not in ("", "nan", "None") else 0.0
    except Exception:
        qtd = 0.0

    # Preço médio
    preco_medio_orig = None
    if col_pm:
        try:
            pm_raw = str(row[col_pm]).replace(",", ".").strip()
            if pm_raw not in ("", "nan", "None", "-", "—"):
                preco_medio_orig = float(pm_raw)
        except Exception:
            pass

    # Moeda original
    moeda_orig = "USD"
    if col_moeda:
        m = str(row[col_moeda]).strip().upper()
        if m not in ("", "NAN", "NONE"):
            moeda_orig = m

    # Classe, País, Setor
    classe = str(row[col_classe]).strip() if col_classe and pd.notna(row[col_classe]) else "N/A"
    pais   = str(row[col_pais]).strip()   if col_pais  and pd.notna(row[col_pais])   else "N/A"
    setor  = str(row[col_setor]).strip()  if col_setor and pd.notna(row[col_setor])  else "N/A"

    # Dados de cotação
    info_cot        = cotacoes.get(ticker, {})
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
            taxa = rates.get(moeda_orig, 1.0)
            preco_medio_usd = preco_medio_orig * taxa

    # Cálculos financeiros
    valor_atual_usd = (preco_usd_atual * qtd) if preco_usd_atual is not None else None
    custo_total_usd = (preco_medio_usd * qtd) if preco_medio_usd is not None else None

    lucro_prejuizo = None
    lucro_pct      = None
    if valor_atual_usd is not None and custo_total_usd is not None and custo_total_usd > 0:
        lucro_prejuizo = valor_atual_usd - custo_total_usd
        lucro_pct      = (lucro_prejuizo / custo_total_usd) * 100

    div_pos_anual = (div_anual_usd * qtd) if div_anual_usd is not None else None

    # ── CHAVES SEM ACENTOS ──────────────────────────────────────────────────
    rows.append({
        "ticker":            ticker,
        "nome":              nome,
        "classe":            classe,
        "pais":              pais,
        "setor":             setor,
        "qtd":               qtd,
        "preco_atual_usd":   preco_usd_atual,
        "var_dia_pct":       variacao_pct,
        "preco_medio_usd":   preco_medio_usd,
        "valor_atual_usd":   valor_atual_usd,
        "custo_total_usd":   custo_total_usd,
        "lp_usd":            lucro_prejuizo,
        "lp_pct":            lucro_pct,
        "div_yield_pct":     (div_yield * 100) if div_yield else None,
        "div_anual_pos_usd": div_pos_anual,
    })

df = pd.DataFrame(rows)

# Mapa de nomes internos → rótulos bonitos para exibição
COL_LABEL = {
    "ticker":            "Ticker",
    "nome":              "Nome",
    "classe":            "Classe",
    "pais":              "País",
    "setor":             "Setor",
    "qtd":               "Qtd",
    "preco_atual_usd":   "Preço Atual (USD)",
    "var_dia_pct":       "Var. Dia (%)",
    "preco_medio_usd":   "Preço Médio (USD)",
    "valor_atual_usd":   "Valor Atual (USD)",
    "custo_total_usd":   "Custo Total (USD)",
    "lp_usd":            "L/P (USD)",
    "lp_pct":            "L/P (%)",
    "div_yield_pct":     "Div. Yield (%)",
    "div_anual_pos_usd": "Div. Anual Pos (USD)",
}

# ─────────────────────────────────────────────────────────────────────────────
#  MÉTRICAS GERAIS
# ─────────────────────────────────────────────────────────────────────────────
patrimonio_total = df["valor_atual_usd"].dropna().sum()
custo_total      = df["custo_total_usd"].dropna().sum()
lucro_total      = patrimonio_total - custo_total if custo_total > 0 else None
div_anual_total  = df["div_anual_pos_usd"].dropna().sum()
div_mensal_total = div_anual_total / 12

pct_meta_renda = (div_mensal_total / meta_mensal_usd * 100) if meta_mensal_usd > 0 else 0

anos_ate_meta = anos_para_meta(patrimonio_total, aporte_mensal_usd, meta_mensal_usd, taxa_retorno_anual)

# ─────────────────────────────────────────────────────────────────────────────
#  LAYOUT PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

# KPIs
st.markdown("## 📈 Resumo Geral")
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("💼 Patrimônio Total", formatar_usd(patrimonio_total))
with c2:
    delta_lp = None
    if lucro_total is not None and custo_total > 0:
        delta_lp = f"{lucro_total/custo_total*100:+.1f}%"
    st.metric("📊 L/P Total", formatar_usd(lucro_total), delta=delta_lp)
with c3:
    st.metric("💰 Renda Mensal Est.", formatar_usd(div_mensal_total))
with c4:
    st.metric("🎯 % da Meta Mensal", f"{pct_meta_renda:.1f}%")
with c5:
    if anos_ate_meta:
        st.metric("⏳ Anos p/ Meta", f"{anos_ate_meta:.1f} anos")
    else:
        st.metric("⏳ Anos p/ Meta", "Meta já atingida!" if pct_meta_renda >= 100 else ">50 anos")

st.markdown("---")

# ── TABS ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Carteira", "🥧 Alocação", "💸 Dividendos", "📈 Projeção", "🔍 Detalhes"
])

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 1 — CARTEIRA
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### 📋 Posições Atuais")

    # Criar cópia renomeada apenas para exibição
    df_display = df.rename(columns=COL_LABEL).copy()

    # Formatar colunas USD (acessa df original com chaves sem acento)
    for col_orig in ["preco_atual_usd", "preco_medio_usd", "valor_atual_usd",
                     "custo_total_usd", "lp_usd", "div_anual_pos_usd"]:
        col_label = COL_LABEL[col_orig]
        df_display[col_label] = df[col_orig].apply(formatar_usd)

    # Formatar colunas %
    for col_orig in ["var_dia_pct", "lp_pct", "div_yield_pct"]:
        col_label = COL_LABEL[col_orig]
        df_display[col_label] = df[col_orig].apply(formatar_pct)

    df_display[COL_LABEL["qtd"]] = df["qtd"].apply(
        lambda x: f"{x:,.0f}" if x is not None and not np.isnan(x) else "—"
    )

    st.dataframe(df_display, use_container_width=True)

    # Top gainers / losers
    df_lp = df[df["lp_pct"].notna()].copy()
    if not df_lp.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🏆 Top Gainers")
            top_g = df_lp.nlargest(5, "lp_pct")
            fig = px.bar(
                top_g, x="ticker", y="lp_pct",
                color="lp_pct", color_continuous_scale="Greens",
                title="Top 5 Maiores Ganhos (%)",
            )
            fig.update_layout(**LAYOUT_BASE)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.markdown("#### 📉 Top Losers")
            top_l = df_lp.nsmallest(5, "lp_pct")
            fig = px.bar(
                top_l, x="ticker", y="lp_pct",
                color="lp_pct", color_continuous_scale="Reds_r",
                title="Top 5 Maiores Perdas (%)",
            )
            fig.update_layout(**LAYOUT_BASE)
            st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 2 — ALOCAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("### 🥧 Alocação da Carteira")

    df_val = df[df["valor_atual_usd"].notna() & (df["valor_atual_usd"] > 0)].copy()

    if df_val.empty:
        st.info("Sem dados de valor para exibir alocação.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            if col_classe:
                df_classe = df_val.groupby("classe")["valor_atual_usd"].sum().reset_index()
                fig = px.pie(
                    df_classe, values="valor_atual_usd", names="classe",
                    title="Alocação por Classe de Ativo",
                    hole=0.4,
                )
                fig.update_layout(**LAYOUT_BASE)
                st.plotly_chart(fig, use_container_width=True)

        with col_b:
            if col_pais:
                df_pais_g = df_val.groupby("pais")["valor_atual_usd"].sum().reset_index()
                fig = px.pie(
                    df_pais_g, values="valor_atual_usd", names="pais",
                    title="Alocação por País",
                    hole=0.4,
                )
                fig.update_layout(**LAYOUT_BASE)
                st.plotly_chart(fig, use_container_width=True)

        top15 = df_val.nlargest(15, "valor_atual_usd")
        fig = px.bar(
            top15, x="ticker", y="valor_atual_usd",
            title="Top 15 Ativos por Valor (USD)",
            color="valor_atual_usd", color_continuous_scale="Blues",
        )
        fig.update_layout(**layout_eixos("Ativo", "Valor (USD)"))
        st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 3 — DIVIDENDOS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 💸 Renda de Dividendos")

    df_div = df[df["div_anual_pos_usd"].notna() & (df["div_anual_pos_usd"] > 0)].copy()

    if df_div.empty:
        st.info("Nenhum ativo com dividendos identificado.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("💰 Renda Anual Total", formatar_usd(div_anual_total))
        with c2:
            st.metric("📅 Renda Mensal Média", formatar_usd(div_mensal_total))
        with c3:
            st.metric("🎯 % da Meta Mensal", f"{pct_meta_renda:.1f}%")

        fig = px.bar(
            df_div.sort_values("div_anual_pos_usd", ascending=False),
            x="ticker", y="div_anual_pos_usd",
            title="Renda Anual de Dividendos por Ativo (USD)",
            color="div_anual_pos_usd", color_continuous_scale="Greens",
        )
        fig.update_layout(**layout_eixos("Ativo", "Dividendo Anual (USD)"))
        st.plotly_chart(fig, use_container_width=True)

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=div_mensal_total,
            delta={"reference": meta_mensal_usd, "valueformat": ".2f"},
            title={"text": f"Renda Mensal vs Meta (${meta_mensal_usd:,.0f}/mês)"},
            gauge={
                "axis": {"range": [0, meta_mensal_usd * 1.5]},
                "bar": {"color": "#22c55e"},
                "steps": [
                    {"range": [0, meta_mensal_usd * 0.5], "color": "#fee2e2"},
                    {"range": [meta_mensal_usd * 0.5, meta_mensal_usd], "color": "#fef9c3"},
                    {"range": [meta_mensal_usd, meta_mensal_usd * 1.5], "color": "#dcfce7"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": meta_mensal_usd,
                },
            },
            number={"prefix": "$", "valueformat": ".2f"},
        ))
        fig_gauge.update_layout(**LAYOUT_BASE)
        st.plotly_chart(fig_gauge, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 4 — PROJEÇÃO
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown("### 📈 Projeção Patrimonial")

    df_proj = calcular_projecao_patrimonial(
        patrimonio_total, aporte_mensal_usd, anos_restantes + 10, taxa_retorno_anual
    )

    if not df_proj.empty:
        fig = px.line(
            df_proj, x="Ano", y="Patrimônio (USD)",
            title=f"Projeção Patrimonial — Taxa {taxa_retorno_anual*100:.1f}% a.a.",
            markers=True,
        )
        meta_patrim = meta_mensal_usd / 0.004
        fig.add_hline(
            y=meta_patrim,
            line_dash="dash", line_color="red",
            annotation_text=f"Meta patrimônio: ${meta_patrim:,.0f}",
        )
        fig.update_layout(**layout_eixos("Ano", "Patrimônio (USD)"))
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            df_proj, x="Ano", y="Renda Mensal Est. (USD)",
            title="Projeção de Renda Mensal Passiva (USD)",
            markers=True,
            color_discrete_sequence=["#22c55e"],
        )
        fig2.add_hline(
            y=meta_mensal_usd,
            line_dash="dash", line_color="red",
            annotation_text=f"Meta: ${meta_mensal_usd:,.0f}/mês",
        )
        fig2.update_layout(**layout_eixos("Ano", "Renda Mensal (USD)"))
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### 📊 Resumo da Projeção")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            patrim_final = df_proj["Patrimônio (USD)"].iloc[-1]
            st.metric(f"Patrimônio em {df_proj['Ano'].iloc[-1]}", formatar_usd(patrim_final))
        with col_b:
            renda_final = df_proj["Renda Mensal Est. (USD)"].iloc[-1]
            st.metric("Renda Mensal Est. Final", formatar_usd(renda_final))
        with col_c:
            if anos_ate_meta:
                ano_meta = datetime.now().year + int(anos_ate_meta)
                st.metric("Ano Estimado para Meta", str(ano_meta))
            else:
                st.metric("Ano Estimado para Meta", "Já atingida!" if pct_meta_renda >= 100 else ">50 anos")

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 5 — DETALHES
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.markdown("### 🔍 Detalhes por Ativo")

    ticker_sel = st.selectbox("Selecione um ativo:", sorted(df["ticker"].unique()))

    if ticker_sel:
        row_sel = df[df["ticker"] == ticker_sel].iloc[0]

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Preço Atual", formatar_usd(row_sel["preco_atual_usd"]))
            st.metric("Variação Dia", formatar_pct(row_sel["var_dia_pct"]))
        with col_b:
            st.metric("Valor na Carteira", formatar_usd(row_sel["valor_atual_usd"]))
            st.metric("Custo Total", formatar_usd(row_sel["custo_total_usd"]))
        with col_c:
            st.metric("L/P (USD)", formatar_usd(row_sel["lp_usd"]))
            st.metric("L/P (%)", formatar_pct(row_sel["lp_pct"]))

        st.markdown("---")
        col_d, col_e = st.columns(2)
        with col_d:
            st.markdown(f"**Nome:** {row_sel['nome']}")
            st.markdown(f"**Classe:** {row_sel['classe']}")
            st.markdown(f"**País:** {row_sel['pais']}")
            st.markdown(f"**Setor:** {row_sel['setor']}")
        with col_e:
            st.markdown(f"**Quantidade:** {row_sel['qtd']}")
            st.markdown(f"**Dividend Yield:** {formatar_pct(row_sel['div_yield_pct'])}")
            st.markdown(f"**Div. Anual (posição):** {formatar_usd(row_sel['div_anual_pos_usd'])}")

        st.markdown("#### 📈 Histórico de Preços (1 ano)")
        try:
            hist_data = yf.Ticker(ticker_sel).history(period="1y")
            if not hist_data.empty:
                fig = px.line(hist_data, x=hist_data.index, y="Close",
                              title=f"Histórico — {ticker_sel}")
                fig.update_layout(**layout_eixos("Data", "Preço"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados históricos disponíveis.")
        except Exception as e:
            st.warning(f"Não foi possível carregar histórico: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  RODAPÉ
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Dashboard de Aposentadoria · Dados via Yahoo Finance · "
    f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)