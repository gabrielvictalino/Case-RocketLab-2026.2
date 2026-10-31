from collections.abc import Mapping
from typing import Protocol


class Assistente(Protocol):
    """Fronteira para implementação futura, sem dependência da sessão do portal.

    A implementação receberá somente um executor ligado à role ai_read.
    Timeout, validação SQL e auditoria serão obrigatórios antes da ativação.
    """

    async def responder(
        self, pergunta: str, contexto: Mapping[str, object]
    ) -> Mapping[str, object]: ...
