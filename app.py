from io import BytesIO
import os
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import streamlit as st

import recognition


# Banco local com nomes e codificações faciais. Não salvamos as fotos originais.
ARQUIVO_DADOS = Path("data/rostos.npz")
LIMIAR_RECONHECIMENTO = 0.5


def ler_imagem(arquivo_enviado) -> np.ndarray:
    imagem = Image.open(arquivo_enviado)
    # Corrige a orientação gravada pela câmera antes de analisar o rosto.
    imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    return np.asarray(imagem)


def carregar_rostos() -> tuple[list[str], np.ndarray]:
    if not ARQUIVO_DADOS.exists():
        return [], np.empty((0, 128), dtype=np.float64)

    with np.load(ARQUIVO_DADOS, allow_pickle=False) as dados:
        return dados["names"].tolist(), dados["encodings"]


def salvar_rostos(nomes: list[str], codificacoes: np.ndarray) -> None:
    ARQUIVO_DADOS.parent.mkdir(parents=True, exist_ok=True)
    memoria = BytesIO()
    np.savez_compressed(
        memoria, names=np.asarray(nomes), encodings=codificacoes
    )

    # Primeiro grava em arquivo temporário para evitar um banco incompleto.
    with tempfile.NamedTemporaryFile(
        dir=ARQUIVO_DADOS.parent, delete=False
    ) as arquivo_temporario:
        arquivo_temporario.write(memoria.getvalue())
        caminho_temporario = arquivo_temporario.name
    os.replace(caminho_temporario, ARQUIVO_DADOS)


def excluir_pessoa(
    pessoa: str, nomes: list[str], codificacoes: np.ndarray
) -> tuple[list[str], np.ndarray]:
    # Uma pessoa pode ter várias fotos e todas são removidas juntas.
    manter = np.asarray([nome != pessoa for nome in nomes])
    return [nome for nome in nomes if nome != pessoa], codificacoes[manter]


def identificar(
    codificacao: np.ndarray,
    nomes: list[str],
    codificacoes_conhecidas: np.ndarray,
) -> str:
    if not nomes:
        return "Desconhecido"

    distancias = recognition.calcular_distancias(
        codificacoes_conhecidas, codificacao
    )
    melhor_indice = int(np.argmin(distancias))
    if distancias[melhor_indice] <= LIMIAR_RECONHECIMENTO:
        return nomes[melhor_indice]
    return "Desconhecido"


def criar_imagem_anotada(
    imagem: np.ndarray,
    localizacoes: list[tuple[int, int, int, int]],
    rotulos: list[str],
) -> Image.Image:
    resultado = Image.fromarray(imagem).copy()
    desenho = ImageDraw.Draw(resultado)
    fonte = ImageFont.load_default(size=16)

    for (topo, direita, base, esquerda), rotulo in zip(localizacoes, rotulos):
        desenho.rectangle(
            (esquerda, topo, direita, base), outline="#22c55e", width=4
        )
        caixa_texto = desenho.textbbox((esquerda, base), rotulo, font=fonte)
        desenho.rectangle(
            (
                caixa_texto[0] - 4,
                caixa_texto[1] - 3,
                caixa_texto[2] + 4,
                caixa_texto[3] + 3,
            ),
            fill="#22c55e",
        )
        desenho.text((esquerda, base), rotulo, fill="white", font=fonte)

    return resultado


st.set_page_config(page_title="Reconhecimento facial", page_icon="👤")
st.title("Reconhecimento facial")
st.caption("Cadastre uma pessoa e reconheça-a em novas fotos.")

nomes, codificacoes_conhecidas = carregar_rostos()
aba_cadastro, aba_reconhecimento = st.tabs(["Cadastrar", "Reconhecer"])

with aba_cadastro:
    if pessoa_excluida := st.session_state.pop("pessoa_excluida", None):
        st.success(f"O cadastro de {pessoa_excluida} foi apagado.")

    nome = st.text_input("Nome da pessoa")
    arquivo_cadastro = st.file_uploader(
        "Foto para cadastro",
        type=["jpg", "jpeg", "png", "webp"],
        key="cadastro",
    )

    if st.button(
        "Cadastrar pessoa",
        type="primary",
        disabled=not (nome.strip() and arquivo_cadastro),
    ):
        imagem = ler_imagem(arquivo_cadastro)
        localizacoes = recognition.localizar_rostos(imagem)

        if len(localizacoes) != 1:
            st.error("A foto precisa conter exatamente um rosto visível.")
        else:
            codificacao = recognition.codificar_rostos(imagem, localizacoes)[0]
            nomes_atualizados = [*nomes, nome.strip()]
            codificacoes_atualizadas = np.vstack(
                (codificacoes_conhecidas, codificacao)
            )
            salvar_rostos(nomes_atualizados, codificacoes_atualizadas)
            st.success(f"{nome.strip()} foi cadastrado(a).")
            st.rerun()

    if nomes:
        st.caption(
            f"{len(nomes)} foto(s) cadastrada(s) para "
            f"{len(set(nomes))} pessoa(s)."
        )

    with st.expander("Gerenciar cadastros"):
        if not nomes:
            st.info("Nenhuma pessoa cadastrada.")
        else:
            pessoa_selecionada = st.selectbox("Pessoa", sorted(set(nomes)))
            quantidade_fotos = nomes.count(pessoa_selecionada)
            st.caption(
                f"Isto apagará {quantidade_fotos} foto(s) cadastrada(s) "
                f"para {pessoa_selecionada}."
            )
            exclusao_confirmada = st.checkbox(
                f"Confirmo que desejo apagar {pessoa_selecionada}",
                key=f"confirmar_exclusao_{pessoa_selecionada}",
            )

            if st.button(
                "Apagar cadastro",
                disabled=not exclusao_confirmada,
                key="excluir_pessoa",
            ):
                nomes, codificacoes_conhecidas = excluir_pessoa(
                    pessoa_selecionada, nomes, codificacoes_conhecidas
                )
                salvar_rostos(nomes, codificacoes_conhecidas)
                st.session_state.pessoa_excluida = pessoa_selecionada
                st.rerun()

with aba_reconhecimento:
    arquivo_reconhecimento = st.file_uploader(
        "Foto para reconhecer",
        type=["jpg", "jpeg", "png", "webp"],
        key="reconhecimento",
    )

    if arquivo_reconhecimento:
        imagem = ler_imagem(arquivo_reconhecimento)
        localizacoes = recognition.localizar_rostos(imagem)
        codificacoes = recognition.codificar_rostos(imagem, localizacoes)

        if not codificacoes:
            st.warning("Nenhum rosto foi encontrado na foto.")
        elif not nomes:
            st.warning("Cadastre ao menos uma pessoa antes de reconhecer.")
        else:
            rotulos = [
                identificar(codificacao, nomes, codificacoes_conhecidas)
                for codificacao in codificacoes
            ]
            st.image(
                criar_imagem_anotada(imagem, localizacoes, rotulos),
                width="stretch",
            )
            st.write("Identificação: " + ", ".join(rotulos))
