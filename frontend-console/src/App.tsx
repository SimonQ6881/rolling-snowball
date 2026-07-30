import { BrowserRouter as Router, Route, Routes } from 'react-router-dom'

import Home from '@/pages/Home'
import IndustriesPage from '@/pages/IndustriesPage'
import LabPage from '@/pages/LabPage'
import RunReviewPage from '@/pages/RunReviewPage'
import RunsPage from '@/pages/RunsPage'
import StockDetailPage from '@/pages/StockDetailPage'
import StocksPage from '@/pages/StocksPage'
import TaskPage from '@/pages/TaskPage'

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/run-review" element={<RunReviewPage />} />
        <Route path="/stocks" element={<StocksPage />} />
        <Route path="/industries" element={<IndustriesPage />} />
        <Route path="/stocks/:tsCode" element={<StockDetailPage />} />
        <Route path="/lab" element={<LabPage />} />
        <Route path="/tasks/:taskId" element={<TaskPage />} />
      </Routes>
    </Router>
  )
}
