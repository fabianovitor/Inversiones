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

st.markdown("""
    <style>
        [data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: bold; }
        [data-testid="stMetricDelta"] { font-size: 0.85rem; }
        .block-container { padding-top: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

META_MENSAL_USD_PADRAO = 2300.0
SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"

COLUMN_MAP = {
    "ticker":      "Ticker",
    "nome":        "Empresa",
    "categoria":   "Categoría",
    "quantidade":  "Cantidad",
    "preco_medio": "Precio Medio",
    "dividendos":  "Dividendos TTM",
    "yield_cost":  "Yield on Cost",
    "preco_atual": "Precio Actual",
    "valor_total": "Valor Total",
    "pct_atual":   "% Actual",
    "diferenca":   "Diferencia",
    "acao":        "Acción",
}


def build_csv_url(spreadsheet_id: str, gid: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )


@st.cache_data(ttl=300)
def load_sheet_raw(spreadsheet_id: str, gid: str) -> tuple:
    url = build_csv_url(spreadsheet_id, gid)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, timeout=15, headers=headers)

        if response.status_code == 403:
            return "", "403_FORBIDDEN", url
        elif response.status_code == 404:
            return "", "404_NOT_FOUND", url
        elif response.status_code != 200:
            return "", f"HTTP_{response.status_code}", url

        content = response.text
        if content.strip().startswith("<!DOCTYPE") or content.strip().startswith("<html"):
            return "", "HTML_RESPONSE", url

        return content, None, url

    except requests.exceptions.Timeout:
        return "", "TIMEOUT", url
    except requests.exceptions.ConnectionError:
        return "", "CONNECTION_ERROR", url
    except Exception as e:
        return "", f"ERROR: {str(e)}", url


@st.cache_data(ttl=300)
def get_exchange_rate(from_currency: str, to_currency: str = "USD") -> float:
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
def get_all_rates() -> dict:
    moedas = ["SEK", "EUR", "GBP", "BRL", "CAD", "CHF", "JPY", "NOK", "DKK"]
    rates = {"USD": 1.0}
    for moeda in moedas:
        rates[moeda] = get_exchange_rate(moeda, "USD")
    return rates


@st.cache_data(ttl=300)
def get_ticker_info(ticker: str, rates: dict) -> dict:
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
            preco_hj = float(hist["Close"].iloc[-1])
            if preco_ant > 0:
                variacao_dia = ((preco_hj - preco_ant) / preco_ant * 100)

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
def get_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        hist.index = pd.to_datetime(hist.index)
        return hist[["Close", "Volume"]].reset_index()
    except Exception:
        return pd.DataFrame()


def to_float(val):
    """Converte valor para float, tratando todos os formatos possíveis."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if pd.isna(val):
            return None
        return float(val)
    try:
        s = str(val).strip()
        # Remove caracteres de formatação
        for char in [",", "%", "$", "€", "£", "kr", "R$", "\xa0", "\u202f", " "]:
            s = s.replace(char, "")
        # Trata ponto como separador decimal (mas apenas se não for separador de milhar)
        # Se tem múltiplos pontos, remove os extras
        if s.count(".") > 1:
            parts = s.split(".")
            s = "".join(parts[:-1]) + "." + parts[-1]
        
        if s in ("", "-", "nan", "NaN", "None", "N/A", "#N/A", "#VALUE!", "#REF!", "n/a"):
            return None
        return float(s)
    except Exception:
        return None


def is_valid_number(val):
    if val is None:
        return False
    if isinstance(val, float) and pd.isna(val):
        return False
    return True


def is_valid_ticker(val):
    """Verifica se o valor é um ticker válido."""
    if val is None:
        return False
    s = str(val).strip()
    # Valores claramente inválidos
    invalid = {
        "", "nan", "NaN", "None", "N/A", "#N/A", "#VALUE!", "#REF!",
        "Ticker", "ticker", "TICKER",
        "Total", "total", "TOTAL",
        "Totals", "totals",
        "Subtotal", "subtotal"
    }
    if s in invalid:
        return False
    # Muito longo para ser ticker
    if len(s) > 15:
        return False
    # Deve ter pelo menos uma letra
    if not any(c.isalpha() for c in s):
        return False
    # Não pode ser puramente numérico
    if s.replace(".", "").replace(",", "").isdigit():
        return False
    return True


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    col_ticker = COLUMN_MAP["ticker"]
    col_qtd    = COLUMN_MAP["quantidade"]
    col_pm     = COLUMN_MAP["preco_medio"]
    col_div    = COLUMN_MAP["dividendos"]
    col_yoc    = COLUMN_MAP["yield_cost"]
    col_pa     = COLUMN_MAP["preco_atual"]
    col_vt     = COLUMN_MAP["valor_total"]

    # ── Filtra linhas com ticker válido ──────────────────────────────────────
    if col_ticker in df.columns:
        mask = df[col_ticker].apply(is_valid_ticker)
        df = df[mask].reset_index(drop=True)

    # ── Converte colunas numéricas ───────────────────────────────────────────
    for col in [col_qtd, col_pm, col_div, col_yoc, col_pa, col_vt]:
        if col in df.columns:
            df[col] = df[col].apply(to_float)

    # ── Calcula Patrimônio ───────────────────────────────────────────────────
    if col_vt in df.columns:
        df["Patrimônio (USD)"] = df[col_vt].apply(
            lambda x: x if is_valid_number(x) else None
        )
    elif col_qtd in df.columns and col_pa in df.columns:
        df["Patrimônio (USD)"] = [
            (q * p) if (is_valid_number(q) and is_valid_number(p)) else None
            for q, p in zip(df[col_qtd], df[col_pa])
        ]

    # ── Custo Total ──────────────────────────────────────────────────────────
    if col_qtd in df.columns and col_pm in df.columns:
        df["Custo Total (USD)"] = [
            (q * p) if (is_valid_number(q) and is_valid_number(p)) else None
            for q, p in zip(df[col_qtd], df[col_pm])
        ]

    # ── Lucro / Retorno ──────────────────────────────────────────────────────
    lucros   = []
    retornos = []
    if "Patrimônio (USD)" in df.columns and "Custo Total (USD)" in df.columns:
        for pat, cus in zip(df["Patrimônio (USD)"], df["Custo Total (USD)"]):
            if is_valid_number(pat) and is_valid_number(cus):
                lucros.append(pat - cus)
                retornos.append(round((pat - cus) / cus * 100, 2) if cus > 0 else None)
            else:
                lucros.append(None)
                retornos.append(None)
        df["Lucro/Prejuízo (USD)"] = lucros
        df["Retorno (%)"]          = retornos

    # ── Renda Mensal Estimada ────────────────────────────────────────────────
    if col_div in df.columns:
        df["DY (%)"] = df[col_yoc].apply(to_float) if col_yoc in df.columns else None
        rendas = []
        for div in df[col_div]:
            if is_valid_number(div):
                rendas.append(round(div / 12, 2))
            else:
                rendas.append(None)
        df["Renda Mensal Est. (USD)"] = rendas
    elif "Patrimônio (USD)" in df.columns and col_yoc in df.columns:
        df["DY (%)"] = df[col_yoc]
        rendas = []
        for pat, yoc in zip(df["Patrimônio (USD)"], df[col_yoc]):
            if is_valid_number(pat) and is_valid_number(yoc):
                rendas.append(round(pat * yoc / 100 / 12, 2))
            else:
                rendas.append(None)
        df["Renda Mensal Est. (USD)"] = rendas

    # ── Remove linhas sem patrimônio válido ──────────────────────────────────
    if "Patrimônio (USD)" in df.columns:
        df = df[df["Patrimônio (USD)"].apply(
            lambda x: is_valid_number(x) and x > 0
        )]

    return df.reset_index(drop=True)


def fmt_usd(val):
    try:
        if not is_valid_number(val):
            return ""
        return f"$ {float(val):,.2f}"
    except Exception:
        return str(val) if val is not None else ""


def fmt_pct_sinal(val):
    try:
        if not is_valid_number(val):
            return ""
        v = float(val)
        return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"
    except Exception:
        return str(val) if val is not None else ""


def fmt_pct(val):
    try:
        if not is_valid_number(val):
            return ""
        return f"{float(val):.2f}%"
    except Exception:
        return str(val) if val is not None else ""


def safe_sum(series):
    try:
        vals = [v for v in series if is_valid_number(v)]
        return sum(vals)
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Dashboard — Aposentadoria")
st.sidebar.markdown("---")

st.sidebar.markdown("### 🎯 Configurar Meta de Renda")

META_MENSAL_USD = st.sidebar.number_input(
    "Meta Final (USD/mês)",
    min_value=100.0,
    max_value=50000.0,
    value=META_MENSAL_USD_PADRAO,
    step=100.0,
)

usar_meta_intermediaria = st.sidebar.checkbox("Usar meta intermediária", value=False)

META_INTERMEDIARIA = None
nome_meta_intermediaria = "Meta Intermediária"
if usar_meta_intermediaria:
    META_INTERMEDIARIA = st.sidebar.number_input(
        "Meta Intermediária (USD/mês)",
        min_value=100.0,
        max_value=float(META_MENSAL_USD),
        value=min(500.0, float(META_MENSAL_USD)),
        step=50.0,
    )
    nome_meta_intermediaria = st.sidebar.text_input(
        "Nome da meta intermediária",
        value="Meta Intermediária",
    )

st.sidebar.markdown(f"🎯 **Meta Final:** $ {META_MENSAL_USD:,.2f} / mês")
if META_INTERMEDIARIA:
    st.sidebar.markdown(f"🎯 **{nome_meta_intermediaria}:** $ {META_INTERMEDIARIA:,.2f} / mês")

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    "📡 Dados sincronizados com:\n\n"
    "- Google Sheets (planilha em USD)\n"
    "- Yahoo Finance (cotações ao vivo)\n\n"
    "🔄 Atualização automática a cada **5 minutos**"
)

# ─────────────────────────────────────────────────────────────────────────────
# CABEÇALHO
# ─────────────────────────────────────────────────────────────────────────────
st.title("📊 Dashboard — Carteira de Aposentadoria")
st.markdown(
    f"Acompanhe sua evolução rumo à renda passiva de **${META_MENSAL_USD:,.2f}/mês** "
    "— dados da planilha em USD + cotações ao vivo convertidas automaticamente"
)
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("📡 Sincronizando dados..."):
    rates = get_all_rates()
    csv_text, erro, url_usada = load_sheet_raw(SPREADSHEET_ID, GID_PADRAO)

# ─────────────────────────────────────────────────────────────────────────────
# TRATA ERROS
# ─────────────────────────────────────────────────────────────────────────────
if erro:
    st.error("❌ **Não foi possível carregar a planilha**")

    if erro in ("403_FORBIDDEN", "HTML_RESPONSE"):
        st.warning("""
### 🔒 Problema de acesso à planilha!

**Como resolver:**
1. Abra a planilha no Google Sheets
2. Clique em **"Compartilhar"** (canto superior direito)
3. Em "Acesso geral", selecione **"Qualquer pessoa com o link"**
4. Permissão: **"Visualizador"**
5. Clique em **"Concluído"**
6. Volte aqui e clique em **"🔄 Atualizar Dados Agora"**
        """)
    elif erro == "404_NOT_FOUND":
        st.warning(f"""
### 🔍 Planilha não encontrada!

**ID atual:** `{SPREADSHEET_ID}`
**GID atual:** `{GID_PADRAO}`
        """)
    else:
        st.warning(f"### ⚠️ Erro: `{erro}`\n\nVerifique sua conexão e tente novamente.")

    st.info(f"**URL tentada:** `{url_usada}`")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# PARSE CSV
# ─────────────────────────────────────────────────────────────────────────────
try:
    df_raw = pd.read_csv(StringIO(csv_text))
except Exception as e:
    st.error(f"❌ Erro ao processar o CSV: {e}")
    st.stop()

if df_raw.empty:
    st.error("❌ A planilha parece estar vazia.")
    st.stop()

# Debug compacto — apenas se necessário (oculto por padrão)
with st.expander("🔍 Debug — Clique apenas se houver problema", expanded=False):
    st.write(f"**Colunas encontradas:** {list(df_raw.columns)}")
    st.write(f"**Total de linhas (bruto):** {len(df_raw)}")
    
    col_ticker_debug = COLUMN_MAP["ticker"]
    if col_ticker_debug in df_raw.columns:
        tickers_brutos = df_raw[col_ticker_debug].tolist()
        st.write(f"**Tickers encontrados (bruto):** {tickers_brutos}")
    
    st.write("**Primeiras 5 linhas brutas:**")
    st.dataframe(df_raw.head())

df = process_dataframe(df_raw)

# Aviso silencioso se poucos ativos
col_ticker = COLUMN_MAP["ticker"]
col_cat    = COLUMN_MAP["categoria"]

if len(df) == 0:
    st.error("❌ Nenhum ativo válido encontrado após processamento.")
    with st.expander("🔍 Ver dados brutos para diagnóstico", expanded=True):
        st.dataframe(df_raw)
    st.stop()

usd_brl_ref = rates.get("BRL", 0)
usd_sek_ref = rates.get("SEK", 0)

st.sidebar.success(f"✅ {len(df)} ativos carregados")
if usd_brl_ref > 0:
    st.sidebar.caption(f"💱 USD/BRL: R$ {1/usd_brl_ref:.4f}")
if usd_sek_ref > 0:
    st.sidebar.caption(f"💱 USD/SEK: kr {1/usd_sek_ref:.4f}")
st.sidebar.caption(f"🕐 Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────
patrimonio_total = safe_sum(df["Patrimônio (USD)"]) if "Patrimônio (USD)" in df.columns else 0.0
custo_total      = safe_sum(df["Custo Total (USD)"]) if "Custo Total (USD)" in df.columns else 0.0
lucro_total      = patrimonio_total - custo_total
retorno_pct      = (lucro_total / custo_total * 100) if custo_total > 0 else 0.0
renda_mensal     = safe_sum(df["Renda Mensal Est. (USD)"]) if "Renda Mensal Est. (USD)" in df.columns else 0.0
falta_para_meta  = max(META_MENSAL_USD - renda_mensal, 0)
progresso_meta   = min((renda_mensal / META_MENSAL_USD) * 100, 100) if META_MENSAL_USD > 0 else 0.0
num_ativos       = len(df)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Patrimônio Total",    f"$ {patrimonio_total:,.2f}")
c2.metric("📈 Lucro / Prejuízo",    f"$ {lucro_total:,.2f}",     f"{retorno_pct:+.2f}%")
c3.metric("💵 Renda Mensal Est.",   f"$ {renda_mensal:,.2f}",    f"{progresso_meta:.1f}% da meta")
c4.metric("🎯 Falta para a Meta",   f"$ {falta_para_meta:,.2f}", f"Meta: $ {META_MENSAL_USD:,.2f}/mês")
c5.metric("📊 Ativos na Carteira",  f"{num_ativos}",             "posições ativas")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# PROGRESSO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 🎯 Progresso Rumo às Metas de Renda Passiva")

cor_progresso = "#22c55e" if progresso_meta >= 75 else "#f59e0b" if progresso_meta >= 40 else "#ef4444"
st.markdown(f"**Meta Final: $ {META_MENSAL_USD:,.2f}/mês**")
st.markdown(f"""
<div style="background:#e2e8f0; border-radius:10px; height:28px; margin-bottom:8px;">
  <div style="background:{cor_progresso}; border-radius:10px; height:28px; width:{progresso_meta:.1f}%;
              display:flex; align-items:center; justify-content:center; color:white; font-weight:bold;">
    {progresso_meta:.1f}%
  </div>
</div>
""", unsafe_allow_html=True)

st.caption(
    f"Renda estimada atual: **$ {renda_mensal:,.2f}/mês** | "
    f"Meta Final: **$ {META_MENSAL_USD:,.2f}/mês** | "
    f"Faltam: **$ {falta_para_meta:,.2f}/mês**"
)

if META_INTERMEDIARIA:
    progresso_inter = min((renda_mensal / META_INTERMEDIARIA) * 100, 100) if META_INTERMEDIARIA > 0 else 0.0
    falta_inter     = max(META_INTERMEDIARIA - renda_mensal, 0)
    cor_inter       = "#22c55e" if progresso_inter >= 75 else "#f59e0b" if progresso_inter >= 40 else "#3b82f6"

    st.markdown(f"**{nome_meta_intermediaria}: $ {META_INTERMEDIARIA:,.2f}/mês**")
    st.markdown(f"""
<div style="background:#e2e8f0; border-radius:10px; height:24px; margin-bottom:8px;">
  <div style="background:{cor_inter}; border-radius:10px; height:24px; width:{progresso_inter:.1f}%;
              display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; font-size:0.85rem;">
    {progresso_inter:.1f}%
  </div>
</div>
""", unsafe_allow_html=True)
    st.caption(
        f"Progresso: **$ {renda_mensal:,.2f}/mês** | "
        f"{nome_meta_intermediaria}: **$ {META_INTERMEDIARIA:,.2f}/mês** | "
        f"Faltam: **$ {falta_inter:,.2f}/mês**"
    )

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICOS COMPOSIÇÃO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 📊 Composição da Carteira")
g1, g2 = st.columns(2)

with g1:
    if col_ticker in df.columns and "Patrimônio (USD)" in df.columns:
        df_plot = df[[col_ticker, "Patrimônio (USD)"]].copy()
        df_plot["Patrimônio (USD)"] = pd.to_numeric(df_plot["Patrimônio (USD)"], errors="coerce")
        df_plot = df_plot.dropna()
        if not df_plot.empty:
            fig_pie = px.pie(
                df_plot, names=col_ticker, values="Patrimônio (USD)",
                title="Patrimônio por Ativo (USD)", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

with g2:
    if col_cat in df.columns and "Patrimônio (USD)" in df.columns:
        df_cat = df.copy()
        df_cat["Patrimônio (USD)"] = pd.to_numeric(df_cat["Patrimônio (USD)"], errors="coerce")
        df_cat = df_cat.dropna(subset=["Patrimônio (USD)", col_cat])
        if not df_cat.empty:
            df_setor = df_cat.groupby(col_cat)["Patrimônio (USD)"].sum().reset_index()
            fig_setor = px.pie(
                df_setor, names=col_cat, values="Patrimônio (USD)",
                title="Distribuição por Categoria", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_setor, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# RENDA E PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 💵 Renda Passiva e Performance por Ativo")
g3, g4 = st.columns(2)

with g3:
    if "Renda Mensal Est. (USD)" in df.columns and col_ticker in df.columns:
        df_renda = df[[col_ticker, "Renda Mensal Est. (USD)"]].copy()
        df_renda["Renda Mensal Est. (USD)"] = pd.to_numeric(df_renda["Renda Mensal Est. (USD)"], errors="coerce")
        df_renda = df_renda.dropna().sort_values("Renda Mensal Est. (USD)", ascending=True)

        if not df_renda.empty:
            fig_renda = go.Figure(go.Bar(
                x=df_renda["Renda Mensal Est. (USD)"],
                y=df_renda[col_ticker],
                orientation="h",
                marker_color="#22c55e",
                text=df_renda["Renda Mensal Est. (USD)"].apply(
                    lambda x: f"$ {x:.2f}" if pd.notna(x) else ""
                ),
                textposition="outside"
            ))
            fig_renda.add_vline(
                x=META_MENSAL_USD, line_dash="dash", line_color="red",
                annotation_text=f"Meta Final: $ {META_MENSAL_USD:,.0f}",
                annotation_position="top right"
            )
            if META_INTERMEDIARIA:
                fig_renda.add_vline(
                    x=META_INTERMEDIARIA, line_dash="dot", line_color="#3b82f6",
                    annotation_text=f"{nome_meta_intermediaria}: $ {META_INTERMEDIARIA:,.0f}",
                    annotation_position="bottom right"
                )
            fig_renda.update_layout(
                title="Renda Mensal Estimada por Ativo (USD)",
                xaxis_title="USD / mês", plot_bgcolor="#f8fafc"
            )
            st.plotly_chart(fig_renda, use_container_width=True)

with g4:
    if "Retorno (%)" in df.columns and col_ticker in df.columns:
        df_ret = df[[col_ticker, "Retorno (%)"]].copy()
        df_ret["Retorno (%)"] = pd.to_numeric(df_ret["Retorno (%)"], errors="coerce")
        df_ret = df_ret.dropna().sort_values("Retorno (%)", ascending=False)

        if not df_ret.empty:
            colors = [
                "#22c55e" if v >= 0 else "#ef4444"
                for v in df_ret["Retorno (%)"]
            ]
            fig_ret = go.Figure(go.Bar(
                x=df_ret[col_ticker],
                y=df_ret["Retorno (%)"],
                marker_color=colors,
                text=df_ret["Retorno (%)"].apply(
                    lambda x: fmt_pct_sinal(x) if pd.notna(x) else ""
                ),
                textposition="outside"
            ))
            fig_ret.update_layout(
                title="Retorno por Ativo (%)",
                plot_bgcolor="#f8fafc",
                yaxis=dict(zeroline=True, zerolinecolor="gray")
            )
            st.plotly_chart(fig_ret, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISE POR ATIVO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🔍 Análise Detalhada por Ativo")

if col_ticker in df.columns:
    tickers_disponiveis = df[col_ticker].dropna().unique().tolist()
    ticker_selecionado = st.selectbox("📌 Selecione um ativo para analisar:", tickers_disponiveis)

    if ticker_selecionado:
        linha_ativo = df[df[col_ticker] == ticker_selecionado].iloc[0]

        with st.spinner(f"🌐 Buscando dados de {ticker_selecionado} no mercado..."):
            info_mercado    = get_ticker_info(ticker_selecionado, rates)
            historico_preco = get_price_history(ticker_selecionado, period="1y")

        a1, a2, a3, a4, a5 = st.columns(5)

        preco_mercado_usd = info_mercado.get("preco_usd")
        preco_raw         = info_mercado.get("preco_raw")
        moeda_mercado     = info_mercado.get("moeda_mercado", "USD")

        label_preco = "💲 Preço Atual (USD)"
        valor_preco = f"$ {preco_mercado_usd:,.2f}" if preco_mercado_usd else "N/D"
        delta_preco = (
            f"{preco_raw:,.2f} {moeda_mercado}"
            if moeda_mercado != "USD" and preco_raw
            else None
        )

        a1.metric(label_preco, valor_preco, delta_preco)
        a2.metric(
            "📈 Variação Hoje",
            f"{info_mercado.get('variacao_dia', 0):+.2f}%",
            delta_color="normal"
        )
        a3.metric(
            "💰 DY Anual (Mercado)",
            f"{info_mercado.get('dy_anual', 0):.2f}%" if info_mercado.get("dy_anual") else "N/D"
        )

        pat_ativo  = linha_ativo.get("Patrimônio (USD)", None)
        renda_ativo = linha_ativo.get("Renda Mensal Est. (USD)", None)
        pat_val    = float(pat_ativo)  if is_valid_number(pat_ativo)   else 0.0
        renda_val  = float(renda_ativo) if is_valid_number(renda_ativo) else 0.0

        a4.metric("📊 Patrimônio neste Ativo", f"$ {pat_val:,.2f}")
        a5.metric("💵 Renda Mensal Est.",       f"$ {renda_val:,.2f}")

        if not historico_preco.empty:
            periodo_opcao = st.radio(
                "📅 Período do histórico:",
                ["3 meses", "6 meses", "1 ano"],
                horizontal=True,
                key=f"periodo_{ticker_selecionado}"
            )
            meses_map    = {"3 meses": 90, "6 meses": 180, "1 ano": 365}
            dias         = meses_map[periodo_opcao]
            hist_filtrado = historico_preco.tail(dias)
            label_eixo_y  = f"Preço ({moeda_mercado})"

            fig_hist = px.area(
                hist_filtrado, x="Date", y="Close",
                title=f"Histórico de Preço — {ticker_selecionado} (em {moeda_mercado})",
                labels={"Close": label_eixo_y, "Date": "Data"},
                color_discrete_sequence=["#3b82f6"]
            )
            fig_hist.update_layout(plot_bgcolor="#f8fafc")
            st.plotly_chart(fig_hist, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# SIMULADOR
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🔮 Simulador — Projeção para Atingir a Meta")

sim1, sim2, sim3 = st.columns(3)
with sim1:
    aporte_mensal = st.number_input("💸 Aporte Mensal (USD)", min_value=0.0, value=500.0, step=50.0)
with sim2:
    dy_simulacao  = st.number_input("📊 DY Médio Anual (%)", min_value=0.0, value=6.0, step=0.5)
with sim3:
    anos_simulacao = st.slider("📅 Horizonte (anos)", min_value=1, max_value=40, value=10)

cenarios = {
    "🐢 Conservador": dy_simulacao * 0.75,
    "📊 Base":        dy_simulacao,
    "🚀 Otimista":    dy_simulacao * 1.25,
}

fig_cenarios   = go.Figure()
historico_todos = {}

cores_cenario = {
    "🐢 Conservador": "#f59e0b",
    "📊 Base":        "#3b82f6",
    "🚀 Otimista":    "#22c55e",
}

for nome_cenario, dy_c in cenarios.items():
    patrimonio_sim   = patrimonio_total
    historico_sim    = []
    meses_meta_c     = None
    meses_meta_inter_c = None

    for mes in range(1, anos_simulacao * 12 + 1):
        patrimonio_sim += aporte_mensal
        patrimonio_sim *= (1 + dy_c / 100 / 12)
        renda_proj = patrimonio_sim * dy_c / 100 / 12
        historico_sim.append({
            "Ano":                     round(mes / 12, 2),
            "Renda Mensal Est. (USD)": round(renda_proj, 2),
            "Patrimônio (USD)":        round(patrimonio_sim, 2),
        })
        if meses_meta_c is None and renda_proj >= META_MENSAL_USD:
            meses_meta_c = mes
        if META_INTERMEDIARIA and meses_meta_inter_c is None and renda_proj >= META_INTERMEDIARIA:
            meses_meta_inter_c = mes

    df_sim = pd.DataFrame(historico_sim)
    historico_todos[nome_cenario] = {
        "df":              df_sim,
        "meses_meta":      meses_meta_c,
        "meses_meta_inter": meses_meta_inter_c
    }

    fig_cenarios.add_trace(go.Scatter(
        x=df_sim["Ano"],
        y=df_sim["Renda Mensal Est. (USD)"],
        name=f"{nome_cenario} (DY {dy_c:.1f}%)",
        line=dict(color=cores_cenario[nome_cenario], width=2)
    ))

fig_cenarios.add_hline(
    y=META_MENSAL_USD, line_dash="dash", line_color="red",
    annotation_text=f"Meta Final $ {META_MENSAL_USD:,.0f}/mês"
)
if META_INTERMEDIARIA:
    fig_cenarios.add_hline(
        y=META_INTERMEDIARIA, line_dash="dot", line_color="#3b82f6",
        annotation_text=f"{nome_meta_intermediaria} $ {META_INTERMEDIARIA:,.0f}/mês"
    )

fig_cenarios.update_layout(
    title="🎯 Projeção de Renda Mensal — 3 Cenários (USD)",
    xaxis_title="Anos",
    yaxis_title="Renda Mensal (USD)",
    plot_bgcolor="#f8fafc",
    legend=dict(orientation="h", y=-0.25)
)
st.plotly_chart(fig_cenarios, use_container_width=True)

r1, r2, r3 = st.columns(3)
for col_res, (nome_c, dados_c) in zip([r1, r2, r3], historico_todos.items()):
    meses       = dados_c["meses_meta"]
    meses_inter = dados_c.get("meses_meta_inter")
    resultado_text = f"**{nome_c}**\n\n"

    if META_INTERMEDIARIA and meses_inter:
        anos_i   = meses_inter // 12
        meses_i  = meses_inter % 12
        resultado_text += f"🎯 {nome_meta_intermediaria}: **{anos_i}a {meses_i}m**\n\n"
    elif META_INTERMEDIARIA:
        resultado_text += f"⚠️ {nome_meta_intermediaria}: não atingida\n\n"

    if meses:
        anos_m  = meses // 12
        meses_m = meses % 12
        col_res.success(resultado_text + f"✅ Meta Final em **{anos_m}a {meses_m}m**")
    else:
        col_res.warning(resultado_text + f"⚠️ Meta Final não atingida em {anos_simulacao} anos")

# ─────────────────────────────────────────────────────────────────────────────
# CONTRIBUIÇÃO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🏆 Contribuição de Cada Ativo para a Meta")

df_contrib = None

if "Renda Mensal Est. (USD)" in df.columns and col_ticker in df.columns:
    df_contrib = df[[col_ticker, "Renda Mensal Est. (USD)", "Patrimônio (USD)"]].copy()
    if "DY (%)" in df.columns:
        df_contrib["DY (%)"] = df["DY (%)"]

    df_contrib["Renda Mensal Est. (USD)"] = pd.to_numeric(df_contrib["Renda Mensal Est. (USD)"], errors="coerce")
    df_contrib["% da Meta Final"] = (
        df_contrib["Renda Mensal Est. (USD)"] / META_MENSAL_USD * 100
    ).round(2)
    df_contrib = df_contrib.sort_values("% da Meta Final", ascending=False)

    if META_INTERMEDIARIA:
        df_contrib["% da Meta Inter."] = (
            df_contrib["Renda Mensal Est. (USD)"] / META_INTERMEDIARIA * 100
        ).round(2)

    if not df_contrib.empty:
        fig_contrib = px.bar(
            df_contrib,
            x=col_ticker,
            y="% da Meta Final",
            color="% da Meta Final",
            color_continuous_scale="Greens",
            title="% da Meta Final de Renda Alcançada por Ativo",
            text=df_contrib["% da Meta Final"].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else ""
            ),
        )
        fig_contrib.add_hline(
            y=100, line_dash="dash", line_color="red",
            annotation_text="100% da Meta Final"
        )
        fig_contrib.update_layout(plot_bgcolor="#f8fafc")
        st.plotly_chart(fig_contrib, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TABELA
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 Tabela Completa da Carteira")

f1, f2 = st.columns(2)
with f1:
    busca = st.text_input("🔍 Buscar ativo", "")
with f2:
    colunas_possiveis = [
        "Patrimônio (USD)", "Renda Mensal Est. (USD)",
        "Retorno (%)", "DY (%)", "% da Meta Final"
    ]
    colunas_ordenacao = [c for c in colunas_possiveis if c in df.columns]
    ordenar_por = st.selectbox("Ordenar por", options=colunas_ordenacao) if colunas_ordenacao else None

df_tabela = df.copy()

if df_contrib is not None and col_ticker in df_tabela.columns and "% da Meta Final" in df_contrib.columns:
    cols_merge = [col_ticker, "% da Meta Final"]
    if META_INTERMEDIARIA and "% da Meta Inter." in df_contrib.columns:
        cols_merge.append("% da Meta Inter.")
    df_tabela = df_tabela.merge(df_contrib[cols_merge], on=col_ticker, how="left")

if busca and col_ticker in df_tabela.columns:
    df_tabela = df_tabela[
        df_tabela[col_ticker].astype(str).str.contains(busca, case=False, na=False)
    ]

if ordenar_por and ordenar_por in df_tabela.columns:
    df_tabela[ordenar_por] = pd.to_numeric(df_tabela[ordenar_por], errors="coerce")
    df_tabela = df_tabela.sort_values(ordenar_por, ascending=False, na_position="last")

df_display = df_tabela.copy()

for col in ["Patrimônio (USD)", "Custo Total (USD)", "Lucro/Prejuízo (USD)", "Renda Mensal Est. (USD)"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(fmt_usd)

if "Retorno (%)" in df_display.columns:
    df_display["Retorno (%)"] = df_display["Retorno (%)"].apply(fmt_pct_sinal)

for col in ["DY (%)", "% da Meta Final", "% da Meta Inter.", "Yield on Cost"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(fmt_pct)

st.dataframe(df_display, use_container_width=True, height=420)

# ─────────────────────────────────────────────────────────────────────────────
# EXPORTAR
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
csv_export = df_tabela.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Baixar CSV da Carteira",
    data=csv_export,
    file_name="carteira_aposentadoria.csv",
    mime="text/csv"
)

# ─────────────────────────────────────────────────────────────────────────────
# RODAPÉ
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"📡 Fonte: Google Sheets (dados em USD) + Yahoo Finance (cotações ao vivo) | "
    f"🔄 Atualização automática a cada 5 minutos | "
    f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)