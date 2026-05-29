export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4">
      <div className="flex max-w-lg flex-col items-center gap-4 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          PRism
        </h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          AI-powered pull request review assistant.
          Configure your projects and let PRism analyze code changes automatically.
        </p>
        <div className="mt-4 flex gap-3">
          <a
            href="/projects"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
          >
            Get Started
          </a>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors"
          >
            GitHub
          </a>
        </div>
      </div>
    </div>
  );
}
