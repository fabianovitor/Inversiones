import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard — Aposentadoria",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# ESTILO CUSTOMIZADO
# ─────────────────────────────────────────────
st.markdown("""
    <style>
        .metric-card {
            background-color: #1e293b;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            color: white;
        }
        .meta-bar {
            background: linear-gradient(90deg, #22c55e, #16a34a);
            border-radius: 8px;
            height: 20px;
        }
        .section-title {
            font-size: 22px;
            font-weight: bold;
            color: #0f172a;
            margin-top: 30px;
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# META GLOBAL
# ─────────────────────────────────────────────
META_MENSAL_USD = 2300.0

# ─────────────────────────────────────────────
# CARREGAMENTO DE DADOS
# ─────────────────────────────────────────────
@st.cache_data
def load_data(file):
    df = pd.read_excel(file, sheet_name=None)
    return df

st.sidebar.title("⚙️ Configurações")
st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader(
    "📂 Carregar Planilha Excel", type=["xlsx", "xls"]
)

taxa_cambio = st.sidebar.number_input(
    "💱 Taxa de Câmbio (BRL/USD)", min_value=1.0, value=5.10, step=0.01
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 Meta Mensal")
st.sidebar.metric("Renda Alvo", f"$ {META_MENSAL_USD:,.2f}")

# ─────────────────────────────────────────────
# CABEÇALHO PRINCIPAL
# ─────────────────────────────────────────────
st.title("💼 Dashboard — Carteira de Aposentadoria")
st.markdown("Acompanhe sua evolução rumo à renda passiva de **$2.300/mês**")
st.markdown("---")

# ─────────────────────────────────────────────
# PROCESSAMENTO DOS DADOS
# ─────────────────────────────────────────────
if uploaded_file:
    sheets = load_data(uploaded_file)
    sheet_names = list(sheets.keys())

    aba = st.sidebar.selectbox("📋 Selecionar Aba", sheet_names)
    df = sheets[aba].copy()

    st.sidebar.markdown(f"✅ **{len(df)} ativos carregados**")

    # ── Normalização de colunas (ajuste conforme sua planilha) ──
    df.columns = [str(c).strip() for c in df.columns]

    # Detecta colunas automaticamente (flexível)
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if "ticker" in cl or "ativo" in cl or "papel" in cl:
            col_map["ticker"] = col
        elif "quantidade" in cl or "qtd" in cl or "cotas" in cl:
            col_map["quantidade"] = col
        elif "preço médio" in cl or "preco medio" in cl or "pm" in cl or "custo" in cl:
            col_map["preco_medio"] = col
        elif "preço atual" in cl or "preco atual" in cl or "cotação" in cl or "cota" in cl:
            col_map["preco_atual"] = col
        elif "dividend" in cl or "dy" in cl or "yield" in cl:
            col_map["dy"] = col
        elif "setor" in cl or "categoria" in cl or "tipo" in cl:
            col_map["setor"] = col
        elif "moeda" in cl or "currency" in cl:
            col_map["moeda"] = col

    # ── Calcula colunas derivadas ──
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

    # ── Remove linhas sem patrimônio ──
    if "Patrimônio (USD)" in df.columns:
        df = df.dropna(subset=["Patrimônio (USD)"])
        df = df[df["Patrimônio (USD)"] > 0]

    # ─────────────────────────────────────────
    # KPIs — LINHA 1
    # ─────────────────────────────────────────
    patrimonio_total = df["Patrimônio (USD)"].sum() if "Patrimônio (USD)" in df.columns else 0
    custo_total = df["Custo Total (USD)"].sum() if "Custo Total (USD)" in df.columns else 0
    lucro_total = patrimonio_total - custo_total
    retorno_pct = (lucro_total / custo_total * 100) if custo_total > 0 else 0
    renda_mensal = df["Renda Mensal Est. (USD)"].sum() if "Renda Mensal Est. (USD)" in df.columns else 0
    progresso_meta = min((renda_mensal / META_MENSAL_USD) * 100, 100)
    num_ativos = len(df)

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "💰 Patrimônio Total",
        f"$ {patrimonio_total:,.2f}",
        f"R$ {patrimonio_total * taxa_cambio:,.2f}"
    )
    col2.metric(
        "📈 Lucro / Prejuízo",
        f"$ {lucro_total:,.2f}",
        f"{retorno_pct:+.2f}%"
    )
    col3.metric(
        "💵 Renda Mensal Est.",
        f"$ {renda_mensal:,.2f}",
        f"{progresso_meta:.1f}% da meta"
    )
    col4.metric(
        "🎯 Meta Mensal",
        f"$ {META_MENSAL_USD:,.2f}",
        f"Faltam $ {max(META_MENSAL_USD - renda_mensal, 0):,.2f}"
    )
    col5.metric(
        "📊 Ativos na Carteira",
        f"{num_ativos}",
        "posições ativas"
    )

    st.markdown("---")

    # ─────────────────────────────────────────
    # BARRA DE PROGRESSO DA META
    # ─────────────────────────────────────────
    st.markdown("### 🎯 Progresso Rumo à Meta de Renda Passiva")
    st.progress(int(progresso_meta))
    st.caption(
        f"**{progresso_meta:.1f}%** da meta atingida — "
        f"Renda atual estimada: **$ {renda_mensal:,.2f}** / "
        f"Meta: **$ {META_MENSAL_USD:,.2f}**"
    )

    st.markdown("---")

    # ─────────────────────────────────────────
    # GRÁFICOS — LINHA 1
    # ─────────────────────────────────────────
    st.markdown("### 📊 Composição da Carteira")

    g1, g2 = st.columns(2)

    # Gráfico Pizza — Patrimônio por Ativo
    with g1:
        if "ticker" in col_map and "Patrimônio (USD)" in df.columns:
            ticker_col = col_map["ticker"]
            fig_pie = px.pie(
                df,
                names=ticker_col,
                values="Patrimônio (USD)",
                title="Patrimônio por Ativo",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

    # Gráfico Rosca — Distribuição por Setor
    with g2:
        if "setor" in col_map and "Patrimônio (USD)" in df.columns:
            setor_col = col_map["setor"]
            df_setor = df.groupby(setor_col)["Patrimônio (USD)"].sum().reset_index()
            fig_setor = px.pie(
                df_setor,
                names=setor_col,
                values="Patrimônio (USD)",
                title="Distribuição por Setor / Tipo",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_setor, use_container_width=True)
        elif "Patrimônio (USD)" in df.columns and "ticker" in col_map:
            # fallback: barras por ativo
            fig_bar = px.bar(
                df.sort_values("Patrimônio (USD)", ascending=False),
                x=col_map["ticker"],
                y="Patrimônio (USD)",
                title="Patrimônio por Ativo (Barras)",
                color="Patrimônio (USD)",
                color_continuous_scale="Blues"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # ─────────────────────────────────────────
    # GRÁFICOS — LINHA 2
    # ─────────────────────────────────────────
    st.markdown("### 💵 Renda Passiva e Performance")

    g3, g4 = st.columns(2)

    # Renda Mensal Estimada por Ativo
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
            fig_renda.update_layout(
                title="Renda Mensal Estimada por Ativo",
                xaxis_title="USD / mês",
                yaxis_title="Ativo",
                plot_bgcolor="#f8fafc"
            )
            # Linha da meta
            fig_renda.add_vline(
                x=META_MENSAL_USD,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Meta: $ {META_MENSAL_USD:,.0f}",
                annotation_position="top right"
            )
            st.plotly_chart(fig_renda, use_container_width=True)

    # Retorno por Ativo
    with g4:
        if "Retorno (%)" in df.columns and "ticker" in col_map:
            df_ret = df[[col_map["ticker"], "Retorno (%)"]].sort_values(
                "Retorno (%)", ascending=False
            )
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
                xaxis_title="Ativo",
                yaxis_title="Retorno (%)",
                plot_bgcolor="#f8fafc",
                yaxis=dict(zeroline=True, zerolinecolor="gray")
            )
            st.plotly_chart(fig_ret, use_container_width=True)

    # ─────────────────────────────────────────
    # SIMULADOR DE PROJEÇÃO DE RENDA
    # ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔮 Simulador — Projeção para Atingir a Meta")

    sim1, sim2, sim3 = st.columns(3)

    with sim1:
        aporte_mensal = st.number_input(
            "💸 Aporte Mensal (USD)", min_value=0.0, value=500.0, step=50.0
        )
    with sim2:
        dy_medio = st.number_input(
            "📊 DY Médio Anual (%)", min_value=0.0, value=6.0, step=0.5
        )
    with sim3:
        anos_simulacao = st.slider(
            "📅 Horizonte (anos)", min_value=1, max_value=40, value=10
        )

    # Simulação mês a mês
    patrimonio_sim = patrimonio_total
    renda_sim = renda_mensal
    meses_para_meta = None
    historico = []

    for mes in range(1, anos_simulacao * 12 + 1):
        patrimonio_sim += aporte_mensal
        patrimonio_sim *= (1 + dy_medio / 100 / 12)
        renda_sim = patrimonio_sim * dy_medio / 100 / 12
        historico.append({
            "Mês": mes,
            "Ano": round(mes / 12, 1),
            "Patrimônio (USD)": round(patrimonio_sim, 2),
            "Renda Mensal Est. (USD)": round(renda_sim, 2)
        })
        if meses_para_meta is None and renda_sim >= META_MENSAL_USD:
            meses_para_meta = mes

    df_sim = pd.DataFrame(historico)

    if meses_para_meta:
        anos_m = meses_para_meta // 12
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

    # Gráfico de projeção
    fig_proj = make_subplots(specs=[[{"secondary_y": True}]])

    fig_proj.add_trace(
        go.Scatter(
            x=df_sim["Ano"], y=df_sim["Patrimônio (USD)"],
            name="Patrimônio (USD)", line=dict(color="#3b82f6", width=2)
        ),
        secondary_y=False
    )
    fig_proj.add_trace(
        go.Scatter(
            x=df_sim["Ano"], y=df_sim["Renda Mensal Est. (USD)"],
            name="Renda Mensal (USD)", line=dict(color="#22c55e", width=2)
        ),
        secondary_y=True
    )
    fig_proj.add_hline(
        y=META_MENSAL_USD, line_dash="dash", line_color="red",
        annotation_text=f"Meta $ {META_MENSAL_USD:,.0f}/mês",
        secondary_y=True
    )
    fig_proj.update_layout(
        title="📈 Projeção de Patrimônio e Renda Mensal",
        xaxis_title="Anos",
        plot_bgcolor="#f8fafc",
        legend=dict(orientation="h", y=-0.2)
    )
    fig_proj.update_yaxes(title_text="Patrimônio (USD)", secondary_y=False)
    fig_proj.update_yaxes(title_text="Renda Mensal (USD)", secondary_y=True)

    st.plotly_chart(fig_proj, use_container_width=True)

    # ─────────────────────────────────────────
    # TABELA DETALHADA
    # ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📋 Tabela Completa da Carteira")

    # Filtros
    f1, f2 = st.columns(2)
    with f1:
        busca = st.text_input("🔍 Buscar ativo", "")
    with f2:
        ordenar_por = st.selectbox(
            "Ordenar por",
            options=[c for c in ["Patrimônio (USD)", "Renda Mensal Est. (USD)",
                                  "Retorno (%)", "DY (%)"] if c in df.columns]
        )

    df_tabela = df.copy()
    if busca and "ticker" in col_map:
        df_tabela = df_tabela[
            df_tabela[col_map["ticker"]].str.contains(busca, case=False, na=False)
        ]

    if ordenar_por in df_tabela.columns:
        df_tabela = df_tabela.sort_values(ordenar_por, ascending=False)

    # Formata colunas numéricas
    colunas_usd = [c for c in ["Patrimônio (USD)", "Custo Total (USD)",
                                "Lucro/Prejuízo (USD)", "Renda Mensal Est. (USD)"]
                   if c in df_tabela.columns]

    st.dataframe(
        df_tabela.style.format(
            {c: "$ {:,.2f}" for c in colunas_usd} |
            ({c: "{:+.2f}%" for c in ["Retorno (%)", "DY (%)"] if c in df_tabela.columns})
        ).background_gradient(subset=colunas_usd, cmap="Greens"),
        use_container_width=True,
        height=400
    )

    # ─────────────────────────────────────────
    # EXPORTAR RELATÓRIO
    # ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Exportar Dados")

    csv = df_tabela.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Baixar CSV da Carteira",
        data=csv,
        file_name="carteira_aposentadoria.csv",
        mime="text/csv"
    )

else:
    # ── Tela de boas-vindas ──
    st.info("👆 Carregue sua planilha Excel na barra lateral para começar.")

    st.markdown("""
    ### 📌 Como usar este dashboard:
    1. Clique em **📂 Carregar Planilha Excel** na barra lateral
    2. Selecione a aba correta da sua planilha
    3. O dashboard detectará automaticamente as colunas
    4. Use o **Simulador de Projeção** para planejar sua aposentadoria

    ### 📋 Colunas esperadas na planilha:

    | Coluna | Exemplos de nomes aceitos |
    |---|---|
    | Ticker/Ativo | `Ticker`, `Ativo`, `Papel` |
    | Quantidade | `Quantidade`, `Qtd`, `Cotas` |
    | Preço Médio | `Preço Médio`, `PM`, `Custo` |
    | Preço Atual | `Preço Atual`, `Cotação` |
    | Dividend Yield | `DY`, `Yield`, `Dividend` |
    | Setor | `Setor`, `Categoria`, `Tipo` |

    """)