# Avaliação do agente

Mede a qualidade das respostas do agente com o modelo real, de forma automatizada (D4).

- `perguntas.yaml`: as perguntas das lideranças no case, termos do dia a dia, perguntas
  com período ambíguo, perguntas que devem dar "não sei" e tentativas de injeção.
- `test_modelo_real.py`: roda cada pergunta no agente, com a role `ai_read` e o banco
  carregado com `contracts/samples`, e escreve `relatorio.md`.
- As regras de comparação ficam em `venergy_ai/avaliacao.py`.

O esperado de cada pergunta é o **resultado** de uma consulta de referência, rodada
como `ai_read` no mesmo banco. A avaliação não compara o texto nem o SQL literal. Ela
confere também o período declarado e se o texto cita algum número que não está nas
linhas. Essa conferência é própria da avaliação, mais estrita que a do agente e
independente dela: só arredondamento, a escala escrita sempre aplicada e os metadados
(linhas, meses, anos, números da pergunta) só na posição de metadado. Assim, um furo do
validador do agente aparece como "número sem lastro" no relatório, em vez de passar
pelas duas conferências iguais.

O relatório traz:

- a taxa de acerto geral e a das perguntas com resposta;
- a taxa de "não sei" correto e o número de "não sei" indevidos;
- as respostas com número sem lastro;
- a latência média e os tokens por pergunta;
- uma linha por pergunta, com o motivo de cada falha.

## Como rodar

Localmente, com Docker:

```bash
GEMINI_API_KEY=... uv run pytest ai-agent/evals
```

No GitHub, pelo workflow "Avaliação do agente", que roda manualmente ou toda segunda-feira.
Ele precisa do secret `GEMINI_API_KEY`, fica fora dos checks obrigatórios e publica o
relatório no resumo da execução e como artefato.

| Variável | Padrão | Uso |
|---|---|---|
| `AI_PROVEDOR` | `google` | `google` ou `openrouter`, com `OPENROUTER_API_KEY` |
| `AI_MODELO` | `gemini-3.1-flash-lite` | Modelo avaliado |
| `AVALIACAO_PAUSA_S` | `4` | Pausa entre perguntas, para não passar do limite por minuto do provedor |
| `AVALIACAO_MINIMO` | `0.7` | Taxa de acerto abaixo da qual o teste falha |

No CI obrigatório, `ai-agent/tests/test_avaliacao.py` testa as regras de comparação e
do relatório com respostas simuladas. `test_agente_postgres.py` roda todas as consultas
de referência na `ai_read`, para o arquivo de perguntas não quebrar sem ninguém ver.
