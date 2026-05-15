# Documentacao Tecnica e Cientifica do Projeto Voice Assistant

## 1. Resumo

Este documento descreve, em nivel tecnico e cientifico, o funcionamento do projeto `voice_assistant`, um assistente de voz modular projetado para operar tanto em modo local quanto em modo distribuido via rede. O sistema implementa um pipeline de processamento de fala composto por captura de audio, deteccao de atividade vocal, transcricao automatica de fala, geracao de resposta por modelo de linguagem e sintese de voz. A arquitetura foi concebida de forma desacoplada, com interfaces abstratas para os modulos de STT, LLM e TTS, permitindo substituicao controlada de componentes sem alterar a logica de orquestracao.

Do ponto de vista computacional, o sistema combina processamento local de sinal, inferencia de modelos neurais em CPU, comunicacao de rede com protocolos UDP e TCP e coleta estruturada de metricas de latencia. O projeto foi desenvolvido como base experimental para integracao futura com o robo NAO, mantendo foco em reprodutibilidade, modularidade e avaliacao de desempenho.

## 2. Objetivo do Sistema

O objetivo principal do sistema e implementar uma cadeia conversacional por voz com baixa complexidade de integracao e possibilidade de experimentacao. Em termos funcionais, o software deve:

- capturar audio de entrada a partir de um microfone;
- detectar automaticamente inicio e fim de fala;
- converter o sinal de voz em texto;
- enviar o texto a um modelo de linguagem para gerar resposta curta;
- sintetizar a resposta em audio;
- reproduzir o resultado localmente ou devolve-lo pela rede.

Em termos de engenharia de software, o sistema tambem busca:

- separacao clara de responsabilidades;
- configuracao centralizada;
- capacidade de operar em diferentes modos de execucao;
- registro de metricas para avaliacao de latencia;
- facilidade de substituicao de backends.

## 3. Visao Geral da Arquitetura

O sistema e organizado ao redor de um pipeline principal:

`Audio -> STT -> LLM -> TTS`

Essa cadeia aparece de forma direta no modo local e de forma distribuida nos modos de rede. A entrada principal do sistema encontra-se em `src/main.py`, onde a configuracao e carregada, os componentes sao instanciados e o modo de operacao e selecionado.

Os principais blocos arquiteturais sao:

- `audio`: captura e reproducao de audio;
- `stt`: transcricao de fala em texto;
- `llm`: geracao de resposta textual;
- `tts`: sintese de voz;
- `pipeline`: orquestracao do fluxo local;
- `network`: transporte distribuido de audio e resposta;
- `utils`: configuracao, logging e metricas.

Essa decomposicao adota um principio de modularidade por responsabilidade unica. Cada modulo encapsula uma classe de problema: I/O de audio, inferencia, comunicacao ou observabilidade.

## 4. Modelo de Execucao

O projeto suporta cinco modos principais:

1. `local`: todo o pipeline executa na mesma maquina.
2. `server`: um servidor UDP recebe audio de um cliente remoto, processa o pipeline e retorna audio sintetizado.
3. `client`: um cliente UDP captura audio localmente, envia ao servidor e reproduz a resposta recebida.
4. `tcp-server`: um servidor TCP recebe uma requisicao em WAV, processa o pipeline e devolve um WAV.
5. `tcp-stream-server`: um servidor TCP recebe stream PCM bruto, com suporte a sobreposicao parcial entre recepcao e STT.

Essa organizacao permite comparar diferentes cenarios de implantacao:

- processamento inteiramente embarcado/local;
- processamento centralizado em um servidor;
- experimentos com impacto da rede sobre a latencia total;
- avaliacao de streaming incremental.

## 5. Carregamento de Configuracao

O arquivo `src/utils/config_loader.py` implementa o carregamento da configuracao a partir de `config/config.yaml` e de variaveis de ambiente. O fluxo e:

1. carregar variaveis definidas em `.env` usando `dotenv`;
2. localizar `config/config.yaml` a partir da raiz do projeto;
3. desserializar o YAML com `yaml.safe_load`;
4. injetar a chave `OPENROUTER_API_KEY` na estrutura `config["api_keys"]["openrouter"]`.

Essa estrategia possui relevancia pratica e metodologica:

- valores operacionais permanecem versionados no YAML;
- segredos nao precisam ser hardcoded;
- a configuracao torna-se reproduzivel entre execucoes;
- os parametros do experimento podem ser alterados sem modificar o codigo-fonte.

Os principais grupos de parametros sao:

- `audio`: taxa de amostragem, canais, limiar de fala, duracao de silencio e limite de gravacao;
- `stt`: modelo Whisper, tipo de computacao, idioma e hiperparametros de decodificacao;
- `llm`: modelo, endpoint, timeout, temperatura e prompt de sistema;
- `tts`: caminho do modelo Piper, sample rate e caminhos auxiliares;
- `network`: host, portas e parametros de streaming.

## 6. Captura de Audio e Deteccao de Fala

O modulo `src/audio/recorder.py` implementa a classe `AudioRecorder`, responsavel pela aquisicao de audio por meio da biblioteca `sounddevice`. A captura e feita com `InputStream`, em blocos de duracao fixa, armazenados em uma fila thread-safe.

### 6.1 Representacao do sinal

O audio e representado como um vetor unidimensional `numpy.ndarray` em ponto flutuante (`float32`), normalizado tipicamente no intervalo `[-1, 1]`. Essa representacao e adequada para:

- alimentacao direta do backend de STT;
- manipulacao numerica eficiente;
- conversao simples para PCM de 16 bits quando necessario.

### 6.2 Deteccao de atividade vocal

A deteccao de fala e baseada em energia RMS (Root Mean Square). Para cada bloco de amostras `x_1, x_2, ..., x_N`, calcula-se:

`RMS = sqrt((1/N) * sum(x_i^2))`

O sistema considera que ha fala quando `RMS >= speech_threshold`.

Essa escolha e simples, eficiente e de baixo custo computacional, sendo apropriada para prototipacao. O comportamento e:

- antes de detectar fala, blocos com RMS abaixo do limiar sao descartados;
- apos detectar fala, os blocos passam a ser acumulados;
- o encerramento da gravacao ocorre quando o numero de amostras em silencio ultrapassa `silence_duration`;
- ha tambem um limite superior `max_duration` para evitar gravacoes indefinidas.

### 6.3 Implicacoes tecnicas

As vantagens do metodo adotado sao:

- custo computacional muito baixo;
- nenhuma dependencia adicional de VAD neural;
- comportamento previsivel e facilmente parametrizavel.

As limitacoes sao:

- sensibilidade a ruido ambiente;
- possibilidade de falsos positivos em ambientes ruidosos;
- desempenho inferior ao de detectores de voz treinados em cenarios de baixa relacao sinal-ruido.

Mesmo com essas limitacoes, a tecnica e suficiente para um sistema experimental controlado.

## 7. Transcricao de Fala para Texto

O subsistema de STT esta definido pela interface `BaseSTT` em `src/stt/base_stt.py` e concretizado por `FasterWhisperSTT` em `src/stt/faster_whisper_stt.py`.

### 7.1 Papel da interface

A interface `BaseSTT` impõe o contrato:

`transcribe(audio: np.ndarray) -> str`

Essa decisao de projeto reduz acoplamento entre a orquestracao e a implementacao concreta. Assim, o pipeline nao depende de Faster Whisper especificamente; ele depende apenas da abstracao de transcricao.

### 7.2 Implementacao com Faster Whisper

O backend `FasterWhisperSTT` carrega um `WhisperModel` com:

- `model_size`: variante do modelo (`tiny`, `small`, `medium`, etc.);
- `device="cpu"`: execucao em CPU;
- `compute_type`: quantizacao, como `int8` ou `float32`.

Na etapa de inferencia, o metodo `transcribe` chama o motor do modelo com:

- audio em `float32`;
- idioma forcado ou autodetectado;
- `beam_size` para busca;
- `condition_on_previous_text` para controlar contexto entre trechos.

O resultado retornado pelo modelo consiste em segmentos, concatenados em uma unica string final.

### 7.3 Consideracoes cientificas

O modelo Whisper e baseado em uma arquitetura sequence-to-sequence treinada em larga escala sobre dados de fala multilingue. Do ponto de vista funcional:

- transforma um sinal acustico em representacao textual;
- pode detectar idioma;
- lida razoavelmente bem com variacoes de pronuncia;
- permite trocas entre custo computacional e qualidade via tamanho de modelo.

No contexto deste projeto, a escolha por `faster-whisper` e importante por oferecer:

- melhor desempenho de inferencia em CPU;
- API simples para integracao;
- suporte direto a audio em `numpy`.

## 8. Geracao de Resposta por Modelo de Linguagem

O subsistema de linguagem segue a mesma estrategia de abstrair a dependencia por meio de `BaseLLM`, definida em `src/llm/base_llm.py`. A implementacao concreta e `OpenRouterClient`, em `src/llm/openrouter_client.py`.

### 8.1 Estrutura da requisicao

O cliente prepara uma lista de mensagens no formato de chat:

- mensagem de sistema, contendo instrucoes comportamentais;
- mensagem do usuario, contendo o texto transcrito.

O payload enviado inclui:

- identificador do modelo;
- lista de mensagens;
- `max_tokens`, se configurado;
- `temperature`, se configurado.

### 8.2 Transporte HTTP

A comunicacao e realizada por `requests.Session`, com cabecalhos:

- `Authorization: Bearer <api_key>`;
- `Content-Type: application/json`.

Esse desenho oferece:

- persistencia de sessao HTTP;
- simplificacao da chamada ao endpoint;
- tratamento padrao de timeout e erros.

Se a resposta nao for bem-sucedida, o cliente registra erro e propaga a falha via `raise_for_status()`.

### 8.3 Papel do prompt de sistema

O `system_prompt` presente no arquivo de configuracao restringe o comportamento do modelo:

- responder em portugues;
- produzir resposta curta e direta;
- evitar markdown, listas e emojis.

Do ponto de vista experimental, isso reduz variabilidade na saida e facilita:

- sintese de voz mais previsivel;
- menor latencia de geracao;
- respostas mais adequadas a interacao oral.

### 8.4 Natureza hibrida do sistema

O projeto nao e integralmente local: a transcricao e a sintese sao executadas localmente, enquanto a inferencia do modelo de linguagem ocorre em nuvem via OpenRouter. Isso caracteriza uma arquitetura hibrida, com impacto direto sobre:

- latencia fim a fim;
- dependencia de conectividade;
- reproducibilidade de respostas entre execucoes.

## 9. Sintese de Voz

O subsistema TTS e definido pela interface `BaseTTS` em `src/tts/base_tts.py` e implementado por `PiperTTS` em `src/tts/piper_tts.py`.

### 9.1 Inicializacao

Na inicializacao, a classe:

- verifica se o executavel `piper` existe no `PATH`;
- armazena caminho do modelo ONNX;
- define a taxa de amostragem esperada;
- constroi `LD_LIBRARY_PATH` com possiveis diretorios de bibliotecas compartilhadas.

Esse passo e importante porque o Piper depende de recursos externos ao ambiente Python, especialmente binario e bibliotecas nativas.

### 9.2 Modos de operacao

O backend oferece tres operacoes:

- `speak(text)`: sintetiza e reproduz localmente;
- `synthesize_raw(text)`: sintetiza e retorna PCM bruto em bytes;
- `speak_to_file(text, output_path)`: sintetiza e salva como WAV.

No modo local, `speak` e suficiente. Nos modos de rede, `synthesize_raw` e preferivel porque permite encapsular ou transmitir o audio sem tocar no dispositivo de saida do servidor.

### 9.3 Conversao e reproducao

O Piper retorna audio bruto em `int16`. O codigo converte esse buffer para `float32`, normalizando por `32768.0`, e utiliza `sounddevice` para reproducao.

Essa conversao segue a relacao:

`x_float = x_int16 / 32768`

onde `x_int16` pertence aproximadamente ao intervalo `[-32768, 32767]`.

## 10. Pipeline Local de Orquestracao

O modulo `src/pipeline/assistant_pipeline.py` implementa `AssistantPipeline`, a classe que materializa o ciclo de interacao local.

### 10.1 Sequencia de operacoes

O metodo `run_once()` executa:

1. iniciar coleta de metricas do turno;
2. capturar audio com `recorder.record()`;
3. medir duracao do audio;
4. transcrever o audio via `stt.transcribe(audio)`;
5. se nao houver texto, encerrar o turno;
6. gerar resposta via `llm.generate(text)`;
7. sintetizar e reproduzir via `tts.speak(response)`;
8. registrar latencias no `MetricsLogger`.

### 10.2 Caracteristicas do desenho

O pipeline e sequencial e sincrono. Isso significa que:

- cada etapa depende da conclusao da etapa anterior;
- o controle de fluxo e simples e facil de depurar;
- a latencia total e aproximadamente a soma das latencias de STT, LLM e TTS, somada ao tempo de captura do audio.

Essa opcao privilegia simplicidade e confiabilidade em detrimento de paralelismo.

## 11. Modos de Rede

O projeto possui dois modelos principais de operacao distribuida: UDP e TCP.

### 11.1 Cliente UDP

O arquivo `src/network/udp_client.py` implementa um cliente que:

1. captura audio localmente;
2. converte o vetor `float32` para PCM `int16`;
3. divide os bytes em blocos de tamanho seguro;
4. envia pacotes `AUDIO_DATA`;
5. envia `AUDIO_END` para sinalizar termino;
6. aguarda `RESPONSE_META`, `RESPONSE_DATA` e `RESPONSE_END`;
7. reconstrui o PCM recebido;
8. reproduz o audio.

No modo `streaming_enabled`, o envio ocorre enquanto o usuario ainda esta falando, por meio de `record_stream()`. Isso reduz tempo ocioso entre captura e processamento.

### 11.2 Servidor UDP

O arquivo `src/network/udp_server.py` implementa a recepcao e processamento do lado servidor.

No modo nao streaming:

- o servidor recebe e ordena todos os pacotes por numero de sequencia;
- concatena os bytes;
- reconstrui o audio `float32`;
- processa STT, LLM e TTS;
- envia a resposta ao cliente.

No modo streaming:

- os chunks sao armazenados progressivamente;
- uma thread secundaria executa transcricoes parciais;
- quando o envio termina, o sistema pode reutilizar a transcricao parcial final;
- a intencao e sobrepor parte da recepcao de audio com o custo de STT.

### 11.3 Servidor TCP

O modulo `src/network/tcp_server.py` oferece uma alternativa baseada em conexao.

Os formatos de entrada sao:

- `wav`: modo legado com envio de arquivo WAV completo;
- `pcm_s16le`: modo de streaming com audio PCM bruto.

O fluxo geral e:

1. aceitar conexao;
2. ler toda a requisicao ou stream;
3. decodificar o audio;
4. salvar copia de depuracao em `/tmp`;
5. transcrever;
6. gerar resposta;
7. sintetizar em PCM;
8. encapsular como WAV;
9. enviar a resposta ao cliente.

### 11.4 Justificativa tecnica para UDP e TCP

O uso de UDP e adequado para experimentos com:

- baixa sobrecarga de protocolo;
- controle explicito do empacotamento;
- streaming simples de datagramas.

Entretanto, UDP nao garante:

- entrega;
- ordenacao;
- ausencia de duplicacao.

Por isso, o codigo usa numeros de sequencia para remontagem.

O uso de TCP oferece:

- canal confiavel;
- ordenacao garantida;
- modelo mais simples para transferencia de fluxo continuo.

Por outro lado, pode introduzir maior latencia e maior acoplamento a conexao.

## 12. Protocolo Binario UDP

O arquivo `src/network/protocol.py` define um protocolo binario proprio. O cabecalho de cada pacote e:

- 1 byte para `type`;
- 4 bytes para `seq` em big-endian;
- 4 bytes para `length` em big-endian.

Assim, o layout e:

`[type][seq][length][payload]`

Os tipos de mensagem sao:

- `AUDIO_DATA = 1`
- `AUDIO_END = 2`
- `RESPONSE_META = 3`
- `RESPONSE_DATA = 4`
- `RESPONSE_END = 5`
- `ERROR = 6`

O tamanho maximo definido para carga util e `MAX_CHUNK = 60000`, escolhido para manter o payload dentro de um intervalo seguro para UDP.

### 12.1 Relevancia do campo de sequencia

Em comunicacao UDP, pacotes podem chegar:

- fora de ordem;
- duplicados;
- perdidos.

O uso de `seq` permite:

- remontar o fluxo no lado receptor;
- organizar os chunks por ordem crescente;
- detectar, ao menos implicitamente, lacunas na sequencia.

O protocolo permanece propositalmente simples, o que e adequado para um prototipo experimental.

## 13. Instrumentacao e Medicao de Latencia

O modulo `src/utils/metrics.py` implementa um mecanismo de observabilidade baseado em CSV. A classe `TurnMetrics` representa as variaveis medidas por turno, e `MetricsLogger` persiste os resultados em `logs/metrics.csv`.

### 13.1 Variaveis medidas

As principais metricas registradas sao:

- `audio_duration_s`: duracao do audio de entrada;
- `receive_wall_s`: tempo de recepcao da requisicao em rede;
- `stt_latency_s`: tempo de transcricao;
- `llm_latency_s`: tempo de resposta do modelo de linguagem;
- `tts_latency_s`: tempo de sintese;
- `total_latency_s`: soma STT + LLM + TTS;
- `post_receive_to_response_s`: tempo entre fim da recepcao e producao da resposta;
- `stt_used_partial`: se a transcricao parcial foi reaproveitada;
- `transcription`: texto transcrito;
- `response_chars`: tamanho da resposta.

### 13.2 Metodo de medicao

As medicoes sao feitas com um context manager `timer()` baseado em `time.perf_counter()`, apropriado para metricas de alta resolucao em benchmarking local.

Em termos analiticos:

`total_latency_s = stt_latency_s + llm_latency_s + tts_latency_s`

Essa metrica exclui o tempo de captura de audio e, no modo local, representa o custo de processamento posterior ao encerramento da fala. Ja em modos de rede, `receive_wall_s` e `post_receive_to_response_s` ajudam a decompor a latencia fim a fim.

### 13.3 Importancia experimental

O registro estruturado em CSV viabiliza:

- analise estatistica posterior;
- comparacao entre configuracoes;
- medicao do impacto de streaming;
- construcao de graficos para TCC ou artigo.

## 14. Logging e Observabilidade Operacional

O modulo `src/utils/logger.py` define um logger centralizado com `StreamHandler` para `stdout`, formato temporal e nivel configuravel. Embora simples, essa decisao e importante para:

- rastrear o estado do sistema em execucao;
- associar mensagens a modulos especificos;
- facilitar depuracao em testes locais e distribuido.

As mensagens de log incluem, por exemplo:

- inicio e fim de captura;
- texto detectado;
- resposta gerada;
- erros HTTP;
- inicio de servidores;
- conexoes recebidas;
- metricas consolidadas por turno.

## 15. Principios de Projeto de Software

O codigo adota alguns principios de engenharia relevantes.

### 15.1 Inversao de dependencia

`AssistantPipeline`, `UDPServer` e `TCPServer` dependem de `BaseSTT`, `BaseLLM` e `BaseTTS`, nao de implementacoes concretas. Isso reduz rigidez arquitetural e permite experimentacao com novos backends.

### 15.2 Baixo acoplamento

Cada modulo trata um problema especifico. Por exemplo:

- `AudioRecorder` nao conhece LLM;
- `OpenRouterClient` nao conhece captura de audio;
- `PiperTTS` nao depende do protocolo de rede;
- `MetricsLogger` nao precisa conhecer detalhes do modelo utilizado.

### 15.3 Alta coesao

As classes concentram responsabilidades semanticamente relacionadas. Isso facilita:

- testes isolados;
- leitura do codigo;
- manutencao incremental;
- extensao controlada.

## 16. Analise Tecnica de Cada Etapa do Pipeline

Esta secao sintetiza o papel cientifico-computacional de cada etapa.

### 16.1 Etapa 1: aquisicao do sinal de fala

Entrada analogica do usuario e convertida em um sinal digital amostrado a 16 kHz. O sinal e recebido em blocos curtos, o que permite avaliar energia local e controlar encerramento automatico da gravacao.

### 16.2 Etapa 2: segmentacao temporal baseada em energia

O sistema precisa isolar a fala util de trechos de silencio. Em vez de depender de delimitacao manual, emprega um criterio energetico local. Isso transforma um fluxo continuo de audio em uma janela de fala candidata ao reconhecimento.

### 16.3 Etapa 3: reconhecimento automatico de fala

O trecho segmentado e processado por um modelo neural do tipo encoder-decoder treinado para mapear representacoes acusticas em texto. O resultado textual substitui a informacao analogica da fala por uma representacao simbolica, adequada ao processamento linguistico subsequente.

### 16.4 Etapa 4: inferencia linguistica

O texto transcrito e interpretado por um modelo de linguagem conversacional. Nessa fase ocorre o processamento semantico da intencao do usuario e a producao de uma resposta textual coerente sob as restricoes do prompt de sistema.

### 16.5 Etapa 5: sintese de fala

O texto gerado e transformado em onda sonora sintetica. Essa etapa fecha o ciclo homem-maquina, reconvertendo representacao textual em sinal acustico compreensivel ao usuario.

### 16.6 Etapa 6: transporte e distribuicao

Nos modos remotos, o audio de entrada e o audio de saida atravessam a rede. Isso introduz requisitos adicionais de serializacao, fragmentacao, ordenacao e controle de latencia, tratados pelos modulos de rede.

### 16.7 Etapa 7: observabilidade

Sem instrumentacao, o sistema seria funcional, mas dificil de avaliar cientificamente. O registro de latencias e eventos transforma o software em uma plataforma experimental, e nao apenas em uma demonstracao funcional.

## 17. Limitacoes Atuais

Apesar de robusto para prototipacao, o sistema possui limitacoes importantes:

- VAD baseado apenas em RMS, sem modelo especializado;
- ausencia de fila assicrona ou paralelismo mais sofisticado no pipeline local;
- dependencia de nuvem na etapa LLM;
- ausencia de mecanismo de retransmissao ou confirmacao no protocolo UDP;
- falta de tratamento avancado de jitter, perda e duplicacao;
- ausencia de avaliacao automatizada da qualidade perceptual do TTS;
- ausencia de gestao de contexto conversacional multi-turno.

Esses pontos nao invalidam o projeto; ao contrario, delimitam claramente o escopo do prototipo.

## 18. Possiveis Evolucoes

O projeto pode evoluir em varias direcoes tecnicas:

- substituir VAD por WebRTC VAD ou modelo neural;
- adicionar backend de LLM local, como Ollama;
- implementar buffering adaptativo e tolerancia a perda em UDP;
- permitir streaming bidirecional completo;
- adicionar memoria conversacional;
- criar harness de benchmark automatizado;
- integrar diretamente com hardware do NAO.

Do ponto de vista cientifico, tais evolucoes permitiriam estudos comparativos entre:

- STT local versus remoto;
- LLM local versus em nuvem;
- UDP versus TCP;
- modos com e sem streaming parcial;
- diferentes limiares de VAD;
- diferentes tamanhos de modelo Whisper.

## 19. Conclusao

O projeto `voice_assistant` apresenta uma arquitetura modular, experimental e tecnicamente consistente para processamento de voz. Sua contribuicao principal nao esta apenas em executar o fluxo `fala -> texto -> resposta -> fala`, mas em organizar esse fluxo de forma extensivel, instrumentada e adequada para avaliacao.

Sob uma perspectiva de engenharia, o sistema demonstra:

- separacao clara entre captura, inferencia, sintese e transporte;
- reutilizacao de abstracoes para permitir substituicao de backends;
- configurabilidade e observabilidade suficientes para experimentacao.

Sob uma perspectiva cientifica, o projeto constitui uma plataforma valida para investigar latencia, acuracia pratica, impacto de arquitetura distribuida e comportamento de pipelines multimodais de voz em tempo quase real.

## 20. Mapeamento do Documento para o Codigo

Para facilitar navegacao tecnica, os principais arquivos relacionados a cada secao sao:

- Entrada e selecao de modo: `src/main.py`
- Pipeline local: `src/pipeline/assistant_pipeline.py`
- Captura de audio: `src/audio/recorder.py`
- Reproducao local: `src/audio/player.py`
- Interface e backend STT: `src/stt/base_stt.py`, `src/stt/faster_whisper_stt.py`
- Interface e backend LLM: `src/llm/base_llm.py`, `src/llm/openrouter_client.py`
- Interface e backend TTS: `src/tts/base_tts.py`, `src/tts/piper_tts.py`
- Cliente e servidor UDP: `src/network/udp_client.py`, `src/network/udp_server.py`
- Servidor TCP: `src/network/tcp_server.py`
- Protocolo UDP: `src/network/protocol.py`
- Configuracao: `src/utils/config_loader.py`, `config/config.yaml`
- Logging: `src/utils/logger.py`
- Metricas: `src/utils/metrics.py`
