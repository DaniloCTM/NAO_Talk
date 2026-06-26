# Voice Assistant

Este projeto roda dividido em duas partes:

- `Servidor`: faz STT, LLM e TTS
- `NAO`: captura o áudio do microfone e toca a resposta

## O que roda em cada máquina

### Servidor

No servidor rodam:

- `faster-whisper`
- integração com OpenRouter
- `piper` para síntese de voz
- servidor TCP do projeto

### NAO

No NAO roda:

- o script [scripts/client.sh](/home/danilo/Faculdade/TCC/code/voice_assistant/scripts/client.sh:1)
- captura de áudio com `arecord`
- envio para o servidor com `nc`
- reprodução da resposta com `aplay`

## Dependências

### Servidor

Pré-requisitos:

- Python 3.10+
- `pip`
- conta no OpenRouter com API key
- `piper`

Instalação:

```bash
cd voice_assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Instalar o Piper:

```bash
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
tar -xzf piper_linux_x86_64.tar.gz -C /tmp/
cp /tmp/piper/piper ~/.local/bin/
```

Baixar o modelo de voz:

```bash
mkdir -p models
wget -O models/pt_BR-faber-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
wget -O models/pt_BR-faber-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"
```

Configurar a API key:

```bash
cp .env.example .env
```

Preencha `OPENROUTER_API_KEY` no arquivo `.env`.

### NAO

Pré-requisitos:

- `arecord`
- `aplay`
- `sox`
- `nc`

Em Ubuntu/Debian:

```bash
sudo apt install alsa-utils sox netcat-openbsd
```

## Como rodar

### 1. Rodar o servidor

No servidor:

```bash
cd voice_assistant
source .venv/bin/activate
python -m src.main --mode tcp-stream-server --host 0.0.0.0 --port 50007
```

Se preferir modo TCP sem streaming:

```bash
python -m src.main --mode tcp-server --host 0.0.0.0 --port 50007
```

### 2. Rodar o cliente no NAO

No NAO:

```bash
cd voice_assistant/scripts
chmod +x client.sh
./client.sh IP_DO_SERVIDOR 50007
```

Exemplo:

```bash
./client.sh 10.0.69.12 50007
```

## Resumo rápido

Servidor:

```bash
cd voice_assistant
source .venv/bin/activate
python -m src.main --mode tcp-stream-server --host 0.0.0.0 --port 50007
```

NAO:

```bash
cd voice_assistant/scripts
./client.sh 10.0.69.12 50007
```
