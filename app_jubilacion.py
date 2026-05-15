import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estratégia de Jubilação Pro", layout="wide")

# --- CONFIGURAÇÃO DE LIGAÇÃO ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
# Exportação direta para CSV para evitar códigos HTML de login
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(URL)
        # Limpeza profunda: remove espaços nos nomes das colunas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Conversão numérica robusta para evitar erros de texto/moeda
        cols_financeiras = ['Cantidad', 'Precio Medio', 'Objetivo %']
        for col in cols_financeiras:
            if col in df.columns:
                # Remove símbolos de moeda e garante que o ponto é o decimal
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('[^0-9.]', '', regex=True), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro ao ler os dados: {e}")
        return None

# --- LÓGICA DE CORES ---
def aplicar_estilos(row):
    estilos = [''] * len(row)
    # Cor para a Diferença (Vermelho se estiver abaixo da meta)
    if 'Dif %' in row.index:
        idx_dif = row.index.get_loc('Dif %')
        if row['Dif %'] < -0.5:
            estilos[idx_dif] = 'background-color: #f8d7da; color: #721c24'
        elif row['Dif %'] > 0.5:
            estilos[idx_dif] = 'background-color: #d4edda; color: #155724'
    return estilos

st.title("🛡️ Centro de Comando Financeiro")

df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()
    
    # Sincronização com Mercado
    if st.sidebar.button('Sincronizar com Yahoo Finance 🚀'):
        with st.spinner('A atualizar preços reais...'):
            precios = []
            for t in df['Ticker']:
                try:
                    # Ajuste para Tickers específicos como ERIC-B
                    tk = str(t).replace('.B', '-B')
                    val = yf.Ticker(tk).fast_info['lastPrice']
                    precios.append(val)
                except:
                    precios.append(0)
            df['Precio_Actual'] = precios
    else:
        # Se não sincronizar, usa o Precio Medio da planilha para os cálculos
        df['Precio_Actual'] = df['Precio Medio']

    # --- CÁLCULOS MATEMÁTICOS (Baseados nos teus prints) ---
    df['Valor_Investido'] = df['Precio Medio'] * df['Cantidad']
    df['Valor_Mercado'] = df['Precio_Actual'] * df['Cantidad']
    
    total_patrimonio = df['Valor_Mercado'].sum()
    
    df['% Real'] = (df['Valor_Mercado'] / total_patrimonio * 100) if total_patrimonio > 0 else 0
    df['Dif %'] = df['% Real'] - df['Objetivo %']

    # --- MÉTRICAS SUPERIORES ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Património Total", f"${total_patrimonio:,.2f}")
    m2.metric("Nº de Ativos", len(df))
    m3.metric("Meta de Alocação", "100.00%")

    st.markdown("---")

    # --- TABELA E GRÁFICO ---
    col_tab, col_gra = st.columns([2, 1])
    
    with col_tab:
        st.subheader("Análise de Rebalanceamento")
        cols_vista = ['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', '% Real', 'Objetivo %', 'Dif %']
        st.dataframe(df[cols_vista].style.apply(aplicar_estilos, axis=1), use_container_width=True)

    with col_gra:
        st.subheader("Distribuição")
        fig_pie = px.pie(df, values='Valor_Mercado', names='Ticker', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # Gráfico de Barras comparativo
    fig_bar = go.Figure(data=[
        go.Bar(name='Meta %', x=df['Ticker'], y=df['Objetivo %'], marker_color='#E5E7EB'),
        go.Bar(name='Real %', x=df['Ticker'], y=df['% Real'], marker_color='#1E40AF')
    ])
    fig_bar.update_layout(title="Desvio da Estratégia", barmode='group')
    st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.warning("Verifica os teus dados no Google Sheets.")