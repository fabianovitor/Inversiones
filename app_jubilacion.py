# ============================================================
# DASHBOARD DE APOSENTADORIA - VERSÃO FINAL
# ============================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import StringIO
import yfinance as yf
from datetime import datetime
import numpy as np
import unicodedata

st.set_page_config(page_title="Dashboard Aposentadoria", layout="wide")

SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"
TICKER_ERICSSON = "ERIC-B.ST"

MAPEAMENTO_TICKERS = {
    "ERICB": "ERIC-B.ST",
    "ERIC-B": "ERIC-B.ST",
    "ERICSSON": "ERIC-B.ST",
    "STO:ERIC-B": "ERIC-B.ST",
}

COLS_IGNORAR = ["porcentagem", "porcentaje", "percent", "%", "dy medio", "total", "total con ecn", "total com ecn"]


def norm(s):
    s = str(s).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def limpar_ticker(ticker_str):
    t = str(ticker_str).strip().upper()
    if t in MAPEAMENTO_TICKERS:
        return MAPEAMENTO_TICKERS[t]
    prefixos = ["NYSEARCA:", "NASDAQ:", "NYSE:", "OTCMKTS:", "BATS:", "AMEX:"]
    for prefixo in prefixos:
        if t.startswith(prefixo):
            return t.replace(prefixo, "")
    if t.startswith("STO:"):
        return t.replace("STO:", "") + ".ST"
    return t


def safe_float(v):
    if v is None or pd.isna(v):
        return None
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except Exception:
        return None


def parse_num(v):
    if pd.isna(v):
        return None
    s = str(v).strip().replace("$", "").replace(" ", "").replace("US", "")
    if not s or s in ("-", "—", "nan", "None"):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def fmt_usd(v):
    v = safe_float(v)
    return "-" if v is None else f"${v:,.2f}"


def fmt_pct(v):
    v = safe_float(v)
    if v is None:
        return "-"
    return f"{'+' if v > 0 else ''}{v:.2f}%"


@st.cache_data(ttl=300)
def load_sheet(sid, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        if r.text.strip().startswith("<"):
            return None, "Planilha nao publica"
        df = pd.read_csv(StringIO(r.text))
        df.columns = [norm(c) for c in df.columns]
        df = df.dropna(how="all")
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=300)
def get_rate(moeda):
    if moeda == "USD":
        return 1.0
    try:
        h = yf.Ticker(f"{moeda}USD=X").history(period="1d")
        if not h.empty:
            return float(h["Close"].iloc[-1])
    except Exception:
        pass
    return 1.0


@st.cache_data(ttl=300)
def get_ticker(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period="5d")
        moeda = (info.get("currency") or "USD").upper()
        rate = get_rate(moeda)
        preco_raw = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        if not preco_raw and hist is not None and not hist.empty:
            preco_raw = float(hist["Close"].iloc[-1])
        preco_usd = float(preco_raw) * rate if preco_raw else None
        var_pct = None
        if hist is not None and len(hist) >= 2:
            try:
                ontem = float(hist["Close"].iloc[-2])
                hoje = float(hist["Close"].iloc[-1])
                if ontem > 0:
                    var_pct = ((hoje - ontem) / ontem) * 100
            except Exception:
                pass
        dy = info.get("dividendYield")
        if dy and dy > 1:
            dy = dy / 100
        div_rate = info.get("dividendRate")
        div_anual_usd = None
        if div_rate:
            div_anual_usd = float(div_rate) * rate
        elif dy and preco_usd:
            div_anual_usd = preco_usd * dy
        return {
            "ticker": ticker,
            "nome": info.get("shortName") or info.get("longName") or ticker,
            "preco_usd": preco_usd,
            "moeda": moeda,
            "var_pct": var_pct,
            "div_yield": dy,
            "div_anual_usd": div_anual_usd,
        }
    except Exception:
        return {"ticker": ticker, "nome": ticker, "preco_usd": None, "moeda": "USD", "var_pct": None, "div_yield": None, "div_anual_usd": None}


def encontrar_col(cols, candidatos):
    cs = set(cols)
    for c in candidatos:
        if norm(c) in cs:
            return norm(c)
    return None


# CONTINUA NA PARTE 2
# SIDEBAR
with st.sidebar:
    st.title("Painel")
    meta_mensal = st.number_input("Meta renda mensal (USD)", 100.0, 50000.0, 2300.0, 100.0)
    aporte_mensal = st.number_input("Aporte mensal (USD)", 0.0, 20000.0, 1500.0, 100.0)
    taxa_retorno = st.slider("Retorno anual (%)", 3.0, 15.0, 7.0, 0.5) / 100
    st.markdown("---")
    st.caption(f"Ericsson ({TICKER_ERICSSON}) tratada como carteira paralela.")
    st.markdown("---")
    sid = st.text_input("ID planilha", SPREADSHEET_ID)
    gid = st.text_input("GID", GID_PADRAO)
    if st.button("Atualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    debug = st.checkbox("Debug", False)

st.title("Dashboard de Aposentadoria")
st.caption(f"Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

df, erro = load_sheet(sid, gid)
if erro or df is None or df.empty:
    st.error(f"Erro ao carregar planilha: {erro}")
    st.stop()

col_ticker = encontrar_col(df.columns, ["ticker", "tickers", "ticket", "simbolo", "ativo"])
col_qtd = encontrar_col(df.columns, ["quantidade", "qtd", "qty", "shares", "acoes", "cantidad", "cant", "cant."])
col_pm = encontrar_col(df.columns, ["preco medio", "precio medio", "avg price", "custo medio", "preco medio usd", "precio medio usd", "pm", "pm usd", "pcio compra", "pcio. compra", "precio compra"])

if debug:
    st.error("馃攳 MODO DEBUG ATIVO - role para baixo para ver os bot玫es de download")
    st.subheader("DEBUG - Informacoes detectadas")
    st.write(f"**Coluna ticker:** `{col_ticker}` | **Quantidade:** `{col_qtd}` | **PM:** `{col_pm}`")
    st.write("**Todas as colunas:**", list(df.columns))
    st.dataframe(df.head(20))
    csv_planilha = df.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV da planilha (debug)", csv_planilha, "planilha_debug.csv", "text/csv")

if not col_ticker:
    st.error("Coluna de ticker nao encontrada. Ative o Debug.")
    st.stop()

df_ok = df[df[col_ticker].notna()].copy()
df_ok = df_ok[~df_ok[col_ticker].astype(str).str.lower().str.strip().isin(COLS_IGNORAR)]
df_ok[col_ticker] = df_ok[col_ticker].astype(str).str.strip()
df_ok = df_ok[df_ok[col_ticker] != ""]

if df_ok.empty:
    st.warning("Nenhum ativo encontrado.")
    st.stop()

ativos = []
with st.spinner("Buscando cotacoes no Yahoo Finance..."):
    for _, row in df_ok.iterrows():
        ticker_original = str(row[col_ticker]).strip().upper()
        ticker = limpar_ticker(ticker_original)
        info = get_ticker(ticker)
        qtd = parse_num(row[col_qtd]) if col_qtd else None
        pm = parse_num(row[col_pm]) if col_pm else None
        valor = (qtd * info["preco_usd"]) if (qtd and info["preco_usd"]) else None
        custo = (qtd * pm) if (qtd and pm) else None
        lucro = (valor - custo) if (valor is not None and custo is not None) else None
        lucro_pct = ((lucro / custo) * 100) if (lucro is not None and custo) else None
        renda = (qtd * info["div_anual_usd"] / 12) if (qtd and info["div_anual_usd"]) else None
        ativos.append({
            "ticker": ticker, "nome": info["nome"], "moeda": info["moeda"],
            "qtd": qtd, "pm_usd": pm, "preco_usd": info["preco_usd"],
            "var_pct": info["var_pct"], "valor_atual": valor,
            "custo_total": custo, "lucro": lucro, "lucro_pct": lucro_pct,
            "div_yield": info["div_yield"], "renda_mensal": renda,
            "ericsson": ticker.upper() == TICKER_ERICSSON.upper() or "ERIC" in ticker_original,
        })

dfa = pd.DataFrame(ativos)

if debug:
    st.warning("猬囷笍 BOT脮ES DE DOWNLOAD DEBUG ABAIXO 猬囷笍")
    st.subheader("DEBUG - Dados completos buscados")
    st.dataframe(dfa)
    csv_debug = dfa.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV dos dados (debug)", csv_debug, "dados_debug.csv", "text/csv")

df_principal = dfa[~dfa["ericsson"]].copy()
df_eric = dfa[dfa["ericsson"]].copy()

patrimonio = df_principal["valor_atual"].sum(skipna=True) or 0
custo_tot = df_principal["custo_total"].sum(skipna=True) or 0
lucro_tot = patrimonio - custo_tot if (patrimonio and custo_tot) else 0
renda_tot = df_principal["renda_mensal"].sum(skipna=True) or 0
patr_eric = df_eric["valor_atual"].sum(skipna=True) or 0
renda_eric = df_eric["renda_mensal"].sum(skipna=True) or 0

# METRICAS
c1, c2, c3, c4 = st.columns(4)
c1.metric("Patrimonio Principal", fmt_usd(patrimonio),
          fmt_pct((lucro_tot / custo_tot * 100) if custo_tot else None))
c2.metric("Renda Mensal Est.", fmt_usd(renda_tot),
          f"{(renda_tot / meta_mensal * 100):.1f}% da meta" if meta_mensal else "-")
c3.metric("Ericsson (Paralela)", fmt_usd(patr_eric),
          f"+{fmt_usd(renda_eric)}/mes" if renda_eric else "-")
c4.metric("Meta Mensal", fmt_usd(meta_mensal),
          f"Faltam {fmt_usd(meta_mensal - renda_tot)}" if meta_mensal > renda_tot else "Atingida!")

st.markdown("---")

# CARTEIRA PRINCIPAL
st.subheader("Carteira Principal")
if not df_principal.empty:
    df_show = df_principal[["ticker", "nome", "moeda", "qtd", "pm_usd", "preco_usd",
                             "var_pct", "valor_atual", "custo_total", "lucro", "lucro_pct",
                             "div_yield", "renda_mensal"]].copy()
    df_show.columns = ["Ticker", "Nome", "Moeda", "Qtd", "PM (USD)", "Preco (USD)",
                       "Var %", "Valor (USD)", "Custo (USD)", "Lucro (USD)", "Lucro %",
                       "DY", "Renda Mes"]
    df_show["Qtd"] = df_show["Qtd"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-")
    df_show["PM (USD)"] = df_show["PM (USD)"].apply(fmt_usd)
    df_show["Preco (USD)"] = df_show["Preco (USD)"].apply(fmt_usd)
    df_show["Var %"] = df_show["Var %"].apply(fmt_pct)
    df_show["Valor (USD)"] = df_show["Valor (USD)"].apply(fmt_usd)
    df_show["Custo (USD)"] = df_show["Custo (USD)"].apply(fmt_usd)
    df_show["Lucro (USD)"] = df_show["Lucro (USD)"].apply(fmt_usd)
    df_show["Lucro %"] = df_show["Lucro %"].apply(fmt_pct)
    df_show["DY"] = df_show["DY"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) and x else "-")
    df_show["Renda Mes"] = df_show["Renda Mes"].apply(fmt_usd)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    df_pie = df_principal[df_principal["valor_atual"].notna() & (df_principal["valor_atual"] > 0)].copy()
    if not df_pie.empty:
        fig = px.pie(df_pie, values="valor_atual", names="ticker",
                     title="Distribuicao da Carteira Principal", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

# ERICSSON
if not df_eric.empty:
    st.markdown("---")
    st.subheader("Ericsson (Carteira Paralela)")
    st.caption(f"Total: {fmt_usd(patr_eric)} | Renda mensal estimada: {fmt_usd(renda_eric)}")
    df_e = df_eric[["ticker", "nome", "moeda", "qtd", "pm_usd", "preco_usd",
                     "valor_atual", "custo_total", "lucro", "lucro_pct",
                     "div_yield", "renda_mensal"]].copy()
    df_e.columns = ["Ticker", "Nome", "Moeda", "Qtd", "PM (USD)", "Preco (USD)",
                    "Valor (USD)", "Custo (USD)", "Lucro (USD)", "Lucro %",
                    "DY", "Renda Mes"]
    df_e["Qtd"] = df_e["Qtd"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-")
    df_e["PM (USD)"] = df_e["PM (USD)"].apply(fmt_usd)
    df_e["Preco (USD)"] = df_e["Preco (USD)"].apply(fmt_usd)
    df_e["Valor (USD)"] = df_e["Valor (USD)"].apply(fmt_usd)
    df_e["Custo (USD)"] = df_e["Custo (USD)"].apply(fmt_usd)
    df_e["Lucro (USD)"] = df_e["Lucro (USD)"].apply(fmt_usd)
    df_e["Lucro %"] = df_e["Lucro %"].apply(fmt_pct)
    df_e["DY"] = df_e["DY"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) and x else "-")
    df_e["Renda Mes"] = df_e["Renda Mes"].apply(fmt_usd)
    st.dataframe(df_e, use_container_width=True, hide_index=True)

# PROJECAO
st.markdown("---")
st.subheader("Projecao Patrimonial")
anos_proj = st.slider("Anos de projecao", 5, 40, 20)
taxa_mensal = (1 + taxa_retorno) ** (1/12) - 1
saldo = float(patrimonio)
proj = []
for m in range(1, anos_proj * 12 + 1):
    saldo = saldo * (1 + taxa_mensal) + aporte_mensal
    if m % 12 == 0:
        proj.append({
            "Ano": datetime.now().year + m // 12,
            "Patrimonio (USD)": saldo,
            "Renda Mensal Est. (USD)": saldo * 0.004,
        })
df_proj = pd.DataFrame(proj)
if not df_proj.empty:
    fig2 = px.line(df_proj, x="Ano", y="Patrimonio (USD)",
                   title=f"Projecao (retorno {taxa_retorno*100:.1f}% a.a., aporte {fmt_usd(aporte_mensal)}/mes)",
                   markers=True)
    st.plotly_chart(fig2, use_container_width=True)

    df_proj_show = df_proj.copy()
    df_proj_show["Patrimonio (USD)"] = df_proj_show["Patrimonio (USD)"].apply(fmt_usd)
    df_proj_show["Renda Mensal Est. (USD)"] = df_proj_show["Renda Mensal Est. (USD)"].apply(fmt_usd)
    st.dataframe(df_proj_show, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Dashboard de Aposentadoria | Dados: Yahoo Finance + Google Sheets")