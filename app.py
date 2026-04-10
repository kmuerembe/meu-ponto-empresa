import streamlit as st
import pandas as pd
import sqlite3
import base64
import pytz
import io
import bcrypt
from datetime import datetime
from streamlit_js_eval import get_geolocation, streamlit_js_eval

# --- CONFIGURAÇÃO DE SEGURANÇA E INTERFACE ---
st.set_page_config(page_title="PontoPro SaaS Edition", layout="wide", page_icon="🔐")

# Estilização Profissional
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    div.stButton > button:first-child { background-color: #00416A; color: white; border-radius: 10px; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    </style>
    """, unsafe_allow_html=True)

# --- BANCO DE DADOS ROBUSTO ---
def init_db():
    conn = sqlite3.connect('pontopro_ultimate.db', check_same_thread=False)
    c = conn.cursor()
    # Tabela de Empresas (Seus Clientes)
    c.execute('''CREATE TABLE IF NOT EXISTS empresas 
                 (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, senha_admin TEXT)''')
    # Tabela de Funcionários
    c.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                 (id INTEGER PRIMARY KEY, empresa_id INTEGER, nome TEXT, cargo TEXT, 
                  FOREIGN KEY(empresa_id) REFERENCES empresas(id))''')
    # Tabela de Presença (O Core)
    c.execute('''CREATE TABLE IF NOT EXISTS presenca 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, func_id INTEGER, empresa_id INTEGER,
                  data TEXT, entrada TEXT, saida TEXT, foto_ent TEXT, foto_sai TEXT, 
                  geo_ent TEXT, geo_sai TEXT, horas_total TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- FUNÇÕES DE SEGURANÇA ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# --- CAPTURA DE HORA LOCAL AUTOMÁTICA ---
# Captura a hora do dispositivo do usuário para evitar fraudes de fuso horário do servidor
client_time_str = streamlit_js_eval(js_expressions="new Date().toLocaleString('pt-BR')", key="js_time")

# --- NAVEGAÇÃO ---
st.sidebar.title("🏢 PontoPro SaaS")
modulo = st.sidebar.selectbox("Ir para:", ["📲 Terminal do Funcionário", "📊 Painel da Empresa (RH)", "🛠 Admin Master (Você)"])

# ----------------------------------------------------------------
# MÓDULO 1: TERMINAL DO FUNCIONÁRIO (O que fica no Tablet/Celular)
# ----------------------------------------------------------------
if modulo == "📲 Terminal do Funcionário":
    st.title("🕒 Registro de Ponto Digital")
    
    # 1. Seleção de Empresa (O funcionário escolhe a empresa dele)
    empresas_df = pd.read_sql("SELECT id, nome FROM empresas", conn)
    if empresas_df.empty:
        st.error("Nenhuma empresa cadastrada no sistema.")
    else:
        lista_empresas = empresas_df['nome'].tolist()
        emp_nome = st.selectbox("Selecione sua Empresa", lista_empresas)
        emp_id = int(empresas_df[empresas_df['nome'] == emp_nome]['id'].values[0])

        # 2. Localização Automática
        loc = get_geolocation()
        if not loc:
            st.warning("📍 O GPS é obrigatório. Por favor, autorize a localização no navegador.")
        else:
            lat_long = f"{loc['coords']['latitude']}, {loc['coords']['longitude']}"
            
            col1, col2 = st.columns(2)
            with col1:
                id_func = st.number_input("Digite seu ID de Funcionário", min_value=1, step=1)
                user = pd.read_sql(f"SELECT * FROM funcionarios WHERE id={id_func} AND empresa_id={emp_id}", conn)
                
                if not user.empty:
                    st.success(f"Bem-vindo, **{user.iloc[0]['nome']}**")
                    st.write(f"⏰ **Hora confirmada:** {client_time_str}")
                    
                    foto = st.camera_input("Reconhecimento Facial")
                    if foto:
                        img_b64 = base64.b64encode(foto.getvalue()).decode()
                        data_hoje = datetime.now().strftime("%Y-%m-%d")
                        agora_hora = datetime.now().strftime("%H:%M:%S")

                        # Lógica de Entrada/Saída
                        reg = pd.read_sql(f"SELECT * FROM presenca WHERE func_id={id_func} AND data='{data_hoje}'", conn)
                        
                        btn_col1, btn_col2 = st.columns(2)
                        if reg.empty:
                            if btn_col1.button("📥 REGISTRAR ENTRADA", use_container_width=True):
                                conn.execute("INSERT INTO presenca (func_id, empresa_id, data, entrada, saida, foto_ent, geo_ent) VALUES (?,?,?,?,?,?,?)",
                                            (id_func, emp_id, data_hoje, agora_hora, "---", img_b64, lat_long))
                                conn.commit()
                                st.balloons()
                                st.rerun()
                        elif reg.iloc[0]['saida'] == "---":
                            if btn_col2.button("📤 REGISTRAR SAÍDA", use_container_width=True):
                                conn.execute("UPDATE presenca SET saida=?, foto_sai=?, geo_sai=? WHERE id=?",
                                            (agora_hora, img_b64, lat_long, int(reg.iloc[0]['id'])))
                                conn.commit()
                                st.snow()
                                st.rerun()
                        else:
                            st.info("✅ Jornada de hoje concluída!")

# ----------------------------------------------------------------
# MÓDULO 2: PAINEL DA EMPRESA (O que você vende para o dono da empresa)
# ----------------------------------------------------------------
elif modulo == "📊 Painel da Empresa (RH)":
    st.title("📊 Gestão de Equipe")
    
    empresas_df = pd.read_sql("SELECT id, nome, senha_admin FROM empresas", conn)
    emp_nome = st.sidebar.selectbox("Sua Empresa", empresas_df['nome'].tolist())
    senha_tentativa = st.sidebar.text_input("Senha RH", type="password")
    
    if senha_tentativa:
        emp_data = empresas_df[empresas_df['nome'] == emp_nome].iloc[0]
        if check_password(senha_tentativa, emp_data['senha_admin']):
            emp_id = emp_data['id']
            
            tab1, tab2, tab3 = st.tabs(["📝 Relatórios de Ponto", "👥 Cadastrar Funcionários", "📈 Insights"])
            
            with tab1:
                df_logs = pd.read_sql(f"""SELECT p.*, f.nome FROM presenca p 
                                         JOIN funcionarios f ON p.func_id = f.id 
                                         WHERE p.empresa_id = {emp_id}""", conn)
                
                if not df_logs.empty:
                    # Filtro por mês
                    df_logs['data'] = pd.to_datetime(df_logs['data'])
                    mes_sel = st.selectbox("Selecione o Mês", df_logs['data'].dt.strftime('%m/%Y').unique())
                    df_filtrado = df_logs[df_logs['data'].dt.strftime('%m/%Y') == mes_sel]
                    
                    st.dataframe(df_filtrado[['nome', 'data', 'entrada', 'saida', 'geo_ent']], use_container_width=True)
                    
                    # EXPORTAÇÃO EXCEL PROFISSIONAL
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_filtrado.to_excel(writer, index=False, sheet_name='Ponto')
                    st.download_button("📥 Baixar Excel Mensal", output.getvalue(), f"Ponto_{emp_nome}_{mes_sel}.xlsx")
                
            with tab2:
                with st.form("add_func"):
                    f_id = st.number_input("ID do Crachá", min_value=1)
                    f_nome = st.text_input("Nome do Colaborador")
                    f_cargo = st.text_input("Cargo")
                    if st.form_submit_button("Cadastrar Funcionário"):
                        conn.execute("INSERT INTO funcionarios (id, empresa_id, nome, cargo) VALUES (?,?,?,?)",
                                    (f_id, emp_id, f_nome, f_cargo))
                        conn.commit()
                        st.success("Cadastrado!")
        else:
            st.error("Senha incorreta.")

# ----------------------------------------------------------------
# MÓDULO 3: ADMIN MASTER (SÓ VOCÊ ENTRA AQUI)
# ----------------------------------------------------------------
elif modulo == "🛠 Admin Master (Você)":
    st.title("🛡 Painel de Controle do Desenvolvedor")
    master_pass = st.text_input("Senha Mestra", type="password")
    
    if master_pass == "suasenhamestra123":
        st.subheader("Cadastrar Nova Empresa Cliente")
        with st.form("nova_empresa"):
            e_nome = st.text_input("Nome da Empresa")
            e_cnpj = st.text_input("CNPJ")
            e_senha = st.text_input("Definir Senha Admin da Empresa", type="password")
            if st.form_submit_button("Ativar Empresa"):
                hash_s = hash_password(e_senha)
                conn.execute("INSERT INTO empresas (nome, cnpj, senha_admin) VALUES (?,?,?)",
                            (e_nome, e_cnpj, hash_s))
                conn.commit()
                st.success(f"Empresa {e_nome} ativada com sucesso!")
        
        st.subheader("Empresas na Base")
        st.table(pd.read_sql("SELECT id, nome, cnpj FROM empresas", conn))
