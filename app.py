import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import math
from datetime import date, datetime
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates

# Configuração da página
st.set_page_config(page_title="Gestão e Calibração de Setores", layout="wide")

COORD_FILE = "coordenadas.json"

# Coordenadas iniciais padrão (caso o arquivo JSON ainda não exista)
COORDENADAS_PADRAO = {
    1: (480, 260), 2: (470, 310), 3: (530, 310), 4: (470, 370), 5: (500, 470),
    6: (570, 360), 7: (600, 380), 8: (610, 420), 9: (530, 360), 10: (540, 420),
    11: (450, 560), 12: (420, 580), 13: (370, 630), 14: (510, 510), 15: (580, 460),
    16: (620, 470), 17: (670, 480), 18: (420, 660), 19: (370, 510), 20: (260, 530),
    21: (150, 370), 22: (260, 480), 23: (150, 460), 24: (440, 710), 25: (280, 290),
    26: (340, 230), 27: (120, 500), 28: (380, 410), 29: (360, 360), 30: (410, 310),
    31: (380, 310), 32: (400, 250), 33: (470, 790), 34: (210, 420), 35: (320, 580),
    36: (360, 460), 37: (410, 740), 38: (340, 730), 39: (330, 660), 40: (270, 670),
    41: (300, 700), 42: (290, 760), 43: (380, 860), 44: (320, 790), 45: (350, 820),
    46: (370, 790)
}

# --- FUNÇÕES DE ARQUIVO E BANCO DE DADOS ---
def carregar_coordenadas():
    """Carrega coordenadas salvas do arquivo JSON ou cria o padrão."""
    if os.path.exists(COORD_FILE):
        with open(COORD_FILE, "r") as f:
            data = json.load(f)
            return {int(k): tuple(v) for k, v in data.items()}
    else:
        salvar_coordenadas(COORDENADAS_PADRAO)
        return COORDENADAS_PADRAO

def salvar_coordenadas(coords):
    """Salva o dicionário de coordenadas no arquivo JSON."""
    with open(COORD_FILE, "w") as f:
        json.dump({str(k): list(v) for k, v in coords.items()}, f, indent=4)

def init_db():
    conn = sqlite3.connect('visitas_bairro.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS visitas (
            zona INTEGER PRIMARY KEY,
            responsavel TEXT,
            data_inicio TEXT,
            data_fim TEXT,
            status TEXT
        )
    ''')
    for i in range(1, 47):
        c.execute('''
            INSERT OR IGNORE INTO visitas (zona, responsavel, data_inicio, data_fim, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (i, 'Não Atribuído', '', '', 'Pendente'))
    conn.commit()
    conn.close()

def carregar_dados():
    conn = sqlite3.connect('visitas_bairro.db')
    df = pd.read_sql_query("SELECT * FROM visitas ORDER BY zona ASC", conn)
    conn.close()
    return df

def atualizar_zona(zona, responsavel, inicio, fim, status):
    conn = sqlite3.connect('visitas_bairro.db')
    c = conn.cursor()
    c.execute('''
        UPDATE visitas
        SET responsavel = ?, data_inicio = ?, data_fim = ?, status = ?
        WHERE zona = ?
    ''', (responsavel, str(inicio) if inicio else '', str(fim) if fim else '', status, zona))
    conn.commit()
    conn.close()

init_db()
coords_setores = carregar_coordenadas()

CORES_STATUS = {
    "Pendente": (255, 0, 0, 140),     # Vermelho
    "Em Andamento": (255, 165, 0, 150), # Laranja
    "Concluída": (0, 180, 0, 140)     # Verde
}

def identificar_setor_clicado(x, y, coords):
    setor_mais_proximo = 1
    menor_distancia = float('inf')
    for setor, (cx, cy) in coords.items():
        dist = math.sqrt((x - cx)**2 + (y - cy)**2)
        if dist < menor_distancia:
            menor_distancia = dist
            setor_mais_proximo = setor
    return setor_mais_proximo

def gerar_mapa(caminho_imagem, df_visitas, coords, setor_em_destaque=None):
    img_base = Image.open(caminho_imagem).convert("RGBA")
    overlay = Image.new("RGBA", img_base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    status_map = dict(zip(df_visitas['zona'], df_visitas['status'])) if df_visitas is not None else {}
    RAIO = 20
    
    for setor, (cx, cy) in coords.items():
        st_zona = status_map.get(setor, "Pendente")
        cor = CORES_STATUS.get(st_zona, (255, 0, 0, 140))
        
        # Se for o setor selecionado na calibração, destaca em azul
        if setor == setor_em_destaque:
            draw.ellipse([cx - RAIO - 5, cy - RAIO - 5, cx + RAIO + 5, cy + RAIO + 5], fill=(0, 200, 255, 220), outline=(255, 255, 255), width=3)
        else:
            draw.ellipse([cx - RAIO, cy - RAIO, cx + RAIO, cy + RAIO], fill=cor, outline=(0, 0, 0, 220), width=2)
            
    mapa_final = Image.alpha_composite(img_base, overlay)
    return mapa_final.convert("RGB")


# --- MENU LATERAL ---
st.sidebar.title("📌 Menu de Navegação")
modo_app = st.sidebar.radio(
    "Escolha o Modo de Uso:", 
    ["📍 Registrar Visitas", "🛠️ Calibrar Coordenadas (Ajustar Posições)"]
)


# -------------------------------------------------------------
# MODO 1: CALIBRAÇÃO DE COORDENADAS
# -------------------------------------------------------------
if modo_app == "🛠️ Calibrar Coordenadas (Ajustar Posições)":
    st.title("🛠️ Reposicionamento Manual das Coordenadas")
    st.info("Selecione o número do setor abaixo e, em seguida, clique no ponto exato no mapa onde esse setor está localizado.")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        setor_alvo = st.selectbox("Selecione o Setor para Reposicionar (1 a 46):", range(1, 47))
        pos_atual = coords_setores.get(setor_alvo, (0, 0))
        st.write(f"Posição atual do Setor **{setor_alvo}**: `X={pos_atual[0]}, Y={pos_atual[1]}`")
        
        if st.button("💾 Exportar Coordenadas como JSON"):
            salvar_coordenadas(coords_setores)
            st.success("Arquivo 'coordenadas.json' atualizado com sucesso!")
            
    with c2:
        df_visitas = carregar_dados()
        mapa_calib = gerar_mapa("mapa.png", df_visitas, coords_setores, setor_em_destaque=setor_alvo)
        
        st.caption(f"Clique no mapa para mover o marcador azul (Setor {setor_alvo}):")
        clique = streamlit_image_coordinates(mapa_calib, key="calibragem_click")
        
        if clique is not None:
            nova_x, nova_y = clique["x"], clique["y"]
            
            # Só atualiza se a posição mudou
            if coords_setores[setor_alvo] != (nova_x, nova_y):
                coords_setores[setor_alvo] = (nova_x, nova_y)
                salvar_coordenadas(coords_setores)
                st.toast(f"Setor {setor_alvo} movido para X:{nova_x}, Y:{nova_y}!", icon="🎯")
                st.rerun()


# -------------------------------------------------------------
# MODO 2: OPERAÇÃO NORMAL (REGISTRAR VISITAS)
# -------------------------------------------------------------
else:
    st.title("📍 Mapa Interativo de Visitas - Território Vale do Sol")
    st.caption("Clique diretamente sobre qualquer setor no mapa para atualizar suas informações de visita.")

    df_visitas = carregar_dados()

    if 'setor_selecionado' not in st.session_state:
        st.session_state.setor_selecionado = 1

    col_mapa, col_form = st.columns([1.3, 1])

    with col_mapa:
        st.subheader("🗺️ Status das Zonas")
        mapa_processado = gerar_mapa("mapa.png", df_visitas, coords_setores)
        coords_clique = streamlit_image_coordinates(mapa_processado, key="mapa_operacao")
        
        if coords_clique is not None:
            x, y = coords_clique["x"], coords_clique["y"]
            setor_detectado = identificar_setor_clicado(x, y, coords_setores)
            st.session_state.setor_selecionado = setor_detectado

    with col_form:
        zona_atual = st.session_state.setor_selecionado
        st.subheader(f"📝 Formulário - Setor Nº {zona_atual}")
        
        dados_zona = df_visitas[df_visitas['zona'] == zona_atual].iloc[0]
        
        with st.form("form_atualizacao"):
            responsavel = st.text_input("Responsável / Visitante:", value=dados_zona['responsavel'])
            
            dt_inicio_val = datetime.strptime(dados_zona['data_inicio'], '%Y-%m-%d').date() if dados_zona['data_inicio'] else date.today()
            dt_fim_val = datetime.strptime(dados_zona['data_fim'], '%Y-%m-%d').date() if dados_zona['data_fim'] else date.today()
            
            c1, c2 = st.columns(2)
            with c1:
                data_inicio = st.date_input("Data de Início:", value=dt_inicio_val)
            with c2:
                data_fim = st.date_input("Data de Término:", value=dt_fim_val)
                
            status = st.selectbox(
                "Status da Visita:", 
                ["Pendente", "Em Andamento", "Concluída"], 
                index=["Pendente", "Em Andamento", "Concluída"].index(dados_zona['status'])
            )
            
            btn_salvar = st.form_submit_button("Salvar Registro")
            
            if btn_salvar:
                atualizar_zona(zona_atual, responsavel, data_inicio, data_fim, status)
                st.success(f"Setor {zona_atual} atualizado!")
                st.rerun()

    # Indicadores
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total de Setores", 46)
    m2.metric("🔴 Pendentes", len(df_visitas[df_visitas['status'] == 'Pendente']))
    m3.metric("🟠 Em Andamento", len(df_visitas[df_visitas['status'] == 'Em Andamento']))
    m4.metric("🟢 Concluídas", len(df_visitas[df_visitas['status'] == 'Concluída']))

    st.dataframe(df_visitas, use_container_width=True)