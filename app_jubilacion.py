import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estrategia de Jubilación Pro", layout="wide")

# --- CONFIGURACIÓN DE CONEXIÓN ---
# Asegúrate de que este ID sea el correcto
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU' 
SHEET_NAME = 'Hoja1'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}'

@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(URL)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def style_portfolio(row):
    styles = [''] * len(row)
    if 'DY_TTM' in row.index:
        dy_idx = row.index.get_loc('DY_TTM')
        if row['DY_TTM'] >= 6.0:
            styles[dy_idx] = 'background-color: #d4edda; color: #155724'
        else:
            styles[dy_idx] = 'background-color: #f8d7da; color: #721c24'
    return styles

st.title("🛡️ Dashboard de Jubilación Inteligente")
df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()
    
    # Verificación de columnas necesarias para evitar que la App se rompa
    columnas_necesarias = ['Ticker', 'Cantidad', 'Precio Medio', 'Objetivo %']
    for col in columnas_necesarias:
        if col not in df.columns:
            df[col] = 0
            st.warning(f"No encontré la columna '{col}' en tu Excel. Usando 0 por defecto.")

    # Motor de datos (Yahoo Finance)
    if st.sidebar.button('Sincronizar con Mercado'):
        with st.spinner('Actualizando datos financieros...'):
            precios, divs = [], []
            for t in df['Ticker']:
                try:
                    tk = str(t).split(':')[-1] if ':' in str(t) else str(t)
                    s = yf.Ticker(tk)
                    precios.append(s.fast_info['lastPrice'])
                    divs.append(s.info.get('trailingAnnualDividendRate', 0))
                except:
                    precios.append(0); divs.append(0)
            df['Precio_Actual'] = precios
            df['Div_USD'] = divs
    else:
        df['Precio_Actual'] = df['Precio Medio']
        df['Div_USD'] = 0

    # Cálculos dinámicos
    df['Valor_Actual'] = df['Precio_Actual'] * df['Cantidad']
    total_cartera = df['Valor_Actual'].sum()
    df['Pct_Actual'] = (df['Valor_Actual'] / total_cartera * 100) if total_cartera > 0 else 0
    df['DY_TTM'] = (df['Div_USD'] / df['Precio_Actual'] * 100) if df['Precio_Actual'].any() else 0
    df['YOC'] = (df['Div_USD'] / df['Precio Medio'] * 100) if df['Precio Medio'].any() else 0
    
    # Métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("Patrimonio Total", f"${total_cartera:,.2f}")
    m2.metric("Media YOC", f"{df['YOC'].mean():.2f}%")
    m3.metric("Media DY", f"{df['DY_TTM'].mean():.2f}%")

    # Gráficos
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.pie(df, values='Valor_Actual', names='Ticker', title="Distribución"), use_container_width=True)
    with c2:
        fig = go.Figure(data=[
            go.Bar(name='Meta %', x=df['Ticker'], y=df['Objetivo %']),
            go.Bar(name='Real %', x=df['Ticker'], y=df['Pct_Actual'])
        ])
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Detalle de Cartera")
    st.dataframe(df.style.apply(style_portfolio, axis=1))