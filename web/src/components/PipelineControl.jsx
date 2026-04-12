import { useApp } from '../context/AppContext'
import { t } from '../i18n/translations'

export default function PipelineControl({ status, progress, total, error, onRun }) {
  const { lang } = useApp()

  const isRunning = status === 'running'
  const isDone    = status === 'done'
  const isError   = status === 'error'

  async function handleRun() {
    try {
      await fetch('/api/run', { method: 'POST' })
      onRun()
    } catch {
      // Network error — useStatus will surface it on next poll
    }
  }

  async function handleCancel() {
    try {
      await fetch('/api/cancel', { method: 'POST' })
    } catch {
      // Polling will update status on next tick
    }
  }

  return (
    <div className="flex flex-col items-center gap-4 py-8">

      {/* Run button */}
      <button
        onClick={handleRun}
        disabled={isRunning}
        className="
          px-6 py-3 rounded-xl font-semibold text-sm tracking-wide
          bg-indigo-600 text-white
          hover:bg-indigo-500 active:bg-indigo-700
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-colors
        "
      >
        {isRunning ? t('running', lang) : t('run', lang)}
      </button>

      {/* Loader + progress */}
      {isRunning && (
        <div className="flex flex-col items-center gap-3">
          {/* Total emails — shown as soon as available */}
          {total && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {total} {t('totalEmails', lang)}
            </p>
          )}

          <div className="
            w-6 h-6 rounded-full border-2
            border-indigo-300 border-t-indigo-600
            animate-spin
          " />

          {/* Full progress message matching console output */}
          {progress && (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-sm">
              {progress}
            </p>
          )}

          {/* Cancel button */}
          <button
            onClick={handleCancel}
            className="
              mt-1 px-4 py-2 rounded-lg text-sm font-medium
              bg-gray-100 text-gray-700
              dark:bg-gray-800 dark:text-gray-300
              hover:bg-red-100 hover:text-red-700
              dark:hover:bg-red-950 dark:hover:text-red-400
              transition-colors
            "
          >
            {t('cancelPipeline', lang)}
          </button>
        </div>
      )}

      {isDone && (
        <p className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
          {t('done', lang)}
        </p>
      )}
      {isError && (
        <p className="text-sm font-medium text-red-500">
          {t('error', lang)}{error ? ` — ${error}` : ''}
        </p>
      )}
    </div>
  )
}