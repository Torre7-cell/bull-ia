import streamlit as st
import io
from google import genai
from google.genai import types
from PIL import Image

# Configuración de página
st.set_page_config(page_title="Bull IA", page_icon="🐂", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #09090b; color: #f4f4f5; }
    div[data-testid="stToolbar"] { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

st.title("🐂 Bull IA")

# 1. API Key
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = st.text_input("Ingresa tu API Key de Gemini:", type="password")

if not api_key:
    st.info("Por favor, ingresa tu API Key de Gemini para comenzar.")
    st.stop()

client = genai.Client(api_key=api_key)

# 2. Modelos actualizados a la generación Gemini 3.x
MODELOS_TEXTO = ['gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash-lite']
MODELOS_IMAGEN = ['gemini-3.1-flash-image', 'gemini-3-pro-image']

# 3. Inicializar estado de sesión (Memoria)
if "messages" not in st.session_state:
    st.session_state.messages = []

# Dibujar historial
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], tuple):
            st.image(message["content"][0], use_container_width=True)
            if message["content"][1]:
                st.write(message["content"][1])
        elif isinstance(message["content"], Image.Image):
            st.image(message["content"], caption="Imagen generada", use_container_width=True)
        else:
            st.write(message["content"])

# 4. Menú lateral
with st.sidebar:
    st.header("⚙️ Opciones de Bull IA")
    modo_arte = st.toggle("🎨 Modo Crear Imagen (PNG)")
    
    st.subheader("📷 Adjuntar Imagen")
    opcion_foto = st.radio("Fuente de imagen:", ["Ninguna", "📁 Galería", "📷 Cámara"])
    
    imagen_subida = None
    if opcion_foto == "📁 Galería":
        imagen_subida = st.file_uploader("Sube una foto", type=["jpg", "jpeg", "png"])
    elif opcion_foto == "📷 Cámara":
        imagen_subida = st.camera_input("Toma una foto")

# 5. Lógica del Chat con Memoria
if prompt := st.chat_input("Escribe un mensaje a Bull IA..."):

    # MODO CREAR IMAGEN
    if modo_arte:
        st.session_state.messages.append({"role": "user", "content": f"🎨 [Crear imagen]: {prompt}"})
        with st.chat_message("user"):
            st.write(f"🎨 [Crear imagen]: {prompt}")

        with st.chat_message("assistant"):
            with st.spinner("Creando tu imagen..."):
                exito = False
                for mod_img in MODELOS_IMAGEN:
                    try:
                        response = client.models.generate_content(
                            model=mod_img,
                            contents=f"Genera una imagen artística de alta calidad sobre: {prompt}",
                            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
                        )
                        for part in response.candidates[0].content.parts:
                            if part.inline_data:
                                img = Image.open(io.BytesIO(part.inline_data.data))
                                st.image(img, caption="Imagen generada", use_container_width=True)
                                st.session_state.messages.append({"role": "assistant", "content": img})
                                exito = True
                                break
                        if exito: break
                    except Exception:
                        continue
                if not exito:
                    msg_err = "⚠️ No se pudo generar la imagen. Intenta con otra descripción."
                    st.error(msg_err)
                    st.session_state.messages.append({"role": "assistant", "content": msg_err})

    # MODO CHAT CON MEMORIA DE CONVERSACIÓN
    else:
        img_pil = Image.open(imagen_subida) if imagen_subida else None

        if img_pil:
            st.session_state.messages.append({"role": "user", "content": (img_pil, prompt)})
            with st.chat_message("user"):
                st.image(img_pil, use_container_width=True)
                st.write(prompt)
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

        # Construir contexto acumulado para recordar todo
        contents = ["Eres Bull IA, un asistente inteligente, directo y respetuoso. Mantén el hilo de la conversación."]
        
        for msg in st.session_state.messages:
            role_prefix = "Usuario:" if msg["role"] == "user" else "Bull IA:"
            if isinstance(msg["content"], str):
                contents.append(f"{role_prefix} {msg['content']}")
            elif isinstance(msg["content"], tuple):
                contents.append(f"{role_prefix} {msg['content'][1]}")
                if msg["content"][0] is not None:
                    contents.append(msg["content"][0])

        with st.chat_message("assistant"):
            with st.spinner("Bull IA está pensando..."):
                respuesta_exitosa = False
                for modelo in MODELOS_TEXTO:
                    try:
                        response = client.models.generate_content(model=modelo, contents=contents)
                        st.write(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        respuesta_exitosa = True
                        break
                    except Exception:
                        continue

                if not respuesta_exitosa:
                    msg_err = "⚠️ Error de conexión o límite de cuota alcanzado. Intenta de nuevo en unos momentos."
                    st.error(msg_err)
                    st.session_state.messages.append({"role": "assistant", "content": msg_err})
