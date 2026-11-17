from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import numpy as np
from PIL import Image, ImageOps

import recognition


DIRETORIO_DADOS = Path("data")
DIRETORIO_IMAGENS = DIRETORIO_DADOS / "imagens"
ARQUIVO_CATALOGO = DIRETORIO_DADOS / "galeria.json"
ARQUIVO_ROSTOS = DIRETORIO_DADOS / "rostos.npz"
LIMIAR_RECONHECIMENTO = 0.5

EXTENSOES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def ler_imagem(origem) -> np.ndarray:
    """Abre uma imagem, corrige sua orientação e retorna pixels RGB."""
    with Image.open(origem) as imagem:
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
        return np.asarray(imagem)


def carregar_catalogo() -> list[dict]:
    if not ARQUIVO_CATALOGO.exists():
        return []
    return json.loads(ARQUIVO_CATALOGO.read_text(encoding="utf-8"))


def salvar_catalogo(catalogo: list[dict]) -> None:
    _salvar_atomicamente(
        ARQUIVO_CATALOGO,
        json.dumps(catalogo, ensure_ascii=False).encode("utf-8"),
    )


def carregar_rostos() -> tuple[list[str], np.ndarray]:
    """Carrega a base antiga para aproveitar pessoas já cadastradas."""
    if not ARQUIVO_ROSTOS.exists():
        return [], np.empty((0, 128), dtype=np.float64)

    with np.load(ARQUIVO_ROSTOS, allow_pickle=False) as dados:
        return dados["names"].tolist(), dados["encodings"]


def adicionar_imagem(
    arquivo_enviado,
    catalogo: list[dict],
    nomes_conhecidos: list[str],
    codificacoes_conhecidas: np.ndarray,
) -> dict | None:
    """Salva uma imagem e registra os rostos encontrados nela."""
    conteudo = arquivo_enviado.getvalue()
    resumo = sha256(conteudo).hexdigest()

    # Evita duplicar a mesma foto caso o botão seja acionado novamente.
    if any(foto.get("hash") == resumo for foto in catalogo):
        return None

    with Image.open(BytesIO(conteudo)) as imagem_original:
        formato = imagem_original.format
        if formato not in EXTENSOES:
            raise ValueError("Formato de imagem não suportado.")
        data_foto = _obter_data_foto(imagem_original)

    imagem = ler_imagem(BytesIO(conteudo))
    localizacoes = recognition.localizar_rostos(imagem)
    codificacoes = recognition.codificar_rostos(imagem, localizacoes)

    rostos = []
    for localizacao, codificacao in zip(localizacoes, codificacoes):
        rostos.append(
            {
                "localizacao": list(localizacao),
                "codificacao": codificacao.tolist(),
                "nome": _identificar(
                    codificacao, nomes_conhecidos, codificacoes_conhecidas
                ),
            }
        )

    identificador = uuid4().hex
    nome_arquivo = identificador + EXTENSOES[formato]
    DIRETORIO_IMAGENS.mkdir(parents=True, exist_ok=True)
    (DIRETORIO_IMAGENS / nome_arquivo).write_bytes(conteudo)

    return {
        "id": identificador,
        "arquivo": nome_arquivo,
        "nome_original": arquivo_enviado.name,
        "data": data_foto.isoformat(),
        "hash": resumo,
        "rostos": rostos,
    }


def nomear_rosto(
    catalogo: list[dict], identificador_foto: str, indice_rosto: int, nome: str
) -> tuple[int, np.ndarray]:
    """Propaga um nome para rostos semelhantes de todas as fotos."""
    foto = next(item for item in catalogo if item["id"] == identificador_foto)
    codificacao_referencia = np.asarray(
        foto["rostos"][indice_rosto]["codificacao"]
    )
    quantidade = 0

    # A comparação retroativa atualiza fotos anteriores e também a selecionada.
    for item in catalogo:
        for rosto in item["rostos"]:
            codificacao = np.asarray(rosto["codificacao"])
            distancia = recognition.calcular_distancias(
                np.asarray([codificacao]), codificacao_referencia
            )[0]
            if distancia <= LIMIAR_RECONHECIMENTO:
                rosto["nome"] = nome
                quantidade += 1

    return quantidade, codificacao_referencia


def adicionar_rosto_conhecido(nome: str, codificacao: np.ndarray) -> None:
    nomes, codificacoes = carregar_rostos()
    nomes.append(nome)
    codificacoes = np.vstack((codificacoes, codificacao))

    memoria = BytesIO()
    np.savez_compressed(
        memoria, names=np.asarray(nomes), encodings=codificacoes
    )
    _salvar_atomicamente(ARQUIVO_ROSTOS, memoria.getvalue())


def caminho_da_imagem(foto: dict) -> Path:
    return DIRETORIO_IMAGENS / foto["arquivo"]


def _identificar(
    codificacao: np.ndarray,
    nomes: list[str],
    codificacoes_conhecidas: np.ndarray,
) -> str | None:
    if not nomes:
        return None

    distancias = recognition.calcular_distancias(
        codificacoes_conhecidas, codificacao
    )
    melhor_indice = int(np.argmin(distancias))
    if distancias[melhor_indice] <= LIMIAR_RECONHECIMENTO:
        return nomes[melhor_indice]
    return None


def _obter_data_foto(imagem: Image.Image) -> datetime:
    """Usa a data EXIF da câmera ou, se ausente, a data do upload."""
    dados_exif = imagem.getexif()
    texto_data = dados_exif.get(36867) or dados_exif.get(306)
    if texto_data:
        try:
            return datetime.strptime(str(texto_data), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now().replace(microsecond=0)


def _salvar_atomicamente(caminho: Path, conteudo: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=caminho.parent, delete=False
    ) as arquivo_temporario:
        arquivo_temporario.write(conteudo)
        caminho_temporario = arquivo_temporario.name
    os.replace(caminho_temporario, caminho)
