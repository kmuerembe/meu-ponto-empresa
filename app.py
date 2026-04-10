import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import base64
from streamlit_js_eval import get_geolocation

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="PontoPro Enterprise v3", layout="wide", page_icon="🏢")

# --- GERENCIAMENTO DE BANCO DE DADOS (SQLITE) ---
def init_db():
    conn = sqlite3.connect('ponto_empresa.db', check_same_thread=False)
    c = conn.cursor()
    # Tabela de Funcionários
    c.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                 (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, cargo TEXT, data_criacao TEXT)''')
    # Tabela de Presença
    c.execute('''CREATE TABLE IF NOT EXISTS presenca 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  func_id INTEGER, 
                  data TEXT, 
                  entrada TEXT, 
                  saida TEXT, 
                  foto_entrada TEXT, 
                  foto_saida TEXT, 
                  geo_entrada TEXT, 
                  geo_saida TEXT,
                  FOREIGN KEY(func_id) REFERENCES funcionarios(id))''')
    conn.commit()
    return conn

conn = init_db()

# --- FUNÇÕES UTILITÁRIAS ---
def get_image_base64(image_file):
    if image_file:
        return base64.b64encode(image_file.getvalue()).decode()
    return None

# --- SIDEBAR ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2800/2800187.png", width=80)
st.sidebar.title("PontoPro v3.0")
app_mode = st.sidebar.selectbox("Escolha o Módulo", ["🕒 Registro de Ponto", "🔐 Painel Administrativo"])

# --- MÓDULO 1: REGISTRO DE PONTO (PARA O FUNCIONÁRIO) ---
if app_mode == "🕒 Registro de Ponto":
    st.title("⏱️ Registro de Presença Inteligente")
    
    # Captura de Localização via JS (Navegador)
    loc = get_geolocation()
    lat_long = f"{loc['coords']['latitude']}, {loc['coords']['longitude']}" if loc else "Localização não autorizada"

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Passo 1: Identificação")
        id_input = st.number_input("Digite seu ID de Funcionário", min_value=0, step=1)
        
        if id_input > 0:
            query = "SELECT * FROM funcionarios WHERE id = ?"
            user = pd.read_sql(query, conn, params=(id_input,))
            
            if not user.empty:
                st.success(f"Funcionário: **{user.iloc[0]['nome']}**")
                st.info(f"📍 GPS detectado: {lat_long}")
                
                st.subheader("Passo 2: Biometria Facial")
                foto = st.camera_input("Tire uma foto para validar")
                
                if foto:
                    data_hoje = datetime.now().strftime("%Y-%m-%d")
                    agora = datetime.now().strftime("%H:%M:%S")
                    foto_b64 = get_image_base64(foto)
                    
                    # Checar se já existe registro hoje
                    check_query = "SELECT * FROM presenca WHERE func_id = ? AND data = ?"
                    registro_hoje = pd.read_sql(check_query, conn, params=(id_input, data_hoje))
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        btn_entrada = st.button("📥 Registrar Entrada", use_container_width=True)
                        if btn_entrada:
                            if registro_hoje.empty:
                                cursor = conn.cursor()
                                cursor.execute('''INSERT INTO presenca 
                                    (func_id, data, entrada, saida, foto_entrada, geo_entrada) 
                                    VALUES (?, ?, ?, ?, ?, ?)''', 
                                    (id_input, data_hoje, agora, "---", foto_b64, lat_long))
                                conn.commit()
                                st.balloons()
                                st.success(f"Entrada confirmada às {agora}")
                            else:
                                st.warning("⚠️ Entrada já realizada hoje.")

                    with c2:
                        btn_saida = st.button("📤 Registrar Saída", use_container_width=True)
                        if btn_saida:
                            if not registro_hoje.empty and registro_hoje.iloc[0]['saida'] == "---":
                                cursor = conn.cursor()
                                cursor.execute('''UPDATE presenca SET saida = ?, foto_saida = ?, geo_saida = ? 
                                                WHERE func_id = ? AND data = ?''', 
                                                (agora, foto_b64, lat_long, id_input, data_hoje))
                                conn.commit()
                                st.snow()
                                st.success(f"Saída confirmada às {agora}")
                            else:
                                st.error("❌ Erro: Saída já registrada ou entrada não realizada.")
            else:
                st.error("Funcionário não encontrado.")

    with col2:
        st.subheader("💡 Instruções")
        st.write("""
        1. Digite seu número de identificação.
        2. Certifique-se de que sua localização está ativa.
        3. Olhe para a câmera e tire a foto.
        4. Clique no botão de entrada ou saída conforme sua jornada.
        """)
        st.image("https://cdn-icons-png.flaticon.com/512/3565/3565937.png", width=200)

# --- MÓDULO 2: PAINEL ADMINISTRATIVO ---
elif app_mode == "🔐 Painel Administrativo":
    st.title("🔐 Gestão e Relatórios")
    
    senha = st.sidebar.text_input("Senha de Acesso", type="password")
    if senha == "admin123": # Altere para uma senha forte
        
        tab1, tab2, tab3 = st.tabs(["📊 Relatórios Mensais", "👥 Gestão de Equipe", "🛠️ Sistema"])
        
        with tab1:
            st.subheader("Filtro de Ponto")
            # Carregar logs com nomes
            df_logs = pd.read_sql('''SELECT p.*, f.nome, f.cargo FROM presenca p 
                                     JOIN funcionarios f ON p.func_id = f.id''', conn)
            
            if not df_logs.empty:
                df_logs['data'] = pd.to_datetime(df_logs['data'])
                df_logs['Mes_Ano'] = df_logs['data'].dt.strftime('%m/%Y')
                
                filtros = st.columns(2)
                mes_selecionado = filtros[0].selectbox("Filtrar por Mês", df_logs['Mes_Ano'].unique())
                df_filtrado = df_logs[df_logs['Mes_Ano'] == mes_selecionado]
                
                st.dataframe(df_filtrado[['id', 'nome', 'cargo', 'data', 'entrada', 'saida', 'geo_entrada']], use_container_width=True)
                
                st.subheader("Visualização de Auditoria (Fotos e GPS)")
                for idx, row in df_filtrado.iterrows():
                    with st.expander(f"Ver Detalhes: {row['nome']} - Dia {row['data'].strftime('%d/%m/%Y')}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write("**ENTRADA**")
                            if row['foto_entrada']:
                                st.image(f"data:image/png;base64,{row['foto_entrada']}", width=200)
                            st.caption(f"📍 GPS: {row['geo_entrada']}")
                        with c2:
                            st.write("**SAÍDA**")
                            if row['foto_saida'] and row['foto_saida'] != "---":
                                st.image(f"data:image/png;base64,{row['foto_saida']}", width=200)
                            st.caption(f"📍 GPS: {row['geo_saida']}")
                
                csv = df_filtrado.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Relatório CSV", csv, "relatorio_ponto.csv", "text/csv")
            else:
                st.info("Nenhum registro no banco de dados.")

        with tab2:
            st.subheader("Adicionar Novo Funcionário")
            with st.form("cadastro"):
                new_id = st.number_input("ID Único", min_value=1)
                new_nome = st.text_input("Nome Completo")
                new_cargo = st.text_input("Cargo")
                if st.form_submit_button("Cadastrar"):
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO funcionarios (id, nome, cargo, data_criacao) VALUES (?, ?, ?, ?)",
                                    (new_id, new_nome, new_cargo, datetime.now().strftime("%Y-%m-%d")))
                        conn.commit()
                        st.success("Funcionário cadastrado!")
                    except:
                        st.error("Erro: Este ID já existe.")
            
            st.subheader("Lista de Funcionários")
            df_f = pd.read_sql("SELECT * FROM funcionarios", conn)
            st.table(df_f)

        with tab3:
            st.subheader("Segurança e Manutenção")
            if st.button("🚨 Limpar todos os registros (CUIDADO)"):
                conn.cursor().execute("DELETE FROM presenca")
                conn.commit()
                st.rerun()
    else:
        st.warning("Insira a senha de administrador na barra lateral.")
