import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import base64

# Configurar favicon e título da página
st.set_page_config(
    page_title="Análise de Consumo e Peso",
    page_icon="assets/icone.png",  # Substitua pelo caminho do seu ícone
    initial_sidebar_state="expanded"
)

# Adicionar logo no canto superior esquerdo da interface principal
st.image("assets/logo.png", width=150)  # Substitua pelo caminho do seu logo

# --- 1. Carregar dados ---
@st.cache_data
def load_data():
    arquivo = 'Planilha completa.xlsx'
    try:
        df = pd.read_excel(arquivo)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo '{arquivo}' não encontrado. Por favor, envie este arquivo para o repositório.")
    
    # Verificar colunas numéricas antes de converter
    cols_numericas = ['Consumo de materia natural_Cocho', 'Consumo_bebedouro', 'Peso médio']
    for col in cols_numericas:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    # Converter coluna Data
    if 'Data' in df.columns:
        df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Data'])
    else:
        raise ValueError("Coluna 'Data' não encontrada no arquivo.")
    
    # Função para converter tempo em minutos
    def tempo_para_minutos(t):
        if pd.isnull(t):
            return 0
        if isinstance(t, str):
            try:
                h, m, s = map(int, t.split(':'))
                return h * 60 + m + s / 60
            except:
                return 0
        elif hasattr(t, 'hour'):
            return t.hour * 60 + t.minute + t.second / 60
        else:
            return 0
    
    tempo_cols = ['tempo de consumo_bebedouro', 'Tempo de consumo_cocho']
    for col in tempo_cols:
        if col in df.columns:
            df[col + '_min'] = df[col].apply(tempo_para_minutos)
    
    # Ordenar e calcular dias permanência
    if 'TAG' in df.columns:
        df = df.sort_values(['TAG', 'Data']).reset_index(drop=True)
        df['dias_permanencia'] = df.groupby('TAG')['Data'].transform(lambda x: (x - x.min()).dt.days)
    else:
        raise ValueError("Coluna 'TAG' não encontrada no arquivo.")
    
    # Calcular ganho peso diário (GPD)
    if 'Peso médio' in df.columns:
        df['peso_anterior'] = df.groupby('TAG')['Peso médio'].shift(1)
        df['dias_diff'] = df.groupby('TAG')['dias_permanencia'].diff()
        df['GPD'] = (df['Peso médio'] - df['peso_anterior']) / df['dias_diff']
        df['GPD'] = df['GPD'].fillna(0)
    else:
        df['GPD'] = 0
    
    return df

# --- Tentar carregar dados com tratamento de erros ---
try:
    df = load_data()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()
except ValueError as e:
    st.error(str(e))
    st.stop()

if df.empty:
    st.warning("Dados carregados estão vazios.")
    st.stop()

# --- Sidebar: filtros ---
st.sidebar.title("Filtros")

data_min = df['Data'].min()
data_max = df['Data'].max()

date_range = st.sidebar.date_input("Selecione intervalo de datas", [data_min, data_max])

if len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
else:
    start_date, end_date = data_min, data_max

df_filtered = df[(df['Data'] >= start_date) & (df['Data'] <= end_date)]

tags = df_filtered['TAG'].unique()
selected_tags = st.sidebar.multiselect("Selecione TAG(s)", options=tags, default=tags[:3])

if not selected_tags:
    st.warning("Selecione ao menos uma TAG para análise.")
    st.stop()

df_selected = df_filtered[df_filtered['TAG'].isin(selected_tags)]

# --- Estatísticas resumo ---
st.title("Análise de Consumo e Peso")

st.markdown(f"**Intervalo de datas selecionado:** {start_date.date()} até {end_date.date()}")
st.markdown(f"**TAGs selecionadas:** {', '.join(map(str, selected_tags))}")

def resumo_estatisticas(df):
    return pd.DataFrame({
        'Média': df.mean(),
        'Mediana': df.median(),
        'Desvio Padrão': df.std()
    }).T

colunas_analise = ['Consumo de materia natural_Cocho', 'Consumo_bebedouro', 'Peso médio', 'GPD']
resumo = df_selected.groupby('TAG')[colunas_analise].apply(resumo_estatisticas).unstack()

st.subheader("Estatísticas Resumo por TAG")
st.dataframe(resumo.style.format("{:.3f}"))

# --- Gráficos comparativos ---
st.subheader("Gráficos Comparativos")

def plot_evolucao_peso(df, tags):
    fig = go.Figure()
    for tag in tags:
        dft = df[df['TAG'] == tag]
        fig.add_trace(go.Scatter(
            x=dft['dias_permanencia'],
            y=dft['Peso médio'],
            mode='lines+markers',
            name=f'TAG {tag}',
            hovertemplate='Dia: %{x}<br>Peso: %{y:.2f} kg<br>Data: %{customdata|%d/%m/%Y}',
            customdata=dft['Data']
        ))
    fig.update_layout(
        title='Evolução do Peso Médio',
        xaxis_title='Dias de permanência',
        yaxis_title='Peso Médio (kg)',
        hovermode='closest',
        showlegend=True,
        width=800,
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

plot_evolucao_peso(df_selected, selected_tags)

def plot_consumo_vs_gpd(df, tags):
    fig = px.scatter(
        df[df['TAG'].isin(tags)],
        x='Consumo de materia natural_Cocho',
        y='GPD',
        color='TAG',
        size_max=10,
        hover_data={'Data': '|%d/%m/%Y', 'Peso médio': ':.2f'},
        title='Consumo no Cocho vs Ganho de Peso Diário',
        labels={
            'Consumo de materia natural_Cocho': 'Consumo Cocho (kg/dia)',
            'GPD': 'Ganho de Peso Diário (kg)',
            'Peso médio': 'Peso Médio (kg)'
        }
    )
    fig.update_layout(
        width=800,
        height=400,
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)

plot_consumo_vs_gpd(df_selected, selected_tags)

# --- Gráficos extras: Histograma e Boxplot ---
st.subheader("Visualizações Extras")

st.markdown("Histograma do Ganho de Peso Diário (GPD)")
fig_hist = px.histogram(
    df_selected,
    x='GPD',
    color='TAG',
    barmode='stack',
    title='Histograma do Ganho de Peso Diário (GPD)',
    labels={'GPD': 'Ganho de Peso Diário (kg)'},
    hover_data={'Data': '|%d/%m/%Y'}
)
fig_hist.update_layout(
    width=800,
    height=400,
    showlegend=True
)
st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("Boxplot do Consumo no Cocho")
fig_box = px.box(
    df_selected,
    x='TAG',
    y='Consumo de materia natural_Cocho',
    color='TAG',
    title='Boxplot do Consumo no Cocho',
    labels={'Consumo de materia natural_Cocho': 'Consumo Cocho (kg/dia)'},
    hover_data={'Data': '|%d/%m/%Y'}
)
fig_box.update_layout(
    width=800,
    height=400,
    showlegend=True
)
st.plotly_chart(fig_box, use_container_width=True)

# --- Destaques: alertas GPD negativo ---
st.subheader("Alertas")

tags_gpd_negativo = df_selected[df_selected['GPD'] < 0]['TAG'].unique()
if len(tags_gpd_negativo) > 0:
    st.error(f"⚠️ Atenção! As TAGs {', '.join(map(str, tags_gpd_negativo))} apresentaram ganho de peso diário NEGATIVO em algum momento.")
else:
    st.success("Nenhuma TAG apresentou ganho de peso negativo.")

# --- Download dos dados filtrados e resumo ---
st.subheader("Download")

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados Filtrados')
    processed_data = output.getvalue()
    return processed_data

excel_data = to_excel(df_selected)

st.download_button(
    label="Download dados filtrados em Excel",
    data=excel_data,
    file_name='dados_filtrados.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# --- Download gráfico peso evolução como imagem ---
def get_image_download_link(fig, filename, text):
    try:
        buf = io.BytesIO()
        fig.write_image(buf, format='png', width=800, height=400)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        href = f'<a href="data:file/png;base64,{b64}" download="{filename}">{text}</a>'
        return href
    except Exception as e:
        st.warning(f"Erro ao gerar a imagem para download: {str(e)}. Tente salvar o gráfico manualmente clicando com o botão direito.")
        return ""

fig_peso = go.Figure()
for tag in selected_tags:
    dft = df_selected[df_selected['TAG'] == tag]
    fig_peso.add_trace(go.Scatter(
        x=dft['dias_permanencia'],
        y=dft['Peso médio'],
        mode='lines+markers',
        name=f'TAG {tag}',
        hovertemplate='Dia: %{x}<br>Peso: %{y:.2f} kg<br>Data: %{customdata|%d/%m/%Y}',
        customdata=dft['Data']
    ))
fig_peso.update_layout(
    title='Evolução do Peso Médio',
    xaxis_title='Dias de permanência',
    yaxis_title='Peso Médio (kg)',
    hovermode='closest',
    showlegend=True,
    width=800,
    height=400
)

st.plotly_chart(fig_peso, use_container_width=True)
download_link = get_image_download_link(fig_peso, 'evolucao_peso.png', 'Download gráfico Evolução do Peso (PNG)')
if download_link:
    st.markdown(download_link, unsafe_allow_html=True)