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


def limpar_filtros() -> None:
    st.session_state.pop("periodo_filtro", None)
    st.session_state.pop("pessoas_filtro", None)


def mostrar_filtros(catalogo: list[dict]) -> list[dict]:
    with st.container(border=True):
        st.markdown("#### Filtrar fotos")

        if not catalogo:
            st.caption("Os filtros estarão disponíveis quando houver fotos.")
            return []

        datas = [datetime.fromisoformat(foto["data"]).date() for foto in catalogo]
        menor_data, maior_data = min(datas), max(datas)
        pessoas = sorted(
            {
                rosto["nome"]
                for foto in catalogo
                for rosto in foto["rostos"]
                if rosto.get("nome")
            }
        )

        coluna_data, coluna_pessoas = st.columns(2, gap="medium")
        with coluna_data:
            periodo = st.date_input(
                "Período",
                value=(menor_data, maior_data),
                min_value=menor_data,
                max_value=maior_data,
                format="DD/MM/YYYY",
                key="periodo_filtro",
            )
        with coluna_pessoas:
            pessoas_selecionadas = st.multiselect(
                "Pessoas",
                options=pessoas,
                placeholder="Todas as pessoas",
                disabled=not pessoas,
                key="pessoas_filtro",
            )

        if isinstance(periodo, tuple) and periodo:
            data_inicial = periodo[0]
            data_final = periodo[-1]
        elif periodo:
            data_inicial = data_final = periodo
        else:
            data_inicial, data_final = menor_data, maior_data

        fotos_filtradas = []
        for foto in catalogo:
            data_foto = datetime.fromisoformat(foto["data"]).date()
            nomes_foto = {
                rosto["nome"] for rosto in foto["rostos"] if rosto.get("nome")
            }
            corresponde_data = data_inicial <= data_foto <= data_final
            corresponde_pessoa = not pessoas_selecionadas or bool(
                nomes_foto.intersection(pessoas_selecionadas)
            )
            if corresponde_data and corresponde_pessoa:
                fotos_filtradas.append(foto)

        filtros_ativos = (
            data_inicial != menor_data
            or data_final != maior_data
            or bool(pessoas_selecionadas)
        )
        coluna_resultado, coluna_limpar = st.columns(
            [4, 1], vertical_alignment="center"
        )
        with coluna_resultado:
            st.caption(
                f"Exibindo {len(fotos_filtradas)} de {len(catalogo)} foto(s)."
            )
        with coluna_limpar:
            st.button(
                "Limpar filtros",
                disabled=not filtros_ativos,
                on_click=limpar_filtros,
                width="stretch",
            )

    return fotos_filtradas


def mostrar_grade(catalogo: list[dict]) -> None:
    if not catalogo:
        st.info("Adicione imagens para começar a galeria.")
        return

    fotos_por_mes = defaultdict(list)
    for foto in catalogo:
        data = datetime.fromisoformat(foto["data"])
        fotos_por_mes[(data.year, data.month)].append(foto)

    for ano, mes in sorted(fotos_por_mes, reverse=True):
        fotos = sorted(
            fotos_por_mes[(ano, mes)], key=lambda item: item["data"], reverse=True
        )
        quantidade = len(fotos)
        texto_quantidade = (
            f"{quantidade} foto" if quantidade == 1 else f"{quantidade} fotos"
        )
        st.markdown(
            f"""
            <div class="cabecalho-mes">
                <h2>{MESES[mes - 1].capitalize()} de {ano}</h2>
                <span>{texto_quantidade}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        colunas = st.columns(4, gap="medium")

        for indice, foto in enumerate(fotos):
            caminho = galeria.caminho_da_imagem(foto)
            data = datetime.fromisoformat(foto["data"])
            nomes = sorted(
                {rosto["nome"] for rosto in foto["rostos"] if rosto.get("nome")}
            )
            legenda = ", ".join(nomes) if nomes else "Não identificado"

            with colunas[indice % 4]:
                miniatura = criar_miniatura(str(caminho))
                # Todo o cartão abre o modal por um parâmetro da própria página.
                st.markdown(
                    f"""
                    <a class="cartao-foto" href="?foto={foto['id']}" target="_self">
                        <img src="data:image/jpeg;base64,{miniatura}"
                             alt="{escape(foto.get('nome_original', 'Foto'))}">
                        <span class="conteudo-cartao">
                            <strong>{escape(legenda)}</strong>
                            <small>{data.strftime('%d/%m/%Y')}</small>
                        </span>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )


st.set_page_config(page_title="Galeria", page_icon="📷", layout="wide")
st.markdown(
    """
    <style>
    .stMainBlockContainer {
        max-width: 1400px;
        padding-top: 2.75rem;
        padding-bottom: 4rem;
    }
    h1 {
        letter-spacing: -0.035em;
        margin-bottom: 1.75rem !important;
    }
    .cabecalho-mes {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 1rem;
        margin: 2.5rem 0 1rem;
        padding-bottom: 0.65rem;
        border-bottom: 1px solid rgba(128, 128, 128, 0.24);
    }
    .cabecalho-mes h2 {
        font-size: 1.35rem;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .cabecalho-mes span {
        color: color-mix(in srgb, currentColor 60%, transparent);
        font-size: 0.88rem;
        white-space: nowrap;
    }
    .cartao-foto {
        display: block;
        color: inherit !important;
        text-decoration: none !important;
        background: rgba(128, 128, 128, 0.06);
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 0.85rem;
        overflow: hidden;
        margin-bottom: 1.15rem;
        transition: transform 140ms ease, box-shadow 140ms ease,
                    border-color 140ms ease;
    }
    .cartao-foto:hover {
        transform: translateY(-3px);
        border-color: rgba(128, 128, 128, 0.42);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.14);
    }
    .cartao-foto img {
        display: block;
        width: 100%;
        aspect-ratio: 13 / 9;
        object-fit: cover;
    }
    .conteudo-cartao {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        min-height: 3.25rem;
        padding: 0.75rem 0.85rem;
    }
    .conteudo-cartao strong {
        overflow: hidden;
        font-size: 0.92rem;
        font-weight: 600;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .conteudo-cartao small {
        flex: none;
        color: color-mix(in srgb, currentColor 58%, transparent);
        font-size: 0.78rem;
    }
    [data-testid="stFileUploaderDropzone"] {
        border-radius: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Galeria")

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

with st.container(border=True):
    st.markdown("#### Adicionar fotos")
    arquivos = st.file_uploader(
        "Arraste ou selecione uma ou mais imagens",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    if st.button(
        "Adicionar à galeria",
        type="primary",
        disabled=not arquivos,
        width="stretch",
    ):
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
