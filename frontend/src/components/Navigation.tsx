import React from 'react';
import {
  LayoutDashboard,
  Camera,
  AlertOctagon,
  ShieldAlert,
  Activity,
  Settings as SettingsIcon,
} from 'lucide-react';

export type NavTab = 'dashboard' | 'cameras' | 'events' | 'zones' | 'analytics' | 'settings';

interface NavigationProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  activeAlertsCount?: number;
}

export const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  onSelectTab,
  activeAlertsCount = 0,
}) => {
  const navItems = [
    {
      id: 'dashboard' as NavTab,
      label: 'Dashboard',
      icon: LayoutDashboard,
      desc: 'Live Command Center',
      badge: null,
    },
    {
      id: 'cameras' as NavTab,
      label: 'Cameras',
      icon: Camera,
      desc: 'Stream Management',
      badge: null,
    },
    {
      id: 'events' as NavTab,
      label: 'Event History',
      icon: AlertOctagon,
      desc: 'Audit Log & Evidence',
      badge: activeAlertsCount > 0 ? activeAlertsCount : null,
      badgeColor: 'bg-accent text-white',
    },
    {
      id: 'zones' as NavTab,
      label: 'Zones & Fences',
      icon: ShieldAlert,
      desc: 'Virtual Perimeters',
      badge: null,
    },
    {
      id: 'analytics' as NavTab,
      label: 'AI Analytics',
      icon: Activity,
      desc: 'Intrusions & Loitering',
      badge: null,
    },
    {
      id: 'settings' as NavTab,
      label: 'Settings',
      icon: SettingsIcon,
      desc: 'System Configuration',
      badge: null,
    },
  ];

  return (
    <aside className="w-64 border-r border-border bg-surface flex flex-col justify-between p-4 select-none shrink-0">
      <div className="space-y-6">
        <div className="px-3 py-1 flex items-center justify-between">
          <p className="text-[10px] font-bold text-secondary uppercase tracking-widest font-mono">
            Core Modules
          </p>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-elevated border border-border text-neutral-400 font-mono">
            v0.1.0
          </span>
        </div>

        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-left transition-all duration-150 group border ${
                  isActive
                    ? 'bg-elevated border-accent text-primary shadow-[inset_2px_0_0_0_#FF1118]'
                    : 'border-transparent text-secondary hover:text-primary hover:bg-elevated/50'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Icon
                    className={`w-4 h-4 shrink-0 transition-colors ${
                      isActive ? 'text-accent' : 'text-secondary group-hover:text-primary'
                    }`}
                  />
                  <div className="truncate">
                    <div className="text-xs font-semibold tracking-wide truncate">{item.label}</div>
                    <div className="text-[10px] text-secondary truncate">{item.desc}</div>
                  </div>
                </div>

                {item.badge !== null && (
                  <span
                    className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full ${
                      item.badgeColor || 'bg-elevated text-secondary'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="border-t border-border pt-4 px-2">
        <div className="bg-background rounded p-3 border border-border">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-mono text-secondary">Platform Status</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          </div>
          <div className="text-xs font-bold text-primary mt-1">IBVAP Command Center</div>
          <div className="text-[10px] text-secondary mt-0.5">SIH26187 • Production Ready</div>
        </div>
      </div>
    </aside>
  );
};
