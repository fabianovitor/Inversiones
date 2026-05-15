import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

st.set_page_config(page_title="Estrategia Jubilación Pro", layout="wide")

# --- CONEXIÓN ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

def clean_val(x):
    """Limpia formatos de México, Brasil o USA sin errores."""
    s = str(x).strip().replace('$', '').replace('%', '').replace(' ', '')
    if not s or s.lower() == 'nan': return 0.0
    # Si tiene comas y puntos (ej 1,234.56), quita la coma
    if ',' in s and '.' in s: s = s.replace(',', '')
    # Si solo tiene coma (ej 1234,56), la cambia por punto
    elif ',' in s: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(URL)
        # 1. Quitar columnas vacías (Unnamed) que desplazan los datos
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Limpieza de datos
        for col in ['Cantidad', 'Precio Medio', 'Objetivo %']:
            if col in df.columns:
                df[col] = df[col].apply(clean_val)
        
        # 3. FILTRAR POSICIONES CERRADAS (Instrucción: Solo posiciones > 0)
        df = df[df['Cantidad'] > 0].copy()
        return df
    except:
        return None

st.title("🛡️ Centro de Control de Jubilación")

df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()

    # --- PRECIOS EN TIEMPO REAL ---
    if st.sidebar.button('Actualizar Mercado 🚀'):
        precios = []
        for t in df['Ticker']:
            try:
                tk = str(t).replace('.B', '-B')
                val = yf.Ticker(tk).fast_info['lastPrice']
                precios.append(val)
            except: precios.append(0.0)
        df['Precio_Actual'] = precios
    else:
        df['Precio_Actual'] = df['Precio Medio']

    # --- LÓGICA DE EXCLUSIÓN ERIC-B ---
    # Calculamos el valor de cada posición
    df['Valor_Posicion'] = (df['Precio_Actual'] * df['Cantidad']).round(4)
    
    # Separamos ERIC-B para que el resto sume el 100% "Estándar"
    df_std = df[df['Ticker'] != 'ERIC-B']
    total_std = df_std['Valor_Posicion'].sum()
    
    # Calculamos % Real basado solo en el portafolio Estándar
    df['% Real'] = df.apply(
        lambda x: (x['Valor_Posicion'] / total_std * 100) if x['Ticker'] != 'ERIC-B' else 0, 
        axis=1
    ).round(4)

    # Diferencia (Meta - Real)
    df['Dif %'] = (df['% Real'] - df['Objetivo %']).round(4)

    # --- MÉTRICAS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Patrimonio Estándar", f"${total_std:,.2f}")
    m2.metric("Valor ERIC-B (Extra)", f"${df[df['Ticker']=='ERIC-B']['Valor_Posicion'].sum():,.2f}")
    m3.metric("Activos Abiertos", len(df))

    st.markdown("---")

    # --- TABLA DE PRECISIÓN 4D ---
    st.subheader("📊 Análisis de Rebalanceo")
    
    def color_dif(val):
        color = '#f8d7da' if val < -0.5 else '#d4edda' # Rojo si falta comprar
        return f'background-color: {color}'

    st.dataframe(
        df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'Objetivo %', '% Real', 'Dif %']].style.format({
            'Cantidad': '{:.4f}', 'Precio Medio': '${:.4f}', 'Precio_Actual': '${:.4f}',
            'Objetivo %': '{:.4f}%', '% Real': '{:.4f}%', 'Dif %': '{:.4f}%'
        }).applymap(color_dif, subset=['Dif %']),
        use_container_width=True
    )

    # --- GRÁFICO ---
    fig = px.bar(df_std, x='Ticker', y=['Objetivo %', '% Real'], barmode='group', title="Alineación del Portafolio Estándar")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("No se pudo cargar la planilla. Verifica el acceso público.")