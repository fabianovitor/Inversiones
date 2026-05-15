import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import StringIO
import yfinance as yf
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ═══════════════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES FIXAS
# ═══════════════════════════════════════════════════════════════════════════════
META_MENSAL_USD = 2300.0
SPREADSHEET_ID  = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_CARTERA     = "0"

COLUMN_MAP = {
    "ticker":      "Ticker",
    "nome":        "Nombre",
    "quantidade":  "Cantidad",
    "preco_medio": "Precio Promedio",
    "preco_atual": "Precio Actual",
    "dy":          "DY%",
    "setor":       "Sector",
    "moeda":       "Moneda",
}

LINHA_IGNORAR = 14

# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE CARREGAMENTO E COTAÇÕES
# ═══════════════════════════════════════════════════════════════════════════════

def build_csv_url(spreadsheet_id: str, gid: str = "0") -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )


@st.cache_data(ttl=300)
def load_sheet(spreadsheet_id: str, gid: str = "0") -> pd.DataFrame:
    url = build_csv_url(spreadsheet_id, gid)
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        return df
    except Exception as e:
        st.error(
            f"❌ Erro ao acessar a planilha: {e}\n\n"
            "Verifique se ela está com acesso público: "
            "**Compartilhar → Qualquer pessoa com o link → Visualizador**"
        )
        return pd.DataFrame()


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
        t    = yf.Ticker(ticker)
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
                variacao_dia = ((preco_hj - preco_ant) / preco_ant * 100)

        dy_raw   = info.get("dividendYield", 0)
        dy_anual = dy_raw * 100 if dy_raw else None

        return {
            "ticker":        ticker,
            "nome":          info.get("longName", ticker),
            "setor":         info.get("sector", info.get("category", "—")),
            "preco_usd":     preco_usd,
            "preco_raw":     preco_raw,
            "moeda_mercado": moeda_mercado,
            "dy_anual":      dy_anual,
            "variacao_dia":  round(variacao_dia, 2),
            "beta":          info.get("beta", None),
            "p_vp":          info.get("priceToBook", None),
            "market_cap":    info.get("marketCap", None),
        }
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(period=period)
        hist.index = pd.to_datetime(hist.index)
        return hist[["Close", "Volume"]].reset_index()
    except Exception:
        return pd.DataFrame()


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    REGRA: Todos os valores da planilha JÁ ESTÃO EM USD.
    Nenhuma conversão de moeda é aplicada aqui.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if LINHA_IGNORAR < len(df):
        df = df.drop(index=LINHA_IGNORAR).reset_index(drop=True)

    df = df.dropna(how="all")

    col_qtd = COLUMN_MAP.get("quantidade",  "Cantidad")
    col_pm  = COLUMN_MAP.get("preco_medio", "Precio Promedio")
    col_pa  = COLUMN_MAP.get("preco_atual", "Precio Actual")
    col_dy  = COLUMN_MAP.get("dy",          "DY%")

    for col in [col_qtd, col_pm, col_pa, col_dy]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace("%", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if col_qtd in df.columns and col_pa in df.columns:
        df["Patrimônio (USD)"] = df[col_qtd] * df[col_pa]

    if col_qtd in df.columns and col_pm in df.columns:
        df["Custo Total (USD)"] = df[col_qtd] * df[col_pm]

    if "Patrimônio (USD)" in df.columns and "Custo Total (USD)" in df.columns:
        df["Lucro/Prejuízo (USD)"] = (
            df["Patrimônio (USD)"] - df["Custo Total (USD)"]
        )
        df["Retorno (%)"] = (
            (df["Lucro/Prejuízo (USD)"] / df["Custo Total (USD)"]) * 100
        ).round(2)

    if col_dy in df.columns and "Patrimônio (USD)" in df.columns:
        df["DY (%)"] = df[col_dy]
        df["Renda Mensal Est. (USD)"] = (
            df["Patrimônio (USD)"] * df["DY (%)"] / 100 / 12
        ).round(2)

    if "Patrimônio (USD)" in df.columns:
        df = df.dropna(subset=["Patrimônio (USD)"])
        df = df[df["Patrimônio (USD)"] > 0]

    return df


def formatar_valor_usd(val):
    """Formata valor como USD, retorna string vazia se NaN."""
    try:
        if pd.isna(val):
            return ""
        return f"$ {val:,.2f}"
    except Exception:
        return str(val)


def formatar_pct(val):
    """Formata valor como percentual com sinal, retorna string vazia se NaN."""
    try:
        if pd.isna(val):
            return ""
        return f"{val:+.2f}%"
    except Exception:
        return str(val)


def formatar_pct_sem_sinal(val):
    """Formata valor como percentual sem sinal, retorna string vazia se NaN."""
    try:
        if pd.isna(val):
            return ""
        return f"{val:.2f}%"
    except Exception:
        return str(val)


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
st.sidebar.title("⚙️ Dashboard — Aposentadoria")
st.sidebar.markdown("---")
st.sidebar.markdown(f"🎯 **Meta:** $ {META_MENSAL_USD:,.2f} / mês")

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

# ═══════════════════════════════════════════════════════════════════════════════
# CABEÇALHO
# ═══════════════════════════════════════════════════════════════════════════════
st.title("📊 Dashboard — Carteira de Aposentadoria")
st.markdown(
    "Acompanhe sua evolução rumo à renda passiva de **$2.300/mês** "
    "— dados da planilha em USD + cotações ao vivo convertidas automaticamente"
)
st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# CARREGAMENTO DE DADOS
# ═══════════════════════════════════════════════════════════════════════════════
with st.spinner("📡 Sincronizando dados..."):
    rates  = get_all_rates()
    df_raw = load_sheet(SPREADSHEET_ID, GID_CARTERA)

if df_raw.empty:
    st.error(
        "❌ Não foi possível carregar os dados da planilha.\n\n"
        "Verifique se a planilha está com acesso público:\n"
        "**Compartilhar → Qualquer pessoa com o link → Visualizador**\n\n"
        f"URL: `{build_csv_url(SPREADSHEET_ID, GID_CARTERA)}`"
    )
    st.stop()

df = process_dataframe(df_raw)

col_ticker = COLUMN_MAP.get("ticker", "Ticker")
col_setor  = COLUMN_MAP.get("setor",  "Sector")

usd_brl_ref = rates.get("BRL", 0)
usd_sek_ref = rates.get("SEK", 0)

st.sidebar.success(f"✅ {len(df)} ativos carregados")
if usd_brl_ref > 0:
    st.sidebar.caption(f"💱 USD/BRL: R$ {1/usd_brl_ref:.4f}")
if usd_sek_ref > 0:
    st.sidebar.caption(f"💱 USD/SEK: kr {1/usd_sek_ref:.4f}")
st.sidebar.caption(f"🕐 Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ═══════════════════════════════════════════════════════════════════════════════
# KPIs PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════════════════
patrimonio_total = df["Patrimônio (USD)"].sum()        if "Patrimônio (USD)"        in df.columns else 0
custo_total      = df["Custo Total (USD)"].sum()       if "Custo Total (USD)"       in df.columns else 0
lucro_total      = patrimonio_total - custo_total
retorno_pct      = (lucro_total / custo_total * 100)   if custo_total > 0 else 0
renda_mensal     = df["Renda Mensal Est. (USD)"].sum() if "Renda Mensal Est. (USD)" in df.columns else 0
falta_para_meta  = max(META_MENSAL_USD - renda_mensal, 0)
progresso_meta   = min((renda_mensal / META_MENSAL_USD) * 100, 100)
num_ativos       = len(df)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Patrimônio Total",   f"$ {patrimonio_total:,.2f}")
c2.metric("📈 Lucro / Prejuízo",   f"$ {lucro_total:,.2f}",     f"{retorno_pct:+.2f}%")
c3.metric("💵 Renda Mensal Est.",  f"$ {renda_mensal:,.2f}",    f"{progresso_meta:.1f}% da meta")
c4.metric("🎯 Falta para a Meta",  f"$ {falta_para_meta:,.2f}", f"Meta: $ {META_MENSAL_USD:,.2f}/mês")
c5.metric("📊 Ativos na Carteira", f"{num_ativos}",             "posições ativas")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# BARRA DE PROGRESSO
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🎯 Progresso Rumo à Meta de Renda Passiva")

cor_progresso = "#22c55e" if progresso_meta >= 75 else "#f59e0b" if progresso_meta >= 40 else "#ef4444"
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
    f"Meta: **$ {META_MENSAL_USD:,.2f}/mês** | "
    f"Faltam: **$ {falta_para_meta:,.2f}/mês**"
)
st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS — COMPOSIÇÃO DA CARTEIRA
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📊 Composição da Carteira")
g1, g2 = st.columns(2)

with g1:
    if col_ticker in df.columns and "Patrimônio (USD)" in df.columns:
        fig_pie = px.pie(
            df, names=col_ticker, values="Patrimônio (USD)",
            title="Patrimônio por Ativo (USD)", hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

with g2:
    if col_setor in df.columns and "Patrimônio (USD)" in df.columns:
        df_setor = df.groupby(col_setor)["Patrimônio (USD)"].sum().reset_index()
        fig_setor = px.pie(
            df_setor, names=col_setor, values="Patrimônio (USD)",
            title="Distribuição por Setor / Tipo", hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_setor, use_container_width=True)
    elif col_ticker in df.columns and "Patrimônio (USD)" in df.columns:
        fig_bar = px.bar(
            df.sort_values("Patrimônio (USD)", ascending=False),
            x=col_ticker, y="Patrimônio (USD)",
            title="Patrimônio por Ativo (USD)",
            color="Patrimônio (USD)", color_continuous_scale="Blues"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS — RENDA E PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("### 💵 Renda Passiva e Performance por Ativo")
g3, g4 = st.columns(2)

with g3:
    if "Renda Mensal Est. (USD)" in df.columns and col_ticker in df.columns:
        df_renda = df[[col_ticker, "Renda Mensal Est. (USD)"]].sort_values(
            "Renda Mensal Est. (USD)", ascending=True
        )
        fig_renda = go.Figure(go.Bar(
            x=df_renda["Renda Mensal Est. (USD)"],
            y=df_renda[col_ticker],
            orientation="h",
            marker_color="#22c55e",
            text=df_renda["Renda Mensal Est. (USD)"].apply(lambda x: f"$ {x:.2f}" if pd.notna(x) else ""),
            textposition="outside"
        ))
        fig_renda.add_vline(
            x=META_MENSAL_USD, line_dash="dash", line_color="red",
            annotation_text=f"Meta: $ {META_MENSAL_USD:,.0f}",
            annotation_position="top right"
        )
        fig_renda.update_layout(
            title="Renda Mensal Estimada por Ativo (USD)",
            xaxis_title="USD / mês", plot_bgcolor="#f8fafc"
        )
        st.plotly_chart(fig_renda, use_container_width=True)

with g4:
    if "Retorno (%)" in df.columns and col_ticker in df.columns:
        df_ret = df[[col_ticker, "Retorno (%)"]].sort_values("Retorno (%)", ascending=False)
        colors = ["#22c55e" if pd.notna(v) and v >= 0 else "#ef4444" for v in df_ret["Retorno (%)"]]
        fig_ret = go.Figure(go.Bar(
            x=df_ret[col_ticker],
            y=df_ret["Retorno (%)"],
            marker_color=colors,
            text=df_ret["Retorno (%)"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else ""),
            textposition="outside"
        ))
        fig_ret.update_layout(
            title="Retorno por Ativo (%)",
            plot_bgcolor="#f8fafc",
            yaxis=dict(zeroline=True, zerolinecolor="gray")
        )
        st.plotly_chart(fig_ret, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ANÁLISE DETALHADA POR ATIVO
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🔍 Análise Detalhada por Ativo")
st.caption(
    "💡 Preços de mercado obtidos do Yahoo Finance. "
    "Ativos em moeda estrangeira (SEK, EUR, etc.) são convertidos automaticamente para USD."
)

if col_ticker in df.columns:
    tickers_disponiveis = df[col_ticker].dropna().unique().tolist()
    ticker_selecionado  = st.selectbox("📌 Selecione um ativo para analisar:", tickers_disponiveis)

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
        a4.metric(
            "📊 Patrimônio neste Ativo",
            f"$ {linha_ativo.get('Patrimônio (USD)', 0):,.2f}"
        )
        a5.metric(
            "💵 Renda Mensal Est.",
            f"$ {linha_ativo.get('Renda Mensal Est. (USD)', 0):,.2f}"
        )

        with st.expander(f"ℹ️ Mais informações sobre {ticker_selecionado}"):
            i1, i2, i3 = st.columns(3)
            i1.write(f"**Nome:** {info_mercado.get('nome', '—')}")
            i1.write(f"**Setor:** {info_mercado.get('setor', '—')}")
            i1.write(f"**Moeda de Mercado:** {moeda_mercado}")
            i2.write(f"**Beta:** {info_mercado.get('beta', '—')}")
            i2.write(f"**P/VP:** {info_mercado.get('p_vp', '—')}")
            mc = info_mercado.get("market_cap")
            i3.write(f"**Market Cap:** $ {mc:,.0f}" if mc else "**Market Cap:** —")

            if moeda_mercado != "USD":
                taxa_utilizada = rates.get(moeda_mercado, get_exchange_rate(moeda_mercado))
                st.info(
                    f"💱 Taxa de conversão utilizada: "
                    f"**1 {moeda_mercado} = $ {taxa_utilizada:.6f} USD** "
                    f"(atualizada via Yahoo Finance)"
                )

        if not historico_preco.empty:
            periodo_opcao = st.radio(
                "📅 Período do histórico:",
                ["3 meses", "6 meses", "1 ano"],
                horizontal=True,
                key=f"periodo_{ticker_selecionado}"
            )
            meses_map = {"3 meses": 90, "6 meses": 180, "1 ano": 365}
            dias = meses_map[periodo_opcao]
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

            if moeda_mercado != "USD":
                st.caption(
                    f"ℹ️ O histórico de preço acima está na moeda original "
                    f"**{moeda_mercado}** para preservar a tendência real do ativo. "
                    f"O preço atual convertido para USD é exibido nos cards acima."
                )

# ═══════════════════════════════════════════════════════════════════════════════
# CENÁRIOS E PROJEÇÕES
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🔮 Simulador — Projeção para Atingir a Meta")

sim1, sim2, sim3 = st.columns(3)
with sim1:
    aporte_mensal  = st.number_input("💸 Aporte Mensal (USD)", min_value=0.0, value=500.0, step=50.0)
with sim2:
    dy_simulacao   = st.number_input("📊 DY Médio Anual (%)", min_value=0.0, value=6.0, step=0.5)
with sim3:
    anos_simulacao = st.slider("📅 Horizonte (anos)", min_value=1, max_value=40, value=10)

cenarios = {
    "🐌 Conservador": dy_simulacao * 0.75,
    "📊 Base":        dy_simulacao,
    "🚀 Otimista":    dy_simulacao * 1.25,
}

fig_cenarios    = go.Figure()
historico_todos = {}

cores_cenario = {
    "🐌 Conservador": "#f59e0b",
    "📊 Base":        "#3b82f6",
    "🚀 Otimista":    "#22c55e",
}

for nome_cenario, dy_c in cenarios.items():
    patrimonio_sim = patrimonio_total
    historico_sim  = []
    meses_meta_c   = None

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

    df_sim = pd.DataFrame(historico_sim)
    historico_todos[nome_cenario] = {"df": df_sim, "meses_meta": meses_meta_c}

    fig_cenarios.add_trace(go.Scatter(
        x=df_sim["Ano"],
        y=df_sim["Renda Mensal Est. (USD)"],
        name=f"{nome_cenario} (DY {dy_c:.1f}%)",
        line=dict(color=cores_cenario[nome_cenario], width=2)
    ))

fig_cenarios.add_hline(
    y=META_MENSAL_USD, line_dash="dash", line_color="red",
    annotation_text=f"Meta $ {META_MENSAL_USD:,.0f}/mês"
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
    meses = dados_c["meses_meta"]
    if meses:
        anos_m  = meses // 12
        meses_m = meses % 12
        col_res.success(f"{nome_c}\n\n✅ Meta em **{anos_m}a {meses_m}m**")
    else:
        col_res.warning(f"{nome_c}\n\n⚠️ Não atingida em {anos_simulacao} anos")

# ═══════════════════════════════════════════════════════════════════════════════
# PERCENTUAL DA META ALCANÇADO POR ATIVO
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🏆 Contribuição de Cada Ativo para a Meta")

df_contrib = None

if "Renda Mensal Est. (USD)" in df.columns and col_ticker in df.columns:
    df_contrib = df[[col_ticker, "Renda Mensal Est. (USD)", "Patrimônio (USD)", "DY (%)"]].copy()
    df_contrib["% da Meta"] = (df_contrib["Renda Mensal Est. (USD)"] / META_MENSAL_USD * 100).round(2)
    df_contrib = df_contrib.sort_values("% da Meta", ascending=False)

    fig_contrib = px.bar(
        df_contrib,
        x=col_ticker,
        y="% da Meta",
        color="% da Meta",
        color_continuous_scale="Greens",
        title="% da Meta de Renda Alcançada por Ativo",
        text=df_contrib["% da Meta"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else ""),
    )
    fig_contrib.add_hline(
        y=100, line_dash="dash", line_color="red",
        annotation_text="100% da Meta"
    )
    fig_contrib.update_layout(plot_bgcolor="#f8fafc")
    st.plotly_chart(fig_contrib, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TABELA DETALHADA — SEM .style para evitar erros com NaN
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📋 Tabela Completa da Carteira")

f1, f2 = st.columns(2)
with f1:
    busca = st.text_input("🔍 Buscar ativo", "")
with f2:
    colunas_possiveis = [
        "Patrimônio (USD)", "Renda Mensal Est. (USD)",
        "Retorno (%)", "DY (%)", "% da Meta"
    ]
    colunas_ordenacao = [c for c in colunas_possiveis if c in df.columns]
    if df_contrib is not None:
        for c in ["% da Meta"]:
            if c in df_contrib.columns and c not in colunas_ordenacao:
                colunas_ordenacao.append(c)
    ordenar_por = st.selectbox("Ordenar por", options=colunas_ordenacao) if colunas_ordenacao else None

# Monta tabela
df_tabela = df.copy()

# Merge seguro com df_contrib
if df_contrib is not None and col_ticker in df_tabela.columns and "% da Meta" in df_contrib.columns:
    df_tabela = df_tabela.merge(
        df_contrib[[col_ticker, "% da Meta"]], on=col_ticker, how="left"
    )

# Filtro por busca
if busca and col_ticker in df_tabela.columns:
    df_tabela = df_tabela[
        df_tabela[col_ticker].astype(str).str.contains(busca, case=False, na=False)
    ]

# Ordenação
if ordenar_por and ordenar_por in df_tabela.columns:
    df_tabela = df_tabela.sort_values(ordenar_por, ascending=False)

# ── Cria versão formatada para exibição (sem usar .style que quebra com NaN) ──
df_display = df_tabela.copy()

# Colunas em USD
for col in ["Patrimônio (USD)", "Custo Total (USD)", "Lucro/Prejuízo (USD)", "Renda Mensal Est. (USD)"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(formatar_valor_usd)

# Colunas percentuais com sinal
for col in ["Retorno (%)"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(formatar_pct)

# Colunas percentuais sem sinal
for col in ["DY (%)", "% da Meta"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(formatar_pct_sem_sinal)

st.dataframe(df_display, use_container_width=True, height=420)

# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTAR
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
csv = df_tabela.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Baixar CSV da Carteira",
    data=csv,
    file_name="carteira_aposentadoria.csv",
    mime="text/csv"
)

# ═══════════════════════════════════════════════════════════════════════════════
# RODAPÉ
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.caption(
    f"📡 Fonte: Google Sheets (dados em USD) + Yahoo Finance (cotações ao vivo) | "
    f"🔄 Atualização automática a cada 5 minutos | "
    f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)