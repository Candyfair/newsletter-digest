import { useApp } from '../context/AppContext'
import { t } from '../i18n/translations'

export default function Header() {
  const {
    theme, toggleTheme,
    lang, toggleLang,
    selected, cancelSelection, setShowConfirm,
  } = useApp()

  const hasSelection = selected.size > 0

  return (
    <header className="
      sticky top-0 z-10 flex items-center justify-between
      px-6 py-4 border-b
      bg-white border-gray-200
      dark:bg-gray-900 dark:border-gray-700
    ">
      <h1 className="text-lg font-bold tracking-tight
        text-gray-900 dark:text-white"
      >
        Newsletter Digest
      </h1>

      <div className="flex items-center gap-3">

        {/* Action buttons — visible only when cards are selected */}
        {hasSelection && (
          <>
            <button
              onClick={() => setShowConfirm(true)}
              className="
                px-4 py-2 rounded-lg text-sm font-medium
                bg-red-600 text-white
                hover:bg-red-500 active:bg-red-700
                transition-colors
              "
            >
              {t('delete', lang)} ({selected.size})
            </button>
            <button
              onClick={cancelSelection}
              className="
                px-4 py-2 rounded-lg text-sm font-medium
                bg-gray-100 text-gray-700
                dark:bg-gray-800 dark:text-gray-300
                hover:bg-gray-200 dark:hover:bg-gray-700
                transition-colors
              "
            >
              {t('cancel', lang)}
            </button>
          </>
        )}

        {/* Language toggle */}
        <button
          onClick={toggleLang}
          className="
            px-3 py-1.5 rounded-md text-sm font-medium
            bg-gray-100 text-gray-700
            dark:bg-gray-800 dark:text-gray-300
            hover:bg-gray-200 dark:hover:bg-gray-700
            transition-colors
          "
        >
          {lang === 'fr' ? 'EN' : 'FR'}
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="
            p-2 rounded-md
            bg-gray-100 text-gray-700
            dark:bg-gray-800 dark:text-gray-300
            hover:bg-gray-200 dark:hover:bg-gray-700
            transition-colors
          "
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </div>
    </header>
  )
}