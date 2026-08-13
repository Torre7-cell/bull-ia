import streamlit as st
import io
import re
from google import genai
from google.genai import types
from PIL import Image

# Configuración de página con tema oscuro
st.set_page_config(page_title="Bull IA", page_icon="🐂", layout="centered")

# CSS personalizado para estilo negro/oscuro elegante (CORREGIDO AQUÍ)
st.markdown("""
    <style>
    .stApp { background-color: #09090b; color: #f4f4f5; }
    div[data-testid="stToolbar"] { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

st.title("🐂 Bull IA")

# 1. Configuración de API Key desde los Secrets de Streamlit
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = st.text_input("Ingresa tu API Key de Gemini:", type="password")

if not api_key:
    st.info("Por favor, ingresa tu API Key de Gemini para comenzar.")
    st.stop()

client = genai.Client(api_key=api_key)

# Modelos configurados
MODELOS_TEXTO = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.1-flash-lite']
MODELOS_IMAGEN = ['gemini-3.1-flash-image', 'gemini-3-pro-image']

# 2. Estado de la memoria del chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar historial de conversación
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], tuple):
            st.image(message["content"][0], use_container_width=True)
            if message["content"][1]:
                st.write(message["content"][1])
        else:
            st.write(message["content"])

# 3. Controles laterales para imágenes
with st.sidebar:
    st.header("⚙️ Opciones de Bull IA")
    modo_arte = st.checkbox("🎨 Modo Crear Imagen (PNG)", value=False)
    
    st.subheader("📷 Adjuntar Imagen")
    opcion_foto = st.radio("Fuente de imagen:", ["Ninguna", "📁 Galería", "📷 Cámara"])
    
    imagen_subida = None
    if opcion_foto == "📁 Galería":
        imagen_subida = st.file_uploader("Sube una foto", type=["jpg", "jpeg", "png"])
    elif opcion_foto == "📷 Cámara":
        imagen_subida = st.camera_input("Toma una foto")

# 4. Procesamiento de mensajes
if prompt := st.chat_input("Escribe un mensaje a Bull IA..."):
    
    # MODO CREACIÓN DE IMÁGENES
    if modo_arte:
        st.session_state.messages.append({"role": "user", "content": f"🎨 [Crear imagen]: {prompt}"})
        with st.chat_message("user"):
            st.write(f"🎨 [Crear imagen]: {prompt}")
            
        with st.chat_message("assistant"):
            with st.spinner("Creando imagen en alta calidad..."):
                exito = False
                for mod_img in MODELOS_IMAGEN:
                    try:
                        response = client.models.generate_content(
                            model=mod_img,
                            contents=f"Genera una imagen en alta calidad de: {prompt}",
                            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
                        )
                        for part in response.candidates[0].content.parts:
                            if part.inline_data:
                                img = Image.open(io.BytesIO(part.inline_data.data))
                                st.image(img, caption="Imagen generada", format="PNG")
                                st.session_state.messages.append({"role": "assistant", "content": img})
                                exito = True
                                break
                        if exito: break
                    except Exception:
                        continue
                if not exito:
                    msg_err = "⚠️ No se pudo generar la imagen. Verifica el estado de tus cuotas o intenta más tarde."
                    st.error(msg_err)
                    st.session_state.messages.append({"role": "assistant", "content": msg_err})

    # MODO CHAT / VISIÓN
    else:
        img_pil = Image.open(imagen_subida) if imagen_subida else None
        
        # Registrar mensaje del usuario
        if img_pil:
            st.session_state.messages.append({"role": "user", "content": (img_pil, prompt)})
            with st.chat_message("user"):
                st.image(img_pil, use_container_width=True)
                st.write(prompt)
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

        # Respuesta de Bull IA
        with st.chat_message("assistant"):
            with st.spinner("Bull IA está pensando..."):
                contents = []
                if img_pil:
                    contents.append(img_pil)
                contents.append(f"Eres Bull IA, un asistente elegante, directo y avanzado. Responde a: {prompt}")

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
                    msg_err = "⚠️ **Límite alcanzado:** Se ha agotado la cuota de peticiones. Inténtalo de nuevo en **3 a 4 horas**."
                    st.error(msg_err)
                    st.session_state.messages.append({"role": "assistant", "content": msg_err})
