# appjubilacion.py
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
import json

st.set_page_config(
    page_title="Dashboard — Aposentadoria",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────────
META_MENSAL_USD_PADRAO = 2300.0
SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"

COLUNAS_AGREGADAS_IGNORAR = [
    "porcentagem", "porcentaje", "percent", "percentage", "%",
    "dy medio", "dy_medio", "yield medio",
    "total", "total con ecn", "total com ecn", "total ecn",
]

TICKERS_ERICSSON_PADRAO = ["ERIC", "ERIC-B.ST", "ERICB.ST", "ERIC-A.ST", "ERICA.ST"]

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
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


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
                preco_usd = float(preco_raw) * taxa if taxa else float(preco_raw)

        variacao_pct = None
        if hist is not None and len(hist) >= 2:
            try:
                preco_ontem = float(hist["Close"].iloc[-2])
                preco_hoje = float(hist["Close"].iloc[-1])
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
            "ticker": ticker, "nome": nome, "preco_usd": preco_usd,
            "moeda_mercado": moeda_mercado, "variacao_pct": variacao_pct,
            "div_yield": div_yield, "div_anual_usd": div_anual_usd, "info": info,
        }
    except Exception as e:
        return {
            "ticker": ticker, "nome": ticker, "preco_usd": None,
            "moeda_mercado": "USD", "variacao_pct": None,
            "div_yield": None, "div_anual_usd": None, "info": {}, "erro": str(e),
        }


def normalizar_str(s):
    s = str(s).strip().lower()
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def parse_sheet(content):
    try:
        df = pd.read_csv(StringIO(content))
        orig_cols = {normalizar_str(c): str(c).strip() for c in df.columns}
        df.columns = [normalizar_str(c) for c in df.columns]
        df = df.dropna(how="all")
        return df, None, orig_cols
    except Exception as e:
        return pd.DataFrame(), str(e), {}


def encontrar_coluna(df_cols_norm, candidatos):
    cols_set = set(df_cols_norm)
    for cand in candidatos:
        cand_norm = normalizar_str(cand)
        if cand_norm in cols_set:
            return cand_norm
    return None


def safe_float(valor):
    if valor is None:
        return None
    try:
        f = float(valor)
        if np.isnan(f):
            return None
        return f
    except Exception:
        return None


def formatar_usd(valor):
    v = safe_float(valor)
    return "—" if v is None else f"${v:,.2f}"


def formatar_pct(valor):
    v = safe_float(valor)
    if v is None:
        return "—"
    sinal = "+" if v > 0 else ""
    return f"{sinal}{v:.2f}%"


def is_ericsson(ticker, lista_ericsson):
    if not ticker:
        return False
    tk_norm = str(ticker).strip().upper()
    return tk_norm in [t.strip().upper() for t in lista_ericsson]


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
    while saldo < meta_patrimonio and meses < 600:
        saldo = saldo * (1 + taxa_mensal) + aporte_mensal
        meses += 1
    return None if meses >= 600 else meses / 12


# ─────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Painel de Controle")
    st.markdown("### 🎯 Meus Objetivos")
    meta_mensal_usd = st.number_input(
        "Meta de renda mensal (USD)", min_value=100.0, max_value=50000.0,
        value=META_MENSAL_USD_PADRAO, step=100.0
    )
    aporte_mensal = st.number_input(
        "Aporte mensal estimado (USD)", min_value=0.0, max_value=20000.0,
        value=1500.0, step=100.0
    )
    taxa_retorno = st.slider("Taxa de retorno anual esperada (%)", 3.0, 15.0, 7.0, 0.5) / 100

    st.markdown("---")
    st.markdown("### 🏢 Ericsson (Carteira Paralela)")
    st.caption("Ações compradas via plano da empresa, fora dos 100% da carteira principal.")
    tickers_eric_str = st.text_area(
        "Tickers Ericsson (um por linha)",
        value="\n".join(TICKERS_ERICSSON_PADRAO),
        height=100,
    )
    tickers_ericsson = [t.strip() for t in tickers_eric_str.split("\n") if t.strip()]
    limite_rebal_pct = st.slider(
        "Limite p/ alerta de rebalanceamento (%)", 5.0, 50.0, 25.0, 1.0
    )

    st.markdown("---")
    st.markdown("### 📋 Planilha")
    spreadsheet_id_input = st.text_input("ID da planilha", value=SPREADSHEET_ID)
    gid_input = st.text_input("GID da aba", value=GID_PADRAO)

    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    debug_mode = st.checkbox("🔧 Modo debug", value=False)


# ─────────────────────────────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────────────────────────────
st.title("📊 Dashboard de Aposentadoria")
st.