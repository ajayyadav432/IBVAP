import React, { useState, useEffect } from 'react';
import { 
  AlertOctagon, 
  Filter, 
  RefreshCw, 
  CheckCircle2, 
  ShieldAlert, 
  Eye, 
  Image as ImageIcon,
  Search,
  X,
  Loader2,
  AlertTriangle
} from 'lucide-react';

export interface EventItem {
  id: number;
  timestamp: string;
  camera_id: number;
  camera_name?: string | null;
  event_type: string;
  severity: 'INFO' | 'WARNING' | 'HIGH' | 'CRITICAL' | string;
  object_type?: string | null;
  track_id?: number | null;
  zone_id?: number | null;
  zone_name?: string | null;
  confidence?: number | null;
  reason?: string | null;
  evidence_path?: string | null;
  status: 'NEW' | 'ACKNOWLEDGED' | 'RESOLVED' | string;
}

export interface CameraSimple {
  id: number;
  name: string;
}

export const EventsPage: React.FC = () => {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [cameras, setCameras] = useState<CameraSimple[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  // Filters State
  const [selectedCameraId, setSelectedCameraId] = useState<string>('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [selectedEventType, setSelectedEventType] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  // Selected Detail Modal
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState<boolean>(false);
  const [evidenceError, setEvidenceError] = useState<boolean>(false);

  const fetchCameras = async () => {
    try {
      const res = await fetch('/api/cameras');
      if (res.ok) {
        const data = await res.json();
        setCameras(data.map((c: any) => ({ id: c.id, name: c.name })));
      }
    } catch (err) {
      console.error('Error fetching camera list:', err);
    }
  };

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (selectedCameraId !== 'ALL') params.append('camera_id', selectedCameraId);
      if (selectedSeverity !== 'ALL') params.append('severity', selectedSeverity);
      if (selectedEventType !== 'ALL') params.append('event_type', selectedEventType);
      if (selectedStatus !== 'ALL') params.append('status', selectedStatus);
      if (searchQuery.trim()) params.append('search', searchQuery.trim());
      if (startDate) params.append('start_time', new Date(startDate).toISOString());
      if (endDate) params.append('end_time', new Date(endDate).toISOString());
      params.append('limit', '100');

      const res = await fetch(`/api/events?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
        setTotal(data.total || 0);
      } else {
        setError('Unable to load events. Check backend connection.');
      }
    } catch (err) {
      setError('Unable to load events. Check backend connection.');
      console.error('Error fetching security events:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCameras();
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [selectedCameraId, selectedSeverity, selectedEventType, selectedStatus, startDate, endDate]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchEvents();
  };

  const handleResetFilters = () => {
    setSelectedCameraId('ALL');
    setSelectedSeverity('ALL');
    setSelectedEventType('ALL');
    setSelectedStatus('ALL');
    setSearchQuery('');
    setStartDate('');
    setEndDate('');
  };

  const handleUpdateStatus = async (eventId: number, newStatus: 'ACKNOWLEDGED' | 'RESOLVED') => {
    try {
      const res = await fetch(`/api/events/${eventId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        const updated = await res.json();
        setEvents((prev) => prev.map((e) => (e.id === eventId ? { ...e, status: updated.status } : e)));
        if (selectedEvent && selectedEvent.id === eventId) {
          setSelectedEvent({ ...selectedEvent, status: updated.status });
        }
      }
    } catch (err) {
      console.error('Failed to update event status:', err);
    }
  };

  const hasActiveFilters = 
    selectedCameraId !== 'ALL' ||
    selectedSeverity !== 'ALL' ||
    selectedEventType !== 'ALL' ||
    selectedStatus !== 'ALL' ||
    searchQuery.trim() !== '' ||
    startDate !== '' ||
    endDate !== '';

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-950/80 text-red-400 border-red-700';
      case 'HIGH':
        return 'bg-orange-950/80 text-orange-400 border-orange-700';
      case 'WARNING':
        return 'bg-amber-950/80 text-amber-400 border-amber-700';
      case 'INFO':
      default:
        return 'bg-blue-950/80 text-blue-400 border-blue-700';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACKNOWLEDGED':
        return 'bg-amber-950/40 text-amber-400 border-amber-800/60';
      case 'RESOLVED':
        return 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60';
      case 'NEW':
      default:
        return 'bg-red-950/40 text-red-400 border-red-800/60';
    }
  };

  return (
    <div className="flex-1 p-6 space-y-6 overflow-y-auto">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-primary uppercase">Security Event Log & History</h1>
          <p className="text-xs text-secondary mt-0.5">
            Immutable audit trail, intrusion logs, and captured evidence snapshots
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchEvents}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-surface border border-border text-secondary hover:text-primary transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-surface rounded border border-border p-4 space-y-3.5 text-xs">
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center gap-3">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[220px]">
            <Search className="w-3.5 h-3.5 text-secondary absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search reason, event type, or camera name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-background border border-border rounded pl-8 pr-3 py-1.5 text-xs text-primary focus:border-accent outline-none font-mono"
            />
          </div>

          <button
            type="submit"
            className="px-3 py-1.5 rounded bg-accent hover:bg-accent-hover text-white text-xs font-bold transition-colors"
          >
            Search
          </button>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="px-3 py-1.5 rounded bg-elevated border border-border text-secondary hover:text-primary text-xs transition-colors flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" />
              <span>Reset Filters</span>
            </button>
          )}
        </form>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-border/50">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-secondary font-semibold uppercase text-[11px] flex items-center gap-1">
              <Filter className="w-3.5 h-3.5 text-accent" />
              Filter By:
            </span>

            {/* Camera Filter */}
            <select
              value={selectedCameraId}
              onChange={(e) => setSelectedCameraId(e.target.value)}
              className="bg-background border border-border rounded px-2.5 py-1 text-primary focus:border-accent outline-none font-mono"
            >
              <option value="ALL">All Cameras</option>
              {cameras.map((c) => (
                <option key={c.id} value={c.id.toString()}>
                  CAM #{c.id}: {c.name}
                </option>
              ))}
            </select>

            {/* Severity Filter */}
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-background border border-border rounded px-2.5 py-1 text-primary focus:border-accent outline-none font-mono"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">🔴 CRITICAL</option>
              <option value="HIGH">🟠 HIGH</option>
              <option value="WARNING">🟡 WARNING</option>
              <option value="INFO">🔵 INFO</option>
            </select>

            {/* Event Type Filter */}
            <select
              value={selectedEventType}
              onChange={(e) => setSelectedEventType(e.target.value)}
              className="bg-background border border-border rounded px-2.5 py-1 text-primary focus:border-accent outline-none font-mono"
            >
              <option value="ALL">All Types</option>
              <option value="ZONE_INTRUSION">ZONE_INTRUSION</option>
              <option value="LOITERING">LOITERING</option>
              <option value="NIGHT_MOVEMENT">NIGHT_MOVEMENT</option>
              <option value="ANPR_DETECTED">ANPR_DETECTED</option>
              <option value="PERSON_DETECTED">PERSON_DETECTED</option>
              <option value="VEHICLE_DETECTED">VEHICLE_DETECTED</option>
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-background border border-border rounded px-2.5 py-1 text-primary focus:border-accent outline-none font-mono"
            >
              <option value="ALL">All Statuses</option>
              <option value="NEW">NEW</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </div>

          {/* Date Pickers */}
          <div className="flex items-center gap-2">
            <span className="text-secondary text-[11px] font-mono">Date Range:</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-background border border-border rounded px-2 py-1 text-[11px] text-primary outline-none font-mono"
            />
            <span className="text-secondary text-[10px]">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-background border border-border rounded px-2 py-1 text-[11px] text-primary outline-none font-mono"
            />
          </div>
        </div>
      </div>

      {/* Error State Banner */}
      {error && (
        <div className="p-3.5 rounded bg-accent-subtle border border-accent text-accent text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Events Table Container */}
      <div className="bg-surface rounded border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-elevated/40 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-accent" />
            <span className="text-xs font-semibold text-primary uppercase tracking-wide">Historical Audit Trail</span>
          </div>
          <span className="text-xs font-mono text-secondary">
            {total} PERSISTED {total === 1 ? 'RECORD' : 'RECORDS'}
          </span>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="flex flex-col items-center justify-center p-12 text-center text-secondary">
            <Loader2 className="w-8 h-8 text-accent animate-spin mb-2" />
            <p className="text-xs font-mono">Loading security events from SQLite...</p>
          </div>
        ) : events.length === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center p-12 text-center text-secondary">
            <CheckCircle2 className="w-10 h-10 text-emerald-500 mb-2 opacity-80" />
            <h3 className="text-sm font-semibold text-primary">
              {hasActiveFilters ? 'No events match the selected filters.' : 'No security events found.'}
            </h3>
            <p className="text-xs text-secondary mt-1 max-w-sm">
              {hasActiveFilters
                ? 'Try adjusting your search query, severity, or date range filters.'
                : 'Real-time suspicious activity, zone intrusion, and night movement events will be indexed here automatically.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-elevated/60 text-secondary uppercase font-mono text-[10px] border-b border-border">
                <tr>
                  <th className="py-2.5 px-3">ID</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Camera Source</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Event Type</th>
                  <th className="py-2.5 px-3">Entity / Zone</th>
                  <th className="py-2.5 px-4">Reason & Evidence</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono text-xs">
                {events.map((ev) => (
                  <tr key={ev.id} className="hover:bg-elevated/30 transition-colors">
                    <td className="py-2.5 px-3 text-secondary font-bold">#{ev.id}</td>
                    <td className="py-2.5 px-3 text-zinc-300">
                      {new Date(ev.timestamp).toLocaleTimeString()}{' '}
                      <span className="text-[10px] text-secondary">
                        ({new Date(ev.timestamp).toLocaleDateString()})
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-primary">
                      {ev.camera_name || `Camera #${ev.camera_id}`}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${getSeverityBadge(ev.severity)}`}>
                        {ev.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-bold text-primary">{ev.event_type}</td>
                    <td className="py-2.5 px-3 text-secondary">
                      <div>{ev.object_type || '—'} {ev.track_id !== null && ev.track_id !== undefined ? `(#${ev.track_id})` : ''}</div>
                      {ev.zone_name && <div className="text-[10px] text-red-400 font-bold">{ev.zone_name}</div>}
                    </td>
                    <td className="py-2.5 px-4 text-zinc-300 max-w-xs truncate">
                      <div className="flex items-center gap-1.5">
                        {ev.evidence_path && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-accent-subtle text-accent border border-accent/40 font-bold shrink-0">
                            EVIDENCE
                          </span>
                        )}
                        <span className="truncate">{ev.reason || '—'}</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${getStatusBadge(ev.status)}`}>
                        {ev.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => {
                            setSelectedEvent(ev);
                            setEvidenceLoading(true);
                            setEvidenceError(false);
                          }}
                          className="p-1 rounded bg-elevated border border-border text-secondary hover:text-primary hover:border-accent transition-colors"
                          title="View Event Details"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {ev.status === 'NEW' && (
                          <button
                            onClick={() => handleUpdateStatus(ev.id, 'ACKNOWLEDGED')}
                            className="px-2 py-0.5 rounded bg-amber-950/50 border border-amber-800 text-amber-300 hover:bg-amber-900/60 text-[10px] font-bold transition-colors"
                            title="Acknowledge"
                          >
                            ACK
                          </button>
                        )}
                        {ev.status !== 'RESOLVED' && (
                          <button
                            onClick={() => handleUpdateStatus(ev.id, 'RESOLVED')}
                            className="px-2 py-0.5 rounded bg-emerald-950/50 border border-emerald-800 text-emerald-300 hover:bg-emerald-900/60 text-[10px] font-bold transition-colors"
                            title="Resolve"
                          >
                            RESOLVE
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Event Details & Evidence Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-surface border border-border rounded-lg max-w-lg w-full p-6 space-y-5 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-accent" />
                <h3 className="text-sm font-bold text-primary uppercase">Event #{selectedEvent.id} Breakdown</h3>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-secondary hover:text-primary text-xs"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs font-mono">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-background p-3 rounded border border-border">
                  <span className="text-secondary text-[10px] uppercase block">Event Type</span>
                  <span className="font-bold text-primary text-sm">{selectedEvent.event_type}</span>
                </div>
                <div className="bg-background p-3 rounded border border-border">
                  <span className="text-secondary text-[10px] uppercase block">Severity</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border inline-block mt-1 ${getSeverityBadge(selectedEvent.severity)}`}>
                    {selectedEvent.severity}
                  </span>
                </div>
                <div className="bg-background p-3 rounded border border-border">
                  <span className="text-secondary text-[10px] uppercase block">Camera Source</span>
                  <span className="font-bold text-primary">
                    {selectedEvent.camera_name || `Camera #${selectedEvent.camera_id}`}
                  </span>
                </div>
                <div className="bg-background p-3 rounded border border-border">
                  <span className="text-secondary text-[10px] uppercase block">Timestamp</span>
                  <span className="font-bold text-primary">{new Date(selectedEvent.timestamp).toLocaleString()}</span>
                </div>
              </div>

              {/* Entity / Track / Zone Details */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-background p-3 rounded border border-border">
                  <span className="text-secondary text-[10px] uppercase block">Object Track ID</span>
                  <span className="font-bold text-primary">
                    {selectedEvent.object_type ? `${selectedEvent.object_type} #${selectedEvent.track_id ?? 'N/A'}` : '—'}
                  </span>
                </div>
                <div className="bg-background p-3 rounded border border-border">
                  <span className="text-secondary text-[10px] uppercase block">Associated Zone</span>
                  <span className="font-bold text-primary">
                    {selectedEvent.zone_name || (selectedEvent.zone_id ? `Zone #${selectedEvent.zone_id}` : 'None / Boundary')}
                  </span>
                </div>
              </div>

              {/* Explainable Reason */}
              <div className="bg-background p-3.5 rounded border border-border space-y-1">
                <span className="text-secondary text-[10px] uppercase block font-semibold">Detection Reason</span>
                <p className="text-zinc-200 text-xs leading-relaxed">{selectedEvent.reason || 'No description recorded.'}</p>
                {selectedEvent.confidence !== null && selectedEvent.confidence !== undefined && (
                  <p className="text-[10px] text-emerald-400 font-bold pt-1">
                    Detector / OCR Confidence: {(selectedEvent.confidence * 100).toFixed(1)}%
                  </p>
                )}
              </div>

              {/* Evidence Snapshot */}
              {selectedEvent.evidence_path && (
                <div className="bg-background p-3.5 rounded border border-border space-y-2">
                  <span className="text-secondary text-[10px] uppercase block font-semibold flex items-center gap-1.5">
                    <ImageIcon className="w-3.5 h-3.5 text-accent" />
                    Captured Evidence Snapshot
                  </span>

                  <div className="rounded overflow-hidden border border-border/80 bg-black flex items-center justify-center min-h-[160px] relative">
                    {evidenceLoading && (
                      <div className="absolute inset-0 flex items-center justify-center bg-black/60 z-10">
                        <Loader2 className="w-5 h-5 text-accent animate-spin" />
                      </div>
                    )}
                    {evidenceError ? (
                      <div className="p-4 text-center text-secondary text-xs">
                        <p>Evidence snapshot unavailable on disk.</p>
                      </div>
                    ) : (
                      <img
                        src={`/api/events/${selectedEvent.id}/evidence`}
                        alt="Event Evidence"
                        className="max-h-56 w-auto object-contain"
                        onLoad={() => setEvidenceLoading(false)}
                        onError={() => {
                          setEvidenceLoading(false);
                          setEvidenceError(true);
                        }}
                      />
                    )}
                  </div>
                  <span className="text-[10px] text-secondary font-mono block break-all">
                    Identifier: {selectedEvent.evidence_path}
                  </span>
                </div>
              )}

              {/* Footer Controls */}
              <div className="flex items-center justify-between pt-2 border-t border-border">
                <div className="flex items-center gap-2">
                  <span className="text-secondary text-xs">Status:</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${getStatusBadge(selectedEvent.status)}`}>
                    {selectedEvent.status}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {selectedEvent.status !== 'RESOLVED' && (
                    <button
                      onClick={() => handleUpdateStatus(selectedEvent.id, 'RESOLVED')}
                      className="px-3 py-1.5 rounded bg-emerald-900/60 border border-emerald-700 text-emerald-300 font-bold hover:bg-emerald-800/80 transition-colors"
                    >
                      RESOLVE EVENT
                    </button>
                  )}
                  <button
                    onClick={() => setSelectedEvent(null)}
                    className="px-3 py-1.5 rounded bg-elevated border border-border text-secondary hover:text-primary transition-colors"
                  >
                    CLOSE
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
