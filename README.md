# Galeria com reconhecimento facial

Aplicação desenvolvida com Streamlit para armazenar e organizar fotos em formato de galeria. O sistema detecta os rostos presentes nas imagens e permite
atribuir um nome a cada pessoa. Depois da identificação, fotos anteriores e
novas fotos com rostos semelhantes recebem o mesmo nome automaticamente.

As imagens e os dados de reconhecimento ficam armazenados localmente. O projeto
não envia fotos para serviços externos.

## Funcionalidades

- Upload de imagens nos formatos JPEG, PNG e WebP.
- Organização automática da galeria por mês e ano.
- Uso da data registrada nos metadados da foto, quando disponível.
- Detecção de uma ou mais pessoas na mesma imagem.
- Propagação de um nome para fotos anteriores da mesma pessoa.
- Reconhecimento automático da pessoa em novos uploads.
- Filtros por intervalo de datas e nomes de pessoas.
- Detecção e descarte de imagens duplicadas.

## Requisitos

- Python 3.10 ou superior.
- Um ambiente compatível com os pacotes binários do dlib.

## Instalação

Clone o repositório e acesse seu diretório:

```bash
git clone git@github.com:luquasgabriel/projeto-pdsi-reconhecimento-facial.git
cd projeto-pdsi-reconhecimento-facial
```

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

No Windows, a ativação pode ser feita com:

```powershell
.venv\Scripts\activate
```

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

Inicie a aplicação:

```bash
python -m streamlit run app.py
```

O Streamlit exibirá no terminal o endereço local para acessar a galeria.

## Bibliotecas utilizadas

| Biblioteca | Finalidade |
|---|---|
| Streamlit | Interface web, upload, filtros, galeria e modal de identificação |
| dlib-bin | Detecção, alinhamento e codificação dos rostos |
| face-recognition-models | Arquivos dos modelos pré-treinados utilizados pelo dlib |
| NumPy | Manipulação dos pixels, vetores faciais e cálculo de distâncias |
| Pillow | Leitura, orientação, redimensionamento e anotação das imagens |

`dlib-bin` fornece uma distribuição binária do dlib, evitando a compilação
local da biblioteca na maioria dos ambientes.

## Modelos utilizados

### Detector frontal HOG

O detector retornado por `dlib.get_frontal_face_detector()` encontra as regiões
da imagem que contêm rostos. Ele utiliza Histogram of Oriented Gradients (HOG)
e não identifica a pessoa, apenas informa onde cada rosto está.

### Preditor de 68 pontos faciais

O arquivo `shape_predictor_68_face_landmarks.dat` localiza 68 pontos de
referência no contorno do rosto, sobrancelhas, olhos, nariz e boca. Esses pontos
orientam o alinhamento necessário para criar uma representação facial
consistente.

### ResNet de reconhecimento facial

O arquivo `dlib_face_recognition_resnet_model_v1.dat` transforma o rosto
alinhado em um vetor de 128 números, também chamado de codificação ou
*embedding* facial.

O sistema calcula a distância euclidiana entre esses vetores. Distâncias
menores indicam rostos mais semelhantes. O limiar usado pelo projeto é `0.5`:

```text
distância <= 0.5  → mesma pessoa
distância > 0.5   → pessoa desconhecida
```

## Fluxo da aplicação

1. O usuário seleciona uma ou mais imagens no painel **Adicionar fotos**.
2. O sistema calcula um hash SHA-256 e ignora arquivos já armazenados.
3. A data é obtida dos metadados EXIF ou, quando ausente, do momento do upload.
4. A imagem original é salva em `data/imagens/`.
5. O detector HOG encontra todos os rostos da imagem.
6. O preditor encontra os 68 pontos de cada rosto.
7. A ResNet gera uma codificação de 128 números para cada pessoa.
8. As codificações são comparadas com os rostos já conhecidos.
9. A foto aparece na galeria, agrupada pelo mês em que foi registrada.
10. Ao clicar na foto, um modal mostra os rostos detectados.
11. O usuário seleciona um rosto e informa o nome da pessoa.
12. O nome é propagado para rostos semelhantes das fotos já armazenadas.
13. A codificação nomeada passa a ser usada nos próximos uploads.

## Armazenamento local

O diretório `data/` é criado automaticamente e não é versionado pelo Git:

```text
data/
├── imagens/       # imagens originais
├── galeria.json   # metadados, rostos detectados e codificações
└── rostos.npz     # nomes e codificações faciais conhecidas
```

- `galeria.json` mantém o catálogo das fotos, suas datas e os rostos presentes.
- `rostos.npz` é um arquivo compactado do NumPy com os nomes e vetores faciais.
- `imagens/` contém os arquivos enviados pelo usuário.

Faça backup do diretório `data/` para preservar a galeria e as identificações.

## Estrutura do projeto

```text
app.py                       # interface e componentes visuais do Streamlit
galeria.py                   # persistência, catálogo e propagação dos nomes
reconhecimento_facial.py     # carregamento e execução dos modelos do dlib
requirements.txt             # dependências Python
```

## Privacidade e limitações

Codificações faciais são dados biométricos. Antes de utilizar a aplicação com
outras pessoas, obtenha consentimento e defina regras de acesso, retenção e
exclusão dos dados.

Este projeto é um protótipo. A qualidade do reconhecimento depende de fatores
como iluminação, posição do rosto, resolução da imagem e semelhança entre as
pessoas.
