import io
import json
import sqlite3
import urllib.parse
import uuid
from google import genai
from google.genai import types
from PIL import Image
import requests
import streamlit as st

# Configuración de página
st.set_page_config(page_title="Bull IA", page_icon="🐂", layout="centered")

# CSS Personalizado: Ajuste de tema oscuro y botón "+" estilo app móvil
st.markdown(
    """
    <style>
    .stApp { background-color: #09090b; color: #f4f4f5; }
    div[data-testid="stToolbar"] { visibility: hidden; }

    /* Botón "+" estilizado estilo flotante/móvil */
    div[data-testid="stPopover"] > button {
        background-color: #111113 !important;
        color: #ffffff !important;
        border: 1px solid #27272a !important;
        border-radius: 50% !important;
        width: 42px !important;
        height: 42px !important;
        font-size: 20px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.5) !important;
    }
    div[data-testid="stPopover"] > button:hover {
        background-color: #27272a !important;
        border-color: #3f3f46 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🐂 Bull IA")


# --- CONFIGURACIÓN DE SQLITE ---
def init_db():
  conn = sqlite3.connect("bull_ia.db")
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            messages TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()


def cargar_chats_db():
  conn = sqlite3.connect("bull_ia.db")
  c = conn.cursor()
  c.execute("SELECT id, title, messages FROM chats")
  rows = c.fetchall()
  conn.close()

  chats = {}
  for row in rows:
    cid, title, msgs_json = row
    # Deserializar mensajes. Las imágenes PIL se omiten o se manejan como texto/etiqueta en persistencia básica
    try:
      parsed_msgs = json.loads(msgs_json)
    except Exception:
      parsed_msgs = []
    chats[cid] = {"title": title, "messages": parsed_msgs}
  return chats


def guardar_chat_db(cid, title, messages):
  # Filtramos contenido complejo que no sea serializable en JSON (como objetos PIL o tuplas de imágenes)
  # Guardaremos representaciones limpias de texto o metadatos de imágenes
  conn = sqlite3.connect("bull_ia.db")
  c = conn.cursor()

  serializable_msgs = []
  for m in messages:
    if isinstance(m["content"], str):
      serializable_msgs.append({"role": m["role"], "content": m["content"]})
    elif isinstance(m["content"], Image.Image):
      serializable_msgs.append(
          {"role": m["role"], "content": "[Imagen generada previamente]"}
      )
    elif isinstance(m["content"], tuple):
      serializable_msgs.append(
          {"role": m["role"], "content": "[Imagen adjunta y texto del usuario]"}
      )

  c.execute(
      "REPLACE INTO chats (id, title, messages) VALUES (?, ?, ?)",
      (cid, title, json.dumps(serializable_msgs)),
  )
  conn.commit()
  conn.close()


# 1. API Key de Gemini
if "GEMINI_API_KEY" in st.secrets:
  api_key = st.secrets["GEMINI_API_KEY"]
else:
  api_key = st.text_input("Ingresa tu API Key de Gemini:", type="password")

if not api_key:
  st.info("Por favor, ingresa tu API Key de Gemini para comenzar.")
  st.stop()

client = genai.Client(api_key=api_key)

# 2. Tus Modelos de la Serie 3 Activos
MODELOS_TEXTO = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

# 3. Sincronizar Estado con SQLite
chats_guardados = cargar_chats_db()
if "chats" not in st.session_state:
  st.session_state.chats = chats_guardados

if not st.session_state.chats:
  first_id = str(uuid.uuid4())
  st.session_state.chats[first_id] = {"title": "Chat Principal", "messages": []}
  guardar_chat_db(first_id, "Chat Principal", [])

if "current_chat_id" not in st.session_state:
  st.session_state.current_chat_id = list(st.session_state.chats.keys())


def crear_nuevo_chat():
  nuevo_id = str(uuid.uuid4())
  num_chat = len(st.session_state.chats) + 1
  titulo_inicial = f"Chat {num_chat}"
  st.session_state.chats[nuevo_id] = {
      "title": titulo_inicial,
      "messages": [],
  }
  st.session_state.current_chat_id = nuevo_id
  guardar_chat_db(nuevo_id, titulo_inicial, [])


# 4. Desplegable Interactivo para Historial
with st.expander("💬 Mis Chats Permanentes (Guardados en SQLite)"):
  if st.button("➕ Crear nuevo chat", key="btn_nuevo_main", use_container_width=True):
    crear_nuevo_chat()
    st.rerun()

  nombres_chats = {
      cid: data["title"] for cid, data in st.session_state.chats.items()
  }
  # Asegurar índice válido
  current_cids = list(nombres_chats.keys())
  if st.session_state.current_chat_id not in current_cids:
    st.session_state.current_chat_id = current_cids

  chat_seleccionado = st.selectbox(
      "Seleccionar conversación activa:",
      options=current_cids,
      format_func=lambda x: nombres_chats[x],
      index=current_cids.index(st.session_state.current_chat_id),
  )
  if chat_seleccionado != st.session_state.current_chat_id:
    st.session_state.current_chat_id = chat_seleccionado
    st.rerun()

st.markdown("---")

current_messages = st.session_state.chats[st.session_state.current_chat_id][
    "messages"
]

# Dibujar historial
for message in current_messages:
  with st.chat_message(message["role"]):
    st.write(message["content"])

# 5. MENÚ + CON LAS 3 OPCIONES
col_plus, col_vacia = st.columns(2)

with col_plus:
  with st.popover("➕", help="Opciones de cámara, galería y creación"):
    st.markdown("### 🛠️ Opciones")
    modo_arte = st.toggle("🎨 Modo Crear Imagen")
    st.markdown("---")
    opcion_foto = st.radio(
        "📷 Adjuntar imagen:", ["Ninguna", "📁 Galería", "📷 Cámara"]
    )

    imagen_subida = None
    if opcion_foto == "📁 Galería":
      imagen_subida = st.file_uploader(
          "Sube una foto", type=["jpg", "jpeg", "png"]
      )
    elif opcion_foto == "📷 Cámara":
      imagen_subida = st.camera_input("Toma una foto")

# 6. Lógica del Chat
if prompt := st.chat_input("Escribe un mensaje a Bull IA..."):
  active_cid = st.session_state.current_chat_id
  active_title = st.session_state.chats[active_cid]["title"]

  if modo_arte:
    current_messages.append(
        {"role": "user", "content": f"🎨 [Crear imagen]: {prompt}"}
    )
    with st.chat_message("user"):
      st.write(f"🎨 [Crear imagen]: {prompt}")

    with st.chat_message("assistant"):
      with st.spinner("Bull IA está dibujando tu imagen gratis..."):
        try:
          prompt_ingles = prompt
          try:
            traduccion = client.models.generate_content(
                model="gemini-3.7-flash",
                contents=(
                    "Translate the following image prompt to descriptive English"
                    f" for an AI image generator, reply with ONLY the translated"
                    f" text: {prompt}"
                ),
            )
            if traduccion.text:
              prompt_ingles = traduccion.text.strip()
          except Exception:
            pass

          prompt_encoded = urllib.parse.quote(prompt_ingles)
          url_imagen = f"https://pollinations.ai{prompt_encoded}?width=1024&height=1024&nologo=true"

          response_img = requests.get(url_imagen, timeout=15)
          if response_img.status_code == 200:
            img_real = Image.open(io.BytesIO(response_img.content))
            st.image(
                img_real, caption=f"Generado con: {prompt}", use_container_width=True
            )
            current_messages.append(
                {"role": "assistant", "content": "[Imagen generada con éxito]"}
            )
          else:
            st.error("⚠️ El servidor de imágenes está ocupado.")
        except Exception as e:
          current_messages.append(
              {"role": "assistant", "content": f"⚠️ Error: {e}"}
          )

  else:
    img_pil = Image.open(imagen_subida) if imagen_subida else None
    if img_pil:
      current_messages.append(
          {"role": "user", "content": f"[Foto enviada] {prompt}"}
      )
      with st.chat_message("user"):
        st.image(img_pil, use_container_width=True)
        st.write(prompt)
    else:
      current_messages.append({"role": "user", "content": prompt})
      with st.chat_message("user"):
        st.write(prompt)

    if len(current_messages) <= 2:
      active_title = prompt[:20] + "..."
      st.session_state.chats[active_cid]["title"] = active_title

    contents = [
        "Eres Bull IA, un asistente inteligente, directo y respetuoso. Mantén el hilo de la conversación."
    ]
    for msg in current_messages:
      contents.append(f"{msg['role']}: {msg['content']}")

    with st.chat_message("assistant"):
      with st.spinner("Bull IA está pensando..."):
        respuesta_exitosa = False
        for modelo in MODELOS_TEXTO:
          try:
            response = client.models.generate_content(
                model=modelo, contents=contents
            )
            st.write(response.text)
            current_messages.append(
                {"role": "assistant", "content": response.text}
            )
            respuesta_exitosa = True
            break
          except Exception:
            continue

        if not respuesta_exitosa:
          err_msg = "⚠️ Error de conexión o límite de cuota alcanzado."
          st.error(err_msg)
          current_messages.append({"role": "assistant", "content": err_msg})

  # Guardar cambios permanentemente en SQLite tras cada interacción
  guardar_chat_db(active_cid, active_title, current_messages)
