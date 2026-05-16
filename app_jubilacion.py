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


def to_float(val):
    """Converte qualquer valor para float, removendo símbolos monetários."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if pd.isna(val):
            return None
        return float(val)
    try:
        s = str(val).strip()
        # Remove símbolos monetários e separadores
        for char in [",", "%", "$", "€", "£", "kr", "R$", "\xa0", "\u202f", " "]:
            s = s.replace(char, "")
        # Trata múltiplos pontos (separador de milhar brasileiro)
        if s.count(".") > 1:
            parts = s.split(".")
            s = "".join(parts[:-1]) + "." + parts[-1]
        if s in ("", "-", "nan", "NaN", "None", "N/A", "#N/A", "#VALUE!", "#REF!", "n/a", "(", ")"):
            return None
        # Remove parênteses (notação de negativo)
        s = s.replace("(", "-").replace(")", "")
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
    if val is None:
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
    """Encontra uma coluna no df dado uma lista de possíveis nomes (case-insensitive)."""
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        if candidate.lower().strip() in cols_lower:
            return cols_lower[candidate.lower().strip()]
    return None


def process_dataframe(df: pd.DataFrame):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    # Detectar colunas
    col_ticker   = find_column(df, ["Ticker", "ticker", "TICKER", "Symbol", "symbol", "Ativo"])
    col_categoria = find_column(df, ["Categoría", "Categoria", "Category", "Tipo", "Type", "categoria"])
    col_qtd      = find_column(df, ["Cantidad", "Quantidade", "Quantity", "Qtd", "Qty", "cantidad"])
    col_pm       = find_column(df, ["Precio Medio", "Preço Médio", "Average Price", "Avg Price", "Preco Medio", "precio medio"])
    col_div      = find_column(df, ["Dividendos TTM", "Dividendos", "Dividends TTM", "Dividends", "Div TTM", "dividendos ttm", "dividendos"])
    col_yoc      = find_column(df, ["Yield on Cost", "YoC", "Yield Cost", "YOC", "yield on cost"])
    col_pa       = find_column(df, ["Precio Actual", "Preço Atual", "Current Price", "Price", "precio actual"])
    col_vt       = find_column(df, ["Valor Total", "Total Value", "Value", "Total", "valor total"])

    # Filtrar linhas com ticker válido
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

    def get_num(col):
        if col and col in df.columns:
            return df[col].apply(to_float)
        return pd.Series([None] * len(df))

    qtd_num = get_num(col_qtd)
    pm_num  = get_num(col_pm)
    div_num = get_num(col_div)
    yoc_num = get_num(col_yoc)
    pa_num  = get_num(col_pa)
    vt_num  = get_num(col_vt)

    # Patrimônio
    if col_vt and col_vt in df.columns:
        df["Patrimônio (USD)"] = vt_num.apply(lambda x: x if is_valid_number(x) else None)
    elif col_qtd and col_pa and col_qtd in df.columns and col_pa in df.columns:
        df["Patrimônio (USD)"] = [
            (q * p) if (is_valid_number(q) and is_valid_number(p)) else None
            for q, p in zip(qtd_num, pa_num)
        ]

    # Custo Total
    if col_qtd and col_pm and col_qtd in df.columns and col_pm in df.columns:
        df["Custo Total (USD)"] = [
            (q * p) if (is_valid_number(q) and is_valid_number(p)) else None
            for q, p in zip(qtd_num, pm_num)
        ]

    # Lucro/Retorno
    if "Patrimônio (USD)" in df.columns and "Custo Total (USD)" in df.columns:
        lucros, retornos = [], []
        for pat, cus in zip(df["Patrimônio (USD)"], df["Custo Total (USD)"]):
            if is_valid_number(pat) and is_valid_number(cus):
                lucros.append(pat - cus)
                retornos.append(round((pat - cus) / cus * 100, 2) if cus > 0 else None)
            else:
                lucros.append(None)
                retornos.append(None)
        df["Lucro/Prejuízo (USD)"] = lucros
        df["Retorno (%)"]          = retornos

    # Renda Mensal — prioridade: Dividendos TTM / 12
    rendas = []
    if col_div and col_div in df.columns:
        for div in div_num:
            rendas.append(round(div / 12, 2) if is_valid_number(div) else None)
        df["Renda Mensal Est. (USD)"] = rendas
    elif "Patrimônio (USD)" in df.columns and col_yoc and col_yoc in df.columns:
        for pat, yoc in zip(df["Patrimônio (USD)"], yoc_num):
            if is_valid_number(pat) and is_valid_number(yoc):
                rendas.append(round(pat * yoc / 100 / 12, 2))
            else:
                rendas.append(None)
        df["Renda Mensal Est. (USD)"] = rendas

    # DY
    if col_yoc and col_yoc in df.columns:
        df["DY (%)"] = yoc_num

    # Filtrar ativos com patrimônio > 0
    if "Patrimônio (USD)" in df.columns:
        df = df[df["Patrimônio (USD)"].apply(
            lambda x: is_valid_number(x) and x > 0
        )]

    return df.reset_index(drop=True), mapa


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


def render_progress_bar(label, valor_atual, meta, cor, nome_meta="Meta"):
    progresso = min((valor_atual / meta) * 100, 100) if meta > 0 else 0.0
    falta = max(meta - valor_atual, 0)
    bar_width = progresso
    st.markdown(f"**{label}: $ {meta:,.2f}/mês**")
    st.markdown(f"""
<div style="background:#e2e8f0; border-radius:8px; height:36px; position:relative; margin-bottom:4px;">
  <div style="background:{cor}; border-radius:8px; height:36px; width:{bar_width:.1f}%;
              min-width:0; transition:width 0.3s ease;">
  </div>
  <div style="position:absolute; top:0; left:0; right:0; height:36px;
              display:flex; align-items:center; padding:0 14px;">
    <span style="color:#1e293b; font-weight:700; font-size:0.95rem;
                 text-shadow:0 0 5px #fff, 0 0 5px #fff;">
      {progresso:.1f}% — $ {valor_atual:,.2f} / $ {meta:,.2f}
    </span>
  </div>
</div>
""", unsafe_allow_html=True)
    st.caption(
        f"Renda atual: **$ {valor_atual:,.2f}/mês** | "
        f"{nome_meta}: **$ {meta:,.2f}/mês** | "
        f"Faltam: **$ {falta:,.2f}/mês**"
    )


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Dashboard — Aposentadoria")
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 Configurar Meta de Renda")

META_MENSAL_USD = st.sidebar.number_input(
    "Meta Final (USD/mês)",
    min_value=100.0, max_value=50000.0,
    value=META_MENSAL_USD_PADRAO, step=100.0,
)

usar_meta_intermediaria = st.sidebar.checkbox("Usar meta intermediária", value=False)
META_INTERMEDIARIA = None
nome_meta_intermediaria = "Meta Intermediária"
if usar_meta_intermediaria:
    META_INTERMEDIARIA = st.sidebar.number_input(
        "Meta Intermediária (USD/mês)",
        min_value=100.0, max_value=float(META_MENSAL_USD),
        value=min(500.0, float(META_MENSAL_USD)), step=50.0,
    )
    nome_meta_intermediaria = st.sidebar.text_input(
        "Nome da meta intermediária", value="Meta Intermediária",
    )

st.sidebar.markdown(f"🎯 **Meta Final:** $ {META_MENSAL_USD:,.2f} / mês")
if META_INTERMEDIARIA:
    st.sidebar.markdown(f"🎯 **{nome_meta_intermediaria}:** $ {META_INTERMEDIARIA:,.2f} / mês")
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.rerun()

# ── CABEÇALHO ────────────────────────────────────────────────────────────────
st.title("📊 Dashboard — Carteira de Aposentadoria")
st.markdown(
    f"Acompanhe sua evolução rumo à renda passiva de **${META_MENSAL_USD:,.2f}/mês** "
    "— dados da planilha em USD + cotações ao vivo convertidas automaticamente"
)
st.markdown("---")

# ── CARREGAMENTO ─────────────────────────────────────────────────────────────
with st.spinner("📡 Sincronizando dados..."):
    rates = get_all_rates()
    csv_text, erro, url_usada = load_sheet_raw(SPREADSHEET_ID, GID_PADRAO)

if erro:
    st.error("❌ **Não foi possível carregar a planilha**")
    st.info(f"**URL tentada:** `{url_usada}`")
    st.stop()

try:
    df_raw = pd.read_csv(StringIO(csv_text))
except Exception as e:
    st.error(f"❌ Erro ao processar o CSV: {e}")
    st.stop()

if df_raw.empty:
    st.error("❌ A planilha parece estar vazia.")
    st.stop()

# ── DEBUG detalhado ───────────────────────────────────────────────────────────
with st.expander("🔍 Debug — Análise detalhada dos dados (clique para ver)", expanded=False):
    st.write(f"**Colunas ({len(df_raw.columns)}):** {list(df_raw.columns)}")
    st.write("**Primeiras 5 linhas:**")
    st.dataframe(df_raw.head(5))
    
    # Verificar cada coluna candidata
    col_div_check = find_column(df_raw.copy().assign(**{c: df_raw[c] for c in df_raw.columns}),
                                 ["Dividendos TTM", "Dividendos", "Dividends TTM", "Dividends"])
    if col_div_check:
        st.write(f"**Coluna Dividendos encontrada:** `{col_div_check}`")
        st.write("**Valores brutos da coluna Dividendos:**")
        st.dataframe(df_raw[[col_div_check]].head(10))
        st.write("**Valores convertidos (to_float):**")
        converted = df_raw[col_div_check].apply(to_float)
        st.dataframe(converted.head(10))
    else:
        st.warning("Coluna de Dividendos NÃO encontrada!")

df, mapa = process_dataframe(df_raw)

col_ticker   = mapa.get("ticker")
col_cat      = mapa.get("categoria")
col_div      = mapa.get("dividendos")
col_yoc      = mapa.get("yield_cost")
col_pm       = mapa.get("preco_medio")
col_pa       = mapa.get("preco_atual")
col_vt       = mapa.get("valor_total")

with st.expander("🔍 Debug — Resultado do processamento (clique para ver)", expanded=False):
    st.write(f"**Mapeamento:** {mapa}")
    st.write(f"**Total de ativos:** {len(df)}")
    st.write(f"**Colunas calculadas:** {[c for c in df.columns if c not in df_raw.columns]}")
    
    if "Renda Mensal Est. (USD)" in df.columns:
        st.success("✅ Coluna 'Renda Mensal Est. (USD)' calculada!")
        if col_ticker:
            st.dataframe(df[[col_ticker, "Renda Mensal Est. (USD)"]].head(10))
    else:
        st.error("❌ Coluna 'Renda Mensal Est. (USD)' NÃO calculada!")
        if col_div:
            st.write(f"col_div = '{col_div}' — está no df: {col_div in df.columns}")
        
    st.dataframe(df.head(10))

if len(df) == 0:
    st.error("❌ Nenhum ativo válido encontrado após processamento.")
    st.stop()

usd_brl_ref = rates.get("BRL", 0)
usd_sek_ref = rates.get("SEK", 0)

st.sidebar.success(f"✅ {len(df)} ativos carregados")
if usd_brl_ref > 0:
    st.sidebar.caption(f"💱 USD/BRL: R$ {1/usd_brl_ref:.4f}")
if usd_sek_ref > 0:
    st.sidebar.caption(f"💱 USD/SEK: kr {1/usd_sek_ref:.4f}")
st.sidebar.caption(f"🕐 Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ── KPIs ──────────────────────────────────────────────────────────────────────
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

# ── PROGRESSO ─────────────────────────────────────────────────────────────────
st.markdown("### 🎯 Progresso Rumo às Metas de Renda Passiva")
cor_final = "#22c55e" if progresso_meta >= 75 else "#f59e0b" if progresso_meta >= 40 else "#ef4444"
render_progress_bar("Meta Final", renda_mensal, META_MENSAL_USD, cor_final, "Meta Final")

if META_INTERMEDIARIA:
    progresso_inter = min((renda_mensal / META_INTERMEDIARIA) * 100, 100) if META_INTERMEDIARIA > 0 else 0.0
    cor_inter = "#22c55e" if progresso_inter >= 75 else "#f59e0b" if progresso_inter >= 40 else "#3b82f6"
    render_progress_bar(nome_meta_intermediaria, renda_mensal, META_INTERMEDIARIA, cor_inter, nome_meta_intermediaria)

st.markdown("---")

# ── GRÁFICOS COMPOSIÇÃO ───────────────────────────────────────────────────────
st.markdown("### 📊 Composição da Carteira")
g1, g2 = st.columns(2)

with g1:
    if col_ticker and "Patrimônio (USD)" in df.columns:
        df_plot = df[[col_ticker, "Patrimônio (USD)"]].copy()
        df_plot["Patrimônio (USD)"] = pd.to_numeric(df_plot["Patrimônio (USD)"], errors="coerce")
        df_plot = df_plot.dropna()
        if not df_plot.empty:
            fig_pie = px.pie(
                df_plot, names=col_ticker, values="Patrimônio (USD)",
                title="Patrimônio por Ativo (USD)", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label", textfont=dict(color="#1e293b", size=13))
            fig_pie.update_layout(**LAYOUT_BASE, title_font=dict(color="#1e293b", size=16), height=500,
                                  legend=dict(font=dict(color="#1e293b", size=12)))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Sem dados de patrimônio para o gráfico.")

with g2:
    if col_cat and "Patrimônio (USD)" in df.columns:
        df_cat = df.copy()
        df_cat["Patrimônio (USD)"] = pd.to_numeric(df_cat["Patrimônio (USD)"], errors="coerce")
        df_cat = df_cat.dropna(subset=["Patrimônio (USD)", col_cat])
        if not df_cat.empty:
            df_setor = df_cat.groupby(col_cat)["Patrimônio (USD)"].sum().reset_index()
            fig_setor = px.pie(
                df_setor, names=col_cat, values="Patrimônio (USD)",
                title="Distribuição por Categoria", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_setor.update_traces(textfont=dict(color="#1e293b", size=13))
            fig_setor.update_layout(**LAYOUT_BASE, title_font=dict(color="#1e293b", size=16), height=500,
                                    legend=dict(font=dict(color="#1e293b", size=12)))
            st.plotly_chart(fig_setor, use_container_width=True)
        else:
            st.info(f"Sem dados de categoria para o gráfico.")
    else:
        st.info(f"Coluna de categoria não mapeada.")

# ── RENDA E PERFORMANCE ───────────────────────────────────────────────────────
st.markdown("### 💵 Renda Passiva e Performance por Ativo")
g3, g4 = st.columns(2)

with g3:
    col_renda = "Renda Mensal Est. (USD)"
    if col_renda in df.columns and col_ticker:
        df_renda = df[[col_ticker, col_renda]].copy()
        df_renda[col_renda] = pd.to_numeric(df_renda[col_renda], errors="coerce")
        df_renda = df_renda.dropna()
        if not df_renda.empty:
            df_renda = df_renda.sort_values(col_renda, ascending=True)
            fig_renda = go.Figure(go.Bar(
                x=df_renda[col_renda], y=df_renda[col_ticker], orientation="h",
                marker_color="#22c55e",
                text=df_renda[col_renda].apply(lambda x: f"$ {x:.2f}" if pd.notna(x) else ""),
                textposition="outside", textfont=dict(color="#1e293b", size=12),
            ))
            fig_renda.add_vline(
                x=META_MENSAL_USD, line_dash="dash", line_color="red",
                annotation_text=f"Meta: $ {META_MENSAL_USD:,.0f}",
                annotation_position="top right",
                annotation_font=dict(color="red", size=12),
            )
            fig_renda.update_layout(
                **layout_eixos("USD / mês", ""),
                title=dict(text="Renda Mensal Estimada por Ativo (USD)", font=dict(color="#1e293b", size=16)),
                height=500, margin=dict(t=70, b=60, l=100, r=120),
            )
            st.plotly_chart(fig_renda, use_container_width=True)
        else:
            st.warning("Coluna de renda existe mas sem dados válidos.")
    else:
        st.warning(f"Renda mensal não calculada. col_div='{col_div}', col_yoc='{col_yoc}'")

with g4:
    if "Retorno (%)" in df.columns and col_ticker:
        df_ret = df[[col_ticker, "Retorno (%)"]].copy()
        df_ret["Retorno (%)"] = pd.to_numeric(df_ret["Retorno (%)"], errors="coerce")
        df_ret = df_ret.dropna().sort_values("Retorno (%)", ascending=False)
        if not df_ret.empty:
            colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df_ret["Retorno (%)"]]
            fig_ret = go.Figure(go.Bar(
                x=df_ret[col_ticker], y=df_ret["Retorno (%)"],
                marker_color=colors,
                text=df_ret["Retorno (%)"].apply(lambda x: fmt_pct_sinal(x) if pd.notna(x) else ""),
                textposition="outside", textfont=dict(color="#1e293b", size=12),
            ))
            max_val = df_ret["Retorno (%)"].max() if not df_ret.empty else 0
            min_val = df_ret["Retorno (%)"].min() if not df_ret.empty else 0
            padding = max(abs(max_val), abs(min_val)) * 0.25
            fig_ret.update_layout(
                **layout_eixos("", "Retorno (%)"),
                title=dict(text="Retorno por Ativo (%)", font=dict(color="#1e293b", size=16)),
                height=500,
                yaxis=dict(
                    range=[min_val - padding, max_val + padding],
                    zeroline=True, zerolinecolor="#64748b",
                    title=dict(text="Retorno (%)", font=dict(color="#1e293b", size=14)),
                    tickfont=dict(color="#1e293b", size=12), gridcolor="#e2e8f0",
                ),
            )
            st.plotly_chart(fig_ret, use_container_width=True)

# ── ANÁLISE POR ATIVO ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🔍 Análise Detalhada por Ativo")

if col_ticker and col_ticker in df.columns:
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

        a1.metric("💲 Preço Atual (USD)", f"$ {preco_mercado_usd:,.2f}" if preco_mercado_usd else "N/D",
                  f"{preco_raw:,.2f} {moeda_mercado}" if moeda_mercado != "USD" and preco_raw else None)
        a2.metric("📈 Variação Hoje", f"{info_mercado.get('variacao_dia', 0):+.2f}%", delta_color="normal")
        a3.metric("💰 DY Anual (Mercado)",
                  f"{info_mercado.get('dy_anual', 0):.2f}%" if info_mercado.get("dy_anual") else "N/D")
        pat_ativo   = linha_ativo.get("Patrimônio (USD)", None)
        renda_ativo = linha_ativo.get("Renda Mensal Est. (USD)", None)
        a4.metric("📊 Patrimônio neste Ativo", f"$ {float(pat_ativo):,.2f}" if is_valid_number(pat_ativo) else "N/D")
        a5.metric("💵 Renda Mensal Est.",       f"$ {float(renda_ativo):,.2f}" if is_valid_number(renda_ativo) else "N/D")

        if not historico_preco.empty:
            periodo_opcao = st.radio(
                "📅 Período do histórico:", ["3 meses", "6 meses", "1 ano"],
                horizontal=True, key=f"periodo_{ticker_selecionado}",
            )
            meses_map    = {"3 meses": 90, "6 meses": 180, "1 ano": 365}
            dias         = meses_map[periodo_opcao]
            hist_filtrado = historico_preco.tail(dias)
            label_eixo_y  = f"Preço ({moeda_mercado})"

            fig_hist = px.area(
                hist_filtrado, x="Date", y="Close",
                title=f"Histórico de Preço — {ticker_selecionado} (em {moeda_mercado})",
                labels={"Close": label_eixo_y, "Date": "Data"},
                color_discrete_sequence=["#3b82f6"],
            )
            fig_hist.update_layout(
                **layout_eixos("Data", label_eixo_y),
                title_font=dict(color="#1e293b", size=16), height=450,
            )
            st.plotly_chart(fig_hist, use_container_width=True)

# ── SIMULADOR ─────────────────────────────────────────────────────────────────
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
cores_cenario = {"🐢 Conservador": "#f59e0b", "📊 Base": "#3b82f6", "🚀 Otimista": "#22c55e"}

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
            "Ano": round(mes / 12, 2),
            "Renda Mensal Est. (USD)": round(renda_proj, 2),
            "Patrimônio (USD)": round(patrimonio_sim, 2),
        })
        if meses_meta_c is None and renda_proj >= META_MENSAL_USD:
            meses_meta_c = mes
        if META_INTERMEDIARIA and meses_meta_inter_c is None and renda_proj >= META_INTERMEDIARIA:
            meses_meta_inter_c = mes

    df_sim = pd.DataFrame(historico_sim)
    historico_todos[nome_cenario] = {
        "df": df_sim, "meses_meta": meses_meta_c,
        "meses_meta_inter": meses_meta_inter_c,
    }
    fig_cenarios.add_trace(go.Scatter(
        x=df_sim["Ano"], y=df_sim["Renda Mensal Est. (USD)"],
        name=f"{nome_cenario} (DY {dy_c:.1f}%)",
        line=dict(color=cores_cenario[nome_cenario], width=3),
    ))

fig_cenarios.add_hline(y=META_MENSAL_USD, line_dash="dash", line_color="red",
    annotation_text=f"Meta Final $ {META_MENSAL_USD:,.0f}/mês",
    annotation_font=dict(color="red", size=13))
if META_INTERMEDIARIA:
    fig_cenarios.add_hline(y=META_INTERMEDIARIA, line_dash="dot", line_color="#3b82f6",
        annotation_text=f"{nome_meta_intermediaria} $ {META_INTERMEDIARIA:,.0f}/mês",
        annotation_font=dict(color="#3b82f6", size=13))
fig_cenarios.update_layout(
    **layout_eixos("Anos", "Renda Mensal (USD)"),
    title=dict(text="🎯 Projeção de Renda Mensal — 3 Cenários (USD)", font=dict(color="#1e293b", size=16)),
    height=500,
    legend=dict(orientation="h", y=-0.18, font=dict(color="#1e293b", size=13)),
)
st.plotly_chart(fig_cenarios, use_container_width=True)

r1, r2, r3 = st.columns(3)
for col_res, (nome_c, dados_c) in zip([r1, r2, r3], historico_todos.items()):
    meses       = dados_c["meses_meta"]
    meses_inter = dados_c.get("meses_meta_inter")
    resultado_text = f"**{nome_c}**\n\n"
    if META_INTERMEDIARIA and meses_inter:
        anos_i  = meses_inter // 12
        meses_i = meses_inter % 12
        resultado_text += f"🎯 {nome_meta_intermediaria}: **{anos_i}a {meses_i}m**\n\n"
    elif META_INTERMEDIARIA:
        resultado_text += f"⚠️ {nome_meta_intermediaria}: não atingida\n\n"
    if meses:
        anos_m  = meses // 12
        meses_m = meses % 12
        col_res.success(resultado_text + f"✅ Meta Final em **{anos_m}a {meses_m}m**")
    else:
        col_res.warning(resultado_text + f"⚠️ Meta Final não atingida em {anos_simulacao} anos")

# ── CONTRIBUIÇÃO ──────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🏆 Contribuição de Cada Ativo para a Meta")

df_contrib = None
col_renda = "Renda Mensal Est. (USD)"
if col_renda in df.columns and col_ticker:
    cols_base = [col_ticker, col_renda, "Patrimônio (USD)"]
    if "DY (%)" in df.columns:
        cols_base.append("DY (%)")
    df_contrib = df[[c for c in cols_base if c in df.columns]].copy()
    df_contrib[col_renda] = pd.to_numeric(df_contrib[col_renda], errors="coerce")

    if META_MENSAL_USD > 0:
        df_contrib["% da Meta Final"] = (df_contrib[col_renda] / META_MENSAL_USD * 100).round(2)
    else:
        df_contrib["% da Meta Final"] = 0.0

    if META_INTERMEDIARIA and META_INTERMEDIARIA > 0:
        df_contrib["% da Meta Inter."] = (df_contrib[col_renda] / META_INTERMEDIARIA * 100).round(2)

    df_contrib = df_contrib.dropna(subset=["% da Meta Final"])
    df_contrib = df_contrib.sort_values("% da Meta Final", ascending=False)

    if not df_contrib.empty:
        max_val = df_contrib["% da Meta Final"].max()
        fig_contrib = px.bar(
            df_contrib, x=col_ticker, y="% da Meta Final",
            color="% da Meta Final", color_continuous_scale="Greens",
            title="% da Meta Final de Renda Alcançada por Ativo",
            text=df_contrib["% da Meta Final"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else ""),
        )
        fig_contrib.add_hline(y=100, line_dash="dash", line_color="red",
            annotation_text="100% da Meta Final", annotation_font=dict(color="red", size=12))
        fig_contrib.update_traces(textposition="outside", textfont=dict(color="#1e293b", size=12))
        fig_contrib.update_layout(
            **layout_eixos("", "% da Meta Final"),
            title_font=dict(color="#1e293b", size=16), height=480,
            yaxis=dict(range=[0, max(max_val * 1.3, 5)],
                       title=dict(text="% da Meta Final", font=dict(color="#1e293b", size=14)),
                       tickfont=dict(color="#1e293b", size=12), gridcolor="#e2e8f0"),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_contrib, use_container_width=True)

# ── TABELA ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 Tabela Completa da Carteira")

f1, f2 = st.columns(2)
with f1:
    busca = st.text_input("🔍 Buscar ativo", "")
with f2:
    colunas_possiveis = ["Patrimônio (USD)", "Renda Mensal Est. (USD)", "Retorno (%)", "DY (%)"]
    colunas_ordenacao = [c for c in colunas_possiveis if c in df.columns]
    ordenar_por = st.selectbox("Ordenar por", options=colunas_ordenacao) if colunas_ordenacao else None

df_tabela = df.copy()
if df_contrib is not None and col_ticker and col_ticker in df_tabela.columns:
    cols_merge = [col_ticker, "% da Meta Final"]
    if META_INTERMEDIARIA and "% da Meta Inter." in df_contrib.columns:
        cols_merge.append("% da Meta Inter.")
    df_tabela = df_tabela.merge(df_contrib[cols_merge], on=col_ticker, how="left")

if busca and col_ticker and col_ticker in df_tabela.columns:
    df_tabela = df_tabela[df_tabela[col_ticker].astype(str).str.contains(busca, case=False, na=False)]

if ordenar_por and ordenar_por in df_tabela.columns:
    df_tabela[ordenar_por] = pd.to_numeric(df_tabela[ordenar_por], errors="coerce")
    df_tabela = df_tabela.sort_values(ordenar_por, ascending=False, na_position="last")

# Formata para exibição
df_display = df_tabela.copy()
for col in ["Patrimônio (USD)", "Custo Total (USD)", "Lucro/Prejuízo (USD)", "Renda Mensal Est. (USD)"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(fmt_usd)
if "Retorno (%)" in df_display.columns:
    df_display["Retorno (%)"] = df_display["Retorno (%)"].apply(fmt_pct_sinal)
for col in ["DY (%)", "% da Meta Final", "% da Meta Inter."]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(fmt_pct)

st.dataframe(df_display, use_container_width=True, height=450)

# ── EXPORTAR ──────────────────────────────────────────────────────────────────
st.markdown("---")
csv_export = df_tabela.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Baixar CSV da Carteira",
    data=csv_export,
    file_name="carteira_aposentadoria.csv",
    mime="text/csv",
)

# ── RODAPÉ ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"📡 Fonte: Google Sheets (dados em USD) + Yahoo Finance (cotações ao vivo) | "
    f"🔄 Atualização automática a cada 5 minutos | "
    f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)