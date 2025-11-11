import streamlit as st
import pandas as pd
from urllib.parse import quote
import io

# --- Configurações do App ---
st.set_page_config(layout="wide", page_title="Processador de Carrinhos Abandonados")

st.title("🛒 Processador de Clientes de Carrinho Abandonado")
st.markdown("Faça o upload do seu arquivo Excel/CSV e processe os dados para disparo de WhatsApp em 1 clique.")

# Definição dos nomes das colunas de ENTRADA
COL_ID = 'Codigo Cliente'
COL_NAME = 'Cliente'
COL_PHONE = 'Fone Fixo'
COL_FILTER = 'Quant. Pedidos Enviados'
# Colunas de SAÍDA
COL_OUT_NAME = 'Cliente_Formatado'
COL_OUT_MSG = 'Mensagem_Personalizada'


# --- Função de Lógica de Negócio (O Cérebro) ---

@st.cache_data
def process_data(df_input):
    """
    Executa a limpeza, filtro e personalização dos dados com base nas colunas fornecidas.
    """
    df = df_input.copy()  # Trabalha em uma cópia

    # 1. Checagem de colunas obrigatórias
    required_cols = [COL_ID, COL_NAME, COL_PHONE, COL_FILTER]
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        st.error(f"O arquivo está faltando as seguintes colunas obrigatórias: {', '.join(missing)}")
        return pd.DataFrame(), {'original_count': 0, 'removed_duplicates': 0, 'removed_filter': 0}

    metrics = {
        'original_count': len(df),
        'removed_duplicates': 0,
        'removed_filter': 0
    }

    # 1. Eliminar Duplicatas (Coluna Codigo Cliente)
    df_unique = df.drop_duplicates(subset=[COL_ID], keep='first')
    metrics['removed_duplicates'] = len(df) - len(df_unique)
    df = df_unique

    # 2. Filtrar clientes que JÁ EFETUARAM COMPRA (Quant. Pedidos Enviados > 0)
    # Mantemos APENAS onde Quant. Pedidos Enviados é menor ou igual a 0.

    # Garante que a coluna de filtro é numérica para comparação
    df[COL_FILTER] = pd.to_numeric(df[COL_FILTER], errors='coerce').fillna(0)

    df_filtered = df[df[COL_FILTER] <= 0]

    metrics['removed_filter'] = len(df) - len(df_filtered)
    df = df_filtered

    # 3. Criar mensagem personalizada

    def format_name_and_create_message(full_name):
        """Formata o nome e cria a mensagem."""
        if pd.isna(full_name) or full_name == '':
            first_name = "Cliente"
        else:
            first_name = str(full_name).strip().split(' ')[0]
            first_name = first_name.capitalize()  # Deixa a primeira letra maiúscula

        # Mensagem padrão (você pode customizar o template aqui!)
        message = f"Olá {first_name}! Notamos que você deixou alguns itens incríveis no seu carrinho. Posso te ajudar a finalizar seu pedido?"

        return first_name, message

    # Aplica a função em cada linha para criar as colunas de saída
    df[[COL_OUT_NAME, COL_OUT_MSG]] = df.apply(
        lambda row: pd.Series(format_name_and_create_message(row[COL_NAME])), axis=1
    )

    return df, metrics


# --- Interface do Usuário (Streamlit) ---

# Seção de Upload
st.header("1. Upload do Relatório de Clientes (Excel/CSV)")
uploaded_file = st.file_uploader(
    "Arraste ou clique para enviar o arquivo. Nomes de colunas esperados: Codigo Cliente, Cliente, Fone Fixo, Quant. Pedidos Enviados",
    type=["csv", "xlsx"]
)

if uploaded_file is not None:
    # Carrega o arquivo
    try:
        if uploaded_file.name.endswith('.csv'):
            df_original = pd.read_csv(uploaded_file)
        else:
            # openpyxl é necessário para ler .xlsx
            df_original = pd.read_excel(uploaded_file, engine='openpyxl')

        st.success(f"Arquivo '{uploaded_file.name}' carregado com sucesso!")
        st.dataframe(df_original.head(), use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao ler o arquivo. Certifique-se que o formato é Excel (.xlsx) ou CSV. Erro: {e}")
        st.stop()

    # Botão de Processamento
    st.header("2. Iniciar Processamento e Filtro")
    if st.button("🚀 Processar Dados e Preparar Disparos"):

        # Chama a função de processamento
        df_processed, metrics = process_data(df_original)

        # --- Seção de Resultados ---
        st.header("3. Resultados e Disparo (1-Clique)")

        col_met1, col_met2, col_met3 = st.columns(3)
        col_met1.metric("Clientes Originais", metrics['original_count'])
        col_met2.metric("Clientes Removidos (Duplicatas)", metrics['removed_duplicates'])
        col_met3.metric("Clientes Filtrados (Com Compra)", metrics['removed_filter'])

        total_ready = len(df_processed)
        st.subheader(f"Lista Final de Clientes para Disparo ({total_ready} Clientes)")

        if total_ready == 0:
            st.info("Nenhum cliente atendeu aos critérios de abandono e filtro. Nenhum disparo necessário.")
        else:
            st.markdown("---")
            st.markdown("### Clique no botão para abrir o WhatsApp Web/App com a mensagem pronta.")

            # Cria um cabeçalho para a 'tabela'
            col_headers = st.columns([1, 1, 8])
            col_headers[0].markdown("**Nome**")
            col_headers[1].markdown(f"**{COL_FILTER}**")
            col_headers[2].markdown("**Ação (Disparo)**")
            st.markdown("---")  # Separador

            # Itera sobre os clientes processados para criar os botões
            for index, row in df_processed.iterrows():
                # As colunas precisam ser definidas com o mesmo layout
                cols = st.columns([1, 1, 8])

                first_name = row[COL_OUT_NAME]

                # Prepara o número de telefone (remove tudo exceto dígitos)
                phone_raw = str(row[COL_PHONE])
                phone_number = "".join(filter(str.isdigit, phone_raw))

                message_text = row[COL_OUT_MSG]
                filter_value = row[COL_FILTER]

                # Cria o link oficial do WhatsApp
                encoded_message = quote(message_text)
                whatsapp_link = f"https://wa.me/{phone_number}?text={encoded_message}"

                # 1. Exibe os dados
                cols[0].write(first_name)
                cols[1].write(f"{filter_value:.0f}")  # Exibe como número inteiro

                # 2. Cria e exibe o botão (usando HTML/CSS para ter a funcionalidade de link)
                button_label = f"Mandar WhatsApp para {first_name}"
                button_html = f"""
                <a href="{whatsapp_link}" target="_blank" style="
                    display: inline-block; 
                    padding: 8px 12px; 
                    background-color: #25D366; 
                    color: white; 
                    text-align: center; 
                    text-decoration: none; 
                    border-radius: 4px; 
                    border: 1px solid #128C7E;
                    cursor: pointer;
                    white-space: nowrap; /* Impede quebra de linha no botão */
                ">
                {button_label} 💬
                </a>
                """
                cols[2].markdown(button_html, unsafe_allow_html=True)

            st.markdown("---")  # Separador após a lista

            # Botão de Download do arquivo final processado
            csv_data = df_processed.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Arquivo CSV dos Clientes Prontos (Log)",
                data=csv_data,
                file_name='clientes_prontos_para_disparo.csv',
                mime='text/csv',
            )