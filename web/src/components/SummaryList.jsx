import { useState, useEffect } from 'react'
import { useApp } from '../context/AppContext'
import { t } from '../i18n/translations'

export default function SummaryList({ status }) {
  const {
    lang,
    selected, toggleCard,
    showConfirm, setShowConfirm,
    cancelSelection,
    setNewsletterCount, 
  } = useApp()

  const [newsletters, setNewsletters] = useState([])
  const [loading, setLoading]         = useState(true)

  useEffect(() => {
    setNewsletterCount(newsletters.length)
  }, [newsletters, setNewsletterCount])

  useEffect(() => {
    async function fetchIndex() {
      setLoading(true)
      try {
        const res  = await fetch('/api/index')
        const data = await res.json()
        setNewsletters(Array.isArray(data) ? data : [])
      } catch {
        setNewsletters([])
      } finally {
        setLoading(false)
      }
    }

  // Reload when pipeline completes or on mount
  if (status === 'done' || status === 'idle') {
    fetchIndex()
  }

  // Clear list immediately when a new pipeline starts
  if (status === 'running') {
    setNewsletters([])
  }
}, [status])

  async function confirmDelete() {
    // Build payload from selected ids
    const selectedItems = newsletters.filter(nl => selected.has(nl.id))
    const ids  = selectedItems.map(nl => nl.id)
    const uids = selectedItems.map(nl => nl.uid).filter(Boolean)

    try {
      const res = await fetch('/api/email', {
        method:  'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ids, uids }),
      })

      if (res.ok) {
        // Remove deleted newsletters from local state immediately
        setNewsletters(prev => prev.filter(nl => !selected.has(nl.id)))
      } else {
        console.error('Delete failed:', await res.json())
      }
    } catch (err) {
      console.error('Network error during delete:', err)
    }

    cancelSelection()
  }

  function formatDate(isoDate) {
    if (!isoDate) return ''
    const d = new Date(isoDate)
    return d.toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', {
      day:   'numeric',
      month: 'long',
      year:  'numeric',
    })
  }

  // Group by theme → sender
  const grouped = newsletters.reduce((acc, nl) => {
    const theme = nl.theme || 'Autres'
    if (!acc[theme]) acc[theme] = {}
    if (!acc[theme][nl.sender]) acc[theme][nl.sender] = []
    acc[theme][nl.sender].push(nl)
    return acc
  }, {})

  // Sort each sender group anti-chronologically
  Object.values(grouped).forEach(themeGroup => {
    Object.values(themeGroup).forEach(group => {
      group.sort((a, b) => {
        if (!a.date) return 1
        if (!b.date) return -1
        return new Date(b.date) - new Date(a.date)
      })
    })
  })

  // Sort themes alphabetically, "Autres" last
  const sortedThemes = Object.keys(grouped).sort((a, b) => {
    if (a === 'Autres') return 1
    if (b === 'Autres') return -1
    return a.localeCompare(b, lang)
  })

  if (loading || newsletters.length === 0) return null

  return (
    <section className="flex flex-col gap-4 px-6 pb-10">

      <h2 className="text-sm font-semibold uppercase tracking-widest
        text-gray-500 dark:text-gray-400"
      >
        Newsletters
      </h2>

      {/* Confirmation modal */}
      {showConfirm && (
        <div className="
          fixed inset-0 z-20 flex items-center justify-center
          bg-black/50 backdrop-blur-sm
        ">
          <div className="
            flex flex-col gap-5 p-6 rounded-2xl w-80
            bg-white dark:bg-gray-800 shadow-xl
          ">
            <p className="text-sm font-medium text-gray-800 dark:text-gray-100">
              {t('confirmDelete', lang)}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="
                  px-4 py-2 rounded-lg text-sm
                  bg-gray-100 text-gray-700
                  dark:bg-gray-700 dark:text-gray-300
                  hover:bg-gray-200 dark:hover:bg-gray-600
                  transition-colors
                "
              >
                {t('confirmNo', lang)}
              </button>
              <button
                onClick={confirmDelete}
                className="
                  px-4 py-2 rounded-lg text-sm font-medium
                  bg-red-600 text-white hover:bg-red-500
                  transition-colors
                "
              >
                {t('confirmYes', lang)}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Grouped cards */}
      <div className="flex flex-col gap-10">
        {sortedThemes.map(theme => (
          <div key={theme} className="flex flex-col gap-6">
            <h2 className="text-sm font-semibold uppercase tracking-widest
              text-indigo-500 dark:text-indigo-400 border-b border-gray-200
              dark:border-gray-700 pb-2"
            >
              {theme}
            </h2>

            {Object.keys(grouped[theme])
              .sort((a, b) => {
                // Sort senders by most recent newsletter within this theme
                const latestA = grouped[theme][a][0]?.date ?? ''
                const latestB = grouped[theme][b][0]?.date ?? ''
                return new Date(latestB) - new Date(latestA)
              })
              .map(sender => (
                <div key={sender} className="flex flex-col gap-3">
                  <h3 className="text-xs font-semibold uppercase tracking-widest
                    text-gray-400 dark:text-gray-500"
                  >
                    {sender}
                  </h3>

                  {grouped[theme][sender].map(nl => {
                    const isSelected = selected.has(nl.id)
                    return (
                      <article
                        key={nl.id}
                        onClick={() => toggleCard(nl.id)}
                        className={`
                          flex flex-col gap-2 p-4 rounded-xl border cursor-pointer
                          transition-all select-none
                          ${isSelected
                            ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40'
                            : `border-gray-200 dark:border-gray-700
                              bg-white dark:bg-gray-900
                              hover:border-indigo-300 dark:hover:border-indigo-700`
                          }
                        `}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm font-semibold
                            text-gray-900 dark:text-white"
                          >
                            {nl.subject}
                          </span>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-xs text-gray-400 dark:text-gray-500">
                              {formatDate(nl.date)}
                            </span>
                            {isSelected && (
                              <span className="text-indigo-600 dark:text-indigo-400">✓</span>
                            )}
                          </div>
                        </div>

                        {nl.summary && (
                          <p className="text-sm leading-relaxed
                            text-gray-600 dark:text-gray-400"
                          >
                            {nl.summary}
                          </p>
                        )}
                      </article>
                    )
                  })}
                </div>
              ))
            }
          </div>
        ))}
      </div>

    </section>
  )
}