import streamlit as st
import pandas as pd
import sqlite3
import base64
import pytz
import io
import hashlib
from datetime import datetime
from streamlit_js_eval import get_geolocation, streamlit_js_eval

# --- CONFIGURAÇÃO DE SEGURANÇA ---
st.set_page_config(page_title="PontoPro SaaS Edition", layout="wide", page_icon="🔐")

# Função de segurança simplificada (SHA-256) que não dá erro de instalação
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_password(password, hashed):
    return hash_password(password) == hashed

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('pontopro_final.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS empresas 
                 (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, senha_admin TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                 (id INTEGER PRIMARY KEY, empresa_id INTEGER, nome TEXT, cargo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS presenca 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, func_id INTEGER, empresa_id INTEGER,
                  data TEXT, entrada TEXT, saida TEXT, foto_ent TEXT, foto_sai TEXT, 
                  geo_ent TEXT, geo_sai TEXT, horas_total TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- INTERFACE ---
st.sidebar.title("🏢 PontoPro SaaS")
modulo = st.sidebar.selectbox("Ir para:", ["📲 Terminal do Funcionário", "📊 Painel da Empresa (RH)", "🛠 Admin Master (Você)"])

# Captura a hora do dispositivo do usuário para evitar fraudes
client_time_str = streamlit_js_eval(js_expressions="new Date().toLocaleString('pt-BR')", key="js_time")

# --- MÓDULO 1: TERMINAL ---
if modulo == "📲 Terminal do Funcionário":
    st.title("🕒 Registro de Ponto Digital")
    empresas_df = pd.read_sql("SELECT id, nome FROM empresas", conn)
    if empresas_df.empty:
        st.error("Nenhuma empresa cadastrada.")
    else:
        emp_nome = st.selectbox("Selecione sua Empresa", empresas_df['nome'].tolist())
        emp_id = int(empresas_df[empresas_df['nome'] == emp_nome]['id'].values[0])
        loc = get_geolocation()
        if not loc:
            st.warning("📍 O GPS é obrigatório para registrar o ponto.")
        else:
            lat_long = f"{loc['coords']['latitude']}, {loc['coords']['longitude']}"
            id_func = st.number_input("Digite seu ID de Funcionário", min_value=1, step=1)
            user = pd.read_sql(f"SELECT * FROM funcionarios WHERE id={id_func} AND empresa_id={emp_id}", conn)
            if not user.empty:
                st.success(f"Olá, {user.iloc[0]['nome']}")
                foto = st.camera_input("Validação Facial")
                if foto:
                    img_b64 = base64.b64encode(foto.getvalue()).decode()
                    data_hoje = datetime.now().strftime("%Y-%m-%d")
                    agora_hora = datetime.now().strftime("%H:%M:%S")
                    reg = pd.read_sql(f"SELECT * FROM presenca WHERE func_id={id_func} AND data='{data_hoje}'", conn)
                    c1, c2 = st.columns(2)
                    if reg.empty:
                        if c1.button("📥 ENTRADA", use_container_width=True):
                            conn.execute("INSERT INTO presenca (func_id, empresa_id, data, entrada, saida, foto_ent, geo_ent) VALUES (?,?,?,?,?,?,?)",
                                        (id_func, emp_id, data_hoje, agora_hora, "---", img_b64, lat_long))
                            conn.commit()
                            st.balloons()
                            st.rerun()
                    elif reg.iloc[0]['saida'] == "---":
                        if c2.button("📤 SAÍDA", use_container_width=True):
                            conn.execute("UPDATE presenca SET saida=?, foto_sai=?, geo_sai=? WHERE id=?",
                                        (agora_hora, img_b64, lat_long, int(reg.iloc[0]['id'])))
                            conn.commit()
                            st.snow()
                            st.rerun()
            else: st.error("Funcionário não encontrado.")

# --- MÓDULO 2: PAINEL DA EMPRESA (RH) ---
elif modulo == "📊 Painel da Empresa (RH)":
    st.title("📊 Gestão de Equipe")
    empresas_df = pd.read_sql("SELECT id, nome, senha_admin FROM empresas", conn)
    if not empresas_df.empty:
        emp_nome = st.sidebar.selectbox("Sua Empresa", empresas_df['nome'].tolist())
        senha_tentativa = st.sidebar.text_input("Senha RH", type="password")
        if senha_tentativa:
            emp_data = empresas_df[empresas_df['nome'] == emp_nome].iloc[0]
            if check_password(senha_tentativa, emp_data['senha_admin']):
                emp_id = emp_data['id']
                t1, t2 = st.tabs(["📝 Relatórios", "👥 Cadastrar"])
                with t1:
                    df_logs = pd.read_sql(f"SELECT p.*, f.nome FROM presenca p JOIN funcionarios f ON p.func_id = f.id WHERE p.empresa_id = {emp_id}", conn)
                    st.dataframe(df_logs)
                with t2:
                    with st.form("add"):
                        f_id = st.number_input("ID", min_value=1)
                        f_nome = st.text_input("Nome")
                        if st.form_submit_button("Salvar"):
                            conn.execute("INSERT INTO funcionarios (id, empresa_id, nome, cargo) VALUES (?,?,?,?)",(f_id, emp_id, f_nome, ""))
                            conn.commit()
                            st.success("Salvo!")
            else: st.error("Senha incorreta.")

# --- MÓDULO 3: ADMIN MASTER ---
elif modulo == "🛠 Admin Master (Você)":
    st.title("🛡 Painel Master")
    master_pass = st.text_input("Senha Mestra", type="password")
    if master_pass == "suasenhamestra123":
        with st.form("nova"):
            e_nome = st.text_input("Empresa")
            e_senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Ativar"):
                conn.execute("INSERT INTO empresas (nome, cnpj, senha_admin) VALUES (?,?,?)", (e_nome, "", hash_password(e_senha)))
                conn.commit()
                st.success("Ativada!")
        st.table(pd.read_sql("SELECT id, nome FROM empresas", conn))
        
