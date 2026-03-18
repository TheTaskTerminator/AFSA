function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            AFSA
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            AI-Driven Fluid Software Architecture
          </p>
        </div>
      </header>
      <main>
        <div className="mx-auto max-w-7xl py-6 sm:px-6 lg:px-8">
          <div className="px-4 py-6 sm:px-0">
            <div className="rounded-lg border-4 border-dashed border-gray-200 p-8 text-center">
              <h2 className="text-xl font-semibold text-gray-700">
                Welcome to AFSA
              </h2>
              <p className="mt-2 text-gray-500">
                The AI-powered software that evolves with your needs
              </p>
              <div className="mt-6">
                <button className="rounded-md bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700">
                  Start a Conversation
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App