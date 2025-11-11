import streamlit as st
import pandas as pd
from urllib.parse import quote
import io

# --- Configurações da Aplicação ---
st.set_page_config(layout="wide", page_title="Processador de Clientes de Vendas Prioritárias")

st.title("🎯 Qualificação para Time de Vendas (Jumbo CDP)")
st.markdown("Filtra clientes **novos** que possuem **apenas** o status 'Pedido salvo'.")

# --- Definição das Colunas ---
COL_ID = 'Codigo Cliente'
COL_NAME = 'Cliente'
COL_PHONE = 'Fone Fixo'
COL_STATUS = 'Status' 
# Nome exato da coluna de contagem
COL_FILTER = 'Quant. Pedidos Enviados' 

# Colunas de SAÍDA
COL_OUT_NAME = 'Cliente_Formatado'
COL_OUT_MSG = 'Mensagem_Personalizada'

# --- Função de Lógica de Negócio (O Cérebro) ---

@st.cache_data
def process_data(df_input):
    """
    Executa a limpeza, filtro (apenas clientes com status exclusivo 'Pedido salvo' E Quant. Pedidos Enviados == 0) e personalização.
    """
    df = df_input.copy() 
    
    # 1. Checagem de colunas obrigatórias
    required_cols = [COL_ID, COL_NAME, COL_PHONE, COL_STATUS, COL_FILTER]
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        raise ValueError(f"O arquivo está faltando as seguintes colunas obrigatórias: {', '.join(missing)}")

    metrics = {
        'original_count': len(df),
        'removed_duplicates': 0,
        'removed_filter': 0
    }

    # Garante que a coluna de contagem é numérica (tratando erros)
    df[COL_FILTER] = pd.to_numeric(df[COL_FILTER], errors='coerce').fillna(-1) 
    
    # 2. --- FILTRO 1: EXCLUSIVIDADE DE STATUS ('PEDIDO SALVO') ---
    
    # Identifica clientes que têm PELO MENOS UM status diferente de 'Pedido salvo'.
    tem_outro_status = df[COL_STATUS] != 'Pedido Salvo'
    
    # Agrupa por Codigo Cliente e verifica se HÁ alguma linha True.
    clientes_com_outro_status = df.groupby(COL_ID)[tem_outro_status].transform('any')
    
    # 3. --- FILTRO 2: CLIENTE NOVO (QUANTIDADE DE PEDIDOS ENVIADOS == 0) ---
    
    df_qualified = df[
        # A linha atual deve ser 'Pedido Salvo'
        (df[COL_STATUS] == 'Pedido Salvo') & 
        
        # O cliente (Codigo Cliente) NÃO pode ter tido NENHUM outro status (exclusividade)
        (~clientes_com_outro_status) & 
        
        # A contagem de pedidos enviados deve ser 0 (garantindo que é um cliente novo/tentativa)
        (df[COL_FILTER] == 0) 
    ]
        
    metrics['removed_filter'] = len(df_input) - len(df_qualified)
    
    # --- CORREÇÕES DE ERRO DE ALINHAMENTO E VAZIO ---
    
    # A. Eliminar Duplicatas (mantém uma linha por Codigo Cliente)
    df_unique = df_qualified.drop_duplicates(subset=[COL_ID], keep='first')
    metrics['removed_duplicates'] = len(df_qualified) - len(df_unique)
    df = df_unique
    
    # B. Redefine o índice para evitar desalinhamento após filtragem (solução do ValueError)
    df = df.reset_index(drop=True)
    
    # C. CHECAGEM DE SEGURANÇA: Retorna imediatamente se não houver leads (solução do Length mismatch)
    if df.empty:
        return df, metrics 
    
    # --------------------------------------------------

    # 4. Criar mensagem personalizada
    
    def format_name_and_create_message(full_name):
        """Formata o nome e cria a mensagem."""
        if not full_name:
            first_name = "Cliente"
        else:
            first_name = str(full_name).strip().split(' ')[0] 
            first_name = first_name.capitalize() 
            
        # --- TEMPLATE DA MENSAGEM DE VENDAS ---
        message = (
            f"Olá {first_name}! Aqui é a Sofia da Jumbo CDP! 👋\n\n"
            f"Vimos que você iniciou seu cadastro, mas não conseguiu finalizar sua compra na Jumbo CDP, por isso tenho uma ótima notícia para você:\n\n"
            f"*Consegui um DESCONTO EXTRA de 3%% no PIX* no valor total do seu pedido! 🎁\n\n"
            f"Sabemos que pontos como a *carteirinha de visitante* ou os *dados do detento* costumam gerar dúvidas.\n\n"
            f"Para que eu possa *ativar seu desconto e te enviar o passo a passo* para resolver isso de forma rápida, qual foi o principal *obstáculo* que você encontrou no site?"
        )
        # ----------------------------------
        
        return first_name, message

    # --- CORREÇÃO DE ERRO DE ATRIBUIÇÃO (KEYERROR) ---
    
    # Garante que a coluna de nome é string
    df[COL_NAME] = df[COL_NAME].astype(str).fillna('')
    
    # Cria a Series com as tuplas
    data_series = df[COL_NAME].apply(format_name_and_create_message)

    # Cria o DataFrame temporário (colunas nomeadas 0 e 1)
    temp_df = pd.DataFrame(data_series.tolist()) 
    
    # Atribui as colunas (0 e 1) individualmente
    df[COL_OUT_NAME] = temp_df[0]
    df[COL_OUT_MSG] = temp_df[1]
    # ---------------------------------------------------
    
    return df, metrics

# --- Interface do Usuário (Streamlit) ---

# Seção de Upload
st.header("1. Upload do Relatório de Vendas (Excel/CSV)")
st.markdown(f"#### Colunas Esperadas: {COL_ID}, {COL_NAME}, {COL_PHONE}, {COL_STATUS}, {COL_FILTER}")

uploaded_file = st.file_uploader(
    "Arraste ou clique para enviar o arquivo.", 
    type=["csv", "xlsx"]
)

if uploaded_file is not None:
    # Carrega o arquivo
    try:
        if uploaded_file.name.endswith('.csv'):
            df_original = pd.read_csv(uploaded_file)
        else:
            # Tenta ler o excel com a dependência openpyxl
            df_original = pd.read_excel(uploaded_file, engine='openpyxl')
            
        st.success(f"Arquivo '{uploaded_file.name}' carregado com sucesso!")
        
    except Exception as e:
        if 'openpyxl' in str(e):
             st.error("Erro ao ler o arquivo Excel (.xlsx). Certifique-se de que a biblioteca 'openpyxl' está instalada no ambiente de execução do seu aplicativo (via requirements.txt).")
        else:
            st.error(f"Erro ao ler o arquivo. Erro: {e}")
        st.stop()


    # Botão de Processamento
    st.header("2. Iniciar Qualificação de Vendas")
    if st.button("🚀 Processar Dados e Gerar Leads Prioritários"):
        
        try:
            df_processed, metrics = process_data(df_original)
        except ValueError as ve:
            st.error(f"Erro de Processamento: {ve}")
            st.stop()
        
        # --- Seção de Resultados ---
        st.header("3. Lista de Disparo com Condição Especial (1-Clique)")
        
        col_met1, col_met2, col_met3 = st.columns(3)
        col_met1.metric("Clientes Originais", metrics['original_count'])
        col_met2.metric("Removidos (Duplicatas)", metrics['removed_duplicates'])
        col_met3.metric("Removidos (Outros Status/Filtro)", metrics['removed_filter'])
        
        total_ready = len(df_processed)
        st.subheader(f"Leads Prioritários para Vendas ({total_ready} Clientes)")
        
        if total_ready == 0:
            st.info("Nenhum lead encontrado com o perfil: Apenas 'Pedido Salvo' E 'Quant. Pedidos Enviados' == 0.")
        else:
            st.markdown("---")
            st.markdown("#### Clique no botão para iniciar o contato de vendas no WhatsApp.")
            
            # Cria o layout da tabela de botões
            col_headers = st.columns([1.5, 1.5, 7]) 
            col_headers[0].markdown("**Nome**")
            col_headers[1].markdown(f"**{COL_FILTER}**") 
            col_headers[2].markdown("**Ação (Disparo de Vendas)**")
            st.markdown("---")
            
            # Itera sobre os leads qualificados
            for index, row in df_processed.iterrows():
                cols = st.columns([1.5, 1.5, 7]) 
                
                first_name = row[COL_OUT_NAME]
                
                # Prepara o número de telefone (remove tudo exceto dígitos)
                # Tenta usar Celular, senão usa Fone Fixo
                phone_raw = str(row.get('Celular') or row[COL_PHONE])
                phone_number = "".join(filter(str.isdigit, phone_raw))

                message_text = row[COL_OUT_MSG]
                filter_value = row[COL_FILTER]
                
                # Cria o link oficial do WhatsApp, codificando a mensagem
                encoded_message = quote(message_text)
                whatsapp_link = f"https://wa.me/55{phone_number}?text={encoded_message}"
                
                # 1. Exibe os dados
                cols[0].write(first_name)
                cols[1].write(f"{filter_value:.0f}")
                
                # 2. Cria e exibe o botão
                button_label = f"WhatsApp para {first_name}"
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
                    white-space: nowrap;
                ">
                {button_label} 💬
                </a>
                """
                cols[2].markdown(button_html, unsafe_allow_html=True)

            st.markdown("---")

            # Botão de Download
            csv_data = df_processed.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Lista de Leads Qualificados (CSV)",
                data=csv_data,
                file_name='leads_qualificados_para_vendas.csv',
                mime='text/csv',
            )
