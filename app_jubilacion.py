import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estrategia Jubilación Pro", layout="wide")

# --- CONEXIÓN ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(URL)
        df.columns = [str(c).strip() for c in df.columns]
        # Limpieza de datos numéricos (quita $ y comas)
        for col in ['Cantidad', 'Precio Medio', 'Objetivo %']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
        return df
    except:
        return None

# --- LÓGICA DE ESTILOS ---
def highlight_rows(s):
    # Verde si el rendimiento (DY) es >= 6%, Rojo si falta mucho para la meta
    return ['background-color: #d1e7dd; color: #0f5132' if (s.name == 'DY_TTM' and v >= 6) else 
            'background-color: #f8d7da; color: #842029' if (s.name == 'Diferencia %' and v < -1) else '' for v in s]

st.title("🛡️ Centro de Comando de Jubilación")

df = load_data()

if df is not None:
    # Sidebar: Botón de Actualización
    if st.sidebar.button('Sincronizar con Wall Street 🚀'):
        with st.spinner('Obteniendo precios reales...'):
            precios, divs = [], []
            for t in df['Ticker']:
                try:
                    # Limpiamos el ticker por si viene con prefijos (ej. BVMF:)
                    tk = str(t).split(':')[-1] if ':' in str(t) else str(t)
                    info = yf.Ticker(tk)
                    precios.append(info.fast_info['lastPrice'])
                    div_val = info.info.get('trailingAnnualDividendRate', 0)
                    divs.append(div_val if div_val else 0)
                except:
                    precios.append(0); divs.append(0)
            df['Precio_Actual'] = precios
            df['Div_USD'] = divs
    else:
        df['Precio_Actual'] = df['Precio Medio']
        df['Div_USD'] = 0

    # --- CÁLCULOS MAESTROS ---
    df['Valor_Total'] = df['Precio_Actual'] * df['Cantidad']
    total_cartera = df['Valor_Total'].sum()
    df['% Real'] = (df['Valor_Total'] / total_cartera * 100) if total_cartera > 0 else 0
    df['Diferencia %'] = df['% Real'] - df['Objetivo %']
    df['DY_TTM'] = (df['Div_USD'] / df['Precio_Actual'] * 100).fillna(0)
    df['Ingreso_Anual'] = df['Div_USD'] * df['Cantidad']

    # --- MÉTRICAS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Patrimonio", f"${total_cartera:,.2f}")
    m2.metric("Renta Anual Est.", f"${df['Ingreso_Anual'].sum():,.2f}")
    m3.metric("Renta Mensual", f"${df['Ingreso_Anual'].sum()/12:,.2f}")
    m4.metric("Yield Medio", f"{df['DY_TTM'].mean():.2f}%")

    # --- VISUALIZACIÓN ---
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Plan de Rebalanceo")
        # Mostramos la tabla con los colores de advertencia/éxito
        st.dataframe(df[['Ticker', 'Precio_Actual', 'DY_TTM', '% Real', 'Objetivo %', 'Diferencia %']].style.apply(highlight_rows))
    
    with col2:
        st.subheader("Composición")
        fig = px.pie(df, values='Valor_Total', names='Ticker', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)

    # Gráfico de barras comparativo
    fig_bar = go.Figure(data=[
        go.Bar(name='Meta %', x=df['Ticker'], y=df['Objetivo %'], marker_color='lightgrey'),
        go.Bar(name='Actual %', x=df['Ticker'], y=df['% Real'], marker_color='#1E40AF')
    ])
    fig_bar.update_layout(title="Alineación con la Estrategia Meta", barmode='group')
    st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.info("Configura tu acceso a Google Sheets para visualizar la estrategia.")