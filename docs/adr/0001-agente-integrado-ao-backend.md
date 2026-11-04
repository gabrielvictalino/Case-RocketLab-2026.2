# Agente de IA como pacote integrado ao backend

O agente Text-to-SQL e os insights vivem no pacote `ai-agent/`, importado e executado pelo próprio backend FastAPI do portal. Não são um serviço separado atrás do Nginx. A primeira proposta de arquitetura previa um container próprio para o agente, mas o case pede um "módulo Python integrado ao backend FastAPI". Além disso, a garantia de segurança que importa (a IA não alterar dados) vem do usuário do Postgres só de leitura e da validação do SQL, não do isolamento de processo. Um serviço separado traria validação de JWT em dois lugares, chamada HTTP interna para os insights e mais um container, com pouco ganho no prazo do case.

## Considered Options

- **Serviço separado (`ai-agent` em container próprio, rota `/api/agent/` no Nginx)**: isola latência e falhas do LLM e permite escalar e publicar o agente separadamente. Foi rejeitado pelo custo operacional e porque o isolamento de segurança já é garantido no banco.
- **Pacote integrado (escolhido)**: o backend chama o agente por uma interface (`assistente` no backend → `venergy_ai`). Se um dia o agente precisar de processo próprio, essa interface vira um cliente HTTP sem reescrever o agente.

## Consequences

- Uma falha ou lentidão do LLM ocupa workers do backend. As chamadas ao LLM precisam de timeout e não podem bloquear as rotas das telas.
- O backend mantém duas conexões com o banco: a do portal (leitura em `analytics`, escrita em `operations`) e a do agente (role `ai_read`, só leitura nas views de `ai_read`). O agente nunca recebe a sessão do portal.
