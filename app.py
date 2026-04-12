import streamlit as st
import pandas as pd
import sqlite3
import base64
import pytz
import io
import hashlib
from datetime import datetime
from streamlit_js_eval import get_geolocation, streamlit_js_eval

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="PontoPro Pro SaaS", layout="wide", page_icon="🔐")

# Função de segurança
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_password(password, hashed):
    return hash_password(password) == hashed

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('pontopro_final.db', check_same_thread=False)
    c = conn.cursor()
    # Adicionamos 'codigo_acesso' para as empresas
    c.execute('''CREATE TABLE IF NOT EXISTS empresas 
                 (id INTEGER PRIMARY KEY, nome TEXT, codigo_acesso TEXT, senha_admin TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                 (id_cracha INTEGER, empresa_id INTEGER, nome TEXT, cargo TEXT, 
                  PRIMARY KEY (id_cracha, empresa_id))''') # Chave dupla para IDs iguais em empresas diferentes
    c.execute('''CREATE TABLE IF NOT EXISTS presenca 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, func_id INTEGER, empresa_id INTEGER,
                  data TEXT, entrada TEXT, saida TEXT, foto_ent TEXT, foto_sai TEXT, 
                  geo_ent TEXT, geo_sai TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- INTERFACE ---
st.sidebar.title("🌍 PontoPro v3.0")
modulo = st.sidebar.selectbox("Escolha o Acesso:", ["🕒 Terminal do Funcionário", "📊 Painel do RH (Empresa)", "⚙️ Admin Master (Você)"])

# Captura hora local
client_time = streamlit_js_eval(js_expressions="new Date().toLocaleString('pt-BR')", key="js_time")

# --- MÓDULO 1: TERMINAL DO FUNCIONÁRIO ---
if modulo == "🕒 Terminal do Funcionário":
    st.title("🕒 Registro de Ponto")
    
    col_a, col_b = st.columns(2)
    with col_a:
        cod_empresa = st.text_input("Código da Empresa (Solicite ao seu RH)")
    with col_b:
        id_func = st.number_input("Seu ID de Funcionário", min_value=1, step=1)

    if cod_empresa and id_func:
        # Busca a empresa pelo código (Protege a privacidade)
        empresa = pd.read_sql("SELECT * FROM empresas WHERE codigo_acesso = ?", conn, params=(cod_empresa,))
        
        if not empresa.empty:
            emp_id = int(empresa.iloc[0]['id'])
            # Busca o funcionário dentro daquela empresa específica
            user = pd.read_sql("SELECT * FROM funcionarios WHERE id_cracha = ? AND empresa_id = ?", 
                               conn, params=(id_func, emp_id))
            
            if not user.empty:
                st.success(f"Olá, **{user.iloc[0]['nome']}** ({user.iloc[0]['cargo']})")
                
                loc = get_geolocation()
                if not loc:
                    st.warning("📍 Ative o GPS para registrar o ponto.")
                else:
                    lat_long = f"{loc['coords']['latitude']}, {loc['coords']['longitude']}"
                    foto = st.camera_input("Foto de Verificação")
                    
                    if foto:
                        img_b64 = base64.b64encode(foto.getvalue()).decode()
                        data_hoje = datetime.now().strftime("%Y-%m-%d")
                        agora_hora = datetime.now().strftime("%H:%M:%S")
                        
                        reg = pd.read_sql("SELECT * FROM presenca WHERE func_id=? AND empresa_id=? AND data=?", 
                                         conn, params=(id_func, emp_id, data_hoje))
                        
                        c1, c2 = st.columns(2)
                        if reg.empty:
                            if c1.button("📥 REGISTRAR ENTRADA", use_container_width=True):
                                conn.execute("INSERT INTO presenca (func_id, empresa_id, data, entrada, saida, foto_ent, geo_ent) VALUES (?,?,?,?,?,?,?)",
                                            (id_func, emp_id, data_hoje, agora_hora, "---", img_b64, lat_long))
                                conn.commit()
                                st.balloons()
                                st.rerun()
                        elif reg.iloc[0]['saida'] == "---":
                            if c2.button("📤 REGISTRAR SAÍDA", use_container_width=True):
                                conn.execute("UPDATE presenca SET saida=?, foto_sai=?, geo_sai=? WHERE func_id=? AND empresa_id=? AND data=?",
                                            (agora_hora, img_b64, lat_long, id_func, emp_id, data_hoje))
                                conn.commit()
                                st.snow()
                                st.rerun()
                        else:
                            st.info("✅ Ponto de hoje já concluído.")
            else:
                st.error("Funcionário não encontrado nesta empresa.")
        else:
            st.error("Código de empresa inválido.")

# --- MÓDULO 2: PAINEL DO RH ---
elif modulo == "📊 Painel do RH (Empresa)":
    st.title("📊 Gestão de RH")
    
    # Login por Código de Acesso
    cod_rh = st.sidebar.text_input("Código de Acesso da Empresa")
    senha_rh = st.sidebar.text_input("Senha Admin", type="password")
    
    if cod_rh and senha_rh:
        emp_check = pd.read_sql("SELECT * FROM empresas WHERE codigo_acesso = ?", conn, params=(cod_rh,))
        if not emp_check.empty and check_password(senha_rh, emp_check.iloc[0]['senha_admin']):
            emp_id = int(emp_check.iloc[0]['id'])
            emp_nome = emp_check.iloc[0]['nome']
            
            st.sidebar.success(f"Conectado: {emp_nome}")
            
            tab1, tab2 = st.tabs(["📝 Relatório de Presença", "👥 Cadastrar Funcionário"])
            
            with tab1:
                st.subheader(f"Registros de {emp_nome}")
                logs = pd.read_sql(f"""SELECT p.data, f.nome, f.cargo, p.entrada, p.saida, p.geo_ent 
                                       FROM presenca p JOIN funcionarios f ON p.func_id = f.id_cracha 
                                       WHERE p.empresa_id = {emp_id} AND f.empresa_id = {emp_id}""", conn)
                st.dataframe(logs, use_container_width=True)
                
            with tab2:
                with st.form("add_func"):
                    new_f_id = st.number_input("ID do Crachá (Ex: 1, 2, 3)", min_value=1)
                    new_f_nome = st.text_input("Nome Completo")
                    new_f_cargo = st.text_input("Cargo")
                    if st.form_submit_button("Cadastrar Funcionário"):
                        try:
                            conn.execute("INSERT INTO funcionarios (id_cracha, empresa_id, nome, cargo) VALUES (?,?,?,?)",
                                        (new_f_id, emp_id, new_f_nome, new_f_cargo))
                            conn.commit()
                            st.success(f"Funcionário {new_f_nome} cadastrado!")
                        except:
                            st.error("Este ID já está em uso nesta empresa.")
        else:
            st.error("Acesso negado. Verifique o código e a senha.")

# --- MÓDULO 3: ADMIN MASTER (VOCÊ) ---
elif modulo == "⚙️ Admin Master (Você)":
    st.title("⚙️ Painel do Desenvolvedor")
    master_pass = st.text_input("Senha Mestra", type="password")
    
    if master_pass == "suasenhamestra123":
        st.subheader("Cadastrar Nova Empresa Cliente")
        with st.form("nova_emp"):
            e_nome = st.text_input("Nome da Empresa")
            e_codigo = st.text_input("Código de Acesso Único (Ex: EMP01)")
            e_senha = st.text_input("Senha da Empresa", type="password")
            if st.form_submit_button("Ativar Empresa"):
                conn.execute("INSERT INTO empresas (nome, codigo_acesso, senha_admin) VALUES (?,?,?)",
                            (e_nome, e_codigo, hash_password(e_senha)))
                conn.commit()
                st.success(f"Empresa {e_nome} ativada! Código: {e_codigo}")
        
        st.subheader("Empresas Ativas")
        st.dataframe(pd.read_sql("SELECT id, nome, codigo_acesso FROM empresas", conn))
