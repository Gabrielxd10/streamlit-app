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
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    
    # Garantir que TAG seja tratado como string
    if 'TAG' in df.columns:
        df['TAG'] = df['TAG'].astype(str)
    
    # Converter e normalizar coluna Data
    if 'Data' in df.columns:
        df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce').dt.normalize()
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
    
    # Consolidar dados por TAG e Data (média de valores numéricos)
    df = df.groupby(['TAG', 'Data']).agg({
        'Consumo de materia natural_Cocho': 'mean',
        'Consumo_bebedouro': 'mean',
        'Peso médio': 'mean',
        'dias_permanencia': 'first',  # Manter o primeiro valor de dias_permanencia
        'tempo de consumo_bebedouro_min': 'mean',
        'Tempo de consumo_cocho_min': 'mean'
    }).reset_index()
    
    # Detectar e remover duplicatas baseadas em TAG e Data (como segurança adicional)
    duplicatas = df[df.duplicated(subset=['TAG', 'Data'], keep=False)]
    if not duplicatas.empty:
        st.warning(f"Duplicatas detectadas em TAG e Data após consolidação. Número de duplicatas: {len(duplicatas)}. Removendo duplicatas e mantendo a primeira ocorrência.")
        df = df.drop_duplicates(subset=['TAG', 'Data'], keep='first')
    
    # Calcular ganho peso diário (GPD) com proteção contra divisão por zero
    if 'Peso médio' in df.columns:
        df['peso_anterior'] = df.groupby('TAG')['Peso médio'].shift(1)
        df['dias_diff'] = df.groupby('TAG')['dias_permanencia'].diff()
        # Usar .fillna(1) para o primeiro registro de cada TAG, evitando divisão por zero
        df['GPD'] = (df['Peso médio'] - df['peso_anterior']) / df['dias_diff'].fillna(1)
        df['GPD'] = df['GPD'].fillna(0).replace([float('inf'), float('-inf')], 0)
        # Adicionar aviso se houver valores inválidos antes da substituição
        if df['GPD'].isin([float('inf'), float('-inf')]).any():
            st.warning("Valores infinitos detectados no cálculo de GPD antes da correção. Esses valores foram substituídos por 0.")
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
        height=400,
        template='plotly'  # Usa uma paleta de cores padrão para melhor distinção
    )
    st.plotly_chart(fig, use_container_width=True)
    return fig  # Retorna o objeto fig para uso no download

fig_peso = plot_evolucao_peso(df_selected, selected_tags)

def plot_consumo_vs_gpd(df, tags):
    # Preservar TAG como string e filtrar dados inválidos
    df_plot = df[df['TAG'].isin(tags)].copy()
    df_plot['TAG'] = df_plot['TAG'].astype(str)  # Garantir que TAG seja string
    
    # Identificar dados inválidos
    invalid_data = df_plot[
        df_plot['Consumo de materia natural_Cocho'].isna() |
        df_plot['GPD'].isna() |
        df_plot['Consumo de materia natural_Cocho'].isin([float('inf'), float('-inf')]) |
        df_plot['GPD'].isin([float('inf'), float('-inf')])
    ]
    if not invalid_data.empty:
        invalid_tags = invalid_data['TAG'].unique()
        st.warning(f"Dados inválidos (NaN ou infinitos) encontrados para as TAGs: {', '.join(map(str, invalid_tags))}. Esses pontos foram removidos do gráfico.")
    
    df_plot = df_plot[
        df_plot['Consumo de materia natural_Cocho'].notna() &
        df_plot['GPD'].notna() &
        ~df_plot['Consumo de materia natural_Cocho'].isin([float('inf'), float('-inf')]) &
        ~df_plot['GPD'].isin([float('inf'), float('-inf')])
    ]
    
    if df_plot.empty:
        st.error("Nenhum dado válido para plotar o gráfico de Consumo vs GPD. Verifique os dados das TAGs selecionadas.")
        return
    
    fig = px.scatter(
        df_plot,
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
        },
        color_discrete_sequence=px.colors.qualitative.Plotly  # Paleta de cores distinta
    )
    fig.update_layout(
        width=800,
        height=400,
        showlegend=True,
        template='plotly'  # Template para melhor visualização
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
    hover_data={'Data': '|%d/%m/%Y'},
    color_discrete_sequence=px.colors.qualitative.Plotly  # Paleta de cores distinta
)
fig_hist.update_layout(
    width=800,
    height=400,
    showlegend=True,
    template='plotly'
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
    hover_data={'Data': '|%d/%m/%Y'},
    color_discrete_sequence=px.colors.qualitative.Plotly  # Paleta de cores distinta
)
fig_box.update_layout(
    width=800,
    height=400,
    showlegend=True,
    template='plotly'
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

# --- Download gráfico peso evolução como HTML ---
st.download_button(
    label="Download gráfico Evolução do Peso (HTML)",
    data=fig_peso.to_html(),
    file_name='evolucao_peso.html',
    mime='text/html'
)