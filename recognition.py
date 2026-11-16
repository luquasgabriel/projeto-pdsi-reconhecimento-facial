from importlib.util import find_spec
from pathlib import Path

import dlib
import numpy as np


# Os modelos são carregados uma única vez, quando a aplicação é iniciada.
_pacote_modelos = find_spec("face_recognition_models")
if _pacote_modelos is None or _pacote_modelos.submodule_search_locations is None:
    raise RuntimeError("O pacote face-recognition-models não está instalado.")

_diretorio_modelos = (
    Path(next(iter(_pacote_modelos.submodule_search_locations))) / "models"
)
_detector_rostos = dlib.get_frontal_face_detector()
_preditor_marcos = dlib.shape_predictor(
    str(_diretorio_modelos / "shape_predictor_68_face_landmarks.dat")
)
_codificador_rostos = dlib.face_recognition_model_v1(
    str(_diretorio_modelos / "dlib_face_recognition_resnet_model_v1.dat")
)


def localizar_rostos(imagem: np.ndarray) -> list[tuple[int, int, int, int]]:
    altura, largura = imagem.shape[:2]
    return [
        (
            max(retangulo.top(), 0),
            min(retangulo.right(), largura),
            min(retangulo.bottom(), altura),
            max(retangulo.left(), 0),
        )
        for retangulo in _detector_rostos(imagem, 1)
    ]


def codificar_rostos(
    imagem: np.ndarray, localizacoes: list[tuple[int, int, int, int]]
) -> list[np.ndarray]:
    codificacoes = []
    for topo, direita, base, esquerda in localizacoes:
        retangulo = dlib.rectangle(
            left=esquerda, top=topo, right=direita, bottom=base
        )
        marcos_faciais = _preditor_marcos(imagem, retangulo)
        descritor = _codificador_rostos.compute_face_descriptor(
            imagem, marcos_faciais
        )
        codificacoes.append(np.asarray(descritor))
    return codificacoes


def calcular_distancias(
    codificacoes_conhecidas: np.ndarray, codificacao: np.ndarray
) -> np.ndarray:
    # Quanto menor a distância, maior a semelhança entre os rostos.
    return np.linalg.norm(codificacoes_conhecidas - codificacao, axis=1)
