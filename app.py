from base64 import b64encode
from collections import defaultdict
from datetime import datetime
from html import escape
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import streamlit as st

import galeria


MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


@st.cache_data(show_spinner=False)
def criar_miniatura(caminho: str) -> str:
    """Cria uma versão leve da foto para a grade da galeria."""
    with Image.open(caminho) as imagem:
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
        imagem = ImageOps.fit(imagem, (520, 360))
        memoria = BytesIO()
        imagem.save(memoria, format="JPEG", quality=82)
    return b64encode(memoria.getvalue()).decode("ascii")


def criar_imagem_anotada(foto: dict) -> Image.Image:
    caminho = galeria.caminho_da_imagem(foto)
    with Image.open(caminho) as original:
        imagem = ImageOps.exif_transpose(original).convert("RGB")

    desenho = ImageDraw.Draw(imagem)
    fonte = ImageFont.load_default(size=18)

    for indice, rosto in enumerate(foto["rostos"]):
        topo, direita, base, esquerda = rosto["localizacao"]
        rotulo = rosto.get("nome") or f"Rosto {indice + 1}"
        desenho.rectangle(
            (esquerda, topo, direita, base), outline="#22c55e", width=4
        )
        caixa = desenho.textbbox((esquerda, base), rotulo, font=fonte)
        desenho.rectangle(
            (caixa[0] - 4, caixa[1] - 3, caixa[2] + 4, caixa[3] + 3),
            fill="#22c55e",
        )
        desenho.text((esquerda, base), rotulo, fill="white", font=fonte)

    return imagem


def fechar_modal() -> None:
    st.query_params.clear()


@st.dialog(
    "Identificar pessoas",
    width="large",
    on_dismiss=fechar_modal,
)
def mostrar_detalhes(foto: dict, catalogo: list[dict]) -> None:
    st.caption(foto.get("nome_original", "Foto"))

    coluna_imagem, coluna_identificacao = st.columns([3, 2], gap="large")
    with coluna_imagem:
        st.image(criar_imagem_anotada(foto), width="stretch")

    with coluna_identificacao:
        mostrar_formulario_identificacao(foto, catalogo)

    if st.button("Fechar", width="stretch"):
        fechar_modal()
        st.rerun()


def mostrar_formulario_identificacao(foto: dict, catalogo: list[dict]) -> None:
    if mensagem := st.session_state.pop("mensagem_nome", None):
        st.success(mensagem)

    if not foto["rostos"]:
        st.warning("Nenhum rosto foi encontrado nesta imagem.")
        return

    st.markdown("#### Identificar pessoa")
    st.caption("Selecione um rosto marcado na imagem e informe o nome.")
    indices = list(range(len(foto["rostos"])))
    indice_rosto = st.selectbox(
        "Rosto",
        indices,
        format_func=lambda indice: foto["rostos"][indice].get("nome")
        or f"Rosto {indice + 1}",
    )
    nome_atual = foto["rostos"][indice_rosto].get("nome") or ""
    nome = st.text_input(
        "Nome da pessoa",
        value=nome_atual,
        key=f"nome_{foto['id']}_{indice_rosto}",
    )

    if st.button("Salvar nome", type="primary", disabled=not nome.strip()):
        quantidade, codificacao = galeria.nomear_rosto(
            catalogo, foto["id"], indice_rosto, nome.strip()
        )
        galeria.salvar_catalogo(catalogo)
        galeria.adicionar_rosto_conhecido(nome.strip(), codificacao)
        st.session_state.mensagem_nome = (
            f"Nome aplicado a {quantidade} rosto(s) semelhante(s)."
        )
        st.rerun()


def mostrar_grade(catalogo: list[dict]) -> None:
    if not catalogo:
        st.info("Adicione imagens para começar a galeria.")
        return

    fotos_por_mes = defaultdict(list)
    for foto in catalogo:
        data = datetime.fromisoformat(foto["data"])
        fotos_por_mes[(data.year, data.month)].append(foto)

    for ano, mes in sorted(fotos_por_mes, reverse=True):
        st.subheader(f"{MESES[mes - 1].capitalize()} de {ano}")
        colunas = st.columns(4)
        fotos = sorted(
            fotos_por_mes[(ano, mes)], key=lambda item: item["data"], reverse=True
        )

        for indice, foto in enumerate(fotos):
            caminho = galeria.caminho_da_imagem(foto)
            nomes = sorted(
                {rosto["nome"] for rosto in foto["rostos"] if rosto.get("nome")}
            )
            legenda = ", ".join(nomes) if nomes else "Sem identificação"

            with colunas[indice % 4]:
                miniatura = criar_miniatura(str(caminho))
                # O link usa um parâmetro da própria página para abrir a foto.
                st.markdown(
                    f"""
                    <a class="cartao-foto" href="?foto={foto['id']}" target="_self">
                        <img src="data:image/jpeg;base64,{miniatura}"
                             alt="{escape(foto.get('nome_original', 'Foto'))}">
                    </a>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption(legenda)


st.set_page_config(page_title="Galeria facial", page_icon="📷", layout="wide")
st.markdown(
    """
    <style>
    .cartao-foto img {
        width: 100%;
        aspect-ratio: 13 / 9;
        object-fit: cover;
        border-radius: 0.65rem;
        transition: transform 120ms ease, box-shadow 120ms ease;
    }
    .cartao-foto img:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(0, 0, 0, 0.18);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Galeria facial")
st.caption("Organize suas fotos por mês e identifique as pessoas nelas.")

catalogo = galeria.carregar_catalogo()
identificador_foto = st.query_params.get("foto")
foto_selecionada = next(
    (foto for foto in catalogo if foto["id"] == identificador_foto), None
)

if identificador_foto:
    if foto_selecionada is None:
        # Remove da URL um identificador que não existe mais no catálogo.
        st.query_params.clear()

if mensagem := st.session_state.pop("mensagem_upload", None):
    st.success(mensagem)

with st.expander("Adicionar fotos", expanded=not catalogo):
    arquivos = st.file_uploader(
        "Selecione uma ou mais imagens",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    if st.button("Adicionar à galeria", type="primary", disabled=not arquivos):
        nomes, codificacoes = galeria.carregar_rostos()
        adicionadas = 0
        repetidas = 0

        with st.spinner("Analisando rostos..."):
            for arquivo in arquivos:
                foto = galeria.adicionar_imagem(
                    arquivo, catalogo, nomes, codificacoes
                )
                if foto is None:
                    repetidas += 1
                else:
                    catalogo.append(foto)
                    adicionadas += 1

        galeria.salvar_catalogo(catalogo)
        mensagem = f"{adicionadas} foto(s) adicionada(s)."
        if repetidas:
            mensagem += f" {repetidas} duplicada(s) ignorada(s)."
        st.session_state.mensagem_upload = mensagem
        st.rerun()

mostrar_grade(catalogo)

if foto_selecionada:
    mostrar_detalhes(foto_selecionada, catalogo)
