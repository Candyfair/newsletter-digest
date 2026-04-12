import { useApp } from '../context/AppContext'
import { t } from '../i18n/translations'

export default function DigestViewer() {
  const { lang } = useApp()

  return (
    <section className="flex flex-col gap-3 px-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-widest
          text-gray-500 dark:text-gray-400"
        >
          Digest
        </h2>
        <a
          href="/api/digest"
          target="_blank"
          rel="noopener noreferrer"
          className="
            text-xs font-medium text-indigo-600 dark:text-indigo-400
            hover:underline
          "
        >
          {t('viewDigest', lang)} ↗
        </a>
      </div>

      {/* iframe renders the Flask /digest route directly */}
      <iframe
        src="/api/digest"
        title="Newsletter digest"
        className="
          w-full rounded-xl border
          border-gray-200 dark:border-gray-700
          bg-white dark:bg-gray-900
        "
        style={{ height: '600px' }}
      />
    </section>
  )
}