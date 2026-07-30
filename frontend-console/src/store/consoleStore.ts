import { create } from 'zustand'

type ConsoleState = {
  selectedRunId: string | null
  setSelectedRunId: (runId: string | null) => void
}

export const useConsoleStore = create<ConsoleState>((set) => ({
  selectedRunId: null,
  setSelectedRunId: (runId) => set({ selectedRunId: runId }),
}))
