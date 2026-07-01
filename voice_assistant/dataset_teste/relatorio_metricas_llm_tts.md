# Relatório de Métricas - LLM e TTS

- Gerado em: `2026-07-01T11:13:17`
- Total de amostras avaliadas: `24`
- Modelo LLM: `openai/gpt-4o-mini`
- Modelo TTS: `models/pt_BR-faber-medium.onnx`

## Resumo

| Métrica | Média | Mediana | P95 | Mín | Máx |
|---|---:|---:|---:|---:|---:|
| LLM latency (s) | 1.756 | 1.708 | 2.447 | 1.307 | 2.489 |
| TTS latency (s) | 0.325 | 0.309 | 0.395 | 0.271 | 0.454 |
| Total LLM+TTS (s) | 2.080 | 2.033 | 2.750 | 1.586 | 2.867 |
| Duração do áudio TTS (s) | 2.488 | 2.180 | 3.981 | 1.570 | 4.171 |
| TTS RTF | 0.137 | 0.142 | 0.166 | 0.092 | 0.178 |

- Média de caracteres por resposta: `35.9`
- Média de palavras por resposta: `6.9`
- Acurácia de tool calling: `24/24` (`100.0%`)
- Acurácia heurística por palavra-chave: `20/24` (`83.3%`)

## Critério heurístico

A coluna `keyword_match` abaixo só é calculada para amostras cuja resposta esperada tem um alvo textual verificável, como `bateria`, `azul`, `esquerda`, `direita` ou `central`. Para os demais casos, ela fica como `n/a`.

## Resultados por amostra

| ID | Categoria | Frase | Tools esperadas | Tools chamadas | tool_match | Esperado | Resposta do modelo | keyword_match | LLM (s) | TTS (s) | Total (s) | Áudio TTS (s) | RTF |
|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| 001 | tool_bateria | Como está a sua bateria? | bateria | bateria | ok | informar o estado da bateria | A bateria está em 75% e não está carregando. | ok | 1.799 | 0.385 | 2.184 | 3.532 | 0.109 |
| 002 | tool_bateria | Qual é o nível de carga do NAO? | bateria | bateria | ok | informar o estado da bateria | A bateria do NAO está em 75% e não está carregando. | ok | 1.361 | 0.454 | 1.816 | 4.171 | 0.109 |
| 003 | tool_bateria | O robô está carregando? | bateria | bateria | ok | informar o estado da bateria | O robô está com 75% de bateria e não está carregando. | ok | 1.383 | 0.372 | 1.756 | 4.055 | 0.092 |
| 004 | tool_acender_led | Acenda o LED do peito | acender_led | acender_led | ok | confirmar que acendeu o LED do peito em azul | O LED do peito foi aceso em azul. | ok | 1.496 | 0.305 | 1.800 | 2.464 | 0.124 |
| 005 | tool_apagar_led | Apague o LED do peito | apagar_led | apagar_led | ok | confirmar que apagou o LED do peito | O LED do peito foi apagado. | ok | 1.523 | 0.317 | 1.840 | 2.104 | 0.151 |
| 006 | tool_acender_led | Ligue a luz do peito | acender_led | acender_led | ok | confirmar que acendeu o LED do peito em azul | A luz do peito está acesa em azul. | falhou | 1.722 | 0.317 | 2.038 | 2.255 | 0.140 |
| 007 | tool_apagar_led | Desligue a luz do peito | apagar_led | apagar_led | ok | confirmar que apagou o LED do peito | A luz do peito foi desligada. | falhou | 1.833 | 0.272 | 2.105 | 1.895 | 0.143 |
| 008 | tool_acender_olhos | Acenda os olhos | acender_olhos | acender_olhos | ok | confirmar que acendeu os olhos em azul | Os olhos estão acesos em azul. | ok | 1.776 | 0.299 | 2.075 | 1.953 | 0.153 |
| 009 | tool_apagar_olhos | Apague os olhos | apagar_olhos | apagar_olhos | ok | confirmar que apagou os olhos | Os olhos foram apagados. | ok | 1.319 | 0.271 | 1.590 | 1.721 | 0.158 |
| 010 | tool_acender_olhos | Ligue as luzes dos olhos | acender_olhos | acender_olhos | ok | confirmar que acendeu os olhos em azul | As luzes dos olhos estão acesas em azul. | ok | 1.695 | 0.333 | 2.028 | 2.487 | 0.134 |
| 011 | tool_apagar_olhos | Desligue as luzes dos olhos | apagar_olhos | apagar_olhos | ok | confirmar que apagou os olhos | As luzes dos olhos foram desligadas. | falhou | 1.817 | 0.294 | 2.111 | 2.394 | 0.123 |
| 012 | tool_cabeca_esquerda | Mova a cabeça para a esquerda | mover_cabeca_esquerda | mover_cabeca_esquerda | ok | confirmar que moveu a cabeça para a esquerda | Cabeça movida para a esquerda. | ok | 1.662 | 0.278 | 1.940 | 1.872 | 0.149 |
| 013 | tool_cabeca_direita | Mova a cabeça para a direita | mover_cabeca_direita | mover_cabeca_direita | ok | confirmar que moveu a cabeça para a direita | Cabeça movida para a direita. | ok | 1.555 | 0.295 | 1.850 | 1.814 | 0.163 |
| 014 | tool_centralizar_cabeca | Centralize a cabeça | centralizar_cabeca | centralizar_cabeca | ok | confirmar que centralizou a cabeça | Cabeça centralizada. | ok | 1.307 | 0.279 | 1.586 | 1.570 | 0.178 |
| 015 | tool_cabeca_esquerda | Vire a cabeça para a esquerda | mover_cabeca_esquerda | mover_cabeca_esquerda | ok | confirmar que moveu a cabeça para a esquerda | Cabeça movida para a esquerda. | ok | 1.405 | 0.309 | 1.713 | 1.860 | 0.166 |
| 016 | tool_cabeca_direita | Olhe para a direita | mover_cabeca_direita | mover_cabeca_direita | ok | confirmar que moveu a cabeça para a direita | Cabeça movida para a direita. | ok | 1.833 | 0.294 | 2.126 | 1.791 | 0.164 |
| 017 | tool_centralizar_cabeca | Volte a cabeça para o centro | centralizar_cabeca | centralizar_cabeca | ok | confirmar que centralizou a cabeça | A cabeça foi centralizada. | ok | 1.754 | 0.309 | 2.063 | 1.883 | 0.164 |
| 018 | tool_composta_luzes | Acenda o LED do peito e os olhos | acender_led|acender_olhos | acender_led|acender_olhos | ok | executar as ações pedidas e responder de forma curta | O LED do peito e os olhos foram acesos. | ok | 2.364 | 0.348 | 2.713 | 2.812 | 0.124 |
| 019 | tool_composta_luzes | Apague o LED do peito e os olhos | apagar_led|apagar_olhos | apagar_led|apagar_olhos | ok | executar as ações pedidas e responder de forma curta | O LED do peito e os olhos foram apagados. | ok | 2.240 | 0.339 | 2.580 | 2.940 | 0.115 |
| 020 | tool_composta_cabeca | Mova a cabeça para a esquerda e depois centralize | mover_cabeca_esquerda|centralizar_cabeca | mover_cabeca_esquerda|centralizar_cabeca | ok | executar as ações pedidas e responder de forma curta | A cabeça foi movida para a esquerda e depois centralizada. | ok | 2.489 | 0.378 | 2.867 | 3.393 | 0.111 |
| 021 | tool_composta_cabeca | Mova a cabeça para a direita e depois centralize | mover_cabeca_direita|centralizar_cabeca | mover_cabeca_direita|centralizar_cabeca | ok | executar as ações pedidas e responder de forma curta | A cabeça foi movida para a direita e depois centralizada. | ok | 2.182 | 0.373 | 2.554 | 3.370 | 0.111 |
| 022 | tool_variacao_led | Ative a luz do peito | acender_led | acender_led | ok | confirmar que acendeu o LED do peito em azul | A luz do peito foi ativada. | falhou | 1.606 | 0.278 | 1.884 | 1.872 | 0.149 |
| 023 | tool_variacao_bateria | Me diga a carga da bateria | bateria | bateria | ok | informar o estado da bateria | A bateria está em 75% e não está carregando. | ok | 1.554 | 0.396 | 1.951 | 3.567 | 0.111 |
| 024 | tool_variacao_cabeca | Centralize sua cabeça agora | centralizar_cabeca | centralizar_cabeca | ok | confirmar que centralizou a cabeça | Minha cabeça está centralizada. | ok | 2.462 | 0.295 | 2.757 | 1.941 | 0.152 |

## Observações

- Para medir tool calling, as tools foram substituídas por stubs locais que apenas registram a chamada e retornam um texto sintético.
- As amostras de contexto foram avaliadas em sessões compartilhadas por bloco semântico para preservar memória conversacional.
- As métricas de geração cobrem latência e um cheque heurístico simples de conteúdo, não uma avaliação semântica completa.
- O TTS foi medido com `synthesize_raw`, sem playback, então a latência aqui representa síntese e não reprodução no alto-falante.
