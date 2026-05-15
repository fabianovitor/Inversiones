import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estrategia de Jubilación Pro", layout="wide")

# --- CONFIGURACIÓN DE CONEXIÓN ---
# He verificado este ID con tus imágenes anteriores
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
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# --- FUNCIÓN DE ESTILO CORREGIDA ---
def apply_custom_style(df_to_style):
    def highlight_logic(column):
        # Inicializamos estilos vacíos
        styles = ['' for _ in column]
        
        # Lógica para DY_TTM (Verde >= 6%, Rojo < 6%)
        if column.name == 'DY_TTM':
            styles = ['background-color: #d4edda; color: #155724' if (v >= 6.0) 
                      else 'background-color: #f8d7da; color: #721c24' for v in column]
        
        # Lógica para Diferencia % (Verde si tienes más de la meta, Rojo si te falta)
        if column.name == 'Diferencia %':
            styles = ['background-color: #d4edda; color: #155724' if (v >= 0) 
                      else 'background-color: #f8d7da; color: #721c24' for v in column]
        return styles

    return df_to_style.style.apply(highlight_logic)

st.title("🛡️ Dashboard de Jubilación Inteligente")

df = load_data()

if df is not None:
    # Asegurar columnas básicas si no existen
    if 'Ticker' not in df.columns: st.error("Falta la columna 'Ticker'"); st.stop()
    if 'Cantidad' not in df.columns: df['Cantidad'] = 0
    if 'Precio Medio' not in df.columns: df['Precio Medio'] = 0
    if 'Objetivo %' not in df.columns: df['Objetivo %'] = 0

    # Sidebar para actualizar
    if st.sidebar.button('Sincronizar con Mercado 🚀'):
        with st.spinner('Obteniendo datos de Yahoo Finance...'):
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

    # --- CÁLCULOS ---
    df['Valor_Actual'] = df['Precio_Actual'] * df['Cantidad']
    total_cartera = df['Valor_Actual'].sum()
    
    df['Pct_Actual'] = (df['Valor_Actual'] / total_cartera * 100) if total_cartera > 0 else 0
    df['Diferencia %'] = df['Pct_Actual'] - df['Objetivo %']
    df['DY_TTM'] = (df['Div_USD'] / df['Precio_Actual'] * 100) if df['Precio_Actual'].any() else 0
    df['YOC'] = (df['Div_USD'] / df['Precio Medio'] * 100) if df['Precio Medio'].any() else 0

    # --- MÉTRICAS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Patrimonio Total", f"${total_cartera:,.2f}")
    m2.metric("YOC Promedio", f"{df['YOC'].mean():.2f}%")
    m3.metric("DY Mercado Promedio", f"{df['DY_TTM'].mean():.2f}%")

    st.markdown("---")

    # --- TABLA FINAL ---
    st.subheader("Análisis de Cartera y Rebalanceo")
    cols_mostrar = ['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'DY_TTM', 'Objetivo %', 'Pct_Actual', 'Diferencia %']
    
    # Aplicamos el estilo solo a las columnas finales
    st.dataframe(apply_custom_style(df[cols_mostrar]), use_container_width=True)

    # Gráfico
    st.plotly_chart(px.bar(df, x='Ticker', y=['Objetivo %', 'Pct_Actual'], barmode='group', title="Meta vs Realidad"), use_container_width=True)

else:
    st.info("Configura tu ID de Google Sheet para comenzar.")