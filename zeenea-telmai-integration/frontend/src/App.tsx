import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AssetBrowser from './pages/AssetBrowser'
import SyncLog from './pages/SyncLog'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="assets" element={<AssetBrowser />} />
        <Route path="log" element={<SyncLog />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
