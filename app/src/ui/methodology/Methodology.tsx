import { ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'

interface MethodologyProps {
  content: ReactNode
  href?: string
  triggerText?: string
}

export default function Methodology({
  content,
  href,
  triggerText = 'How this is calculated →',
}: MethodologyProps) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="text-xs text-muted hover:text-accent transition-colors underline underline-offset-2">
          {triggerText}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
        <Dialog.Content style={{ backgroundColor: 'rgb(var(--color-bg))' }} className="fixed right-0 top-0 h-full w-full max-w-md border-l border-border z-50 overflow-y-auto p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold">Methodology</Dialog.Title>
            <Dialog.Close className="text-muted hover:text-[rgb(var(--color-text))] transition-colors text-lg leading-none">
              ×
            </Dialog.Close>
          </div>
          <div className="text-sm text-muted leading-relaxed prose prose-invert prose-sm max-w-none">
            {content}
          </div>
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-auto text-xs text-accent hover:underline"
            >
              Full reference documentation →
            </a>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
