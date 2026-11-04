# Avaliação do agente com o modelo real

Resultado da avaliação automatizada do agente (D4), com o modelo real e a base carregada
com `contracts/samples`. As perguntas, as regras de comparação e o modo de rodar estão
em [ai-agent/evals/README.md](../ai-agent/evals/README.md).

> A rodada com o modelo real ainda não foi registrada aqui. Para gerar este arquivo:
>
> ```bash
> GEMINI_API_KEY=... uv run pytest ai-agent/evals -rs
> ```
>
> e copie `ai-agent/evals/relatorio.md` para baixo desta linha, com a data, o commit e o
> modelo da rodada.
