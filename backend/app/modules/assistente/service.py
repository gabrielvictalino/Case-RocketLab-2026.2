from venergy_ai.interface import Andamento, Assistente, Contexto


class AssistenteService:
    """Adaptador preparado; não publica rotas até a implementação segura do agente."""

    def __init__(self, agente: Assistente):
        self.agente = agente

    async def responder(
        self, pergunta: str, contexto: Contexto, andamento: Andamento | None = None
    ):
        return await self.agente.responder(pergunta, contexto, andamento)
