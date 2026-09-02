import streamlit as st
import base64
from pathlib import Path


def get_base64_image(image_path):
    img_bytes = Path(image_path).read_bytes()
    return base64.b64encode(img_bytes).decode()


def render_landing():
    img_base64 = get_base64_image("aegis_logo.png")

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Rethink+Sans:ital,wght@0,400..800;1,400..800&family=Russo+One&display=swap');

        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        section.main {{
            overflow: hidden !important;
        }}

        .stApp {{
            background: linear-gradient(180deg, #FFFFFF 0%, #E4E5F1 100%);
            background-attachment: fixed;
        }}

        header {{ visibility: hidden !important; }}

        .top-window-bar {{
            position: fixed;
            top: 0; left: 0; width: 100%; height: 35px;
            background-color: #E4E5F1;
            border-bottom: 1px solid #cbd5e1;
            z-index: 999;
            display: flex;
            align-items: center;
            padding-left: 15px;
            box-shadow: 0px 2px 2px rgba(0, 0, 0, 0.15);
        }}

        .block-container {{
            padding-top: 4rem;
            overflow: hidden !important;
        }}

        div.stButton {{
            display: flex;
            justify-content: center;
            width: 100%;
        }}

        .aegis-logo-container {{
            display: flex;
            justify-content: center;
            margin-bottom: 10px;
        }}

        .aegis-logo-container img {{
            width: 100%;
            max-width: 225px;
            margin-top: 30px;
            height: auto;
            pointer-events: none;
            user-select: none;
        }}

        .aegis-title {{
            font-family: 'Russo One', sans-serif;
            font-size: 100px;
            color: #477B9E;
            margin-top: -20px;
            margin-bottom: 20px;
            letter-spacing: 2px;
            text-align: center;
        }}

        .aegis-subtitle {{
            font-family: 'Rethink Sans', sans-serif;
            font-size: 18px;
            font-weight: 600;
            color: #3E3F49;
            margin-top: 30px;
            margin-bottom: 40px;
            text-align: center;
        }}

        div.stButton > button:first-child {{
            background-color: #9DC6FB;
            color: #000000;
            border-radius: 12px;
            padding: 10px 35px;
            width: 400px;
            height: 65px;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Rethink Sans', sans-serif;
            border: none;
            box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
        }}

        div.stButton > button:first-child p,
        div.stButton > button:first-child div {{
            font-family: 'Rethink Sans', sans-serif !important;
            font-weight: bold !important;
            font-size: 18px !important;
        }}

        div.stButton > button:first-child:hover {{
            background-color: #8ab4f8;
        }}
        </style>

        <div class="top-window-bar"></div>

        <div class="aegis-logo-container">
            <img src="data:image/png;base64,{img_base64}">
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="aegis-title">AEGIS</div>', unsafe_allow_html=True)
    st.markdown('<div class="aegis-subtitle">System ready for deployment!</div>', unsafe_allow_html=True)

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        if st.button("Initialize Simulation"):
            st.session_state["page"] = "dashboardd"
            st.rerun()