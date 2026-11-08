import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useState } from 'react'
import ChatDrawer, { type ChatApi } from './ChatDrawer'
import type { Turn } from './useChat'

function chatOf(turns: Turn[] = [], over: Partial<ChatApi> = {}): ChatApi {
  return { turns, busy: false, send: vi.fn(), clear: vi.fn(), ...over }
}

function Host({ chat }: { chat: ChatApi }) {
  const [open, setOpen] = useState(false)
  return (
    <MemoryRouter>
      <button onClick={() => setOpen(true)}>Ask</button>
      <button>other</button>
      <ChatDrawer open={open} onClose={() => setOpen(false)} chat={chat} />
    </MemoryRouter>
  )
}

describe('ChatDrawer', () => {
  it('renders nothing when closed', () => {
    render(<Host chat={chatOf()} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('opens as a named modal dialog with a labelled field, focus on the field', async () => {
    const user = userEvent.setup()
    render(<Host chat={chatOf()} />)
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    const dlg = screen.getByRole('dialog', { name: 'Ask the assistant' })
    expect(dlg.getAttribute('aria-modal')).toBe('true')
    const field = screen.getByLabelText('Your question')
    expect(document.activeElement).toBe(field)
    expect(screen.getByRole('log', { name: 'Conversation' }).getAttribute('aria-live')).toBe('polite')
  })

  it('Escape closes and focus returns to the opener', async () => {
    const user = userEvent.setup()
    render(<Host chat={chatOf()} />)
    const opener = screen.getByRole('button', { name: 'Ask' })
    await user.click(opener)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('traps Tab inside the dialog', async () => {
    const user = userEvent.setup()
    render(<Host chat={chatOf()} />)
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    const dlg = screen.getByRole('dialog')
    for (let i = 0; i < 12; i++) {
      await user.tab()
      expect(dlg.contains(document.activeElement)).toBe(true)
    }
    for (let i = 0; i < 6; i++) {
      await user.tab({ shift: true })
      expect(dlg.contains(document.activeElement)).toBe(true)
    }
  })

  it('sends the typed question on submit and on Enter, not on Shift+Enter', async () => {
    const user = userEvent.setup()
    const chat = chatOf()
    render(<Host chat={chat} />)
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    const field = screen.getByLabelText('Your question')
    await user.type(field, 'who won?')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    expect(chat.send).not.toHaveBeenCalled()
    await user.keyboard('{Enter}')
    expect(chat.send).toHaveBeenCalledTimes(1)
    expect((chat.send as ReturnType<typeof vi.fn>).mock.calls[0][0]).toContain('who won?')
  })

  it('shows step progress while pending and each failure message with its action', async () => {
    const user = userEvent.setup()
    const turns: Turn[] = [
      { id: 1, question: 'q1', status: 'pending', steps: ['Reading the question...', 'Looking up cards...'] },
      { id: 2, question: 'q2', status: 'error', steps: [], error: { kind: 'updated', text: 'The app was updated. Reload to keep asking.' } },
      { id: 3, question: 'q3', status: 'error', steps: [], error: { kind: 'paused', text: 'Answers are paused for today. The rest of the app is unaffected.' } },
    ]
    render(<Host chat={chatOf(turns)} />)
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    expect(screen.getByTestId('step-progress').textContent).toBe('Looking up cards...')
    expect(screen.getByTestId('error-updated')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeTruthy()
    expect(screen.getByTestId('error-paused').textContent).toContain('paused for today')
    // navigation outside the dialog is untouched
    expect(screen.getByRole('button', { name: 'other' })).toBeTruthy()
  })

  it('the close button closes it', () => {
    render(<Host chat={chatOf()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close the assistant' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('uses a slide animation that is switched off for reduced motion', () => {
    render(<Host chat={chatOf()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(screen.getByRole('dialog').className).toContain('motion-reduce:animate-none')
  })
})
