import type { components } from '@/lib/api/schema'

type StatusOrdem = components['schemas']['Ordem']['status']

export const rotulosOrdem: Record<StatusOrdem, string> = {
  ABERTA: 'Aberta',
  EM_CAMPO: 'Em campo',
  CONCLUIDA: 'Concluída',
  CANCELADA: 'Cancelada',
}
