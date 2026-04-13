import { useStatus } from './hooks/useStatus'
import Header from './components/Header'
import PipelineControl from './components/PipelineControl'
import SummaryList from './components/SummaryList'

export default function App() {
  const { status, progress, total, error, startPolling } = useStatus()

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
      <Header />

      <main className="max-w-3xl mx-auto flex flex-col gap-8 py-8">
        <PipelineControl
          status={status}
          progress={progress}
          total={total}
          error={error}
          onRun={startPolling}
        />

        <SummaryList status={status} />
      </main>
    </div>
  )
}