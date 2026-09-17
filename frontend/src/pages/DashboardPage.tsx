import React, { useEffect, useState } from 'react';
import {
  RefreshCw,
  User,
  Car,
  Cpu,
  Crosshair,
  ShieldAlert,
  Bell,
  Scan,
  CreditCard,
  Eye,
  Activity,
  CheckCircle2,
  X,
  ChevronRight,
} from 'lucide-react';
import { SurveillanceFeed } from '../components/SurveillanceFeed';

export interface RealtimeAlertItem {
  event_id: number;
  timestamp: string;
  camera_id: number;
  camera_name?: string;
  event_type: string;
  severity: 'INFO' | 'WARNING' | 'HIGH' | 'CRITICAL' | string;
  object_type?: string | null;
  track_id?: number | null;
  zone_id?: number | null;
  zone_name?: string | null;
  confidence?: number | null;
  reason: string;
  evidence_path?: string | null;
  status: string;
}

export interface CameraItem {
  id: number;
  name: string;
  source_type: string;
  source_uri: string;
  enabled: boolean;
  status: 'CONNECTED' | 'CONNECTING' | 'DISCONNECTED' | 'ERROR' | 'STOPPED' | string;
  resolution?: string;
  source_fps?: number;
  measured_fps?: number;
  inference_device?: string;
  inference_latency_ms?: number;
  inference_fps?: number;
  detection_counts?: {
    total: number;
    person: number;
    vehicle: number;
  };
  tracking_counts?: {
    total_active_tracks: number;
    tracked_persons: number;
    tracked_vehicles: number;
  };
  faces_count?: number;
  anpr_count?: number;
  zones_count?: number;
  activities_count?: number;
  anpr_results?: Array<{
    plate_text: string;
    quality: string;
    confidence: number;
    state_code?: string;
  }>;
  zones?: Array<{
    id: number;
    name: string;
    zone_type: string;
    enabled: boolean;
  }>;
}

export interface SystemInferenceInfo {
  model_name: string;
  variant: string;
  framework: string;
  device: string;
  tracker_engine: string;
  face_model_name: string;
  anpr_engine: string;
  zone_engine: string;
  activity_engine: string;
}

interface DashboardPageProps {
  realtimeAlerts?: RealtimeAlertItem[];
  onNavigateToTab?: (tab: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  realtimeAlerts = [],
  onNavigateToTab,
}) => {
  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [selectedCamId, setSelectedCamId] = useState<number | null>(null);
  const [inferenceInfo, setInferenceInfo] = useState<SystemInferenceInfo | null>(null);
  const [recentEvents, setRecentEvents] = useState<RealtimeAlertItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedEvidenceEvent, setSelectedEvidenceEvent] = useState<RealtimeAlertItem | null>(null);

  // Fetch all cameras and inference metadata
  const fetchDashboardData = async () => {
    try {
      // 1. Fetch Cameras
      const camRes = await fetch('/api/cameras');
      if (camRes.ok) {
        const camData: CameraItem[] = await camRes.json();
        setCameras(camData);
        setSelectedCamId((prevSelectedId) => {
          if (prevSelectedId !== null && camData.some((c: CameraItem) => c.id === prevSelectedId)) {
            return prevSelectedId;
          }
          return camData.length > 0 ? camData[0].id : null;
        });
      }

      // 2. Fetch Inference System Info
      const infRes = await fetch('/api/system/inference');
      if (infRes.ok) {
        const infData = await infRes.json();
        setInferenceInfo(infData);
      }

      // 3. Fetch Recent Historical Events
      const evRes = await fetch('/api/events?limit=8&offset=0');
      if (evRes.ok) {
        const evData = await evRes.json();
        setRecentEvents(
          evData.events.map((e: any) => ({
            event_id: e.id,
            timestamp: e.timestamp,
            camera_id: e.camera_id,
            camera_name: e.camera_name,
            event_type: e.event_type,
            severity: e.severity,
            object_type: e.object_type,
            track_id: e.track_id,
            zone_id: e.zone_id,
            zone_name: e.zone_name,
            confidence: e.confidence,
            reason: e.reason,
            evidence_path: e.evidence_path,
            status: e.status,
          }))
        );
      }
    } catch (err: any) {
      console.error('Error updating dashboard telemetry:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 3000);
    return () => clearInterval(interval);
  }, []);

  const selectedCam = cameras.find((c) => c.id === selectedCamId) || (cameras.length > 0 ? cameras[0] : undefined);

  // Aggregate platform telemetry metrics
  const totalPersons = cameras.reduce((acc, c) => acc + (c.detection_counts?.person || 0), 0);
  const totalVehicles = cameras.reduce((acc, c) => acc + (c.detection_counts?.vehicle || 0), 0);
  const totalTracks = cameras.reduce(
    (acc, c) => acc + (c.tracking_counts?.total_active_tracks || 0),
    0
  );
  const totalFaces = cameras.reduce((acc, c) => acc + (c.faces_count || 0), 0);
  const totalPlates = cameras.reduce((acc, c) => acc + (c.anpr_count || 0), 0);
  const avgLatency =
    cameras.length > 0
      ? cameras.reduce((acc, c) => acc + (c.inference_latency_ms || 0), 0) / cameras.length
      : 0;

  // Real-time alerts feed (prioritize live WS alerts, fallback to recent)
  const displayAlerts = realtimeAlerts.length > 0 ? realtimeAlerts : recentEvents.slice(0, 6);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-background">
      {/* 1. Global Telemetry Ribbon */}
      <div className="h-16 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0 gap-4 overflow-x-auto">
        <div className="flex items-center gap-6">
          {/* Target Persons */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-background border border-border flex items-center justify-center text-primary">
              <User className="w-4 h-4 text-neutral-300" />
            </div>
            <div>
              <div className="text-[10px] uppercase font-mono text-secondary">Persons</div>
              <div className="text-sm font-bold text-primary font-mono">{totalPersons}</div>
            </div>
          </div>

          {/* Target Vehicles */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-background border border-border flex items-center justify-center text-primary">
              <Car className="w-4 h-4 text-neutral-300" />
            </div>
            <div>
              <div className="text-[10px] uppercase font-mono text-secondary">Vehicles</div>
              <div className="text-sm font-bold text-primary font-mono">{totalVehicles}</div>
            </div>
          </div>

          {/* Active ByteTracks */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-background border border-border flex items-center justify-center text-primary">
              <Crosshair className="w-4 h-4 text-neutral-300" />
            </div>
            <div>
              <div className="text-[10px] uppercase font-mono text-secondary">Tracks</div>
              <div className="text-sm font-bold text-primary font-mono">{totalTracks}</div>
            </div>
          </div>

          {/* Face Detections */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-background border border-border flex items-center justify-center text-primary">
              <Scan className="w-4 h-4 text-neutral-300" />
            </div>
            <div>
              <div className="text-[10px] uppercase font-mono text-secondary">Faces</div>
              <div className="text-sm font-bold text-primary font-mono">{totalFaces}</div>
            </div>
          </div>

          {/* ANPR Plates */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-background border border-border flex items-center justify-center text-primary">
              <CreditCard className="w-4 h-4 text-neutral-300" />
            </div>
            <div>
              <div className="text-[10px] uppercase font-mono text-secondary">Plates</div>
              <div className="text-sm font-bold text-primary font-mono">{totalPlates}</div>
            </div>
          </div>

          {/* AI Latency */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-background border border-border flex items-center justify-center text-primary">
              <Cpu className="w-4 h-4 text-accent" />
            </div>
            <div>
              <div className="text-[10px] uppercase font-mono text-secondary">AI Latency</div>
              <div className="text-sm font-bold text-primary font-mono">
                {avgLatency > 0 ? `${avgLatency.toFixed(0)} ms` : '< 1 ms'}
              </div>
            </div>
          </div>
        </div>

        {/* Engine Diagnostics Pill */}
        <div className="flex items-center gap-3">
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded bg-background border border-border text-[11px] font-mono text-secondary">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>
              {inferenceInfo?.variant || 'YOLOX-Tiny'} + {inferenceInfo?.tracker_engine || 'ByteTrack'} (
              {inferenceInfo?.device || 'CPU'})
            </span>
          </div>

          <button
            onClick={fetchDashboardData}
            className="p-2 rounded bg-surface hover:bg-elevated border border-border text-secondary hover:text-primary transition-colors"
            title="Refresh Dashboard"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* 2. Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden p-6 gap-6">
        {/* Left Column: Primary Video Surveillance & Multi-Cam Selector */}
        <div className="w-7/12 flex flex-col gap-4 overflow-y-auto">
          {/* Main Video Viewport Card */}
          <div className="bg-surface rounded border border-border overflow-hidden flex flex-col shadow-sm">
            {/* Viewport Header */}
            <div className="p-3 border-b border-border bg-elevated/40 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse" />
                <span className="font-bold text-xs text-primary font-mono uppercase">
                  FEED: {selectedCam ? selectedCam.name : 'NO FEED SELECTED'}
                </span>
                {selectedCam && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-background border border-border text-secondary font-mono">
                    CH-0{selectedCam.id}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 text-xs font-mono">
                <span
                  className={`px-2 py-0.5 rounded border text-[10px] font-bold ${
                    selectedCam?.status === 'CONNECTED'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : 'bg-accent/15 border-accent text-accent'
                  }`}
                >
                  {selectedCam?.status || 'OFFLINE'}
                </span>
              </div>
            </div>

            {/* Video Canvas Container */}
            <SurveillanceFeed camera={selectedCam} />

            {/* Bottom HUD Analytics Strip */}
            <div className="p-3 border-t border-border grid grid-cols-4 gap-2 bg-background text-center font-mono">
              <div className="p-2 rounded bg-surface border border-border">
                <div className="text-[9px] uppercase text-secondary">Target Persons</div>
                <div className="text-xs font-bold text-primary mt-0.5">
                  {selectedCam?.detection_counts?.person ?? 0}
                </div>
              </div>

              <div className="p-2 rounded bg-surface border border-border">
                <div className="text-[9px] uppercase text-secondary">Target Vehicles</div>
                <div className="text-xs font-bold text-primary mt-0.5">
                  {selectedCam?.detection_counts?.vehicle ?? 0}
                </div>
              </div>

              <div className="p-2 rounded bg-surface border border-border">
                <div className="text-[9px] uppercase text-secondary">Active Tracks</div>
                <div className="text-xs font-bold text-primary mt-0.5">
                  {selectedCam?.tracking_counts?.total_active_tracks ?? 0}
                </div>
              </div>

              <div className="p-2 rounded bg-surface border border-border">
                <div className="text-[9px] uppercase text-secondary">Perimeter Zones</div>
                <div className="text-xs font-bold text-primary mt-0.5">
                  {selectedCam?.zones_count ?? 0}
                </div>
              </div>
            </div>
          </div>

          {/* Multi-Channel Switcher Strip */}
          <div className="bg-surface rounded border border-border p-3">
            <div className="flex items-center justify-between mb-2.5 px-1">
              <span className="text-[11px] font-bold text-secondary uppercase tracking-wider font-mono">
                Channel Switcher ({cameras.length} Active Channels)
              </span>
              <button
                onClick={() => onNavigateToTab?.('cameras')}
                className="text-[11px] text-primary hover:text-accent font-mono flex items-center gap-1 transition-colors"
              >
                <span>Manage All</span>
                <ChevronRight className="w-3 h-3" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2.5">
              {cameras.map((cam) => {
                const isSelected = cam.id === selectedCamId;
                return (
                  <button
                    key={cam.id}
                    onClick={() => setSelectedCamId(cam.id)}
                    className={`p-2.5 rounded border text-left transition-all ${
                      isSelected
                        ? 'bg-elevated border-accent shadow-[inset_2px_0_0_0_#FF1118]'
                        : 'bg-background border-border hover:border-neutral-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-primary truncate">{cam.name}</span>
                      <span
                        className={`w-2 h-2 rounded-full ${
                          cam.status === 'CONNECTED' ? 'bg-emerald-500' : 'bg-neutral-600'
                        }`}
                      />
                    </div>
                    <div className="text-[10px] font-mono text-secondary truncate">
                      {cam.source_type} • {cam.resolution || '720p'}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Real-Time Threat Alerts & Recent Audit Log */}
        <div className="w-5/12 flex flex-col gap-4 overflow-y-auto">
          {/* Priority Real-Time Alert Feed */}
          <div className="bg-surface rounded border border-border p-4 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-accent" />
                <h2 className="text-xs font-bold text-primary uppercase font-mono tracking-wider">
                  Real-Time Threat Alerts (WebSocket)
                </h2>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent/15 border border-accent text-accent font-bold">
                {displayAlerts.length} Active
              </span>
            </div>

            <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
              {displayAlerts.length > 0 ? (
                displayAlerts.map((alert, idx) => {
                  const isCrit = alert.severity === 'CRITICAL';
                  const isHigh = alert.severity === 'HIGH';

                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedEvidenceEvent(alert)}
                      className={`p-3 rounded border transition-all cursor-pointer ${
                        isCrit
                          ? 'bg-accent/10 border-accent text-white shadow-sm'
                          : isHigh
                          ? 'bg-amber-400/10 border-amber-400/40 text-neutral-200'
                          : 'bg-background border-border text-neutral-300 hover:border-neutral-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              isCrit ? 'bg-accent animate-ping' : isHigh ? 'bg-amber-400' : 'bg-blue-400'
                            }`}
                          />
                          <span className="text-xs font-bold font-mono tracking-wide">
                            {alert.event_type.replace(/_/g, ' ')}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                              isCrit
                                ? 'bg-accent text-white border-accent'
                                : isHigh
                                ? 'bg-amber-400/20 text-amber-400 border-amber-400/40'
                                : 'bg-elevated text-secondary border-border'
                            }`}
                          >
                            {alert.severity}
                          </span>
                        </div>
                      </div>

                      <p className="text-xs text-neutral-300 leading-snug line-clamp-2 mb-2">
                        {alert.reason}
                      </p>

                      <div className="flex items-center justify-between text-[10px] font-mono text-secondary pt-1 border-t border-border/40">
                        <span>
                          CAM #{alert.camera_id} • Track #{alert.track_id ?? 'N/A'}
                        </span>
                        <span className="flex items-center gap-1 text-primary hover:text-accent font-semibold">
                          <span>Inspect Evidence</span>
                          <Eye className="w-3 h-3" />
                        </span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="text-center py-8 bg-background rounded border border-border">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500/40 mx-auto mb-2" />
                  <p className="text-xs text-secondary font-mono">No threat alerts triggered. Perimeter secure.</p>
                </div>
              )}
            </div>
          </div>

          {/* Recent Event Audit Table */}
          <div className="bg-surface rounded border border-border p-4 flex flex-col flex-1">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-accent" />
                <h2 className="text-xs font-bold text-primary uppercase font-mono tracking-wider">
                  Recent Audit History
                </h2>
              </div>
              <button
                onClick={() => onNavigateToTab?.('events')}
                className="text-[11px] text-primary hover:text-accent font-mono flex items-center gap-1 transition-colors"
              >
                <span>View All History</span>
                <ChevronRight className="w-3 h-3" />
              </button>
            </div>

            <div className="overflow-y-auto space-y-2 flex-1 max-h-56">
              {recentEvents.length > 0 ? (
                recentEvents.map((ev) => (
                  <div
                    key={ev.event_id}
                    onClick={() => setSelectedEvidenceEvent(ev)}
                    className="p-2.5 rounded bg-background border border-border hover:border-neutral-700 transition-colors cursor-pointer flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-primary font-mono">
                          {ev.event_type.replace(/_/g, ' ')}
                        </span>
                        <span className="text-[10px] text-secondary font-mono">
                          • {ev.camera_name || `CAM #${ev.camera_id}`}
                        </span>
                      </div>
                      <div className="text-[11px] text-secondary truncate max-w-xs mt-0.5">
                        {ev.reason}
                      </div>
                    </div>

                    <div className="text-right font-mono text-[10px]">
                      <span
                        className={`px-1.5 py-0.5 rounded ${
                          ev.severity === 'CRITICAL'
                            ? 'bg-accent/15 text-accent border border-accent/40 font-bold'
                            : 'bg-elevated text-secondary border border-border'
                        }`}
                      >
                        {ev.severity}
                      </span>
                      <div className="text-neutral-500 mt-1">
                        {new Date(ev.timestamp).toISOString().substring(11, 19)} UTC
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-6 text-xs text-secondary font-mono">
                  No historical events logged.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Evidence Snapshot Inspection Modal */}
      {selectedEvidenceEvent && (
        <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-surface border border-border rounded max-w-2xl w-full overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-4 border-b border-border bg-elevated/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-accent" />
                <h3 className="text-xs font-bold text-primary uppercase font-mono">
                  EVIDENCE SNAPSHOT — EVENT #{selectedEvidenceEvent.event_id}
                </h3>
              </div>
              <button
                onClick={() => setSelectedEvidenceEvent(null)}
                className="p-1 rounded text-secondary hover:text-primary transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Image & Telemetry */}
            <div className="p-4 space-y-4">
              {/* Snapshot Frame */}
              <div className="relative aspect-video bg-black rounded border border-border overflow-hidden flex items-center justify-center">
                <img
                  src={`/api/events/${selectedEvidenceEvent.event_id}/evidence`}
                  alt="Evidence Frame"
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = '';
                  }}
                />
              </div>

              {/* Event Metadata Breakdown */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div className="p-2 bg-background rounded border border-border">
                  <span className="text-[10px] text-secondary">Event Type</span>
                  <div className="font-bold text-primary mt-0.5">
                    {selectedEvidenceEvent.event_type}
                  </div>
                </div>

                <div className="p-2 bg-background rounded border border-border">
                  <span className="text-[10px] text-secondary">Severity</span>
                  <div className="font-bold text-accent mt-0.5">
                    {selectedEvidenceEvent.severity}
                  </div>
                </div>

                <div className="p-2 bg-background rounded border border-border">
                  <span className="text-[10px] text-secondary">Target Track</span>
                  <div className="font-bold text-primary mt-0.5">
                    #{selectedEvidenceEvent.track_id ?? 'N/A'} (
                    {selectedEvidenceEvent.object_type ?? 'person'})
                  </div>
                </div>

                <div className="p-2 bg-background rounded border border-border">
                  <span className="text-[10px] text-secondary">Channel</span>
                  <div className="font-bold text-primary mt-0.5">
                    CAM #{selectedEvidenceEvent.camera_id}
                  </div>
                </div>
              </div>

              {/* Explainable Detection Rationale */}
              <div className="p-3 bg-background rounded border border-border">
                <span className="text-[10px] uppercase font-mono text-secondary">
                  Rule Trigger Rationale:
                </span>
                <p className="text-xs text-neutral-200 mt-1 leading-relaxed">
                  {selectedEvidenceEvent.reason}
                </p>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-3 border-t border-border bg-background flex items-center justify-between">
              <span className="text-[10px] font-mono text-secondary">
                Logged at: {new Date(selectedEvidenceEvent.timestamp).toISOString()}
              </span>

              <button
                onClick={() => setSelectedEvidenceEvent(null)}
                className="px-4 py-1.5 bg-elevated hover:bg-border text-primary rounded text-xs font-mono font-medium border border-border transition-colors"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
