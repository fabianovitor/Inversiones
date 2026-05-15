import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Mi Plan de Jubilación", layout="wide")

# --- CONEXIÓN ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Hoja1'

@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(URL)
        # Limpiamos nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

st.title("🛡️ Dashboard de Jubilación")

df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()
    
    # Asegurar columnas mínimas
    for col in ['Ticker', 'Cantidad', 'Precio Medio', 'Objetivo %']:
        if col not in df.columns:
            df[col] = 0

    # Lógica de Precios
    if st.sidebar.button('Sincronizar Mercado 🚀'):
        precios = []
        for t in df['Ticker']:
            try:
                tk = str(t).split(':')[-1] if ':' in str(t) else str(t)
                precios.append(yf.Ticker(tk).fast_info['lastPrice'])
            except:
                precios.append(0)
        df['Precio_Actual'] = precios
    else:
        df['Precio_Actual'] = df['Precio Medio']

    # Cálculos
    df['Valor_Total'] = df['Precio_Actual'] * df['Cantidad']
    total = df['Valor_Total'].sum()
    df['% Actual'] = (df['Valor_Total'] / total * 100) if total > 0 else 0

    # Visualización
    st.metric("Patrimonio Total", f"${total:,.2f}")
    
    st.subheader("Análisis de Cartera")
    st.dataframe(df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', '% Actual', 'Objetivo %']])

    fig = px.bar(df, x='Ticker', y=['Objetivo %', '% Actual'], barmode='group')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Esperando datos de Google Sheets...")