import '@testing-library/jest-dom/vitest'
import { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Dialogo } from './Dialogo'
afterEach(cleanup)
function Exemplo({ bloqueado = false }: { bloqueado?: boolean }) {
  const [aberto, setAberto] = useState(false)
  return (
    <>
      <button onClick={() => setAberto(true)}>Abrir</button>
      <Dialogo
        aberto={aberto}
        titulo="Diálogo"
        bloqueado={bloqueado}
        aoFechar={() => setAberto(false)}
      >
        <input aria-label="Primeiro" />
        <button onClick={() => setAberto(false)}>Voltar</button>
      </Dialogo>
    </>
  )
}
it('retém foco e devolve ao abrir após Escape', () => {
  render(<Exemplo />)
  const botao = screen.getByRole('button', { name: 'Abrir' })
  botao.focus()
  fireEvent.click(botao)
  expect(screen.getByLabelText('Primeiro')).toHaveFocus()
  const dialog = screen.getByRole('dialog')
  fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true })
  expect(screen.getByRole('button', { name: 'Voltar' })).toHaveFocus()
  fireEvent.keyDown(dialog, { key: 'Tab' })
  expect(screen.getByLabelText('Primeiro')).toHaveFocus()
  fireEvent.keyDown(dialog, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(botao).toHaveFocus()
})
it('não fecha pelo Escape enquanto bloqueado', () => {
  render(<Exemplo bloqueado />)
  fireEvent.click(screen.getByRole('button', { name: 'Abrir' }))
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

it('usa foco alternativo quando o elemento de origem é removido', () => {
  const destino = document.createElement('button')
  document.body.append(destino)
  const origem = document.createElement('button')
  document.body.append(origem)
  origem.focus()
  const { unmount } = render(
    <Dialogo
      aberto
      titulo="Teste"
      aoFechar={() => {}}
      focoAoFechar={() => destino}
    >
      <input aria-label="Campo" />
    </Dialogo>,
  )
  origem.remove()
  unmount()
  expect(destino).toHaveFocus()
  destino.remove()
})

it('preserva foco e inert quando o callback inline muda', () => {
  const raiz = document.createElement('div')
  raiz.id = 'root'
  document.body.append(raiz)
  const setAtributo = vi.spyOn(raiz, 'setAttribute')
  const removerAtributo = vi.spyOn(raiz, 'removeAttribute')
  const conteudo = (callback: () => HTMLElement | null) => (
    <Dialogo aberto titulo="Teste" aoFechar={() => {}} focoAoFechar={callback}>
      <input aria-label="Primeiro" />
      <input aria-label="Segundo" />
    </Dialogo>
  )
  const { rerender, unmount } = render(conteudo(() => null))
  const segundo = screen.getByLabelText('Segundo')
  segundo.focus()
  expect(raiz.inert).toBe(true)
  setAtributo.mockClear()
  removerAtributo.mockClear()
  rerender(conteudo(() => null))
  expect(segundo).toHaveFocus()
  expect(raiz.inert).toBe(true)
  expect(setAtributo).not.toHaveBeenCalled()
  expect(removerAtributo).not.toHaveBeenCalled()
  unmount()
  raiz.remove()
})
