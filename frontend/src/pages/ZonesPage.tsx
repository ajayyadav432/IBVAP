import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  RefreshCw,
  Plus,
  Layers,
  Info,
  ExternalLink,
} from 'lucide-react';

interface ZoneItem {
  id: number;
  camera_id: number;
  camera_name?: string;
  name: string;
  zone_type: 'RESTRICTED' | 'MONITORING';
  polygon: number[][];
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

interface CameraItem {
  id: number;
  name: string;
  source_type: string;
  enabled: boolean;
  status: string;
  zones?: ZoneItem[];
  active_intrusions?: { [trackId: string]: any };
}

interface ZonesPageProps {
  onNavigateToSettings?: (subtab?: string) => void;
}

export const ZonesPage: React.FC<ZonesPageProps> = ({ onNavigateToSettings }) => {
  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedCameraId, setSelectedCameraId] = useState<number | 'ALL'>('ALL');

  const fetchZonesData = async () => {
    try {
      const res = await fetch('/api/cameras');
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch cameras`);
      const data = await res.json();
      setCameras(data);
    } catch (err: any) {
      console.error('Could not fetch perimeter zones:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchZonesData();
    const interval = setInterval(fetchZonesData, 4000);
    return () => clearInterval(interval);
  }, []);

  const allZones: ZoneItem[] = [];
  cameras.forEach((cam) => {
    if (cam.zones) {
      cam.zones.forEach((z) => {
        allZones.push({
          ...z,
          camera_id: cam.id,
          camera_name: cam.name,
        });
      });
    }
  });

  const filteredZones =
    selectedCameraId === 'ALL'
      ? allZones
      : allZones.filter((z) => z.camera_id === selectedCameraId);

  const restrictedCount = allZones.filter((z) => z.zone_type === 'RESTRICTED').length;
  const monitoringCount = allZones.filter((z) => z.zone_type === 'MONITORING').length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-background">
      {/* Top Page Header */}
      <div className="h-14 border-b border-border bg-surface px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-accent" />
          <div>
            <h1 className="text-sm font-bold tracking-wide text-primary uppercase">
              Virtual Perimeter & Fencing Engine
            </h1>
            <p className="text-[11px] text-secondary">
              Ray-casting Point-in-Polygon boundary definitions, restricted intrusions, and buffer zones
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="px-2 py-1 rounded bg-accent/15 border border-accent text-accent font-bold">
              {restrictedCount} Restricted
            </span>
            <span className="px-2 py-1 rounded bg-blue-500/10 border border-blue-500/30 text-blue-400 font-bold">
              {monitoringCount} Monitoring
            </span>
          </div>

          <button
            onClick={() => onNavigateToSettings?.('zones')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent text-white text-xs font-semibold hover:bg-accent-hover transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Draw New Zone</span>
          </button>
        </div>
      </div>

      {/* Camera Filter Toolbar */}
      <div className="h-11 border-b border-border bg-elevated/30 px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 overflow-x-auto py-1">
          <span className="text-[11px] text-secondary font-mono mr-2">Filter Channel:</span>
          <button
            onClick={() => setSelectedCameraId('ALL')}
            className={`px-2.5 py-1 rounded text-xs font-mono font-medium border transition-colors ${
              selectedCameraId === 'ALL'
                ? 'bg-elevated border-accent text-primary'
                : 'border-border text-secondary hover:text-primary'
            }`}
          >
            All Channels ({allZones.length})
          </button>

          {cameras.map((cam) => (
            <button
              key={cam.id}
              onClick={() => setSelectedCameraId(cam.id)}
              className={`px-2.5 py-1 rounded text-xs font-mono font-medium border transition-colors ${
                selectedCameraId === cam.id
                  ? 'bg-elevated border-accent text-primary'
                  : 'border-border text-secondary hover:text-primary'
              }`}
            >
              {cam.name} ({cam.zones?.length ?? 0})
            </button>
          ))}
        </div>

        <button
          onClick={fetchZonesData}
          className="p-1.5 rounded bg-surface hover:bg-elevated border border-border text-secondary hover:text-primary transition-colors"
          title="Refresh Zones"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Main Grid Area */}
      {loading && cameras.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-secondary">
            <RefreshCw className="w-6 h-6 animate-spin text-accent" />
            <p className="text-xs font-mono">Synchronizing polygon boundaries...</p>
          </div>
        </div>
      ) : filteredZones.length === 0 ? (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-surface border border-border rounded p-8 text-center">
            <Layers className="w-12 h-12 text-secondary mx-auto mb-3 opacity-40" />
            <h3 className="text-sm font-bold text-primary mb-1">No Perimeter Zones Configured</h3>
            <p className="text-xs text-secondary mb-4">
              Create restricted exclusion boundaries or monitoring zones on live camera views to trigger automated alarms.
            </p>
            <button
              onClick={() => onNavigateToSettings?.('zones')}
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white rounded text-xs font-bold hover:bg-accent-hover"
            >
              <Plus className="w-4 h-4" />
              <span>Launch Canvas Polygon Editor</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredZones.map((zone) => {
              const isRestricted = zone.zone_type === 'RESTRICTED';

              return (
                <div
                  key={zone.id}
                  className="bg-surface rounded border border-border overflow-hidden flex flex-col justify-between hover:border-neutral-700 transition-all"
                >
                  <div>
                    {/* Header */}
                    <div className="p-4 border-b border-border bg-elevated/30 flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        {isRestricted ? (
                          <ShieldAlert className="w-4 h-4 text-accent" />
                        ) : (
                          <ShieldCheck className="w-4 h-4 text-blue-400" />
                        )}
                        <div>
                          <h3 className="text-xs font-bold text-primary tracking-wide">{zone.name}</h3>
                          <span className="text-[10px] text-secondary font-mono">
                            {zone.camera_name || `Camera #${zone.camera_id}`}
                          </span>
                        </div>
                      </div>

                      <span
                        className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded border ${
                          isRestricted
                            ? 'bg-accent/15 border-accent/40 text-accent'
                            : 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                        }`}
                      >
                        {zone.zone_type}
                      </span>
                    </div>

                    {/* Body & Polygon Coordinates */}
                    <div className="p-4 space-y-3">
                      {/* Status / Alarm Indicator */}
                      <div className="flex items-center justify-between p-2 rounded bg-background border border-border text-xs font-mono">
                        <span className="text-secondary text-[11px]">Enforcement State:</span>
                        {zone.enabled ? (
                          <span className="text-emerald-400 font-bold flex items-center gap-1 text-[11px]">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                            ACTIVE
                          </span>
                        ) : (
                          <span className="text-neutral-500 font-bold text-[11px]">MUTED</span>
                        )}
                      </div>

                      {/* Vertex Summary */}
                      <div className="bg-background rounded p-3 border border-border">
                        <div className="flex items-center justify-between text-[10px] uppercase font-mono text-secondary mb-1.5">
                          <span>Geometry Points</span>
                          <span className="font-bold text-primary font-mono">{zone.polygon?.length || 0} Vertices</span>
                        </div>

                        <div className="text-[10px] font-mono text-secondary space-y-1 max-h-24 overflow-y-auto">
                          {zone.polygon && zone.polygon.length > 0 ? (
                            zone.polygon.map((pt, idx) => (
                              <div key={idx} className="flex items-center justify-between">
                                <span className="text-neutral-500">P{idx + 1}:</span>
                                <span className="text-neutral-300">
                                  X: {(pt[0] * 100).toFixed(1)}% , Y: {(pt[1] * 100).toFixed(1)}%
                                </span>
                              </div>
                            ))
                          ) : (
                            <div className="text-neutral-500">No vertex coordinates available</div>
                          )}
                        </div>
                      </div>

                      {/* Rule Description */}
                      <div className="text-[11px] text-secondary flex items-start gap-2 bg-elevated/20 p-2.5 rounded border border-border">
                        <Info className="w-3.5 h-3.5 text-neutral-400 shrink-0 mt-0.5" />
                        <span>
                          {isRestricted
                            ? 'Immediate CRITICAL alert triggered if bottom-center of any tracked human or vehicle crosses polygon boundary.'
                            : 'Monitors target dwell time and movement flow inside buffer perimeter.'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Footer Action */}
                  <div className="p-3 border-t border-border bg-background flex items-center justify-between">
                    <span className="text-[10px] font-mono text-secondary">
                      Zone ID: #{zone.id}
                    </span>

                    <button
                      onClick={() => onNavigateToSettings?.('zones')}
                      className="text-[11px] font-mono text-primary hover:text-accent flex items-center gap-1 transition-colors"
                    >
                      <span>Edit in Canvas</span>
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
