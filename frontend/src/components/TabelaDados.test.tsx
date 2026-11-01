import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TabelaDados, type ColunaTabela } from '@/components/TabelaDados'

afterEach(() => {
  cleanup()
})

interface LinhaTeste {
  id: string
  municipio: string
  valor: number
}

const COLUNAS: ColunaTabela<LinhaTeste>[] = [
  { accessorKey: 'municipio', header: 'Município' },
  {
    accessorKey: 'valor',
    header: 'Valor',
    meta: { alinhamento: 'direita' },
  },
]

const DADOS: LinhaTeste[] = [
  { id: '1', municipio: 'Olinda', valor: 200 },
  { id: '2', municipio: 'Recife', valor: 500 },
  { id: '3', municipio: 'Caruaru', valor: 100 },
]

describe('TabelaDados', () => {
  it('ordena as linhas ao clicar no cabeçalho e dispara aoClicarLinha', () => {
    const aoClicar = vi.fn()
    render(
      <TabelaDados
        colunas={COLUNAS}
        dados={DADOS}
        legenda="Tabela de teste"
        chaveLinha={(l) => l.id}
        aoClicarLinha={aoClicar}
      />,
    )

    const botaoValor = screen.getByRole('button', { name: /Valor/ })
    fireEvent.click(botaoValor)

    const linhasAsc = screen.getAllByRole('row').slice(1)
    expect(within(linhasAsc[0]!).getByText('Caruaru')).toBeInTheDocument()
    expect(within(linhasAsc[2]!).getByText('Recife')).toBeInTheDocument()

    fireEvent.click(botaoValor)
    const linhasDesc = screen.getAllByRole('row').slice(1)
    expect(within(linhasDesc[0]!).getByText('Recife')).toBeInTheDocument()
    expect(within(linhasDesc[2]!).getByText('Caruaru')).toBeInTheDocument()

    fireEvent.click(linhasDesc[0]!)
    expect(aoClicar).toHaveBeenCalledWith({
      id: '2',
      municipio: 'Recife',
      valor: 500,
    })
  })

  it('mantém o rodapé no estado vazio', () => {
    render(
      <TabelaDados
        colunas={COLUNAS}
        dados={[]}
        legenda="Tabela vazia"
        tituloVazio="Nada por aqui"
        rodape={<button type="button">Anterior</button>}
      />,
    )

    expect(screen.getByText('Nada por aqui')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeInTheDocument()
  })
})
