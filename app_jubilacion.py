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


def parse_sheet(content):
    try:
        df = pd.read_csv(StringIO(content))
        # Normaliza nomes de colunas: remove espaços extras
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how="all")
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def normalizar_coluna(nome):
    """Normaliza nome de coluna para comparação: lowercase, sem acentos, sem espaços."""
    import unicodedata
    nome = str(nome).lower().strip()
    # Remove acentos
    nfkd = unicodedata.normalize('NFKD', nome)
    nome = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return nome


def encontrar_coluna_flexivel(colunas, candidatos):
    """Encontra coluna por lista de candidatos (normalizado)."""
    mapa = {normalizar_coluna(c): c for c in colunas}
    for cand in candidatos:
        cand_norm = normalizar_coluna(cand)
        if cand_norm in mapa:
            return mapa[cand_norm]
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

df_raw, erro_parse = parse_sheet(content_raw)

if mostrar_debug:
    with st.expander("🔧 DEBUG — Conteúdo bruto (primeiros 3000 chars)"):
        st.text(content_raw[:3000])
    with st.expander("🔧 DEBUG — DataFrame bruto"):
        st.dataframe(df_raw)
    with st.expander("🔧 DEBUG — Colunas encontradas"):
        st.write(list(df_raw.columns))
        st.write("Colunas normalizadas:", [normalizar_coluna(c) for c in df_raw.columns])

if erro_parse or df_raw.empty:
    st.error(f"❌ Erro ao interpretar planilha: {erro_parse}")
    with st.expander("Conteúdo bruto"):
        st.text(content_raw[:3000])
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
#  MAPEAMENTO DE COLUNAS
#  Baseado nos prints: Ticker | Qtd | Preço Médio | Moeda | Classe | País | Setor
# ─────────────────────────────────────────────────────────────────────────────
colunas_disponiveis = list(df_raw.columns)

# Candidatos para cada campo (serão normalizados na busca)
CANDIDATOS = {
    "ticker":      ["Ticker", "ticker", "Ativo", "ativo", "Symbol", "symbol", "Símbolo", "simbolo", "Code", "Código"],
    "quantidade":  ["Qtd", "qtd", "Quantidade", "quantidade", "Qty", "qty", "Shares", "shares", "Cotas"],
    "preco_medio": ["Preço Médio", "Preco Medio", "PrecoMedio", "Avg Price", "avg_price",
                    "preco_medio", "Custo Médio", "custo_medio", "PM", "Preço de Custo"],
    "moeda":       ["Moeda", "moeda", "Currency", "currency", "Moeda Orig", "Moeda Original"],
    "classe":      ["Classe", "classe", "Class", "class", "Tipo", "tipo", "Categoria", "Asset Class"],
    "pais":        ["País", "Pais", "pais", "Country", "country", "Mercado", "mercado", "Região"],
    "setor":       ["Setor", "setor", "Sector", "sector", "Segmento", "segment"],
}

col_ticker   = encontrar_coluna_flexivel(colunas_disponiveis, CANDIDATOS["ticker"])
col_qtd      = encontrar_coluna_flexivel(colunas_disponiveis, CANDIDATOS["quantidade"])
col_pm       = encontrar_coluna_flexivel(colunas_disponiveis, CANDIDATOS["preco_medio"])
col_moeda    = encontrar_coluna_flexivel(colunas_disponiveis, CANDIDATOS["moeda"])
col_classe   = encontrar_coluna_flexivel(colunas_disponiveis, CANDIDATOS["classe"])
col_pais     = encontrar_coluna_flexivel(colunas_disponiveis, CANDIDATOS["pais"])
col_setor    = encontrar_coluna_flexivel(colunas_disponiveis, CANDIDATOS["setor"])

if mostrar_debug:
    with st.expander("🔧 DEBUG — Mapeamento de colunas"):
        st.write({
            "ticker":      col_ticker,
            "quantidade":  col_qtd,
            "preco_medio": col_pm,
            "moeda":       col_moeda,
            "classe":      col_classe,
            "pais":        col_pais,
            "setor":       col_setor,
        })

# Se coluna ticker não encontrada, deixa o usuário selecionar
if not col_ticker:
    st.warning("⚠️ Coluna 'Ticker' não detectada automaticamente. Selecione abaixo:")
    col_ticker = st.selectbox("Coluna com os tickers/ativos:", colunas_disponiveis)

if not col_qtd:
    st.warning("⚠️ Coluna 'Quantidade' não detectada. Selecione abaixo:")
    col_qtd = st.selectbox("Coluna com as quantidades:", colunas_disponiveis)

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

    # Classe e País
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

    rows.append({
        "Ticker":               ticker,
        "Nome":                 nome,
        "Classe":               classe,
        "País":                 pais,
        "Setor":                setor,
        "Qtd":                  qtd,
        "Preço Atual (USD)":    preco_usd_atual,
        "Var. Dia (%)":         variacao_pct,
        "Preço Médio (USD)":    preco_medio_usd,
        "Valor Atual (USD)":    valor_atual_usd,
        "Custo Total (USD)":    custo_total_usd,
        "L/P (USD)":            lucro_prejuizo,
        "L/P (%)":              lucro_pct,
        "Div. Yield (%)":       (div_yield * 100) if div_yield else None,
        "Div. Anual Pos (USD)": div_pos_anual,
    })

df = pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────────────────
#  MÉTRICAS GERAIS
# ─────────────────────────────────────────────────────────────────────────────
patrimonio_total = df["Valor Atual (USD)"].dropna().sum()
custo_total      = df["Custo Total (USD)"].dropna().sum()
lucro_total      = patrimonio_total - custo_total if custo_total > 0 else None
div_anual_total  = df["Div. Anual Pos (USD)"].dropna().sum()
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

# ─── TABS ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Carteira", "🥧 Alocação", "💸 Dividendos", "📈 Projeção", "🔍 Detalhes"
])

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 1 — CARTEIRA
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### 📋 Posições Atuais")

    def color_lp(val):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return ""
        return "color: green" if val >= 0 else "color: red"

    df_display = df.copy()
    for col in ["Preço Atual (USD)", "Preço Médio (USD)", "Valor Atual (USD)",
                "Custo Total (USD)", "L/P (USD)", "Div. Anual Pos (USD)"]:
        df_display[col] = df_display[col].apply(formatar_usd)
    for col in ["Var. Dia (%)", "L/P (%)", "Div. Yield (%)"]:
        df_display[col] = df_display[col].apply(formatar_pct)
    df_display["Qtd"] = df_display["Qtd"].apply(
        lambda x: f"{x:,.0f}" if x and not np.isnan(x) else "—"
    )

    st.dataframe(df_display, use_container_width=True)

    # Top gainers / losers
    df_lp = df[df["L/P (%)"].notna()].copy()
    if not df_lp.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🏆 Top Gainers")
            top_g = df_lp.nlargest(5, "L/P (%)")
            fig = px.bar(
                top_g, x="Ticker", y="L/P (%)",
                color="L/P (%)", color_continuous_scale="Greens",
                title="Top 5 Maiores Ganhos (%)",
            )
            fig.update_layout(**LAYOUT_BASE)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.markdown("#### 📉 Top Losers")
            top_l = df_lp.nsmallest(5, "L/P (%)")
            fig = px.bar(
                top_l, x="Ticker", y="L/P (%)",
                color="L/P (%)", color_continuous_scale="Reds_r",
                title="Top 5 Maiores Perdas (%)",
            )
            fig.update_layout(**LAYOUT_BASE)
            st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 2 — ALOCAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("### 🥧 Alocação da Carteira")

    df_val = df[df["Valor Atual (USD)"].notna() & (df["Valor Atual (USD)"] > 0)].copy()

    if df_val.empty:
        st.info("Sem dados de valor para exibir alocação.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            # Por Classe
            if col_classe:
                df_classe = df_val.groupby("Classe")["Valor Atual (USD)"].sum().reset_index()
                fig = px.pie(
                    df_classe, values="Valor Atual (USD)", names="Classe",
                    title="Alocação por Classe de Ativo",
                    hole=0.4,
                )
                fig.update_layout(**LAYOUT_BASE)
                st.plotly_chart(fig, use_container_width=True)

        with col_b:
            # Por País
            if col_pais:
                df_pais = df_val.groupby("País")["Valor Atual (USD)"].sum().reset_index()
                fig = px.pie(
                    df_pais, values="Valor Atual (USD)", names="País",
                    title="Alocação por País",
                    hole=0.4,
                )
                fig.update_layout(**LAYOUT_BASE)
                st.plotly_chart(fig, use_container_width=True)

        # Por Ativo (Top 15)
        top15 = df_val.nlargest(15, "Valor Atual (USD)")
        fig = px.bar(
            top15, x="Ticker", y="Valor Atual (USD)",
            title="Top 15 Ativos por Valor (USD)",
            color="Valor Atual (USD)", color_continuous_scale="Blues",
        )
        fig.update_layout(**layout_eixos("Ativo", "Valor (USD)"))
        st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB 3 — DIVIDENDOS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 💸 Renda de Dividendos")

    df_div = df[df["Div. Anual Pos (USD)"].notna() & (df["Div. Anual Pos (USD)"] > 0)].copy()

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

        # Gráfico de barras dividendos por ativo
        fig = px.bar(
            df_div.sort_values("Div. Anual Pos (USD)", ascending=False),
            x="Ticker", y="Div. Anual Pos (USD)",
            title="Renda Anual de Dividendos por Ativo (USD)",
            color="Div. Anual Pos (USD)", color_continuous_scale="Greens",
        )
        fig.update_layout(**layout_eixos("Ativo", "Dividendo Anual (USD)"))
        st.plotly_chart(fig, use_container_width=True)

        # Gauge meta
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
        # Linha da meta de patrimônio
        meta_patrim = meta_mensal_usd / 0.004
        fig.add_hline(
            y=meta_patrim,
            line_dash="dash", line_color="red",
            annotation_text=f"Meta patrimônio: ${meta_patrim:,.0f}",
        )
        fig.update_layout(**layout_eixos("Ano", "Patrimônio (USD)"))
        st.plotly_chart(fig, use_container_width=True)

        # Renda mensal estimada
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

        # Resumo da projeção
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

    ticker_sel = st.selectbox("Selecione um ativo:", sorted(df["Ticker"].unique()))

    if ticker_sel:
        row_sel = df[df["Ticker"] == ticker_sel].iloc[0]
        info_sel = cotacoes.get(ticker_sel, {}).get("info", {})

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Preço Atual", formatar_usd(row_sel["Preço Atual (USD)"]))
            st.metric("Variação Dia", formatar_pct(row_sel["Var. Dia (%)"]))
        with col_b:
            st.metric("Valor na Carteira", formatar_usd(row_sel["Valor Atual (USD)"]))
            st.metric("Custo Total", formatar_usd(row_sel["Custo Total (USD)"]))
        with col_c:
            st.metric("L/P (USD)", formatar_usd(row_sel["L/P (USD)"]))
            st.metric("L/P (%)", formatar_pct(row_sel["L/P (%)"]))

        st.markdown("---")
        col_d, col_e = st.columns(2)
        with col_d:
            st.markdown(f"**Nome:** {row_sel['Nome']}")
            st.markdown(f"**Classe:** {row_sel['Classe']}")
            st.markdown(f"**País:** {row_sel['País']}")
            st.markdown(f"**Setor:** {row_sel['Setor']}")
        with col_e:
            st.markdown(f"**Quantidade:** {row_sel['Qtd']}")
            st.markdown(f"**Dividend Yield:** {formatar_pct(row_sel['Div. Yield (%)'])}")
            st.markdown(f"**Div. Anual (posição):** {formatar_usd(row_sel['Div. Anual Pos (USD)'])}")

        # Histórico de preços
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