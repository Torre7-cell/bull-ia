import io
import urllib.parse
import uuid
from PIL import Image
from google import genai
from google.genai import types
import requests
import streamlit as st

# Configuración de página
st.set_page_config(page_title="Bull IA", page_icon="🐂", layout="centered")

# CSS Personalizado: Ajuste de tema oscuro y botón "+" negro/discreto estilo app móvil
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

# 1. API Key de Gemini (Solo para Texto y Análisis de Visión)
if "GEMINI_API_KEY" in st.secrets:
  api_key = st.secrets["GEMINI_API_KEY"]
else:
  api_key = st.text_input("Ingresa tu API Key de Gemini:", type="password")

if not api_key:
  st.info("Por favor, ingresa tu API Key de Gemini para comenzar.")
  st.stop()

client = genai.Client(api_key=api_key)

# 2. TUS MODELOS ACTUALIZADOS
MODELOS_TEXTO = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

# 3. Inicializar Estado de Chats Múltiples
if "chats" not in st.session_state:
  st.session_state.chats = {}

if "current_chat_id" not in st.session_state:
  first_id = str(uuid.uuid4())
  st.session_state.chats[first_id] = {"title": "Chat Principal", "messages": []}
  st.session_state.current_chat_id = first_id


def crear_nuevo_chat():
  nuevo_id = str(uuid.uuid4())
  num_chat = len(st.session_state.chats) + 1
  st.session_state.chats[nuevo_id] = {
      "title": f"Chat {num_chat}",
      "messages": [],
  }
  st.session_state.current_chat_id = nuevo_id


# 4. Desplegable Interactivo para Historial de Chats
with st.expander("💬 Mis Chats (Toca aquí para desplegar conversaciones)"):
  if st.button("➕ Crear nuevo chat", key="btn_nuevo_main", use_container_width=True):
    crear_nuevo_chat()
    st.rerun()

  nombres_chats = {
      cid: data["title"] for cid, data in st.session_state.chats.items()
  }
  chat_seleccionado = st.selectbox(
      "Seleccionar conversación activa:",
      options=list(nombres_chats.keys()),
      format_func=lambda x: nombres_chats[x],
      index=list(nombres_chats.keys()).index(st.session_state.current_chat_id),
  )
  if chat_seleccionado != st.session_state.current_chat_id:
    st.session_state.current_chat_id = chat_seleccionado
    st.rerun()

st.markdown("---")

# Obtener mensajes del chat activo
current_messages = st.session_state.chats[st.session_state.current_chat_id][
    "messages"
]

# Dibujar historial del chat seleccionado
for message in current_messages:
  with st.chat_message(message["role"]):
    if isinstance(message["content"], tuple):
      st.image(message["content"][0], use_container_width=True)
      if message["content"][1]:
        st.write(message["content"][1])
    elif isinstance(message["content"], Image.Image):
      st.image(message["content"], caption="Imagen generada", use_container_width=True)
    else:
      st.write(message["content"])

# 5. MENÚ + CON LAS 3 OPCIONES
col_plus, col_vacia = st.columns([1, 10])

with col_plus:
  with st.popover("➕", help="Opciones de cámara, galería y creación"):
    st.markdown("### 🛠️ Opciones")

    # Opción 1: Modo crear imágenes
    modo_arte = st.toggle("🎨 Modo Crear Imagen")

    st.markdown("---")

    # Opción 2 y 3: Adjuntar foto desde galería o cámara
    opcion_foto = st.radio(
        "📷 Adjuntar imagen:", ["Ninguna", "📁 Galería", "📷 Cámara"]
    )

    imagen_subida = None
    if opcion_foto == "📁 Galería":
      imagen_subida = st.file_uploader(
          "Sube una foto de tu galería", type=["jpg", "jpeg", "png"]
      )
    elif opcion_foto == "📷 Cámara":
      imagen_subida = st.camera_input("Toma una foto")

# 6. Lógica del Chat
if prompt := st.chat_input("Escribe un mensaje a Bull IA..."):

  # MODO CREAR IMAGEN
  if modo_arte:
    current_messages.append(
        {"role": "user", "content": f"🎨 [Crear imagen]: {prompt}"}
    )
    with st.chat_message("user"):
      st.write(f"🎨 [Crear imagen]: {prompt}")

    with st.chat_message("assistant"):
      with st.spinner("Bull IA está dibujando tu imagen gratis..."):
        try:
          # Traducir al inglés en segundo plano usando tu modelo preferido
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

          # Codificar texto para formato URL
          prompt_encoded = urllib.parse.quote(prompt_ingles)

          # CORRECCIÓN AQUÍ: Se añadió la estructura /prompt/ correctamente
          url_imagen = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true"

          # Descarga de la imagen
          response_img = requests.get(url_imagen, timeout=20)

          if response_img.status_code == 200:
            img_real = Image.open(io.BytesIO(response_img.content))
            st.image(
                img_real, caption=f"Generado con: {prompt}", use_container_width=True
            )
            current_messages.append({"role": "assistant", "content": img_real})
          else:
            st.error(
                "⚠️ El servidor de imágenes gratuito está temporalmente"
                " ocupado. Intenta de nuevo."
            )

        except Exception as e:
          msg_err = f"⚠️ No se pudo procesar la imagen: {e}"
          st.error(msg_err)
          current_messages.append({"role": "assistant", "content": msg_err})

  # MODO CHAT CON MEMORIA DE CONVERSACIÓN
  else:
    img_pil = Image.open(imagen_subida) if imagen_subida else None

    if img_pil:
      current_messages.append({"role": "user", "content": (img_pil, prompt)})
      with st.chat_message("user"):
        st.image(img_pil, use_container_width=True)
        st.write(prompt)
    else:
      current_messages.append({"role": "user", "content": prompt})
      with st.chat_message("user"):
        st.write(prompt)

    # Cambiar el título del chat automáticamente al primer mensaje
    if len(current_messages) <= 2:
      st.session_state.chats[st.session_state.current_chat_id]["title"] = (
          prompt[:20] + "..."
      )

    # Construir contexto de memoria del chat activo
    contents = [
        "Eres Bull IA, un asistente inteligente, directo y respetuoso. Mantén el hilo de la conversación."
    ]

    for msg in current_messages:
      role_prefix = "Usuario:" if msg["role"] == "user" else "Bull IA:"

      if isinstance(msg["content"], str):
        contents.append(f"{role_prefix} {msg['content']}")
      elif isinstance(msg["content"], tuple):
        foto_usuario = msg["content"][0]
        texto_usuario = msg["content"][1]

        if texto_usuario:
          contents.append(f"{role_prefix} {texto_usuario}")
        if foto_usuario is not None:
          contents.append(foto_usuario)
      elif isinstance(msg["content"], Image.Image):
        contents.append(f"{role_prefix} [Imagen generada previamente]")

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
          msg_err = "⚠️ Error de conexión o límite de cuota alcanzado. Intenta de nuevo en unos momentos."
          st.error(msg_err)
          current_messages.append({"role": "assistant", "content": msg_err})
