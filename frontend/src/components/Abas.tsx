export interface ItemAba {
  id: string
  rotulo: string
  contador?: number | string | null
}

export interface AbasProps {
  abas: ReadonlyArray<ItemAba>
  abaAtiva: string
  aoSelecionar: (id: string) => void
  ariaLabel?: string
}

export function Abas({
  abas,
  abaAtiva,
  aoSelecionar,
  ariaLabel = 'Abas',
}: AbasProps) {
  return (
    <div role="tablist" aria-label={ariaLabel} className="ve-tabs">
      {abas.map((aba) => {
        const ativa = aba.id === abaAtiva
        return (
          <button
            key={aba.id}
            role="tab"
            type="button"
            aria-selected={ativa}
            className="ve-tab"
            onClick={() => aoSelecionar(aba.id)}
          >
            <span>{aba.rotulo}</span>
            {aba.contador !== undefined && aba.contador !== null && (
              <span className="ve-tab-count">{aba.contador}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}
