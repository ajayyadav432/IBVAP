import React, { useEffect, useState } from 'react';
import { Shield, Radio, Server, Activity, Volume2, VolumeX, Wifi, AlertTriangle } from 'lucide-react';

interface HeaderProps {
  apiStatus: 'checking' | 'online' | 'offline';
  wsStatus: 'connected' | 'connecting' | 'disconnected';
  activeAlertsCount: number;
  soundEnabled: boolean;
  onToggleSound: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  apiStatus,
  wsStatus,
  activeAlertsCount,
  soundEnabled,
  onToggleSound,
}) => {
  const [time, setTime] = useState<string>('');

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTime(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 border-b border-border bg-surface px-6 flex items-center justify-between select-none shrink-0 z-20">
      {/* Brand & Platform Identity */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-background border border-border flex items-center justify-center text-accent shadow-sm">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold tracking-wider text-sm text-primary uppercase">IBVAP</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-elevated border border-border text-neutral-300 font-mono">
              SIH26187
            </span>
          </div>
          <p className="text-[11px] text-secondary font-medium tracking-tight">
            Intelligent Border Video Analytics Platform
          </p>
        </div>
      </div>

      {/* Operational Indicators & Actions */}
      <div className="flex items-center gap-4">
        {/* Real-time UTC Timestamp */}
        <div className="hidden md:flex items-center gap-2 text-xs font-mono text-secondary bg-background px-3 py-1 rounded border border-border">
          <Activity className="w-3.5 h-3.5 text-secondary" />
          <span>{time || '--:--:-- UTC'}</span>
        </div>

        {/* WebSocket Stream Indicator */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-background border border-border text-xs font-mono">
          <Wifi className={`w-3.5 h-3.5 ${wsStatus === 'connected' ? 'text-emerald-400' : 'text-amber-400'}`} />
          <span className="text-secondary text-[11px]">WS:</span>
          {wsStatus === 'connected' && <span className="text-emerald-400 text-[11px] font-bold">LIVE</span>}
          {wsStatus === 'connecting' && <span className="text-amber-400 text-[11px] animate-pulse">SYNC</span>}
          {wsStatus === 'disconnected' && <span className="text-accent text-[11px]">OFFLINE</span>}
        </div>

        {/* Core Backend API Status */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-background border border-border text-xs font-mono">
          <Server className="w-3.5 h-3.5 text-secondary" />
          <span className="text-secondary text-[11px]">API:</span>
          {apiStatus === 'online' && (
            <span className="flex items-center gap-1.5 text-emerald-400 text-[11px] font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              OK
            </span>
          )}
          {apiStatus === 'offline' && (
            <span className="flex items-center gap-1.5 text-accent text-[11px] font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-accent"></span>
              ERR
            </span>
          )}
          {apiStatus === 'checking' && (
            <span className="text-amber-400 text-[11px] animate-pulse">
              ...
            </span>
          )}
        </div>

        {/* Sound Alert Toggle */}
        <button
          onClick={onToggleSound}
          title={soundEnabled ? 'Alert Sound Enabled (Click to Mute)' : 'Alert Sound Muted (Click to Enable)'}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded border transition-colors text-xs font-mono ${
            soundEnabled
              ? 'bg-elevated border-border text-primary hover:border-accent'
              : 'bg-background border-border text-secondary hover:text-primary'
          }`}
        >
          {soundEnabled ? <Volume2 className="w-3.5 h-3.5 text-emerald-400" /> : <VolumeX className="w-3.5 h-3.5 text-secondary" />}
          <span className="text-[11px] hidden sm:inline">{soundEnabled ? 'AUDIO ON' : 'MUTED'}</span>
        </button>

        {/* Active Threats / Defense Badge */}
        {activeAlertsCount > 0 ? (
          <div className="flex items-center gap-2 px-3 py-1 rounded bg-accent/15 border border-accent text-accent text-xs font-bold font-mono animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{activeAlertsCount} THREAT{activeAlertsCount > 1 ? 'S' : ''} ACTIVE</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-1 rounded bg-accent-subtle border border-accent/40 text-accent text-xs font-semibold uppercase tracking-wider font-mono">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            <span>SECURE</span>
          </div>
        )}
      </div>
    </header>
  );
};
