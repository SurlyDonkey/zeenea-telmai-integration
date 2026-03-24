import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊', end: true },
  { to: '/assets', label: 'Asset Browser', icon: '🗂️', end: false },
  { to: '/log', label: 'Sync Log', icon: '📋', end: false },
  { to: '/settings', label: 'Settings', icon: '⚙️', end: false },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar */}
      <aside
        className="flex flex-col w-64 flex-shrink-0"
        style={{ backgroundColor: '#1e293b' }}
      >
        {/* Logo / Brand */}
        <div className="px-6 py-5 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <span className="text-xl">🔗</span>
            <div>
              <div className="text-white font-semibold text-sm leading-tight">Zeenea ↔ Telmai</div>
              <div className="text-slate-400 text-xs">Integration Hub</div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700 hover:text-white'
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-700">
          <div className="text-slate-500 text-xs">v1.0.0</div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-50">
        <Outlet />
      </main>
    </div>
  )
}
