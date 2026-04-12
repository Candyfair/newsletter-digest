import { createContext, useContext, useState } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('theme') || 'dark'
  )
  const [lang, setLang] = useState(
    () => localStorage.getItem('lang') || 'fr'
  )

  // Selection state — shared between Header and SummaryList
  const [selected, setSelected]       = useState(new Set())
  const [showConfirm, setShowConfirm] = useState(false)

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('theme', next)
  }

  function toggleLang() {
    const next = lang === 'fr' ? 'en' : 'fr'
    setLang(next)
    localStorage.setItem('lang', next)
  }

  function toggleCard(id) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function cancelSelection() {
    setSelected(new Set())
    setShowConfirm(false)
  }

  return (
    <AppContext.Provider value={{
      theme, toggleTheme,
      lang, toggleLang,
      selected, toggleCard,
      showConfirm, setShowConfirm,
      cancelSelection,
    }}>
      <div className={theme === 'dark' ? 'dark' : ''}>
        {children}
      </div>
    </AppContext.Provider>
  )
}

export function useApp() {
  return useContext(AppContext)
}