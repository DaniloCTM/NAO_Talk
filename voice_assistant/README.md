# Voice Assistant — Pipeline Local

Assistente de voz modular que roda majoritariamente de forma local.
Desenvolvido como protótipo para futura integração com o robô NAO.

## Fluxo

```
Microfone → STT (Whisper, local) → LLM (OpenRouter, cloud) → TTS (Piper, local) → Caixa de som
```

---

## Pré-requisitos

- Python 3.11+
- `pip`
- Binário do Piper (instruções abaixo)
- Conta no [OpenRouter](https://openrouter.ai/) com API key

---

## Instalação

### 1. Clonar e entrar no diretório

```bash
cd voice_assistant
```

### 2. Criar ambiente virtual e instalar dependências

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Instalar o Piper TTS

```bash
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
tar -xzf piper_linux_x86_64.tar.gz -C /tmp/
cp /tmp/piper/piper ~/.local/bin/
```

> O diretório `~/.local/bin` precisa estar no `PATH`. Verifique com `which piper`.

### 4. Baixar o modelo de voz PT-BR

```bash
mkdir -p models
wget -O models/pt_BR-faber-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
wget -O models/pt_BR-faber-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"
```

### 5. Configurar a API key

```bash
cp .env.example .env
# editar .env e preencher OPENROUTER_API_KEY
```

---

## Executar

```bash
cd voice_assistant
python -m src.main
```

O assistente ficará aguardando fala. Quando detectar voz, grava até o silêncio, transcreve, consulta o LLM e responde em voz.
Para encerrar: `Ctrl+C`.

### Gravar dataset de teste

Para gravar um conjunto de áudios rotulados em `dataset_teste/`:

```bash
cd voice_assistant
python3 scripts/record_test_dataset.py
```

O script usa as frases de `dataset_teste/prompts_default.json`, salva os WAVs em `dataset_teste/audio/` e atualiza `manifest.csv` e `manifest.jsonl` a cada gravação aceita.

---

## Configuração

Todos os parâmetros ficam em `config/config.yaml`:

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `audio.vad_mode` | Backend de VAD (`webrtc` recomendado, `rms` legado) | `webrtc` |
| `audio.vad_aggressiveness` | Agressividade do WebRTC VAD (`0` a `3`) | `2` |
| `audio.vad_frame_ms` | Tamanho do frame do WebRTC VAD | `30` |
| `audio.speech_threshold` | RMS mínimo para considerar fala no modo `rms` (0.0–1.0) | `0.02` |
| `audio.silence_duration` | Segundos de silêncio para encerrar gravação | `1.5` |
| `audio.max_duration` | Limite máximo de gravação em segundos | `30.0` |
| `stt.model` | Modelo Whisper (`tiny`, `small`, `medium`) | `small` |
| `stt.compute_type` | Quantização CPU (`int8`, `float32`) | `int8` |
| `stt.language` | Idioma forçado (`pt`, `en`, ou `null` para auto) | `pt` |
| `llm.model` | Modelo no OpenRouter | `arcee-ai/trinity-large-preview:free` |
| `llm.system_prompt` | Instrução de comportamento do assistente | ver config |
| `tts.model_path` | Caminho para o arquivo `.onnx` do Piper | `models/pt_BR-faber-medium.onnx` |
| `tts.sample_rate` | Taxa de amostragem do modelo TTS (Hz) | `22050` |

### Ajustando a detecção de fala

O padrão recomendado é `audio.vad_mode: webrtc`, que costuma detectar fala melhor sem aumentar a latência perceptível.

Se o assistente estiver cortando a fala muito cedo, aumente `silence_duration`.
Se quiser uma detecção mais conservadora no modo `webrtc`, aumente `vad_aggressiveness`.
Se estiver usando o fallback `rms` e o assistente captar ruído de fundo como fala, aumente `speech_threshold`.

---

## Métricas de latência

A cada turno completo, as latências são salvas em `logs/metrics.csv`:

| Coluna | Descrição |
|---|---|
| `timestamp` | Data e hora do turno |
| `turn` | Número sequencial do turno |
| `audio_duration_s` | Duração do áudio capturado |
| `stt_latency_s` | Tempo de transcrição (Whisper) |
| `llm_latency_s` | Tempo de resposta do LLM |
| `tts_latency_s` | Tempo de síntese de voz (Piper) |
| `total_latency_s` | Soma STT + LLM + TTS |
| `transcription` | Texto transcrito |
| `response_chars` | Tamanho da resposta em caracteres |

---

## Estrutura do projeto

```
voice_assistant/
├── config/
│   └── config.yaml          # Configuração central
├── logs/
│   └── metrics.csv          # Gerado automaticamente
├── models/
│   └── pt_BR-faber-medium.onnx
├── src/
│   ├── main.py
│   ├── pipeline/
│   │   └── assistant_pipeline.py
│   ├── audio/
│   │   ├── recorder.py      # Captura com WebRTC VAD e fallback RMS
│   │   └── player.py
│   ├── stt/
│   │   ├── base_stt.py
│   │   └── faster_whisper_stt.py
│   ├── llm/
│   │   ├── base_llm.py
│   │   └── openrouter_client.py
│   ├── tts/
│   │   ├── base_tts.py
│   │   └── piper_tts.py
│   └── utils/
│       ├── config_loader.py
│       ├── logger.py
│       └── metrics.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Substituindo componentes

A arquitetura é baseada em interfaces (`BaseSTT`, `BaseLLM`, `BaseTTS`).
Para trocar um componente, implemente a interface e passe a nova instância em `main.py`:

```python
# Exemplo: trocar para Ollama (LLM local)
from src.llm.ollama_client import OllamaClient
llm = OllamaClient(model="llama3")

# Exemplo: trocar STT para Vosk
from src.stt.vosk_stt import VoskSTT
stt = VoskSTT(model_path="models/vosk-pt")
```
