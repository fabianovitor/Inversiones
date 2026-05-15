import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# CONFIGURAÇÕES FIXAS
# ─────────────────────────────────────────────
META_MENSAL_USD   = 2300.0
SPREADSHEET_ID    = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"

# GIDs das abas — ajuste conforme suas abas reais
# Para descobrir o gid de cada aba: abra a planilha no navegador,
# clique na aba desejada e veja o número após "gid=" na URL
ABAS = {
    "Cartera": "79928919",
    # "Histórico":        "123456789",   # adicione outras abas aqui se necessário
}

def build_csv_url(spreadsheet_id: str, gid: str = "0") -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )

# ─────────────────────────────────────────────
# FUNÇÕES DE CARREGAMENTO
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_sheet(spreadsheet_id: str, gid: str = "0") -> pd.DataFrame:
    """
    Lê a planilha Google Sheets publicada como CSV.
    Cache de 5 minutos (ttl=300).
    """
    url = build_csv_url(spreadsheet_id, gid)
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        return df
    except requests.exceptions.HTTPError:
        st.error(
            "❌ Erro ao acessar a planilha.\n\n"
            "Verifique se ela está com acesso público: "
            "**Compartilhar → Qualquer pessoa com o link → Visualizador**"
        )
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")
        return pd.DataFrame()


def detect_columns(df: pd.DataFrame) -> dict:
    """
    Detecta automaticamente os nomes das colunas,
    aceitando variações em português, inglês e abreviações.
    """
    col_map = {}
    for col in df.columns:
        cl = str(col).lower().strip()
        if any(k in cl for k in ["ticker", "ativo", "papel", "symbol", "código", "codigo"]):
            col_map["ticker"] = col
        elif any(k in cl for k in ["quantidade", "qtd", "cotas", "shares", "units", "qnt"]):
            col_map["quantidade"] = col
        elif any(k in cl for k in ["preço médio", "preco medio", "pm", "custo", "avg price", "average", "p.médio", "p. médio"]):
            col_map["preco_medio"] = col
        elif any(k in cl for k in ["preço atual", "preco atual", "cotação", "cotacao", "current price", "price", "p.atual", "p. atual"]):
            col_map["preco_atual"] = col
        elif any(k in cl for k in ["dividend", "dy", "yield"]):
            col_map["dy"] = col
        elif any(k in cl for k in ["setor", "categoria", "tipo", "sector", "type", "classe"]):
            col_map["setor"] = col
        elif any(k in cl for k in ["moeda", "currency", "divisa"]):
            col_map["moeda"] = col
    return col_map


def process_dataframe(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """
    Calcula colunas derivadas a partir dos dados primários da planilha.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "quantidade" in col_map and "preco_atual" in col_map:
        df["Patrimônio (USD)"] = (
            pd.to_numeric(df[col_map["quantidade"]], errors="coerce") *
            pd.to_numeric(df[col_map["preco_atual"]], errors="coerce")
        )

    if "quantidade" in col_map and "preco_medio" in col_map:
        df["Custo Total (USD)"] = (
            pd.to_numeric(df[col_map["quantidade"]], errors="coerce") *
            pd.to_numeric(df[col_map["preco_medio"]], errors="coerce")
        )

    if "Patrimônio (USD)" in df.columns and "Custo Total (USD)" in df.columns:
        df["Lucro/Prejuízo (USD)"] = df["Patrimônio (USD)"] - df["Custo Total (USD)"]
        df["Retorno (%)"] = (
            (df["Lucro/Prejuízo (USD)"] / df["Custo Total (USD)"]) * 100
        ).round(2)

    if "dy" in col_map and "Patrimônio (USD)" in df.columns:
        df["DY (%)"] = pd.to_numeric(df[col_map["dy"]], errors="coerce")
        df["Renda Mensal Est. (USD)"] = (
            df["Patrimônio (USD)"] * df["DY (%)"] / 100 / 12
        ).round(2)

    if "Patrimônio (USD)" in df.columns:
        df = df.dropna(subset=["Patrimônio (USD)"])
        df = df[df["Patrimônio (USD)"] > 0]

    return df


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.title("⚙️ Configurações")
st.sidebar.markdown("---")

aba_selecionada = st.sidebar.selectbox("📋 Selecionar Aba", list(ABAS.keys()))
taxa_cambio     = st.sidebar.number_input("💱 Taxa de Câmbio (BRL/USD)", min_value=1.0, value=5.10, step=0.01)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 Meta Mensal")
st.sidebar.metric("Renda Alvo", f"$ {META_MENSAL_USD:,.2f}")

if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    "📡 Dados sincronizados com Google Sheets\n\n"
    "🔄 Atualização automática a cada **5 minutos**"
)

# ─────────────────────────────────────────────
# CABEÇALHO
# ─────────────────────────────────────────────
st.title("📊 Dashboard — Carteira de Aposentadoria")
st.markdown(
    "Acompanhe sua evolução rumo à renda passiva de **$2.300/mês** "
    "— dados sincronizados automaticamente com sua planilha Google Sheets"
)
st.markdown("---")

# ─────────────────────────────────────────────
# CARREGAMENTO DOS DADOS
# ─────────────────────────────────────────────
gid_selecionado = ABAS[aba_selecionada]

with st.spinner("📡 Carregando dados da planilha..."):
    df_raw = load_sheet(SPREADSHEET_ID, gid_selecionado)

if df_raw.empty:
    st.warning(
        "⚠️ Não foi possível carregar os dados.\n\n"
        "**Verifique:**\n"
        "1. A planilha está com acesso público?\n"
        "2. O GID da aba está correto?\n\n"
        f"URL tentada: `{build_csv_url(SPREADSHEET_ID, gid_selecionado)}`"
    )
    st.stop()

col_map = detect_columns(df_raw)
# Adicione logo após: col_map = detect_columns(df_raw)
with st.sidebar.expander("🔍 Colunas Detectadas"):
    if col_map:
        for chave, coluna in col_map.items():
            st.write(f"**{chave}** → `{coluna}`")
    else:
        st.warning("Nenhuma coluna reconhecida automaticamente.")

    st.markdown("**Todas as colunas da planilha:**")
    for c in df_raw.columns:
        st.write(f"- `{c}`")
df      = process_dataframe(df_raw, col_map)

st.sidebar.success(f"✅ {len(df)} ativos carregados")

# ─────────────────────────────────────────────
# KPIs PRINCIPAIS
# ─────────────────────────────────────────────
patrimonio_total = df["Patrimônio (USD)"].sum()        if "Patrimônio (USD)"        in df.columns else 0
custo_total      = df["Custo Total (USD)"].sum()       if "Custo Total (USD)"       in df.columns else 0
lucro_total      = patrimonio_total - custo_total
retorno_pct      = (lucro_total / custo_total * 100)   if custo_total > 0 else 0
renda_mensal     = df["Renda Mensal Est. (USD)"].sum() if "Renda Mensal Est. (USD)" in df.columns else 0
progresso_meta   = min((renda_mensal / META_MENSAL_USD) * 100, 100)
num_ativos       = len(df)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Patrimônio Total",    f"$ {patrimonio_total:,.2f}",  f"R$ {patrimonio_total * taxa_cambio:,.2f}")
c2.metric("📈 Lucro / Prejuízo",    f"$ {lucro_total:,.2f}",       f"{retorno_pct:+.2f}%")
c3.metric("💵 Renda Mensal Est.",   f"$ {renda_mensal:,.2f}",      f"{progresso_meta:.1f}% da meta")
c4.metric("🎯 Meta Mensal",         f"$ {META_MENSAL_USD:,.2f}",   f"Faltam $ {max(META_MENSAL_USD - renda_mensal, 0):,.2f}")
c5.metric("📊 Ativos na Carteira",  f"{num_ativos}",               "posições ativas")

st.markdown("---")

# ─────────────────────────────────────────────
# BARRA DE PROGRESSO
# ─────────────────────────────────────────────
st.markdown("### 🎯 Progresso Rumo à Meta de Renda Passiva")
st.progress(int(progresso_meta))
st.caption(
    f"**{progresso_meta:.1f}%** da meta atingida — "
    f"Renda atual estimada: **$ {renda_mensal:,.2f}** / "
    f"Meta: **$ {META_MENSAL_USD:,.2f}**"
)
st.markdown("---")

# ─────────────────────────────────────────────
# GRÁFICOS — COMPOSIÇÃO DA CARTEIRA
# ─────────────────────────────────────────────
st.markdown("### 📊 Composição da Carteira")
g1, g2 = st.columns(2)

with g1:
    if "ticker" in col_map and "Patrimônio (USD)" in df.columns:
        fig_pie = px.pie(
            df, names=col_map["ticker"], values="Patrimônio (USD)",
            title="Patrimônio por Ativo", hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

with g2:
    if "setor" in col_map and "Patrimônio (USD)" in df.columns:
        df_setor = df.groupby(col_map["setor"])["Patrimônio (USD)"].sum().reset_index()
        fig_setor = px.pie(
            df_setor, names=col_map["setor"], values="Patrimônio (USD)",
            title="Distribuição por Setor / Tipo", hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_setor, use_container_width=True)
    elif "ticker" in col_map and "Patrimônio (USD)" in df.columns:
        fig_bar = px.bar(
            df.sort_values("Patrimônio (USD)", ascending=False),
            x=col_map["ticker"], y="Patrimônio (USD)",
            title="Patrimônio por Ativo (Barras)",
            color="Patrimônio (USD)", color_continuous_scale="Blues"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ─────────────────────────────────────────────
# GRÁFICOS — RENDA E PERFORMANCE
# ─────────────────────────────────────────────
st.markdown("### 💵 Renda Passiva e Performance")
g3, g4 = st.columns(2)

with g3:
    if "Renda Mensal Est. (USD)" in df.columns and "ticker" in col_map:
        df_renda = df[[col_map["ticker"], "Renda Mensal Est. (USD)"]].sort_values(
            "Renda Mensal Est. (USD)", ascending=True
        )
        fig_renda = go.Figure(go.Bar(
            x=df_renda["Renda Mensal Est. (USD)"],
            y=df_renda[col_map["ticker"]],
            orientation="h",
            marker_color="#22c55e",
            text=df_renda["Renda Mensal Est. (USD)"].apply(lambda x: f"$ {x:.2f}"),
            textposition="outside"
        ))
        fig_renda.add_vline(
            x=META_MENSAL_USD, line_dash="dash", line_color="red",
            annotation_text=f"Meta: $ {META_MENSAL_USD:,.0f}",
            annotation_position="top right"
        )
        fig_renda.update_layout(
            title="Renda Mensal Estimada por Ativo",
            xaxis_title="USD / mês", plot_bgcolor="#f8fafc"
        )
        st.plotly_chart(fig_renda, use_container_width=True)

with g4:
    if "Retorno (%)" in df.columns and "ticker" in col_map:
        df_ret = df[[col_map["ticker"], "Retorno (%)"]].sort_values("Retorno (%)", ascending=False)
        colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df_ret["Retorno (%)"]]
        fig_ret = go.Figure(go.Bar(
            x=df_ret[col_map["ticker"]],
            y=df_ret["Retorno (%)"],
            marker_color=colors,
            text=df_ret["Retorno (%)"].apply(lambda x: f"{x:+.2f}%"),
            textposition="outside"
        ))
        fig_ret.update_layout(
            title="Retorno por Ativo (%)",
            plot_bgcolor="#f8fafc",
            yaxis=dict(zeroline=True, zerolinecolor="gray")
        )
        st.plotly_chart(fig_ret, use_container_width=True)

# ─────────────────────────────────────────────
# SIMULADOR DE PROJEÇÃO
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🔮 Simulador — Projeção para Atingir a Meta")

sim1, sim2, sim3 = st.columns(3)
with sim1:
    aporte_mensal  = st.number_input("💸 Aporte Mensal (USD)", min_value=0.0, value=500.0, step=50.0)
with sim2:
    dy_medio       = st.number_input("📊 DY Médio Anual (%)", min_value=0.0, value=6.0, step=0.5)
with sim3:
    anos_simulacao = st.slider("📅 Horizonte (anos)", min_value=1, max_value=40, value=10)

patrimonio_sim  = patrimonio_total
meses_para_meta = None
historico       = []

for mes in range(1, anos_simulacao * 12 + 1):
    patrimonio_sim += aporte_mensal
    patrimonio_sim *= (1 + dy_medio / 100 / 12)
    renda_proj = patrimonio_sim * dy_medio / 100 / 12
    historico.append({
        "Mês": mes,
        "Ano": round(mes / 12, 1),
        "Patrimônio (USD)": round(patrimonio_sim, 2),
        "Renda Mensal Est. (USD)": round(renda_proj, 2)
    })
    if meses_para_meta is None and renda_proj >= META_MENSAL_USD:
        meses_para_meta = mes

df_sim = pd.DataFrame(historico)

if meses_para_meta:
    anos_m  = meses_para_meta // 12
    meses_m = meses_para_meta % 12
    st.success(
        f"🎯 Com aporte de **$ {aporte_mensal:,.2f}/mês** e DY de **{dy_medio}%**, "
        f"você atingirá a meta em aprox. **{anos_m} anos e {meses_m} meses**!"
    )
else:
    st.warning(
        f"⚠️ Com os parâmetros atuais, a meta não é atingida em {anos_simulacao} anos. "
        "Tente aumentar o aporte ou o horizonte de tempo."
    )

fig_proj = make_subplots(specs=[[{"secondary_y": True}]])
fig_proj.add_trace(
    go.Scatter(x=df_sim["Ano"], y=df_sim["Patrimônio (USD)"],
               name="Patrimônio (USD)", line=dict(color="#3b82f6", width=2)),
    secondary_y=False
)
fig_proj.add_trace(
    go.Scatter(x=df_sim["Ano"], y=df_sim["Renda Mensal Est. (USD)"],
               name="Renda Mensal (USD)", line=dict(color="#22c55e", width=2)),
    secondary_y=True
)
fig_proj.add_hline(
    y=META_MENSAL_USD, line_dash="dash", line_color="red",
    annotation_text=f"Meta $ {META_MENSAL_USD:,.0f}/mês", secondary_y=True
)
fig_proj.update_layout(
    title="📈 Projeção de Patrimônio e Renda Mensal",
    xaxis_title="Anos", plot_bgcolor="#f8fafc",
    legend=dict(orientation="h", y=-0.2)
)
fig_proj.update_yaxes(title_text="Patrimônio (USD)", secondary_y=False)
fig_proj.update_yaxes(title_text="Renda Mensal (USD)", secondary_y=True)
st.plotly_chart(fig_proj, use_container_width=True)

# ─────────────────────────────────────────────
# TABELA DETALHADA
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 Tabela Completa da Carteira")

f1, f2 = st.columns(2)
with f1:
    busca = st.text_input("🔍 Buscar ativo", "")
with f2:
    opcoes_ordem = [c for c in ["Patrimônio (USD)", "Renda Mensal Est. (USD)",
                                 "Retorno (%)", "DY (%)"] if c in df.columns]
    ordenar_por = st.selectbox("Ordenar por", options=opcoes_ordem) if opcoes_ordem else None

df_tabela = df.copy()
if busca and "ticker" in col_map:
    df_tabela = df_tabela[
        df_tabela[col_map["ticker"]].astype(str).str.contains(busca, case=False, na=False)
    ]
if ordenar_por and ordenar_por in df_tabela.columns:
    df_tabela = df_tabela.sort_values(ordenar_por, ascending=False)

colunas_usd = [c for c in ["Patrimônio (USD)", "Custo Total (USD)",
                             "Lucro/Prejuízo (USD)", "Renda Mensal Est. (USD)"]
               if c in df_tabela.columns]
colunas_pct = {c: "{:+.2f}%" for c in ["Retorno (%)", "DY (%)"] if c in df_tabela.columns}

st.dataframe(
    df_tabela.style.format(
        {c: "$ {:,.2f}" for c in colunas_usd} | colunas_pct
    ).background_gradient(subset=colunas_usd if colunas_usd else [], cmap="Greens"),
    use_container_width=True,
    height=420
)

# ─────────────────────────────────────────────
# EXPORTAR
# ─────────────────────────────────────────────
st.markdown("---")
csv = df_tabela.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Baixar CSV da Carteira",
    data=csv,
    file_name="carteira_aposentadoria.csv",
    mime="text/csv"
)

# ─────────────────────────────────────────────
# RODAPÉ
# ─────────────────────────────────────────────
st.markdown("---")
st.caption(
    "📡 Fonte: Google Sheets — "
    f"[Abrir Planilha](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit) "
    "| 🔄 Dados atualizados automaticamente a cada 5 minutos"
)