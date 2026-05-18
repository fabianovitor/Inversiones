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
                taxa = rates.get(moeda_mercado, get_exchange_rate(moeda_mercado))
                preco_usd = float(preco_raw) * taxa
        variacao_dia = 0.0
        if preco_raw and len(hist) >= 2:
            preco_ant = float(hist["Close"].iloc[-2])
            preco_hj  = float(hist["Close"].iloc[-1])
            if preco_ant > 0:
                variacao_dia = (preco_hj - preco_ant) / preco_ant * 100
        dy_raw = info.get("dividendYield", 0)
        dy_anual = dy_raw * 100 if dy_raw else None
        return {
            "ticker": ticker,
            "nome": info.get("longName", ticker),
            "setor": info.get("sector", info.get("category", "—")),
            "preco_usd": preco_usd,
            "preco_raw": preco_raw,
            "moeda_mercado": moeda_mercado,
            "dy_anual": dy_anual,
            "variacao_dia": round(variacao_dia, 2),
            "beta": info.get("beta", None),
            "p_vp": info.get("priceToBook", None),
            "market_cap": info.get("marketCap", None),
        }
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_price_history(ticker, period="1y"):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        hist.index = pd.to_datetime(hist.index)
        return hist[["Close", "Volume"]].reset_index()
    except Exception:
        return pd.DataFrame()


def safe_isna(val):
    if val is None:
        return True
    try:
        if isinstance(val, float) and (val != val):
            return True
    except Exception:
        pass
    try:
        result = pd.isna(val)
        if hasattr(result, '__iter__'):
            return False
        return bool(result)
    except Exception:
        pass
    return False


def to_float(val):
    if val is None:
        return None
    if safe_isna(val):
        return None
    if isinstance(val, (int, float)):
        try:
            f = float(val)
            if f != f:
                return None
            return f
        except Exception:
            return None
    try:
        s = str(val).strip()
        chars_to_remove = [",", "%", "$", "€", "£", "kr", "R$", "\xa0", "\u202f", " ", "\t"]
        for char in chars_to_remove:
            s = s.replace(char, "")
        s = s.replace("(", "-").replace(")", "")
        if s in ("", "-", "nan", "NaN", "None", "N/A", "#N/A", "#VALUE!", "#REF!", "n/a", "null", "NULL"):
            return None
        if s.count(".") > 1:
            parts = s.split(".")
            s = "".join(parts[:-1]) + "." + parts[-1]
        result = float(s)
        if result != result:
            return None
        return result
    except Exception:
        return None


def is_valid_number(val):
    if val is None:
        return False
    if safe_isna(val):
        return False
    if isinstance(val, str):
        return False
    try:
        f = float(val)
        return f == f
    except Exception:
        return False


def is_valid_ticker(val):
    if val is None:
        return False
    if safe_isna(val):
        return False
    s = str(val).strip()
    invalid = {
        "", "nan", "NaN", "None", "N/A", "#N/A", "#VALUE!", "#REF!",
        "Ticker", "ticker", "TICKER", "Total", "total", "TOTAL",
        "Totals", "totals", "Subtotal", "subtotal"
    }
    if s in invalid:
        return False
    if len(s) > 15:
        return False
    if not any(c.isalpha() for c in s):
        return False
    if s.replace(".", "").replace(",", "").isdigit():
        return False
    return True


def find_column(df, candidates):
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate is None:
            continue
        if safe_isna(candidate):
            continue
        candidate_str = str(candidate)
        if candidate_str in df.columns:
            return candidate_str
        if candidate_str.lower().strip() in cols_lower:
            return cols_lower[candidate_str.lower().strip()]
    return None


def detectar_moeda_ticker(ticker):
    """Detecta a moeda provável baseado no sufixo do ticker"""
    if not ticker:
        return "USD"
    t = str(ticker).upper().strip()
    if t.endswith(".ST") or t.endswith(".SE"):
        return "SEK"
    if t.endswith(".L") or t.endswith(".LON"):
        return "GBP"
    if t.endswith(".PA") or t.endswith(".DE") or t.endswith(".MI") or t.endswith(".AS") or t.endswith(".MC"):
        return "EUR"
    if t.endswith(".SA") or t.endswith(".BR"):
        return "BRL"
    if t.endswith(".TO") or t.endswith(".V"):
        return "CAD"
    if t.endswith(".SW"):
        return "CHF"
    if t.endswith(".T"):
        return "JPY"
    if t.endswith(".OL"):
        return "NOK"
    if t.endswith(".CO"):
        return "DKK"
    return "USD"


def process_dataframe(df: pd.DataFrame, rates: dict = None):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    if rates is None:
        rates = {"USD": 1.0}

    col_ticker   = find_column(df, ["Ticker", "ticker", "TICKER", "Symbol", "symbol", "Ativo"])
    col_categoria = find_column(df, ["Categoría", "Categoria", "Category", "Tipo", "Type", "categoria"])
    col_qtd      = find_column(df, ["Cantidad", "Quantidade", "Quantity", "Qtd", "Qty", "cantidad"])
    col_pm       = find_column(df, ["Precio Medio", "Preço Médio", "Average Price", "Avg Price", "Preco Medio", "precio medio"])
    col_div      = find_column(df, ["Dividendos TTM", "Dividendos", "Dividends TTM", "Dividends", "Div TTM", "dividendos ttm", "dividendos"])
    col_yoc      = find_column(df, ["Yield on Cost", "YoC", "Yield Cost", "YOC", "yield on cost"])
    col_pa       = find_column(df, ["Precio Actual", "Preço Atual", "Current Price", "Price", "precio actual"])
    col_vt       = find_column(df, ["Valor Total", "Total Value", "Value", "Total", "valor total"])

    if col_ticker and col_ticker in df.columns:
        mask = df[col_ticker].apply(is_valid_ticker)
        df = df[mask].reset_index(drop=True)

    if len(df) == 0:
        return df, {}

    mapa = {
        "ticker": col_ticker,
        "categoria": col_categoria,
        "quantidade": col_qtd,
        "preco_medio": col_pm,
        "dividendos": col_div,
        "yield_cost": col_yoc,
        "preco_atual": col_pa,
        "valor_total": col_vt,
    }

    def get_num_series(col):
        if col and col in df.columns:
            result = []
            for v in df[col]:
                try:
                    result.append(to_float(v))
                except Exception:
                    result.append(None)
            return pd.Series(result, dtype=object)
        return pd.Series([None] * len