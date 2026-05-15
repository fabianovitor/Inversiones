import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estrategia de Jubilación Pro", layout="wide")

# --- CONFIGURACIÓN DE CONEXIÓN ---
# Reemplaza con tu ID de Google Sheet (Asegúrate de que esté 'Publicado en la Web' como CSV)
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU' 
SHEET_NAME = 'Hoja1'
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}'

@st.cache_data(ttl=600)
def load_data():
    try:
        df = pd.read_csv(URL)
        # Limpiamos nombres de columnas (quitar espacios)
        df.columns = [c.strip() for c in df.columns]
        return df
    except:
        return None

# --- ESTILOS DE COLOR (Lógica solicitada) ---
def style_portfolio(row):
    styles = [''] * len(row)
    
    # Lógica DY (Dividend Yield TTM)
    dy_idx = row.index.get_loc('DY_TTM')
    if row['DY_TTM'] >= 6.0:
        styles[dy_idx] = 'background-color: #d4edda; color: #155724' # Verde
    else:
        styles[dy_idx] = 'background-color: #f8d7da; color: #721c24' # Rojo
        
    # Lógica Rebalanceo (Actual vs Objetivo)
    diff_idx = row.index.get_loc('Estado')
    if row['Diferencia_USD'] <= 0:
        styles[diff_idx] = 'background-color: #d4edda; color: #155724' # Verde (Ya tienes suficiente)
    else:
        styles[diff_idx] = 'background-color: #f8d7da; color: #721c24' # Rojo (Falta comprar)
        
    return styles

st.title("🛡️ Dashboard de Jubilación Inteligente")
df_raw = load_data()

if df_raw is not None:
    df = df_raw.copy()
    
    # Motor de datos en tiempo real
    if st.sidebar.button('Sincronizar con Mercado'):
        with st.spinner('Actualizando precios y dividendos...'):
            precios, divs = [], []
            for t in df['Ticker']:
                try:
                    tk = t.split(':')[-1] if ':' in str(t) else t
                    s = yf.Ticker(str(tk))
                    precios.append(s.fast_info['lastPrice'])
                    divs.append(s.info.get('trailingAnnualDividendRate', 0))
                except:
                    precios.append(0); divs.append(0)
            df['Precio_Actual'] = precios
            df['Div_USD'] = divs
    else:
        # Valores iniciales (puedes ajustarlos para que no aparezcan en 0)
        df['Precio_Actual'] = df['Precio Medio']
        df['Div_USD'] = 0

    # --- CÁLCULOS ---
    df['Valor_Actual'] = df['Precio_Actual'] * df['Cantidad']
    total_cartera = df['Valor_Actual'].sum()
    
    df['Pct_Actual'] = (df['Valor_Actual'] / total_cartera) * 100
    df['DY_TTM'] = (df['Div_USD'] / df['Precio_Actual']) * 100
    df['YOC'] = (df['Div_USD'] / df['Precio Medio']) * 100
    
    # Lógica de compra/venta
    df['Valor_Objetivo'] = (df['Objetivo %'] / 100) * total_cartera
    df['Diferencia_USD'] = df['Valor_Objetivo'] - df['Valor_Actual']
    df['Estado'] = df['Diferencia_USD'].apply(lambda x: f"Comprar ${x:,.2f}" if x > 0 else "Mantener/Vender")

    # --- MÉTRICAS SUPERIORES ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Patrimonio Total", f"${total_cartera:,.2f}")
    m2.metric("Ingreso Anual", f"${(df['Div_USD'] * df['Cantidad']).sum():,.2f}")
    m3.metric("Media YOC", f"{df['YOC'].mean():.2f}%")
    m4.metric("Media DY", f"{df['DY_TTM'].mean():.2f}%")

    st.markdown("---")

    # --- VISUALIZACIÓN ---
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Distribución Actual")
        st.plotly_chart(px.pie(df, values='Valor_Actual', names='Ticker', hole=0.4), use_container_width=True)
    with col_b:
        st.subheader("Objetivo vs Real")
        fig = go.Figure(data=[
            go.Bar(name='Meta %', x=df['Ticker'], y=df['Objetivo %'], marker_color='#E5E7EB'),
            go.Bar(name='Real %', x=df['Ticker'], y=df['Pct_Actual'], marker_color='#1E40AF')
        ])
        st.plotly_chart(fig, use_container_width=True)

    # --- TABLA CON ESTILO ---
    st.subheader("Plan de Acción y Dividendos")
    columnas_ver = ['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'DY_TTM', 'YOC', 'Objetivo %', 'Pct_Actual', 'Estado']
    st.dataframe(df[columnas_ver].style.apply(style_portfolio, axis=1).format({
        'Precio Medio': '${:.2f}',
        'Precio_Actual': '${:.2f}',
        'DY_TTM': '{:.2f}%',
        'YOC': '{:.2f}%',
        'Objetivo %': '{:.2f}%',
        'Pct_Actual': '{:.2f}%'
    }), use_container_width=True)

else:
    st.warning("Conecta tu ID de Google Sheet en el código para empezar.")