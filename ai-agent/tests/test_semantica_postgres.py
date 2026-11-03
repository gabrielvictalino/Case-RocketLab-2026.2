import pytest

from venergy_ai.semantica import VISOES

pytestmark = pytest.mark.integration


async def test_catalogo_e_as_views_de_ai_read_tem_as_mesmas_colunas(ai):
    linhas = await ai.fetch(
        """SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = 'ai_read'"""
    )
    no_banco = {}
    for linha in linhas:
        no_banco.setdefault(linha['table_name'], set()).add(linha['column_name'])
    # Nos dois sentidos: coluna nova numa view também precisa entrar no catálogo.
    assert no_banco == {v.nome: {c.nome for c in v.colunas} for v in VISOES}
