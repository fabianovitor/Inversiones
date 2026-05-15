import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estrategia de Jubilación Pro", layout="wide")

# --- CONFIGURACIÓN DE CONEXIÓN ---
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

# --- FUNCIÓN DE ESTILO (CORREGIDA) ---
def apply_custom_style(df_to_style):
    def highlight_logic(column):
        # Inicializamos estilos vacíos
        styles = ['' for _ in range(len(column))]
        
        # Lógica para DY_TTM (Verde >= 6%, Rojo < 6%)
        if column.name == 'DY_TTM':
            styles = ['background-color: #d4edda; color: #155724' if (val >= 6.0) 
                      else 'background-color: #f8d7da; color: #721c24' for val in column]
        
        # Lógica para Diferencia % (Verde si cumples meta, Rojo si falta)
        if column.name == 'Diferencia':
            styles = ['background-color: #d4edda; color: #155724' if (val >= 0) 
                      else 'background-color: #f8d7da; color: #721c24' for val in column]
        return styles

    return df_to_style.style.apply(highlight_logic)

st.title("🛡️ Dashboard de Jubilación Inteligente")

df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()
    
    # Asegurar que existan las columnas para que el código no falle
    for col in ['Ticker', 'Cantidad', 'Precio Medio', 'Objetivo %']:
        if col not in df.columns:
            df[col] = 0

    # Sincronización con Yahoo Finance
    if st.sidebar.button('Sincronizar con Mercado 🚀'):
        with st.spinner('Actualizando precios y dividendos...'):
            precios, divs = [], []
            for t in df['Ticker']:
                try:
                    tk = str(t).split(':')[-1] if ':' in str(t) else str(t)
                    s = yf.Ticker(tk)
                    precios.append(s.fast_info['lastPrice'])
                    # Obtenemos dividendo anualizado
                    div_val = s.info.get('trailingAnnualDividendRate', 0)
                    if div_val is None: div_val = 0
                    divs.append(div_val)
                except:
                    precios.append(0); divs.append(0)
            df['Precio_Actual'] = precios
            df['Div_USD'] = divs
    else:
        # Por defecto usa el precio medio si no se ha sincronizado
        df['Precio_Actual'] = df['Precio Medio']
        df['Div_USD'] = 0

    # --- CÁLCULOS ---
    df['Valor_Actual'] = df['Precio_Actual'] * df['Cantidad']
    total_cartera = df['Valor_Actual'].sum()
    
    df['Pct_Actual'] = (df['Valor_Actual'] / total_cartera * 100) if total_cartera > 0 else 0
    df['Diferencia'] = df['Pct_Actual'] - df['Objetivo %']
    df['DY_TTM'] = (df['Div_USD'] / df['Precio_Actual'] * 100) if (df['Precio_Actual'] > 0).any() else 0
    df['YOC'] = (df['Div_USD'] / df['Precio Medio'] * 100) if (df['Precio Medio'] > 0).any() else 0

    # --- MÉTRICAS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Patrimonio Total", f"${total_cartera:,.2f}")
    m2.metric("YOC Promedio", f"{df['YOC'].mean():.2f}%")
    m3.metric("DY Mercado Promedio", f"{df['DY_TTM'].mean():.2f}%")

    st.markdown("---")

    # --- TABLA Y GRÁFICO ---
    cols_mostrar = ['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'DY_TTM', 'Objetivo %', 'Pct_Actual', 'Diferencia %']
    
    # Mostrar tabla con estilos
    st.subheader("Análisis de Rebalanceo")
    st.dataframe(apply_custom_style(df[cols_mostrar]), use_container_width=True)

    # Gráfico de barras
    fig = go.Figure(data=[
        go.Bar(name='Meta %', x=df['Ticker'], y=df['Objetivo %'], marker_color='#E5E7EB'),
        go.Bar(name='Actual %', x=df['Ticker'], y=df['Pct_Actual'], marker_color='#1E40AF')
    ])
    fig.update_layout(title="Distribución: Meta vs Realidad", barmode='group')
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("No se pudo cargar la planilla. Verifica el SHEET_ID y que esté compartida como 'Cualquier persona con el enlace'.")