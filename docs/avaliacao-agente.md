# Avaliação do agente com o modelo real

Registro da avaliação automatizada do agente (D4), com o modelo real e a base carregada
com `contracts/samples`. **Status em 04/11/2026: rodada real ainda não executada neste
fechamento; falta a chave do provedor.** Os testes com modelos simulados e os checks
da CI não substituem esta evidência. As perguntas, as regras de comparação e o modo de rodar estão
em [ai-agent/evals/README.md](../ai-agent/evals/README.md).

> A rodada com o modelo real ainda não foi registrada aqui. Para gerar este arquivo:
>
> ```bash
> GEMINI_API_KEY=... uv run pytest ai-agent/evals -rs
> ```
>
> e copie `ai-agent/evals/relatorio.md` para baixo desta linha, com a data, o commit e o
> modelo da rodada.

## Critérios para registrar o resultado

1. Confirmar que o teste executou e não ficou `SKIPPED` por falta da chave. O comando
   lê `GEMINI_API_KEY` do ambiente, não do `.env` do Compose.
2. Registrar data, commit, provedor/modelo e origem da base. O teste atual carrega a
   amostra sintética em containers temporários; não é uma rodada sobre a Gold real.
3. Anexar `ai-agent/evals/relatorio.md`, incluindo falhas, acerto, recusas, números sem
   lastro e latências. O mínimo configurável é 70% de acerto; qualquer número sem
   lastro precisa de investigação antes da demonstração.
4. No navegador, registrar uma pergunta de receita, a auditoria com SQL/tabela, um
   follow-up mudando o município e uma recusa de dado pessoal ou pergunta fora do domínio.
5. Registrar os insights da Visão Geral e Receita, com os mesmos períodos/recortes dos
   gráficos, e anexar os prints aos PRs #132/#135 ou a este documento.

Falhas `401`/`403` do provedor pedem revisão da chave e do projeto; `429` pede conferir
quota no AI Studio e espaçar as chamadas (`AVALIACAO_PAUSA_S`). Não reduzir a exigência
de acerto para ocultar erros. Se houver custo habilitado, a rodada usa a conta do projeto.
