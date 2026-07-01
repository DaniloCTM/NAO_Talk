## Dataset de teste orientado a tools

O arquivo `dataset_teste/prompts_default.json` foi reorganizado para priorizar apenas comandos que devem acionar tools reais do NAO.

Campos novos relevantes:

- `tools_esperadas`: tool única esperada ou conjunto separado por `|` em comandos compostos
- `keyword_esperada`: heurística textual usada na avaliação de LLM/TTS

Observação importante:

- Tools apenas mockadas não devem ser usadas neste dataset enquanto não houver implementação real.
- Os áudios e manifests já gravados em `dataset_teste/` pertencem ao conjunto antigo.
- Para que as métricas representem o novo dataset, é necessário regravar as amostras com `scripts/record_test_dataset.py`.
