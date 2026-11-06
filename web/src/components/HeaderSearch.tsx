import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { NAV_SECTIONS } from '@/config/navigation'
import { cn } from '@/lib/utils'

// Flatten all nav items once
const ALL_PAGES = NAV_SECTIONS.flatMap(s =>
  s.items.map(item => ({ ...item, section: s.label }))
)

export default function HeaderSearch() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const results = query.trim()
    ? ALL_PAGES.filter(p =>
        p.label.toLowerCase().includes(query.toLowerCase()) ||
        p.section.toLowerCase().includes(query.toLowerCase())
      )
    : ALL_PAGES

  // Reset cursor when results change
  useEffect(() => { setCursor(0) }, [query])

  // Global shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(true)
        setTimeout(() => inputRef.current?.focus(), 0)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Scroll active item into view
  useEffect(() => {
    const el = listRef.current?.children[cursor] as HTMLElement | undefined
    el?.scrollIntoView({ block: 'nearest' })
  }, [cursor])

  const go = (path: string) => {
    navigate(path)
    setOpen(false)
    setQuery('')
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, results.length - 1)) }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)) }
    if (e.key === 'Enter' && results[cursor]) go(results[cursor].path)
    if (e.key === 'Escape') setOpen(false)
  }

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        onClick={() => { setOpen(true); setTimeout(() => inputRef.current?.focus(), 0) }}
        className="flex items-center gap-2 h-8 rounded-lg border border-border bg-muted/50 px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors w-48 sm:w-56"
      >
        <Search className="h-3.5 w-3.5 shrink-0" />
        <span className="flex-1 text-left truncate">Search pages…</span>
        <kbd className="hidden sm:inline-flex h-5 items-center rounded border border-border bg-background px-1 text-[10px] font-mono text-muted-foreground">
          ⌘K
        </kbd>
      </button>

      {/* Dropdown */}
      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />

          <div className="absolute left-0 top-10 z-50 w-72 rounded-xl border border-border bg-card shadow-xl overflow-hidden">
            {/* Input */}
            <div className="flex items-center gap-2 border-b border-border px-3 py-2">
              <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Search pages…"
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              {query && (
                <button onClick={() => setQuery('')} className="text-muted-foreground hover:text-foreground">
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* Results */}
            <ul ref={listRef} className="max-h-72 overflow-y-auto py-1">
              {results.length === 0 ? (
                <li className="px-4 py-6 text-center text-sm text-muted-foreground">No pages found</li>
              ) : results.map((item, i) => {
                const Icon = item.icon
                return (
                  <li key={item.path + i}>
                    <button
                      onMouseEnter={() => setCursor(i)}
                      onClick={() => go(item.path)}
                      className={cn(
                        'flex w-full items-center gap-3 px-3 py-2 text-sm transition-colors',
                        i === cursor ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-muted'
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="flex-1 text-left">{item.label}</span>
                      <span className="text-[10px] text-muted-foreground">{item.section}</span>
                    </button>
                  </li>
                )
              })}
            </ul>

            <div className="border-t border-border px-3 py-1.5 flex items-center gap-3 text-[10px] text-muted-foreground">
              <span><kbd className="font-mono">↑↓</kbd> navigate</span>
              <span><kbd className="font-mono">↵</kbd> go</span>
              <span><kbd className="font-mono">Esc</kbd> close</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
