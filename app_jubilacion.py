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
import json
import io

st.set_page_config(
    page_title="Dashboard — Aposentadoria",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
META_MENSAL_USD_PADRAO = 2300.0
SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"

# Colunas agregadas/resumo da planilha que NÃO devem aparecer como coluna por ativo
COLUNAS_AGREGADAS_IGNORAR = [
    "porcentagem", "porcentaje", "percent", "percentage", "%",
    "dy medio", "dy_medio", "yield medio",
    "total", "total con ecn", "total com ecn", "total ecn",
]

# Tickers padrão tratados como "Ericsson" (carteira paralela)
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
    if v is None:
        return "—"
    return f"${v:,.2f}"


def formatar_pct(valor):
    v = safe_float(valor)
    if v is None:
        return "—"
    sinal = "+" if v > 0 else ""
    return f"{sinal}{v:.2f}%"


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


def is_ericsson(ticker, lista_ericsson):
    """Verifica se um ticker é da Ericsson."""
    if not ticker:
        return False
    tk_norm = str(ticker).strip().upper()
    return tk_norm in [t.strip().upper() for t in lista_ericsson]


# ─────────────────────────────────────────────────────────────────────────────
#  🔧 DEBUG — utilitários
# ─────────────────────────────────────────────────────────────────────────────
def gerar_relatorio_debug(debug_data):
    linhas = []
    linhas.append("=" * 80)
    linhas.append("RELATÓRIO DE DEBUG — DASHBOARD APOSENTADORIA")
    linhas.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    linhas.append("=" * 80)

    for secao, conteudo in debug_data.items():
        linhas.append("")
        linhas.append("─" * 80)
        linhas.append(f"▶ {secao}")
        linhas.append("─" * 80)
        if isinstance(conteudo, (dict, list)):
            try:
                linhas.append(json.dumps(conteudo, indent=2, ensure_ascii=False, default=str))
            except Exception:
                linhas.append(str(conteudo))
        else:
            linhas.append(str(conteudo))

    txt = "\n".join(linhas)

    try:
        js = json.dumps(debug_data, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        js = json.dumps({"erro_serializacao": str(e)}, indent=2, ensure_ascii=False)

    return txt, js


def df_para_dict_seguro(df, max_linhas=500):
    if df is None or df.empty:
        return []
    df_copy = df.head(max_linhas).