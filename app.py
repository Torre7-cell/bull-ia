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

# CSS Personalizado: Ajuste de tema oscuro y optimización de botones
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
    </style>""",
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
    try:
      parsed_msgs = json.loads(msgs_json)
    except Exception:
      parsed_msgs = []
    chats[cid] = {"title": title, "messages": parsed_msgs}
  return chats

def guardar_chat_db(cid, title, messages):
  conn = sqlite3.connect("bull_ia.db")
  c = conn.cursor()

  serializable_msgs = []
  for m in messages:
    if m.get("content_type") == "text":
      serializable_msgs.append({
          "role": m["role"],
          "content_type": "text",
          "content": m["content"],
      })
    elif m.get("content_type") == "generated_image":
      serializable_msgs.append({
          "role": m["role"],
          "content_type": "generated_image",
          "content": "[Imagen generada previamente]",
          "url": m.get("url", ""),
      })
    elif m.get("content_type") == "user_photo":
      serializable_msgs.append({
          "role": m["role"],
          "content_type": "user_photo",
          "content": m["content"],
      })

  c.execute(
      "REPLACE INTO chats (id, title, messages) VALUES (?, ?, ?)",
      (cid, title, json.dumps(serializable_msgs)),
  )
  conn.commit()
  conn.close()

def eliminar_chat_db(cid):
  conn = sqlite3.connect("bull_ia.db")
  c = conn.cursor()
  c.execute("DELETE FROM chats WHERE id = ?", (cid,))
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

# 2. Modelos de la Serie 3 Activos
MODELOS_TEXTO = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

# 3. Sincronizar Estado con SQLite
chats_guardados = cargar_chats_db()
st.session_state.chats = chats_guardados
if not st.session_state.chats:
  first_id = str(uuid.uuid4())
  st.session_state.chats[first_id] = {"title": "Chat Principal", "messages": []}
  guardar_chat_db(first_id, "Chat Principal", [])

if "current_chat_id" not in st.session_state:
  st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]

if not isinstance(st.session_state.current_chat_id, str):
  st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]

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
  col_nav_1, col_nav_2 = st.columns(2)

  with col_nav_1:
    if st.button("➕ Crear nuevo chat", key="btn_nuevo_main", use_container_width=True):
      crear_nuevo_chat()
      st.rerun()

  nombres_chats = {
      cid: data["title"] for cid, data in st.session_state.chats.items()
  }
  current_cids = list(nombres_chats.keys())

  if st.session_state.current_chat_id not in current_cids:
    st.session_state.current_chat_id = current_cids[0]

  chat_seleccionado = st.selectbox(
      "Seleccionar conversación activa:",
      options=current_cids,
      format_func=lambda x: nombres_chats[x],
      index=current_cids.index(st.session_state.current_chat_id),
  )
  if chat_seleccionado != st.session_state.current_chat_id:
    st.session_state.current_chat_id = chat_seleccionado
    st.rerun()

  # Cambiar nombre del chat manualmente
  nuevo_titulo = st.text_input(
      "✏️ Cambiar nombre a este chat:",
      value=nombres_chats[st.session_state.current_chat_id],
  )
  if nuevo_titulo != nombres_chats[st.session_state.current_chat_id]:
    st.session_state.chats[st.session_state.current_chat_id]["title"] = (
        nuevo_titulo
    )
    guardar_chat_db(
        st.session_state.current_chat_id,
        nuevo_titulo,
        st.session_state.chats[st.session_state.current_chat_id]["messages"],
    )
    st.rerun()

  # Botón para eliminar el chat activo con el emoji 🗑️
  if st.button(
      f"🗑️ Eliminar '{nombres_chats[st.session_state.current_chat_id]}'",
      use_container_width=True,
  ):
    id_a_eliminar = st.session_state.current_chat_id
    eliminar_chat_db(id_a_eliminar)
    del st.session_state.chats[id_a_eliminar]

    restantes = list(st.session_state.chats.keys())
    if restantes:
      st.session_state.current_chat_id = restantes[0]
    else:
      first_id = str(uuid.uuid4())
      st.session_state.chats[first_id] = {
          "title": "Chat Principal",
          "messages": [],
      }
      st.session_state.current_chat_id = first_id
      guardar_chat_db(first_id, "Chat Principal", [])

    st.success("Chat eliminado con éxito.")
    st.rerun()

st.markdown("---")
current_messages = st.session_state.chats[st.session_state.current_chat_id][
    "messages"
]

# Dibujar historial
for idx, message in enumerate(current_messages):
  with st.chat_message(message["role"]):
    if message.get("content_type") == "text":
      st.write(message["content"])

    elif message.get("content_type") == "generated_image":
      if "url" in message and message["url"]:
        try:
          response_hist = requests.get(message["url"], timeout=10)
          if response_hist.status_code == 200:
            st.image(
                Image.open(io.BytesIO(response_hist.content)),
                use_container_width=True,
            )
            st.download_button(
                label="📥 Descargar Imagen",
                data=response_hist.content,
                file_name=f"bull_ia_{idx}.png",
                mime="image/png",
                key=f"dl_{idx}",
            )
        except Exception:
          st.write("🎨 [Imagen generada en esta sesión]")
      else:
        st.write(message["content"])

    elif message.get("content_type") == "user_photo":
      st.write(message["content"])

# 5. MENÚ + CON LAS 3 OPCIONES
col_plus, col_vacia = st.columns([1, 4])
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
    current_messages.append({
        "role": "user",
        "content_type": "text",
        "content": f"🎨 [Crear imagen]: {prompt}",
    })
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
          url_imagen = f"https://pollinations.ai/p/{prompt_encoded}?width=1024&height=1024&nologo=true"

          response_img = requests.get(url_imagen, timeout=15)
          if response_img.status_code == 200:
            img_real = Image.open(io.BytesIO(response_img.content))
            st.image(
                img_real, caption=f"Generado con: {prompt}", use_container_width=True
            )
            st.download_button(
                label="📥 Descargar Imagen Creada",
                data=response_img.content,
                file_name="bull_ia_imagen.png",
                mime="image/png",
                key="dl_inmediato",
            )
            current_messages.append({
                "role": "assistant",
                "content_type": "generated_image",
                "content": "[Imagen generada con éxito]",
                "url": url_imagen,
            })
          else:
            st.error("⚠️ El servidor de imágenes está ocupado.")
        except Exception as e:
          current_messages.append({
              "role": "assistant",
              "content_type": "text",
              "content": f"⚠️ Error: {e}",
          })
  else:
    img_pil = Image.open(imagen_subida) if imagen_subida else None
    if img_pil:
      current_messages.append({
          "role": "user",
          "content_type": "user_photo",
          "content": f"[Foto enviada] {prompt}",
      })
      with st.chat_message("user"):
        st.image(img_pil, use_container_width=True)
        st.write(prompt)
    else:
      current_messages.append({
          "role": "user",
          "content_type": "text",
          "content": prompt,
      })
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
            current_messages.append({
                "role": "assistant",
                "content_type": "text",
                "content": response.text,
            })
            respuesta_exitosa = True
            break
          except Exception:
            continue

        if not respuesta_exitosa:
          err_msg = "⚠️ Error de conexión o límite de cuota alcanzado."
          st.error(err_msg)
          current_messages.append({
              "role": "assistant",
              "content_type": "text",
              "content": err_msg,
          })

  guardar_chat_db(active_cid, active_title, current_messages)
