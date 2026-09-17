import React, { useState, useEffect } from 'react';
import {
  Camera,
  RefreshCw,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Users,
  Car,
  Scan,
  CreditCard,
  Activity,
  Shield,
} from 'lucide-react';
import { SurveillanceFeed } from '../components/SurveillanceFeed';

interface CameraItem {
  id: number;
  name: string;
  source_type: string;
  source_uri: string;
  enabled: boolean;
  status: string;
  resolution?: string;
  source_fps?: number;
  measured_fps?: number;
  inference_device?: string;
  inference_latency_ms?: number;
  inference_fps?: number;
  face_latency_ms?: number;
  anpr_latency_ms?: number;
  zone_latency_ms?: number;
  activity_latency_ms?: number;
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
  created_at?: string;
  updated_at?: string;
  error_message?: string;
}

export const CamerasPage: React.FC = () => {
  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCamId, setSelectedCamId] = useState<number | null>(null);
  const [testingCamId, setTestingCamId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ [id: number]: { status: string; message: string } }>({});

  const fetchCameras = async () => {
    try {
      const res = await fetch('/api/cameras');
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch cameras`);
      const data: CameraItem[] = await res.json();
      setCameras(data);
      setSelectedCamId((prevSelectedId) => {
        if (prevSelectedId !== null && data.some((c: CameraItem) => c.id === prevSelectedId)) {
          return prevSelectedId;
        }
        return data.length > 0 ? data[0].id : null;
      });
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Could not connect to camera service.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCameras();
    const interval = setInterval(fetchCameras, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleEnabled = async (cam: CameraItem) => {
    try {
      const res = await fetch(`/api/cameras/${cam.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !cam.enabled }),
      });
      if (res.ok) {
        fetchCameras();
      }
    } catch (err) {
      console.error('Failed to toggle camera:', err);
    }
  };

  const handleTestConnection = async (camId: number) => {
    setTestingCamId(camId);
    try {
      const res = await fetch(`/api/cameras/${camId}/test`, {
        method: 'POST',
      });
      const data = await res.json();
      setTestResult((prev) => ({
        ...prev,
        [camId]: {
          status: data.status,
          message: data.message,
        },
      }));
    } catch (err: any) {
      setTestResult((prev) => ({
        ...prev,
        [camId]: {
          status: 'FAILED',
          message: err.message || 'Connection test failed.',
        },
      }));
    } finally {
      setTestingCamId(null);
    }
  };

  const selectedCam = cameras.find((c) => c.id === selectedCamId) || (cameras.length > 0 ? cameras[0] : undefined);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-background">
      {/* Top Page Header */}
      <div className="h-14 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Camera className="w-5 h-5 text-accent" />
          <div>
            <h1 className="text-sm font-bold tracking-wide text-primary uppercase">Camera Surveillance Management</h1>
            <p className="text-[11px] text-secondary">
              Live ingest feeds, decoder telemetry, resolution metrics, and channel probes
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-secondary bg-elevated px-3 py-1 rounded border border-border">
            Total Channels: <strong className="text-primary">{cameras.length}</strong>
          </span>
          <button
            onClick={fetchCameras}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-elevated hover:bg-border text-primary text-xs font-medium border border-border transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading && cameras.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-secondary">
            <RefreshCw className="w-6 h-6 animate-spin text-accent" />
            <p className="text-xs font-mono">Initializing camera telemetry streams...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-surface border border-accent/40 rounded p-6 text-center">
            <AlertTriangle className="w-10 h-10 text-accent mx-auto mb-3" />
            <h3 className="text-sm font-bold text-primary mb-1">Camera Service Offline</h3>
            <p className="text-xs text-secondary mb-4">{error}</p>
            <button
              onClick={fetchCameras}
              className="px-4 py-2 bg-elevated border border-border rounded text-xs text-primary font-medium hover:border-accent"
            >
              Retry Connection
            </button>
          </div>
        </div>
      ) : cameras.length === 0 ? (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-surface border border-border rounded p-8 text-center">
            <Camera className="w-12 h-12 text-secondary mx-auto mb-3 opacity-40" />
            <h3 className="text-sm font-bold text-primary mb-1">No Cameras Registered</h3>
            <p className="text-xs text-secondary mb-4">
              Add video streams or RTSP feeds in the Settings module to begin AI surveillance.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden p-6 gap-6">
          {/* Left: Camera List & Telemetry Cards */}
          <div className="w-1/2 flex flex-col gap-4 overflow-y-auto pr-1">
            {cameras.map((cam) => {
              const isSelected = cam.id === selectedCamId;
              const isOnline = cam.status === 'CONNECTED' && cam.enabled;
              const res = testResult[cam.id];

              return (
                <div
                  key={cam.id}
                  onClick={() => setSelectedCamId(cam.id)}
                  className={`p-4 rounded border transition-all cursor-pointer bg-surface ${
                    isSelected
                      ? 'border-accent shadow-[inset_2px_0_0_0_#FF1118]'
                      : 'border-border hover:border-neutral-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`w-2.5 h-2.5 rounded-full ${
                          isOnline ? 'bg-emerald-500 animate-pulse' : cam.enabled ? 'bg-amber-400' : 'bg-neutral-600'
                        }`}
                      />
                      <span className="font-bold text-xs text-primary tracking-wide">{cam.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-elevated border border-border text-secondary font-mono">
                        CAM #{cam.id}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                          cam.status === 'CONNECTED'
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                            : cam.status === 'CONNECTING'
                            ? 'bg-amber-400/10 border-amber-400/30 text-amber-400'
                            : 'bg-neutral-800 border-neutral-700 text-neutral-400'
                        }`}
                      >
                        {cam.status}
                      </span>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleEnabled(cam);
                        }}
                        title={cam.enabled ? 'Disable Camera' : 'Enable Camera'}
                        className={`p-1 rounded border transition-colors ${
                          cam.enabled
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                            : 'bg-elevated border-border text-secondary hover:text-primary'
                        }`}
                      >
                        {cam.enabled ? <Play className="w-3 h-3 fill-current" /> : <Pause className="w-3 h-3" />}
                      </button>
                    </div>
                  </div>

                  {/* Sanitized Source URI */}
                  <div className="text-[11px] font-mono text-secondary truncate mb-3 bg-background px-2.5 py-1 rounded border border-border">
                    <span className="text-neutral-300 mr-1.5">[{cam.source_type}]</span>
                    {cam.source_uri}
                  </div>

                  {/* Metric Counters Grid */}
                  <div className="grid grid-cols-4 gap-2 mb-3">
                    <div className="bg-background rounded p-2 border border-border text-center">
                      <div className="text-[9px] uppercase font-mono text-secondary flex items-center justify-center gap-1">
                        <Users className="w-3 h-3 text-secondary" />
                        Persons
                      </div>
                      <div className="text-xs font-bold text-primary mt-0.5 font-mono">
                        {cam.detection_counts?.person ?? 0}
                      </div>
                    </div>

                    <div className="bg-background rounded p-2 border border-border text-center">
                      <div className="text-[9px] uppercase font-mono text-secondary flex items-center justify-center gap-1">
                        <Car className="w-3 h-3 text-secondary" />
                        Vehicles
                      </div>
                      <div className="text-xs font-bold text-primary mt-0.5 font-mono">
                        {cam.detection_counts?.vehicle ?? 0}
                      </div>
                    </div>

                    <div className="bg-background rounded p-2 border border-border text-center">
                      <div className="text-[9px] uppercase font-mono text-secondary flex items-center justify-center gap-1">
                        <Scan className="w-3 h-3 text-secondary" />
                        Faces
                      </div>
                      <div className="text-xs font-bold text-primary mt-0.5 font-mono">
                        {cam.faces_count ?? 0}
                      </div>
                    </div>

                    <div className="bg-background rounded p-2 border border-border text-center">
                      <div className="text-[9px] uppercase font-mono text-secondary flex items-center justify-center gap-1">
                        <CreditCard className="w-3 h-3 text-secondary" />
                        Plates
                      </div>
                      <div className="text-xs font-bold text-primary mt-0.5 font-mono">
                        {cam.anpr_count ?? 0}
                      </div>
                    </div>
                  </div>

                  {/* Operational Telemetry & Connection Test */}
                  <div className="flex items-center justify-between pt-2 border-t border-border text-[11px] text-secondary">
                    <div className="flex items-center gap-3 font-mono">
                      <span>FPS: <strong className="text-primary">{cam.measured_fps?.toFixed(1) || '0.0'}</strong></span>
                      <span>Res: <strong className="text-primary">{cam.resolution || 'Unknown'}</strong></span>
                      <span>Latency: <strong className="text-primary">{cam.inference_latency_ms?.toFixed(0) || '0'}ms</strong></span>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleTestConnection(cam.id);
                      }}
                      disabled={testingCamId === cam.id}
                      className="text-[10px] font-mono px-2 py-1 rounded bg-elevated border border-border text-neutral-300 hover:border-accent flex items-center gap-1"
                    >
                      <Activity className={`w-3 h-3 ${testingCamId === cam.id ? 'animate-spin text-accent' : ''}`} />
                      <span>{testingCamId === cam.id ? 'Probing...' : 'Probe Channel'}</span>
                    </button>
                  </div>

                  {/* Probe Result Box */}
                  {res && (
                    <div
                      className={`mt-2.5 p-2 rounded text-[11px] font-mono border ${
                        res.status === 'CONNECTED'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                          : 'bg-accent/10 border-accent/30 text-accent'
                      }`}
                    >
                      <div className="font-bold flex items-center gap-1.5">
                        {res.status === 'CONNECTED' ? (
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5" />
                        )}
                        <span>PROBE {res.status}</span>
                      </div>
                      <div className="text-[10px] text-secondary mt-0.5">{res.message}</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Right: Live Stream Viewer & Deep Telemetry */}
          {selectedCam && (
            <div className="w-1/2 flex flex-col gap-4 overflow-y-auto">
              {/* Video Player Card */}
              <div className="bg-surface rounded border border-border overflow-hidden flex flex-col">
                <div className="p-3 border-b border-border bg-elevated/40 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                    <span className="font-bold text-xs text-primary font-mono uppercase">
                      LIVE SURVEILLANCE FEED — {selectedCam.name}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-secondary bg-background px-2 py-0.5 rounded border border-border">
                    {selectedCam.inference_device || 'CPU Engine'}
                  </span>
                </div>

                <SurveillanceFeed camera={selectedCam} />

                {/* Bottom HUD Bar */}
                <div className="p-3 border-t border-border grid grid-cols-3 gap-3 bg-background">
                  <div>
                    <div className="text-[10px] uppercase font-mono text-secondary">Inference Latency</div>
                    <div className="text-xs font-bold text-primary font-mono mt-0.5">
                      {selectedCam.inference_latency_ms?.toFixed(1) || '0.0'} ms
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-mono text-secondary">Active Tracks</div>
                    <div className="text-xs font-bold text-primary font-mono mt-0.5">
                      {selectedCam.tracking_counts?.total_active_tracks ?? 0} targets
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-mono text-secondary">Active Zones</div>
                    <div className="text-xs font-bold text-primary font-mono mt-0.5">
                      {selectedCam.zones_count ?? 0} configured
                    </div>
                  </div>
                </div>
              </div>

              {/* ANPR Plates Detected Card */}
              <div className="bg-surface rounded border border-border p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-accent" />
                    <span className="text-xs font-bold text-primary uppercase font-mono">
                      Recent Plate Observations (ANPR)
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-secondary">
                    {selectedCam.anpr_results?.length ?? 0} records
                  </span>
                </div>

                {selectedCam.anpr_results && selectedCam.anpr_results.length > 0 ? (
                  <div className="space-y-2 max-h-44 overflow-y-auto">
                    {selectedCam.anpr_results.map((anpr, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2.5 rounded bg-background border border-border"
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-elevated border border-border text-secondary">
                            {anpr.state_code || 'IND'}
                          </span>
                          <span className="text-xs font-mono font-bold text-primary tracking-wider">
                            {anpr.plate_text}
                          </span>
                        </div>

                        <div className="flex items-center gap-3 text-[10px] font-mono">
                          <span
                            className={`px-1.5 py-0.5 rounded ${
                              anpr.quality === 'READABLE'
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                : 'bg-amber-400/10 text-amber-400 border border-amber-400/30'
                            }`}
                          >
                            {anpr.quality}
                          </span>
                          <span className="text-secondary">
                            {(anpr.confidence * 100).toFixed(0)}% CONF
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 bg-background rounded border border-border">
                    <CreditCard className="w-8 h-8 text-secondary mx-auto mb-2 opacity-30" />
                    <p className="text-xs text-secondary font-mono">No vehicle number plates logged for this feed.</p>
                  </div>
                )}
              </div>

              {/* Configured Zones List */}
              <div className="bg-surface rounded border border-border p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-accent" />
                    <span className="text-xs font-bold text-primary uppercase font-mono">
                      Virtual Perimeter Zones
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-secondary">
                    {selectedCam.zones?.length ?? 0} defined
                  </span>
                </div>

                {selectedCam.zones && selectedCam.zones.length > 0 ? (
                  <div className="space-y-2">
                    {selectedCam.zones.map((zone) => (
                      <div
                        key={zone.id}
                        className="flex items-center justify-between p-2.5 rounded bg-background border border-border"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              zone.zone_type === 'RESTRICTED' ? 'bg-accent' : 'bg-blue-400'
                            }`}
                          />
                          <span className="text-xs font-semibold text-primary">{zone.name}</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                              zone.zone_type === 'RESTRICTED'
                                ? 'bg-accent/10 border-accent/30 text-accent'
                                : 'bg-blue-400/10 border-blue-400/30 text-blue-400'
                            }`}
                          >
                            {zone.zone_type}
                          </span>
                          <span className="text-[10px] font-mono text-secondary">
                            {zone.enabled ? 'ACTIVE' : 'MUTED'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 bg-background rounded border border-border">
                    <Shield className="w-8 h-8 text-secondary mx-auto mb-2 opacity-30" />
                    <p className="text-xs text-secondary font-mono">No virtual perimeter zones drawn for this camera.</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
