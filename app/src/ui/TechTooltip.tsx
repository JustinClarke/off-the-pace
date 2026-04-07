import * as Tooltip from '@radix-ui/react-tooltip'
import { ReactNode } from 'react'

interface TechTooltipProps {
  children: ReactNode
  content: ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
  align?: 'start' | 'center' | 'end'
}

export function TechTooltipProvider({ children }: { children: ReactNode }) {
  return <Tooltip.Provider delayDuration={200}>{children}</Tooltip.Provider>
}

export function TechTooltip({ children, content, side = 'top', align = 'center' }: TechTooltipProps) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        {children}
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side={side}
          align={align}
          className="z-50 max-w-xs rounded border border-border bg-[#13151a] px-3 py-2 text-xs text-muted shadow-xl animate-in fade-in zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out data-[state=closed]:zoom-out-95"
          sideOffset={4}
        >
          {content}
          <Tooltip.Arrow className="fill-border" width={11} height={5} />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}
