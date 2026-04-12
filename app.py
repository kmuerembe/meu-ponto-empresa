import streamlit as st
import pandas as pd
import sqlite3
import base64
import io
import hashlib
from datetime import datetime, timedelta
from streamlit_js_eval import get_geolocation, streamlit_js_eval

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="PontoPro Enterprise v4", layout="wide", page_icon="🔐")

# --- CSS PROFISSIONAL (TEMA DARK/LIGHT) ---
st.markdown("""
    <style>
    .main { background-color: #f4f7f6; }
    [data-testid="stMetricValue"] { font-size: 24px; color: #004a99; }
    .stButton>button { border-radius: 5px; height: 3em; width: 100%; }
    .status-active { color: green; font-weight: bold; }
    .status-inactive { color: red; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE SEGURANÇA ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('pontopro_enterprise.db', check_same_thread=False)
    c = conn.cursor()
    # Tabela de Empresas (Seus Clientes)
    c.execute('''CREATE TABLE IF NOT EXISTS empresas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, codigo TEXT UNIQUE, senha TEXT)''')
    # Tabela de Funcionários
    c.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                 (id_f INTEGER, empresa_id INTEGER, nome TEXT, cargo TEXT, depto TEXT, 
                  email TEXT, status TEXT, jornada_inicio TEXT, jornada_fim TEXT, 
                  PRIMARY KEY(id_f, empresa_id))''')
    # Tabela de Presença
    c.execute('''CREATE TABLE IF NOT EXISTS presenca 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, func_id INTEGER, empresa_id INTEGER,
                  data TEXT, entrada TEXT, saída TEXT, foto TEXT, lat_long TEXT, 
                  atraso TEXT, extra TEXT)''')
    # Tabela de Justificativas e Férias
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, func_id INTEGER, empresa_id INTEGER,
                  tipo TEXT, data_inicio TEXT, data_fim TEXT, status TEXT, motivo TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- CAPTURA DE HORA DO CLIENTE (MOÇAMBIQUE / GLOBAL) ---
js_time = streamlit_js_eval(js_expressions="new Date().toLocaleString('pt-BR')", key="js_clock")
if js_time:
    try:
        data_local = js_time.split(', ')[0]
        hora_local = js_time.split(', ')[1]
        d, m, y = data_local.split('/')
        data_db = f"{y}-{m}-{d}"
    except:
        data_db = datetime.now().strftime("%Y-%m-%d")
        hora_local = datetime.now().strftime("%H:%M:%S")
else:
    data_db = datetime.now().strftime("%Y-%m-%d")
    hora_local = datetime.now().strftime("%H:%M:%S")

# --- NAVEGAÇÃO ---
st.sidebar.title("🏢 PontoPro Enterprise")
st.sidebar.markdown(f"**Data:** {data_db} \n\n **Hora:** {hora_local}")
modulo = st.sidebar.radio("Módulos:", ["🏠 Dashboard / Ponto", "📊 Gestão RH", "📅 Férias & Justificativas", "⚙️ Admin Master"])

# --- MODULO 1: DASHBOARD E REGISTRO DE PONTO ---
if modulo == "🏠 Dashboard / Ponto":
    st.title("⏱️ Terminal de Presença")
    
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        st.subheader("Registrar Ponto")
        cod_emp = st.text_input("Código da Empresa")
        id_f = st.number_input("ID do Funcionário", min_value=1, step=1)
        
        if cod_emp and id_f:
            emp_data = pd.read_sql("SELECT * FROM empresas WHERE codigo = ?", conn, params=(cod_emp,))
            if not emp_data.empty:
                e_id = int(emp_data.iloc[0]['id'])
                user = pd.read_sql("SELECT * FROM funcionarios WHERE id_f = ? AND empresa_id = ?", conn, params=(id_f, e_id))
                
                if not user.empty:
                    st.success(f"**{user.iloc[0]['nome']}**")
                    loc = get_geolocation()
                    foto = st.camera_input("Biometria Facial")
                    
                    if foto and loc:
                        coords = f"{loc['coords']['latitude']}, {loc['coords']['longitude']}"
                        img_b64 = base64.b64encode(foto.getvalue()).decode()
                        
                        # Lógica de Horários (Atraso/Extra)
                        h_inicio = user.iloc[0]['jornada_inicio']
                        atraso = "Não"
                        if hora_local > h_inicio:
                            atraso = "Sim"

                        reg = pd.read_sql("SELECT * FROM presenca WHERE func_id=? AND empresa_id=? AND data=?", conn, params=(id_f, e_id, data_db))
                        
                        btn_c1, btn_c2 = st.columns(2)
                        if reg.empty:
                            if btn_c1.button("📥 ENTRADA"):
                                conn.execute("INSERT INTO presenca (func_id, empresa_id, data, entrada, saída, foto, lat_long, atraso, extra) VALUES (?,?,?,?,?,?,?,?,?)",
                                            (id_f, e_id, data_db, hora_local, "---", img_b64, coords, atraso, "0"))
                                conn.commit()
                                st.rerun()
                        elif reg.iloc[0]['saída'] == "---":
                            if btn_c2.button("📤 SAÍDA"):
                                conn.execute("UPDATE presenca SET saída=?, foto=?, lat_long=? WHERE func_id=? AND empresa_id=? AND data=?",
                                            (hora_local, img_b64, coords, id_f, e_id, data_db))
                                conn.commit()
                                st.rerun()
                else: st.error("Funcionário não encontrado.")
    
    with col_b:
        st.subheader("Meu Painel")
        if id_f > 0 and cod_emp:
             # Histórico Simplificado
             hist = pd.read_sql(f"SELECT data, entrada, saída FROM presenca WHERE func_id={id_f} ORDER BY id DESC LIMIT 5", conn)
             st.write("Últimos registros:")
             st.table(hist)

# --- MODULO 2: GESTÃO RH (PARA A EMPRESA) ---
elif modulo == "📊 Gestão RH":
    st.title("📊 Painel de Controle Administrativo")
    cod_rh = st.sidebar.text_input("Código Empresa")
    pass_rh = st.sidebar.text_input("Senha", type="password")
    
    if cod_rh and pass_rh:
        emp = pd.read_sql("SELECT * FROM empresas WHERE codigo = ?", conn, params=(cod_rh,))
        if not emp.empty and hash_password(pass_rh) == emp.iloc[0]['senha']:
            e_id = int(emp.iloc[0]['id'])
            
            tab1, tab2, tab3 = st.tabs(["👥 Funcionários", "📋 Relatórios", "📈 Dashboard"])
            
            with tab1:
                with st.expander("Cadastrar Novo Funcionário"):
                    with st.form("cad_func"):
                        f_id = st.number_input("ID", min_value=1)
                        f_nome = st.text_input("Nome Completo")
                        f_cargo = st.text_input("Cargo")
                        f_inicio = st.text_input("Início Jornada (Ex: 08:00:00)")
                        if st.form_submit_button("Cadastrar"):
                            conn.execute("INSERT INTO funcionarios (id_f, empresa_id, nome, cargo, status, jornada_inicio) VALUES (?,?,?,?,?,?)",
                                        (f_id, e_id, f_nome, f_cargo, "Ativo", f_inicio))
                            conn.commit()
                            st.success("Cadastrado!")
                st.write("Lista de Equipe")
                st.dataframe(pd.read_sql(f"SELECT id_f, nome, cargo, status FROM funcionarios WHERE empresa_id={e_id}", conn))

            with tab2:
                st.subheader("Extração de Dados")
                logs = pd.read_sql(f"SELECT * FROM presenca WHERE empresa_id={e_id}", conn)
                st.dataframe(logs)
                # Exportação Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    logs.to_excel(writer, index=False)
                st.download_button("📥 Baixar Relatório Excel", output.getvalue(), "relatorio_ponto.xlsx")

            with tab3:
                # Dashboard Admin
                total_f = len(pd.read_sql(f"SELECT * FROM funcionarios WHERE empresa_id={e_id}", conn))
                presentes = len(pd.read_sql(f"SELECT * FROM presenca WHERE empresa_id={e_id} AND data='{data_db}'", conn))
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Equipe", total_f)
                c2.metric("Presentes Hoje", presentes)
                c3.metric("Faltas", total_f - presentes)

# --- MODULO 3: ADMIN MASTER (VOCÊ) ---
elif modulo == "⚙️ Admin Master":
    st.title("🛡️ Sistema SaaS - Gestão de Clientes")
    senha_m = st.text_input("Senha Mestra", type="password")
    
    if senha_m == "suasenhamestra123":
        st.subheader("Cadastrar Nova Empresa Cliente")
        with st.form("nova_emp"):
            nome_e = st.text_input("Nome da Empresa")
            cod_e = st.text_input("Código Único (Ex: EMP01)")
            pass_e = st.text_input("Senha Admin Empresa", type="password")
            if st.form_submit_button("Ativar Empresa"):
                try:
                    conn.execute("INSERT INTO empresas (nome, codigo, senha) VALUES (?,?,?)", 
                                (nome_e, cod_e, hash_password(pass_e)))
                    conn.commit()
                    st.success(f"Empresa {nome_e} ativada com sucesso!")
                except: st.error("Erro: Código já existe.")
        
        st.subheader("Clientes Ativos")
        st.dataframe(pd.read_sql("SELECT id, nome, codigo FROM empresas", conn))
