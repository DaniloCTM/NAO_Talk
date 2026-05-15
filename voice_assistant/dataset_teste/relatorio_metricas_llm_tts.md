# Relatório de Métricas - LLM e TTS

<!-- STT_SECTION_START -->
## STT

- Gerado em: `2026-04-27T10:23:39`
- Modelo STT: `small`
- Compute type: `int8`

### Resumo

| Métrica | Média | Mediana | P95 | Mín | Máx |
|---|---:|---:|---:|---:|---:|
| STT latency (s) | 1.442 | 1.408 | 1.800 | 1.186 | 1.992 |
| Duração do áudio (s) | 3.545 | 2.805 | 6.120 | 1.560 | 6.630 |

- Exact match normalizado: `15/26` (`57.7%`)

### Resultados por amostra

| ID | Categoria | Frase esperada | Transcrição STT | Exact match | STT (s) | Áudio (s) |
|---|---|---|---|---|---:|---:|
| 003 | acao_tool | Levante-se | Levante! | falhou | 1.649 | 2.940 |
| 004 | acao_tool | Pode sentar | Pode sentar. | ok | 1.413 | 2.010 |
| 005 | acao_tool | Observe o ambiente | Observe o ambiente! | ok | 1.389 | 3.180 |
| 006 | tempo | Que horas são? | Que horas são? | ok | 1.507 | 5.940 |
| 007 | clima | Como está o clima hoje? | Como está o clima hoje? | ok | 1.815 | 2.760 |
| 008 | pergunta_simples | Quanto é dois mais dois? | quanto é 2 mais 2? | falhou | 1.356 | 5.730 |
| 009 | idioma | Responda em português | Respondo em português. | falhou | 1.441 | 6.630 |
| 010 | comando_composto | Levante e depois observe | Levante e depois observe. | ok | 1.451 | 5.790 |
| 011 | confirmacao | Você me ouviu? | Você me ouviu? | ok | 1.291 | 5.610 |
| 012 | ruido_sem_acao | Estou apenas testando o microfone | Estou apenas testando o microfone. | ok | 1.238 | 5.640 |
| 013 | memoria | Meu nome é Danilo | Meu nome é Danilo. | ok | 1.186 | 1.860 |
| 014 | memoria | Qual é o meu nome? | Qual é o seu nome? | falhou | 1.233 | 1.770 |
| 015 | memoria | Guarde que minha cor favorita é azul | Guarde que minha cor favorita é azul. | ok | 1.261 | 2.700 |
| 016 | memoria | Qual é minha cor favorita? | Qual é a minha favorita? | falhou | 1.495 | 2.850 |
| 017 | contexto_acao | Levante-se | Levante! | falhou | 1.374 | 1.560 |
| 018 | contexto_acao | O que você acabou de fazer? | o que você acabou de fazer. | ok | 1.353 | 2.160 |
| 019 | contexto_acao | Agora sente | Agora sente. | ok | 1.992 | 1.680 |
| 020 | contexto_acao | E agora, o que você fez? | E agora, o que você fez? | ok | 1.755 | 2.160 |
| 021 | memoria_factual | Estou em um laboratório de robótica | Estou em um laboratório de robótica. | ok | 1.455 | 5.550 |
| 022 | memoria_factual | Onde eu estou? | onde eu estou. | ok | 1.599 | 2.430 |
| 023 | frase_longa | Hoje eu quero testar se o assistente consegue entender uma frase um pouco maior sem perder o contexto | Hoje eu quero testar se o assistente consegue entender uma frase um pouco maior sem perder o contexto. | ok | 1.530 | 6.180 |
| 024 | numero | Anote o número quarenta e dois | a noite número 42. | falhou | 1.265 | 2.610 |
| 025 | numero | Qual número eu falei? | Qual o número eu falei? | falhou | 1.415 | 1.920 |
| 026 | fala_natural | Hum, deixa eu pensar, acho que você pode observar o ambiente agora | Um, deixa eu pensar. Acho que você pode observar o ambiente agora. | falhou | 1.402 | 5.610 |
| 027 | variacao_acao | NAO, sente por favor | NAL, sente por favor. | falhou | 1.275 | 2.850 |
| 028 | variacao_acao | NAO, levanta agora | Now, levanta agora! | falhou | 1.353 | 2.040 |
<!-- STT_SECTION_END -->
- Gerado em: `2026-04-27T10:01:30`
- Total de amostras avaliadas: `26`
- Modelo LLM: `openai/gpt-4o-mini`
- Modelo TTS: `models/pt_BR-faber-medium.onnx`

## Resumo

| Métrica | Média | Mediana | P95 | Mín | Máx |
|---|---:|---:|---:|---:|---:|
| LLM latency (s) | 1.491 | 1.140 | 2.767 | 0.805 | 5.071 |
| TTS latency (s) | 0.285 | 0.276 | 0.356 | 0.223 | 0.488 |
| Total LLM+TTS (s) | 1.776 | 1.466 | 3.000 | 1.076 | 5.316 |
| Duração do áudio TTS (s) | 2.391 | 2.291 | 4.524 | 0.862 | 6.751 |
| TTS RTF | 0.148 | 0.124 | 0.241 | 0.072 | 0.280 |

- Média de caracteres por resposta: `37.3`
- Média de palavras por resposta: `6.2`
- Acurácia heurística por palavra-chave: `14/15` (`93.3%`)

## Critério heurístico

A coluna `keyword_match` abaixo só é calculada para amostras cuja resposta esperada tem um alvo textual verificável, como `Danilo`, `azul`, `quatro`, `levantar` ou `sentar`. Para os demais casos, ela fica como `n/a`.

## Resultados por amostra

| ID | Categoria | Frase | Esperado | Resposta do modelo | keyword_match | LLM (s) | TTS (s) | Total (s) | Áudio TTS (s) | RTF |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| 003 | acao_tool | Levante-se | confirmar que vai levantar | Levantei-me. | ok | 2.333 | 0.223 | 2.556 | 0.943 | 0.236 |
| 004 | acao_tool | Pode sentar | confirmar que vai sentar | Já estou sentado. | ok | 1.288 | 0.233 | 1.522 | 1.361 | 0.171 |
| 005 | acao_tool | Observe o ambiente | confirmar que está observando | Estou observando o ambiente. | ok | 1.860 | 0.282 | 2.142 | 1.640 | 0.172 |
| 006 | tempo | Que horas são? | informar que não sabe ao certo ou responder de forma curta coerente | Desculpe, não consigo informar as horas. | n/a | 0.871 | 0.300 | 1.171 | 2.626 | 0.114 |
| 007 | clima | Como está o clima hoje? | responder que não tem acesso ao clima atual ou falar de forma curta coerente | Desculpe, não consigo acessar informações sobre o clima. Você pode verificar em um aplicativo ou site de meteorologia. | n/a | 1.688 | 0.488 | 2.176 | 6.751 | 0.072 |
| 008 | pergunta_simples | Quanto é dois mais dois? | quatro | Dois mais dois é igual a quatro. | ok | 0.964 | 0.273 | 1.237 | 2.023 | 0.135 |
| 009 | idioma | Responda em português | resposta curta em português | Claro, estou aqui para ajudar. O que você precisa? | n/a | 1.039 | 0.330 | 1.368 | 3.163 | 0.104 |
| 010 | comando_composto | Levante e depois observe | executar no máximo uma ação e responder curto | Levantei e estou observando o ambiente. | n/a | 2.231 | 0.295 | 2.526 | 2.313 | 0.128 |
| 011 | confirmacao | Você me ouviu? | confirmação curta | Sim, eu te ouvi. Como posso ajudar? | n/a | 1.240 | 0.268 | 1.508 | 2.571 | 0.104 |
| 012 | ruido_sem_acao | Estou apenas testando o microfone | resposta curta reconhecendo o teste | Entendido! Estou aqui para ajudar. | n/a | 0.805 | 0.271 | 1.076 | 2.269 | 0.119 |
| 013 | memoria | Meu nome é Danilo | reconhecer ou confirmar o nome | Prazer em conhecê-lo, Danilo. Como posso ajudar você hoje? | n/a | 0.980 | 0.349 | 1.329 | 3.779 | 0.092 |
| 014 | memoria | Qual é o meu nome? | Danilo | Seu nome é Danilo. | ok | 0.863 | 0.248 | 1.112 | 1.164 | 0.213 |
| 015 | memoria | Guarde que minha cor favorita é azul | confirmação curta | Desculpe, não posso guardar informações. Posso ajudar com mais alguma coisa? | n/a | 1.029 | 0.359 | 1.388 | 4.580 | 0.078 |
| 016 | memoria | Qual é minha cor favorita? | azul | Desculpe, não tenho como lembrar da sua cor favorita. | falhou | 1.139 | 0.332 | 1.471 | 3.137 | 0.106 |
| 017 | contexto_acao | Levante-se | confirmar que vai levantar | Levantei-me. | ok | 1.827 | 0.233 | 2.061 | 1.001 | 0.233 |
| 018 | contexto_acao | O que você acabou de fazer? | responder que acabou de levantar | Eu me levantei. | ok | 0.837 | 0.239 | 1.076 | 1.198 | 0.199 |
| 019 | contexto_acao | Agora sente | confirmar que vai sentar | Sentei-me. | ok | 1.587 | 0.241 | 1.828 | 0.862 | 0.280 |
| 020 | contexto_acao | E agora, o que você fez? | responder que sentou | Eu me sentei. | ok | 5.071 | 0.245 | 5.316 | 1.140 | 0.215 |
| 021 | memoria_factual | Estou em um laboratório de robótica | confirmação curta | Isso é interessante! O que você está fazendo aí? | n/a | 0.894 | 0.292 | 1.186 | 3.047 | 0.096 |
| 022 | memoria_factual | Onde eu estou? | em um laboratório de robótica | Você mencionou que está em um laboratório de robótica. | ok | 0.875 | 0.293 | 1.168 | 2.835 | 0.103 |
| 023 | frase_longa | Hoje eu quero testar se o assistente consegue entender uma frase um pouco maior sem perder o contexto | resposta curta coerente com o teste | Claro, pode falar a frase que eu vou entender e responder. | n/a | 0.997 | 0.313 | 1.311 | 3.277 | 0.096 |
| 024 | numero | Anote o número quarenta e dois | confirmação curta | Desculpe, não posso anotar informações. Posso ajudar com outra coisa? | n/a | 1.140 | 0.320 | 1.460 | 4.359 | 0.073 |
| 025 | numero | Qual número eu falei? | quarenta e dois | Você falou o número quarenta e dois. | ok | 0.897 | 0.278 | 1.175 | 2.394 | 0.116 |
| 026 | fala_natural | Hum, deixa eu pensar, acho que você pode observar o ambiente agora | confirmar que está observando | Observei o ambiente. | ok | 2.911 | 0.236 | 3.148 | 1.396 | 0.169 |
| 027 | variacao_acao | NAO, sente por favor | confirmar que vai sentar | Já estou sentado. | ok | 1.711 | 0.236 | 1.947 | 1.396 | 0.169 |
| 028 | variacao_acao | NAO, levanta agora | confirmar que vai levantar | Levantei. | ok | 1.686 | 0.226 | 1.912 | 0.931 | 0.243 |

## Observações

- As amostras de contexto foram avaliadas em sessões compartilhadas por bloco semântico para preservar memória conversacional.
- As métricas de geração cobrem latência e um cheque heurístico simples de conteúdo, não uma avaliação semântica completa.
- O TTS foi medido com `synthesize_raw`, sem playback, então a latência aqui representa síntese e não reprodução no alto-falante.
