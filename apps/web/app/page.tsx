export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center">
          <h1 className="text-6xl font-bold text-white mb-6">
            GPUCloud
          </h1>
          <p className="text-xl text-gray-300 mb-8">
            RunPod-style GPU Cloud Computing Platform
          </p>
          <div className="bg-white/10 backdrop-blur-sm rounded-lg p-8 max-w-2xl mx-auto">
            <h2 className="text-2xl font-semibold text-white mb-4">
              Welcome to GPUCloud MVP
            </h2>
            <p className="text-gray-300 mb-6">
              A modern, scalable platform for GPU-powered machine learning workloads.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="bg-white/5 rounded p-4">
                <h3 className="font-semibold text-white mb-2">FastAPI Backend</h3>
                <p className="text-gray-400">Python 3.11 + FastAPI</p>
              </div>
              <div className="bg-white/5 rounded p-4">
                <h3 className="font-semibold text-white mb-2">Next.js Frontend</h3>
                <p className="text-gray-400">React 18 + TypeScript</p>
              </div>
              <div className="bg-white/5 rounded p-4">
                <h3 className="font-semibold text-white mb-2">Infrastructure</h3>
                <p className="text-gray-400">Terraform + AWS</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
