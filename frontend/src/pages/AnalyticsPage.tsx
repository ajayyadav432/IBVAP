import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  Clock,
  Moon,
  ShieldAlert,
  UserCheck,
  RefreshCw,
  CheckCircle2,
  Sliders,
} from 'lucide-react';

interface ActivityItem {
  event_type: string;
  camera_id: number;
  track_id: number;
  zone_id?: number;
  zone_name?: string;
  zone_type?: string;
  object_type: string;
  timestamp: string;
  severity: string;
  reason: string;
  confidence?: number;
  duration_sec?: number;
  anchor_point?: number[];
}

interface LoiteringState {
  track_id: number;
  zone_id?: number;
  duration_sec: number;
  threshold_sec: number;
  is_loitering: boolean;
}

interface AnalyticsSettings {
  loitering_threshold_sec: number;
  detection_conf_threshold: number;
  face_conf_threshold: number;
  night_movement_enabled: boolean;
  night_start_time: string;
  night_end_time: string;
  night_cooldown_sec: number;
  supported_rules: string[];
}

interface AnalyticsPageProps {
  onNavigateToSettings?: (subtab?: string) => void;
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({
  onNavigateToSettings,
}) => {
  const [analyticsSettings, setAnalyticsSettings] = useState<AnalyticsSettings | null>(null);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loiteringStates, setLoiteringStates] = useState<LoiteringState[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchAnalyticsData = async () => {
    try {
      // 1. Fetch system analytics settings
      const settingsRes = await fetch('/api/system/analytics');
      if (settingsRes.ok) {
        const sData = await settingsRes.json();
        setAnalyticsSettings(sData);
      }

      // 2. Fetch active camera activities across all cameras
      const camerasRes = await fetch('/api/cameras');
      if (camerasRes.ok) {
        const cams = await camerasRes.json();
        const allActs: ActivityItem[] = [];
        const allLoitering: LoiteringState[] = [];

        for (const cam of cams) {
          try {
            const actRes = await fetch(`/api/cameras/${cam.id}/activities`);
            if (actRes.ok) {
              const actData = await actRes.json();
              if (actData.activities) allActs.push(...actData.activities);
              if (actData.active_loitering) allLoitering.push(...actData.active_loitering);
            }
          } catch (e) {
            // ignore individual camera fetch failure
          }
        }

        setActivities(allActs);
        setLoiteringStates(allLoitering);
      }
    } catch (err: any) {
      console.error('Failed to fetch analytics intelligence:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalyticsData();
    const interval = setInterval(fetchAnalyticsData, 3000);
    return () => clearInterval(interval);
  }, []);

  // Helper to determine if current time falls within night schedule
  const isNightWindowActive = () => {
    if (!analyticsSettings || !analyticsSettings.night_movement_enabled) return false;
    const now = new Date();
    const curH = now.getUTCHours();
    const curM = now.getUTCMinutes();
    const curMins = curH * 60 + curM;

    const [sh, sm] = analyticsSettings.night_start_time.split(':').map(Number);
    const [eh, em] = analyticsSettings.night_end_time.split(':').map(Number);
    const startMins = sh * 60 + sm;
    const endMins = eh * 60 + em;

    if (startMins <= endMins) {
      return curMins >= startMins && curMins <= endMins;
    } else {
      return curMins >= startMins || curMins <= endMins;
    }
  };

  const nightActive = isNightWindowActive();

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-background">
      {/* Top Page Header */}
      <div className="h-14 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-accent" />
          <div>
            <h1 className="text-sm font-bold tracking-wide text-primary uppercase">
              AI Suspicious Activity & Behavioral Rules
            </h1>
            <p className="text-[11px] text-secondary">
              Deterministic intrusion detection, dwell time tracking, and night surveillance window enforcement
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigateToSettings?.('analytics')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-elevated hover:bg-border text-primary text-xs font-medium border border-border transition-colors"
          >
            <Sliders className="w-3.5 h-3.5 text-accent" />
            <span>Tune Thresholds</span>
          </button>

          <button
            onClick={fetchAnalyticsData}
            className="p-1.5 rounded bg-surface hover:bg-elevated border border-border text-secondary hover:text-primary transition-colors"
            title="Refresh Analytics"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Rule Engine Architecture Banner */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Rule 1: Restricted Zone Intrusion */}
          <div className="p-4 rounded border border-border bg-surface flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-accent" />
                  <span className="font-bold text-xs text-primary uppercase font-mono">
                    RULE 1: ZONE INTRUSION
                  </span>
                </div>
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-accent/15 border border-accent text-accent">
                  CRITICAL
                </span>
              </div>
              <p className="text-[11px] text-secondary leading-relaxed mb-3">
                Evaluates bottom-center coordinate of ByteTrack targets against polygon perimeters via ray-casting.
              </p>
            </div>

            <div className="p-2.5 rounded bg-background border border-border flex items-center justify-between text-xs font-mono">
              <span className="text-secondary text-[10px]">Algorithm:</span>
              <span className="text-emerald-400 font-bold text-[10px]">Ray-Casting PIP</span>
            </div>
          </div>

          {/* Rule 2: Loitering Detection */}
          <div className="p-4 rounded border border-border bg-surface flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-amber-400" />
                  <span className="font-bold text-xs text-primary uppercase font-mono">
                    RULE 2: LOITERING DWELL
                  </span>
                </div>
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-400/15 border border-amber-400/30 text-amber-400">
                  HIGH
                </span>
              </div>
              <p className="text-[11px] text-secondary leading-relaxed mb-3">
                Tracks cumulative dwell time per track ID inside monitoring zones. Triggers alarm when threshold exceeded.
              </p>
            </div>

            <div className="p-2.5 rounded bg-background border border-border flex items-center justify-between text-xs font-mono">
              <span className="text-secondary text-[10px]">Dwell Threshold:</span>
              <span className="text-primary font-bold text-[10px]">
                {analyticsSettings?.loitering_threshold_sec ?? 30}s
              </span>
            </div>
          </div>

          {/* Rule 3: Night-Time Movement Detection */}
          <div className="p-4 rounded border border-border bg-surface flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Moon className="w-4 h-4 text-indigo-400" />
                  <span className="font-bold text-xs text-primary uppercase font-mono">
                    RULE 3: NIGHT SURVEILLANCE
                  </span>
                </div>
                <span
                  className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                    nightActive
                      ? 'bg-indigo-500/20 border-indigo-500 text-indigo-300 animate-pulse'
                      : 'bg-elevated border-border text-secondary'
                  }`}
                >
                  {nightActive ? 'ACTIVE NOW' : 'STANDBY'}
                </span>
              </div>
              <p className="text-[11px] text-secondary leading-relaxed mb-3">
                Restricted window schedule flag. Flags all person/vehicle tracks during designated hours.
              </p>
            </div>

            <div className="p-2.5 rounded bg-background border border-border flex items-center justify-between text-xs font-mono">
              <span className="text-secondary text-[10px]">Window (UTC):</span>
              <span className="text-indigo-400 font-bold text-[10px]">
                {analyticsSettings?.night_start_time || '22:00'} → {analyticsSettings?.night_end_time || '05:00'}
              </span>
            </div>
          </div>
        </div>

        {/* Active Dwell Timers & Target Tracking */}
        <div className="bg-surface rounded border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <Clock className="w-4 h-4 text-accent" />
              <h2 className="text-xs font-bold text-primary uppercase tracking-wide font-mono">
                Active Zone Dwell Timers ({loiteringStates.length} Monitored Targets)
              </h2>
            </div>
            <span className="text-[11px] text-secondary font-mono">
              Configured Limit: {analyticsSettings?.loitering_threshold_sec ?? 30}s
            </span>
          </div>

          {loiteringStates.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {loiteringStates.map((st, idx) => {
                const percent = Math.min(100, (st.duration_sec / st.threshold_sec) * 100);
                const isViolated = st.is_loitering;

                return (
                  <div
                    key={idx}
                    className={`p-3 rounded bg-background border ${
                      isViolated ? 'border-accent bg-accent/5' : 'border-border'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono font-bold text-primary">
                        Target Track #{st.track_id}
                      </span>
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                          isViolated
                            ? 'bg-accent text-white'
                            : 'bg-elevated text-secondary'
                        }`}
                      >
                        {isViolated ? 'LOITERING ALARM' : 'MONITORING'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] font-mono text-secondary mb-1">
                      <span>Dwell Time:</span>
                      <span className={`font-bold ${isViolated ? 'text-accent' : 'text-primary'}`}>
                        {st.duration_sec.toFixed(1)}s / {st.threshold_sec}s
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-elevated rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          isViolated ? 'bg-accent' : 'bg-amber-400'
                        }`}
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-6 bg-background rounded border border-border">
              <UserCheck className="w-8 h-8 text-secondary mx-auto mb-2 opacity-30" />
              <p className="text-xs text-secondary font-mono">No active dwell timers currently accumulating.</p>
            </div>
          )}
        </div>

        {/* Live Suspicious Activity Candidates Feed */}
        <div className="bg-surface rounded border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-accent" />
              <h2 className="text-xs font-bold text-primary uppercase tracking-wide font-mono">
                Recent Suspicious Activity Triggers ({activities.length})
              </h2>
            </div>
          </div>

          {activities.length > 0 ? (
            <div className="space-y-2.5">
              {activities.map((act, idx) => {
                const isCrit = act.severity === 'CRITICAL';
                return (
                  <div
                    key={idx}
                    className={`p-3 rounded bg-background border flex items-center justify-between ${
                      isCrit ? 'border-accent/40 bg-accent/5' : 'border-border'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-2 h-2 rounded-full ${
                          isCrit ? 'bg-accent animate-ping' : 'bg-amber-400'
                        }`}
                      />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-primary font-mono">
                            {act.event_type.replace(/_/g, ' ')}
                          </span>
                          <span className="text-[10px] text-secondary font-mono">
                            • Track #{act.track_id}
                          </span>
                          <span className="text-[10px] text-secondary font-mono">
                            • Camera #{act.camera_id}
                          </span>
                        </div>
                        <p className="text-xs text-neutral-300 mt-0.5">{act.reason}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 text-right">
                      <div>
                        <span
                          className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                            isCrit
                              ? 'bg-accent/15 border-accent text-accent'
                              : 'bg-amber-400/10 border-amber-400/30 text-amber-400'
                          }`}
                        >
                          {act.severity}
                        </span>
                        <div className="text-[10px] font-mono text-secondary mt-1">
                          {new Date(act.timestamp).toISOString().substring(11, 19)} UTC
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 bg-background rounded border border-border">
              <CheckCircle2 className="w-8 h-8 text-emerald-500/40 mx-auto mb-2" />
              <p className="text-xs text-secondary font-mono">No active suspicious activity triggers in current buffer.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
