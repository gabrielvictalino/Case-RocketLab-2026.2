import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

export function PaginaNaoEncontrada() {
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">
        Página não encontrada
      </h1>
      <p className="text-muted-foreground">
        O endereço solicitado não existe no portal V-Energy Grid 360.
      </p>
      <Button asChild variant="outline">
        <Link to="/visao-geral">Voltar para Visão Geral</Link>
      </Button>
    </section>
  )
}
