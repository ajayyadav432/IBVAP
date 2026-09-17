import React, { useState, useEffect, useRef } from 'react';
import { 
  Camera as CameraIcon, 
  Cpu, 
  ShieldAlert, 
  Bell, 
  Moon, 
  Server, 
  Plus, 
  Trash2, 
  Play, 
  Pause, 
  CheckCircle2, 
  Loader2, 
  RotateCcw, 
  AlertTriangle, 
  Radio, 
  Save, 
  AlertOctagon 
} from 'lucide-react';

export interface CameraData {
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
  error_message?: string;
}

export interface ZoneData {
  id: number;
  camera_id: number;
  name: string;
  zone_type: 'RESTRICTED' | 'MONITORING';
  polygon: [number, number][];
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SystemInfoData {
  app_name: string;
  app_version: string;
  environment: string;
  detector_model: string;
  face_model: string;
  ocr_model: string;
  inference_device: string;
  database_type: string;
  database_status: string;
  system_status: string;
  uptime_seconds: number;
}

export interface SettingsState {
  // Analytics
  person_detection_enabled: boolean;
  vehicle_detection_enabled: boolean;
  tracking_enabled: boolean;
  face_detection_enabled: boolean;
  anpr_enabled: boolean;
  suspicious_activity_enabled: boolean;
  
  // Thresholds
  detection_conf_threshold: number;
  loitering_threshold_sec: number;
  
  // Alerts
  alert_cooldown_sec: number;
  alert_min_severity: string;
  alert_sound_enabled: boolean;
  evidence_capture_enabled: boolean;
  
  // Night Schedule
  night_movement_enabled: boolean;
  night_start_time: string;
  night_end_time: string;
  night_cooldown_sec: number;
}

type SettingsSection = 'cameras' | 'analytics' | 'zones' | 'alerts' | 'night' | 'system';

interface SettingsPageProps {
  initialSubtab?: string;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ initialSubtab }) => {
  const [activeSection, setActiveSection] = useState<SettingsSection>(
    (initialSubtab as SettingsSection) || 'cameras'
  );

  useEffect(() => {
    if (initialSubtab) {
      setActiveSection(initialSubtab as SettingsSection);
    }
  }, [initialSubtab]);
  const [cameras, setCameras] = useState<CameraData[]>([]);
  const [systemInfo, setSystemInfo] = useState<SystemInfoData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Settings State & Initial snapshot for Unsaved Changes tracking
  const [settings, setSettings] = useState<SettingsState>({
    person_detection_enabled: true,
    vehicle_detection_enabled: true,
    tracking_enabled: true,
    face_detection_enabled: true,
    anpr_enabled: true,
    suspicious_activity_enabled: true,
    detection_conf_threshold: 0.40,
    loitering_threshold_sec: 30.0,
    alert_cooldown_sec: 30.0,
    alert_min_severity: 'INFO',
    alert_sound_enabled: true,
    evidence_capture_enabled: true,
    night_movement_enabled: true,
    night_start_time: '22:00',
    night_end_time: '05:00',
    night_cooldown_sec: 60.0,
  });
  const [initialSettings, setInitialSettings] = useState<SettingsState>(settings);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Toast / Feedback banners
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Camera Management State
  const [showAddCameraModal, setShowAddCameraModal] = useState(false);
  const [newCamName, setNewCamName] = useState('');
  const [newCamSourceType, setNewCamSourceType] = useState('VIDEO_FILE');
  const [newCamSourceUri, setNewCamSourceUri] = useState('./data/demo/sample_cctv.mp4');
  const [newCamEnabled, setNewCamEnabled] = useState(true);

  // Test Connection State
  const [testingProbe, setTestingProbe] = useState(false);
  const [probeResult, setProbeResult] = useState<{ status: string; success: boolean; message: string } | null>(null);

  // Zone Management State
  const [selectedZoneCamId, setSelectedZoneCamId] = useState<number | null>(null);
  const [cameraZones, setCameraZones] = useState<ZoneData[]>([]);
  const [loadingZones, setLoadingZones] = useState(false);
  const [zoneName, setZoneName] = useState('RESTRICTED ZONE A');
  const [zoneType, setZoneType] = useState<'RESTRICTED' | 'MONITORING'>('RESTRICTED');
  const [currentPolygon, setCurrentPolygon] = useState<[number, number][]>([]);
  const [snapshotKey, setSnapshotKey] = useState<number>(Date.now());
  const canvasContainerRef = useRef<HTMLDivElement>(null);

  // Confirmation Modal State
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    actionText: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    actionText: 'Confirm',
    onConfirm: () => {},
  });

  // Track Unsaved Changes
  useEffect(() => {
    const isDifferent = JSON.stringify(settings) !== JSON.stringify(initialSettings);
    setHasUnsavedChanges(isDifferent);
  }, [settings, initialSettings]);

  // Initial Data Fetch
  const fetchAllData = async () => {
    setLoading(true);
    try {
      // 1. Fetch Settings
      const setRes = await fetch('/api/settings');
      if (setRes.ok) {
        const data = await setRes.json();
        setSettings(data);
        setInitialSettings(data);
      }

      // 2. Fetch Cameras
      const camRes = await fetch('/api/cameras');
      if (camRes.ok) {
        const camData: CameraData[] = await camRes.json();
        setCameras(camData);
        setSelectedZoneCamId((prev) => {
          if (prev !== null && camData.some((c) => c.id === prev)) {
            return prev;
          }
          return camData.length > 0 ? camData[0].id : null;
        });
      }

      // 3. Fetch System Info
      const sysRes = await fetch('/api/system/info');
      if (sysRes.ok) {
        const sysData: SystemInfoData = await sysRes.json();
        setSystemInfo(sysData);
      }
    } catch (err) {
      console.error('Error fetching initial settings:', err);
      showToast('error', 'Unable to load configuration from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  // Fetch Camera Zones on camera selection
  useEffect(() => {
    if (selectedZoneCamId) {
      fetchCameraZones(selectedZoneCamId);
      setCurrentPolygon([]);
    }
  }, [selectedZoneCamId]);

  const fetchCameraZones = async (camId: number) => {
    setLoadingZones(true);
    try {
      const res = await fetch(`/api/cameras/${camId}/zones`);
      if (res.ok) {
        const data = await res.json();
        setCameraZones(data.zones || []);
      }
    } catch (err) {
      console.error('Error fetching camera zones:', err);
    } finally {
      setLoadingZones(false);
    }
  };

  const showToast = (type: 'success' | 'error', text: string) => {
    setToastMessage({ type, text });
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  // ---------------------------------------------------------------------------
  // Save Settings
  // ---------------------------------------------------------------------------
  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      const res = await fetch('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });

      if (res.ok) {
        const updated = await res.json();
        setSettings(updated);
        setInitialSettings(updated);
        setHasUnsavedChanges(false);
        showToast('success', '✓ Settings saved and applied to runtime.');
      } else {
        const errData = await res.json();
        showToast('error', errData.detail || 'Settings could not be saved.');
      }
    } catch (err) {
      console.error('Failed to save settings:', err);
      showToast('error', 'Network error: could not persist configuration.');
    } finally {
      setSaving(false);
    }
  };

  const handleDiscardChanges = () => {
    setSettings(initialSettings);
    setHasUnsavedChanges(false);
    showToast('info' as any, 'Unsaved modifications discarded.');
  };

  // ---------------------------------------------------------------------------
  // Reset Settings to Defaults
  // ---------------------------------------------------------------------------
  const handleResetCategory = (category: string) => {
    setConfirmModal({
      isOpen: true,
      title: `Reset ${category.toUpperCase()} Settings?`,
      message: `Are you sure you want to reset ${category} configuration to factory defaults? Any active runtime customizations will be reverted.`,
      actionText: 'Reset Defaults',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        try {
          const res = await fetch('/api/settings/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category }),
          });
          if (res.ok) {
            const data = await res.json();
            setSettings(data.settings);
            setInitialSettings(data.settings);
            setHasUnsavedChanges(false);
            showToast('success', `✓ ${category} settings reset to defaults.`);
          } else {
            showToast('error', 'Failed to reset settings.');
          }
        } catch (err) {
          showToast('error', 'Network error while resetting settings.');
        }
      },
    });
  };

  // ---------------------------------------------------------------------------
  // Connection Tester
  // ---------------------------------------------------------------------------
  const handleProbeConnection = async (sourceType: string, sourceUri: string) => {
    setTestingProbe(true);
    setProbeResult(null);
    try {
      const res = await fetch('/api/cameras/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_type: sourceType, source_uri: sourceUri }),
      });
      if (res.ok) {
        const data = await res.json();
        setProbeResult({
          status: data.status,
          success: data.success,
          message: data.message,
        });
      } else {
        const err = await res.json();
        setProbeResult({
          status: 'FAILED',
          success: false,
          message: err.detail || 'Connection test probe failed.',
        });
      }
    } catch (err) {
      setProbeResult({
        status: 'FAILED',
        success: false,
        message: 'Could not connect to the video stream. Check network reachability.',
      });
    } finally {
      setTestingProbe(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Camera CRUD Operations
  // ---------------------------------------------------------------------------
  const handleCreateCamera = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCamName.trim()) {
      showToast('error', 'Camera name is required.');
      return;
    }
    try {
      const res = await fetch('/api/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newCamName.trim(),
          source_type: newCamSourceType,
          source_uri: newCamSourceUri.trim(),
          enabled: newCamEnabled,
        }),
      });

      if (res.ok) {
        setShowAddCameraModal(false);
        setNewCamName('');
        setNewCamSourceUri('./data/demo/sample_cctv.mp4');
        setProbeResult(null);
        showToast('success', '✓ Camera added successfully.');
        fetchAllData();
      } else {
        const err = await res.json();
        showToast('error', err.detail || 'Failed to add camera.');
      }
    } catch (err) {
      showToast('error', 'Network error creating camera.');
    }
  };

  const handleToggleCamera = async (cam: CameraData) => {
    try {
      const res = await fetch(`/api/cameras/${cam.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !cam.enabled }),
      });
      if (res.ok) {
        showToast('success', `Camera ${cam.enabled ? 'disabled' : 'enabled'}.`);
        fetchAllData();
      }
    } catch (err) {
      showToast('error', 'Failed to update camera state.');
    }
  };

  const handleDeleteCamera = (cam: CameraData) => {
    setConfirmModal({
      isOpen: true,
      title: `Delete Camera '${cam.name}'?`,
      message: `Are you sure you want to delete Camera #${cam.id} (${cam.name})? All associated zones will also be removed.`,
      actionText: 'Delete Camera',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        try {
          const res = await fetch(`/api/cameras/${cam.id}`, { method: 'DELETE' });
          if (res.ok || res.status === 204) {
            showToast('success', `✓ Camera '${cam.name}' deleted.`);
            fetchAllData();
          } else {
            showToast('error', 'Failed to delete camera.');
          }
        } catch (err) {
          showToast('error', 'Network error deleting camera.');
        }
      },
    });
  };

  // ---------------------------------------------------------------------------
  // Zone Canvas Editor Operations
  // ---------------------------------------------------------------------------
  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!canvasContainerRef.current) return;
    const rect = canvasContainerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const normX = Math.max(0.0, Math.min(1.0, parseFloat((clickX / rect.width).toFixed(4))));
    const normY = Math.max(0.0, Math.min(1.0, parseFloat((clickY / rect.height).toFixed(4))));

    setCurrentPolygon((prev) => [...prev, [normX, normY]]);
  };

  const handleSaveZone = async () => {
    if (!selectedZoneCamId) {
      showToast('error', 'Please select a camera first.');
      return;
    }
    if (currentPolygon.length < 3) {
      showToast('error', 'A zone requires at least 3 valid coordinate points.');
      return;
    }
    if (!zoneName.trim()) {
      showToast('error', 'Zone name is required.');
      return;
    }

    try {
      const res = await fetch(`/api/cameras/${selectedZoneCamId}/zones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: zoneName.trim(),
          zone_type: zoneType,
          polygon: currentPolygon,
          enabled: true,
        }),
      });

      if (res.ok) {
        showToast('success', `✓ Zone '${zoneName}' saved.`);
        setCurrentPolygon([]);
        fetchCameraZones(selectedZoneCamId);
        setSnapshotKey(Date.now());
      } else {
        const err = await res.json();
        showToast('error', err.detail || 'Failed to save zone.');
      }
    } catch (err) {
      showToast('error', 'Network error saving zone.');
    }
  };

  const handleToggleZone = async (zone: ZoneData) => {
    try {
      const res = await fetch(`/api/zones/${zone.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !zone.enabled }),
      });
      if (res.ok) {
        showToast('success', `Zone ${zone.enabled ? 'disabled' : 'enabled'}.`);
        if (selectedZoneCamId) fetchCameraZones(selectedZoneCamId);
      }
    } catch (err) {
      showToast('error', 'Failed to toggle zone state.');
    }
  };

  const handleDeleteZone = (zone: ZoneData) => {
    setConfirmModal({
      isOpen: true,
      title: `Delete Zone '${zone.name}'?`,
      message: `Are you sure you want to remove Zone #${zone.id} (${zone.name})? Intrusion detection will no longer evaluate this boundary.`,
      actionText: 'Delete Zone',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        try {
          const res = await fetch(`/api/zones/${zone.id}`, { method: 'DELETE' });
          if (res.ok || res.status === 204) {
            showToast('success', `✓ Zone '${zone.name}' deleted.`);
            if (selectedZoneCamId) fetchCameraZones(selectedZoneCamId);
          } else {
            showToast('error', 'Failed to delete zone.');
          }
        } catch (err) {
          showToast('error', 'Network error deleting zone.');
        }
      },
    });
  };

  return (
    <div className="min-h-screen bg-[#090909] text-white p-6 font-sans flex flex-col">
      {/* Toast Notification */}
      {toastMessage && (
        <div 
          className={`fixed top-5 right-5 z-50 px-4 py-3 rounded border shadow-xl flex items-center gap-3 transition-all duration-300 ${
            toastMessage.type === 'success' 
              ? 'bg-[#151515] border-[#2A2A2A] text-emerald-400 border-l-4 border-l-emerald-500' 
              : 'bg-[#151515] border-[#2A2A2A] text-[#FF1118] border-l-4 border-l-[#FF1118]'
          }`}
        >
          {toastMessage.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertOctagon className="w-5 h-5 text-[#FF1118]" />}
          <span className="text-xs font-mono font-medium">{toastMessage.text}</span>
        </div>
      )}

      {/* Unsaved Changes Banner */}
      {hasUnsavedChanges && (
        <div className="sticky top-0 z-40 mb-6 bg-[#1D1D1D] border border-[#FF1118]/40 px-5 py-3 rounded flex items-center justify-between shadow-2xl backdrop-blur-md">
          <div className="flex items-center gap-3">
            <span className="flex h-2.5 w-2.5 rounded-full bg-[#FF1118] animate-pulse" />
            <span className="text-xs font-mono font-bold tracking-wider text-white uppercase">
              UNSAVED CONFIGURATION CHANGES
            </span>
            <span className="text-xs text-[#A3A3A3] hidden sm:inline font-mono">
              — Modifications will not take effect on runtime workers until saved.
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleDiscardChanges}
              disabled={saving}
              className="px-3 py-1.5 rounded bg-[#151515] hover:bg-[#2A2A2A] text-xs font-mono text-[#A3A3A3] hover:text-white transition-colors border border-[#2A2A2A]"
            >
              DISCARD
            </button>
            <button
              onClick={handleSaveSettings}
              disabled={saving}
              className="px-4 py-1.5 rounded bg-[#FF1118] hover:bg-[#D90E14] text-xs font-mono font-bold text-white transition-colors flex items-center gap-2 shadow-lg shadow-[#FF1118]/20"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              SAVE CHANGES
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#2A2A2A] pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-wider uppercase text-white font-mono">
              SYSTEM SETTINGS & CONFIGURATION
            </h1>
            <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-[#151515] text-[#A3A3A3] border border-[#2A2A2A]">
              ADMIN CONSOLE
            </span>
          </div>
          <p className="text-xs text-[#A3A3A3] font-mono mt-1">
            Authoritative platform parameter management and hardware-synchronized worker control.
          </p>
        </div>
      </div>

      {/* Main Settings Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1">
        {/* Navigation Sidebar */}
        <div className="lg:col-span-3 space-y-1">
          <nav className="bg-[#151515] border border-[#2A2A2A] rounded p-2 space-y-1">
            <button
              onClick={() => setActiveSection('cameras')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-mono transition-all ${
                activeSection === 'cameras'
                  ? 'bg-[#1D1D1D] text-white border-l-2 border-[#FF1118] font-bold shadow-md'
                  : 'text-[#A3A3A3] hover:bg-[#1D1D1D]/50 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <CameraIcon className="w-4 h-4 text-[#A3A3A3]" />
                <span>Cameras</span>
              </div>
              <span className="text-[10px] text-[#A3A3A3] px-1.5 py-0.5 rounded bg-[#090909]">
                {cameras.length}
              </span>
            </button>

            <button
              onClick={() => setActiveSection('analytics')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-mono transition-all ${
                activeSection === 'analytics'
                  ? 'bg-[#1D1D1D] text-white border-l-2 border-[#FF1118] font-bold shadow-md'
                  : 'text-[#A3A3A3] hover:bg-[#1D1D1D]/50 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Cpu className="w-4 h-4 text-[#A3A3A3]" />
                <span>Analytics & AI</span>
              </div>
              <span className="text-[10px] text-emerald-400">● LIVE</span>
            </button>

            <button
              onClick={() => setActiveSection('zones')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-mono transition-all ${
                activeSection === 'zones'
                  ? 'bg-[#1D1D1D] text-white border-l-2 border-[#FF1118] font-bold shadow-md'
                  : 'text-[#A3A3A3] hover:bg-[#1D1D1D]/50 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <ShieldAlert className="w-4 h-4 text-[#A3A3A3]" />
                <span>Virtual Zones</span>
              </div>
            </button>

            <button
              onClick={() => setActiveSection('alerts')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-mono transition-all ${
                activeSection === 'alerts'
                  ? 'bg-[#1D1D1D] text-white border-l-2 border-[#FF1118] font-bold shadow-md'
                  : 'text-[#A3A3A3] hover:bg-[#1D1D1D]/50 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Bell className="w-4 h-4 text-[#A3A3A3]" />
                <span>Alert Rules</span>
              </div>
            </button>

            <button
              onClick={() => setActiveSection('night')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-mono transition-all ${
                activeSection === 'night'
                  ? 'bg-[#1D1D1D] text-white border-l-2 border-[#FF1118] font-bold shadow-md'
                  : 'text-[#A3A3A3] hover:bg-[#1D1D1D]/50 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Moon className="w-4 h-4 text-[#A3A3A3]" />
                <span>Night Schedule</span>
              </div>
              {settings.night_movement_enabled && (
                <span className="text-[10px] text-amber-400 font-mono">ACTIVE</span>
              )}
            </button>

            <button
              onClick={() => setActiveSection('system')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-mono transition-all ${
                activeSection === 'system'
                  ? 'bg-[#1D1D1D] text-white border-l-2 border-[#FF1118] font-bold shadow-md'
                  : 'text-[#A3A3A3] hover:bg-[#1D1D1D]/50 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Server className="w-4 h-4 text-[#A3A3A3]" />
                <span>System Health</span>
              </div>
            </button>
          </nav>
        </div>

        {/* Configuration Panel */}
        <div className="lg:col-span-9 bg-[#151515] border border-[#2A2A2A] rounded p-6">
          {loading ? (
            <div className="py-24 flex flex-col items-center justify-center gap-3 text-[#A3A3A3]">
              <Loader2 className="w-8 h-8 animate-spin text-[#FF1118]" />
              <span className="text-xs font-mono">Loading configuration from database...</span>
            </div>
          ) : (
            <>
              {/* ======================================================= */}
              {/* 1. CAMERAS SECTION                                      */}
              {/* ======================================================= */}
              {activeSection === 'cameras' && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-4">
                    <div>
                      <h2 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                        CAMERA STREAMS & INGESTION SOURCES
                      </h2>
                      <p className="text-xs text-[#A3A3A3] font-mono mt-0.5">
                        Configure physical RTSP CCTV streams, demo MP4 sources, and direct webcams.
                      </p>
                    </div>
                    <button
                      onClick={() => setShowAddCameraModal(true)}
                      className="px-3 py-1.5 rounded bg-[#FF1118] hover:bg-[#D90E14] text-xs font-mono font-bold text-white flex items-center gap-1.5 transition-colors shadow-md"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      ADD CAMERA
                    </button>
                  </div>

                  {cameras.length === 0 ? (
                    <div className="py-16 text-center border border-dashed border-[#2A2A2A] rounded p-6">
                      <CameraIcon className="w-8 h-8 mx-auto text-[#A3A3A3] mb-2" />
                      <p className="text-xs font-mono text-[#A3A3A3]">No cameras configured.</p>
                      <p className="text-xs text-[#A3A3A3]/70 font-mono mt-1">
                        Add a camera source to begin surveillance monitoring.
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-4">
                      {cameras.map((cam) => (
                        <div
                          key={cam.id}
                          className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2.5">
                              <span className="font-mono text-sm font-bold text-white">{cam.name}</span>
                              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-[#090909] text-[#A3A3A3] border border-[#2A2A2A]">
                                {cam.source_type}
                              </span>
                              <span
                                className={`px-2 py-0.5 text-[10px] font-mono rounded ${
                                  cam.status === 'CONNECTED' || cam.status === 'ONLINE' || cam.status === 'PLAYING'
                                    ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800'
                                    : cam.status === 'CONNECTING'
                                    ? 'bg-amber-950/60 text-amber-400 border border-amber-800'
                                    : 'bg-rose-950/60 text-[#FF1118] border border-rose-900'
                                }`}
                              >
                                {cam.status}
                              </span>
                            </div>
                            <div className="text-xs font-mono text-[#A3A3A3]">
                              Source:{' '}
                              <span className="text-[#FFFFFF]/90">
                                {cam.source_uri}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            <button
                              onClick={() => handleToggleCamera(cam)}
                              className={`px-3 py-1.5 rounded text-xs font-mono flex items-center gap-1.5 transition-colors border ${
                                cam.enabled
                                  ? 'bg-[#151515] border-[#2A2A2A] text-white hover:bg-[#2A2A2A]'
                                  : 'bg-emerald-950/40 border-emerald-900 text-emerald-400 hover:bg-emerald-900/40'
                              }`}
                            >
                              {cam.enabled ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                              {cam.enabled ? 'DISABLE' : 'ENABLE'}
                            </button>
                            <button
                              onClick={() => handleDeleteCamera(cam)}
                              className="p-1.5 rounded bg-[#151515] border border-[#2A2A2A] text-rose-400 hover:bg-rose-950/40 hover:border-rose-900 transition-colors"
                              title="Delete camera"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ======================================================= */}
              {/* 2. ANALYTICS SECTION                                    */}
              {/* ======================================================= */}
              {activeSection === 'analytics' && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-4">
                    <div>
                      <h2 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                        AI DETECTORS & INFERENCE ENGINES
                      </h2>
                      <p className="text-xs text-[#A3A3A3] font-mono mt-0.5">
                        Enable or disable inference pipelines and calibrate detection thresholds dynamically.
                      </p>
                    </div>
                    <button
                      onClick={() => handleResetCategory('analytics')}
                      className="px-3 py-1.5 rounded bg-[#1D1D1D] hover:bg-[#2A2A2A] text-xs font-mono text-[#A3A3A3] hover:text-white transition-colors border border-[#2A2A2A] flex items-center gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      RESET TO DEFAULTS
                    </button>
                  </div>

                  {/* Feature Toggles */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Person Detection */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">Person Detection</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Detects humans in active camera streams.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({ ...prev, person_detection_enabled: !prev.person_detection_enabled }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.person_detection_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.person_detection_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* Vehicle Detection */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">Vehicle Detection</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Detects cars, trucks, buses, and motorcycles.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({ ...prev, vehicle_detection_enabled: !prev.vehicle_detection_enabled }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.vehicle_detection_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.vehicle_detection_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* ByteTrack Tracking */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">Multi-Object Tracking (ByteTrack)</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Maintains object track continuity and trajectories.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({ ...prev, tracking_enabled: !prev.tracking_enabled }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.tracking_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.tracking_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* Face Detection */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">Face Detection (YuNet)</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Identifies human facial regions and landmarks.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({ ...prev, face_detection_enabled: !prev.face_detection_enabled }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.face_detection_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.face_detection_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* ANPR */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">License Plate Recognition (ANPR)</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Extracts license plate text from tracked vehicles.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({ ...prev, anpr_enabled: !prev.anpr_enabled }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.anpr_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.anpr_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* Suspicious Activity */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">Suspicious Activity Rules</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Evaluates restricted zone intrusion and loitering.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({ ...prev, suspicious_activity_enabled: !prev.suspicious_activity_enabled }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.suspicious_activity_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.suspicious_activity_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>
                  </div>

                  {/* Threshold Sliders */}
                  <div className="border-t border-[#2A2A2A] pt-6 space-y-6">
                    <h3 className="text-xs font-bold font-mono uppercase text-white tracking-wider">
                      DETECTION & BEHAVIOR THRESHOLDS
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Detection Confidence */}
                      <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-mono font-bold text-white">
                            Detection Confidence Threshold
                          </label>
                          <span className="text-xs font-mono font-bold text-[#FF1118] px-2 py-0.5 rounded bg-[#151515] border border-[#2A2A2A]">
                            {settings.detection_conf_threshold.toFixed(2)}
                          </span>
                        </div>
                        <input
                          type="range"
                          min="0.10"
                          max="0.95"
                          step="0.05"
                          value={settings.detection_conf_threshold}
                          onChange={(e) =>
                            setSettings((prev) => ({
                              ...prev,
                              detection_conf_threshold: parseFloat(e.target.value),
                            }))
                          }
                          className="w-full accent-[#FF1118] bg-[#151515] cursor-pointer"
                        />
                        <div className="flex justify-between text-[10px] font-mono text-[#A3A3A3]">
                          <span>0.10 (High Recall)</span>
                          <span>Default: 0.40</span>
                          <span>0.95 (High Precision)</span>
                        </div>
                      </div>

                      {/* Loitering Duration */}
                      <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-mono font-bold text-white">
                            Loitering Dwell Threshold
                          </label>
                          <span className="text-xs font-mono font-bold text-[#FF1118] px-2 py-0.5 rounded bg-[#151515] border border-[#2A2A2A]">
                            {settings.loitering_threshold_sec} seconds
                          </span>
                        </div>
                        <input
                          type="number"
                          min="1"
                          max="3600"
                          value={settings.loitering_threshold_sec}
                          onChange={(e) =>
                            setSettings((prev) => ({
                              ...prev,
                              loitering_threshold_sec: Math.max(1, Math.min(3600, parseInt(e.target.value) || 1)),
                            }))
                          }
                          className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                        />
                        <p className="text-[10px] font-mono text-[#A3A3A3]">
                          Triggers a LOITERING alert when a tracked subject lingers in a monitoring zone beyond this duration.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ======================================================= */}
              {/* 3. ZONES SECTION                                        */}
              {/* ======================================================= */}
              {activeSection === 'zones' && (
                <div className="space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#2A2A2A] pb-4">
                    <div>
                      <h2 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                        VIRTUAL FENCE & ZONE CONFIGURATION
                      </h2>
                      <p className="text-xs text-[#A3A3A3] font-mono mt-0.5">
                        Define polygon monitoring perimeters and restricted exclusion zones on camera viewpoints.
                      </p>
                    </div>

                    {/* Camera Select */}
                    {cameras.length > 0 && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-[#A3A3A3]">Camera:</span>
                        <select
                          value={selectedZoneCamId || ''}
                          onChange={(e) => setSelectedZoneCamId(parseInt(e.target.value))}
                          className="bg-[#1D1D1D] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                        >
                          {cameras.map((c) => (
                            <option key={c.id} value={c.id}>
                              Camera #{c.id} ({c.name})
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>

                  {/* Coordinate Warning Box */}
                  <div className="bg-[#1D1D1D] border-l-4 border-l-amber-500 border border-[#2A2A2A] p-3 rounded flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                    <div className="text-xs font-mono text-[#A3A3A3]">
                      <span className="font-bold text-white">Camera View Coordinate Notice:</span>{' '}
                      Zone polygon boundaries are normalized relative to this camera angle. If the physical camera is reframed, panned, or rotated, re-evaluate existing zones.
                    </div>
                  </div>

                  {/* Zone Editor Canvas */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2 space-y-3">
                      <div
                        ref={canvasContainerRef}
                        onClick={handleCanvasClick}
                        className="relative w-full aspect-video bg-[#090909] border border-[#2A2A2A] rounded overflow-hidden cursor-crosshair select-none"
                      >
                        {selectedZoneCamId ? (
                          <img
                            src={`/api/cameras/${selectedZoneCamId}/snapshot?t=${snapshotKey}`}
                            alt="Camera Feed Snapshot"
                            className="w-full h-full object-contain pointer-events-none"
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-xs font-mono text-[#A3A3A3]">
                            Select a camera to preview feed.
                          </div>
                        )}

                        {/* Existing Zones SVG Overlay */}
                        <svg className="absolute inset-0 w-full h-full pointer-events-none">
                          {cameraZones.map((z) => {
                            if (!z.polygon || z.polygon.length < 3) return null;
                            const pointsStr = z.polygon
                              .map(([x, y]) => `${x * 100}%,${y * 100}%`)
                              .join(' ');
                            const isRestricted = z.zone_type === 'RESTRICTED';
                            return (
                              <g key={z.id}>
                                <polygon
                                  points={pointsStr}
                                  fill={isRestricted ? 'rgba(255, 17, 24, 0.25)' : 'rgba(234, 179, 8, 0.25)'}
                                  stroke={isRestricted ? '#FF1118' : '#EAB308'}
                                  strokeWidth="2"
                                  strokeDasharray={z.enabled ? 'none' : '4 4'}
                                />
                                {z.polygon[0] && (
                                  <text
                                    x={`${z.polygon[0][0] * 100}%`}
                                    y={`${z.polygon[0][1] * 100}%`}
                                    fill="#FFFFFF"
                                    fontSize="10"
                                    fontFamily="monospace"
                                    dy="-5"
                                  >
                                    {z.name}
                                  </text>
                                )}
                              </g>
                            );
                          })}

                          {/* Current Drawing Polygon */}
                          {currentPolygon.length > 0 && (
                            <g>
                              {currentPolygon.map(([x, y], idx) => (
                                <circle
                                  key={idx}
                                  cx={`${x * 100}%`}
                                  cy={`${y * 100}%`}
                                  r="4"
                                  fill="#FF1118"
                                  stroke="#FFFFFF"
                                  strokeWidth="1.5"
                                />
                              ))}
                              {currentPolygon.length > 1 && (
                                <polyline
                                  points={currentPolygon
                                    .map(([x, y]) => `${x * 100}%,${y * 100}%`)
                                    .join(' ')}
                                  fill="none"
                                  stroke="#FF1118"
                                  strokeWidth="2"
                                  strokeDasharray="4 2"
                                />
                              )}
                              {currentPolygon.length >= 3 && (
                                <polygon
                                  points={currentPolygon
                                    .map(([x, y]) => `${x * 100}%,${y * 100}%`)
                                    .join(' ')}
                                  fill="rgba(255, 17, 24, 0.2)"
                                  stroke="#FF1118"
                                  strokeWidth="2"
                                />
                              )}
                            </g>
                          )}
                        </svg>
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono text-[#A3A3A3]">
                          Vertices: <span className="text-white font-bold">{currentPolygon.length}</span> (min 3 required)
                        </span>
                        <div className="flex gap-2">
                          <button
                            onClick={() => setCurrentPolygon((prev) => prev.slice(0, -1))}
                            disabled={currentPolygon.length === 0}
                            className="px-3 py-1 rounded bg-[#1D1D1D] hover:bg-[#2A2A2A] text-xs font-mono text-[#A3A3A3] hover:text-white transition-colors border border-[#2A2A2A] disabled:opacity-50"
                          >
                            UNDO POINT
                          </button>
                          <button
                            onClick={() => setCurrentPolygon([])}
                            disabled={currentPolygon.length === 0}
                            className="px-3 py-1 rounded bg-[#1D1D1D] hover:bg-[#2A2A2A] text-xs font-mono text-[#A3A3A3] hover:text-white transition-colors border border-[#2A2A2A] disabled:opacity-50"
                          >
                            CLEAR
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Zone Definition Form & List */}
                    <div className="space-y-4">
                      <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-3">
                        <h4 className="text-xs font-bold font-mono uppercase text-white tracking-wider">
                          CREATE NEW ZONE
                        </h4>
                        <div>
                          <label className="text-[11px] font-mono text-[#A3A3A3] block mb-1">Zone Name</label>
                          <input
                            type="text"
                            value={zoneName}
                            onChange={(e) => setZoneName(e.target.value)}
                            placeholder="e.g. North Gate Perimeter"
                            className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                          />
                        </div>

                        <div>
                          <label className="text-[11px] font-mono text-[#A3A3A3] block mb-1">Zone Type</label>
                          <select
                            value={zoneType}
                            onChange={(e) => setZoneType(e.target.value as any)}
                            className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                          >
                            <option value="RESTRICTED">RESTRICTED (Immediate Critical Alert)</option>
                            <option value="MONITORING">MONITORING (Loitering Evaluation)</option>
                          </select>
                        </div>

                        <button
                          onClick={handleSaveZone}
                          disabled={currentPolygon.length < 3}
                          className="w-full py-2 rounded bg-[#FF1118] hover:bg-[#D90E14] text-xs font-mono font-bold text-white transition-colors shadow-md disabled:opacity-40"
                        >
                          SAVE ZONE
                        </button>
                      </div>

                      {/* Configured Zones List */}
                      <div className="space-y-2">
                        <h4 className="text-xs font-bold font-mono uppercase text-[#A3A3A3] tracking-wider">
                          EXISTING ZONES ({cameraZones.length})
                        </h4>
                        {loadingZones ? (
                          <div className="py-4 text-center text-xs font-mono text-[#A3A3A3]">Loading zones...</div>
                        ) : cameraZones.length === 0 ? (
                          <div className="p-3 border border-dashed border-[#2A2A2A] rounded text-center text-xs font-mono text-[#A3A3A3]">
                            No zones configured for this camera.
                          </div>
                        ) : (
                          cameraZones.map((z) => (
                            <div
                              key={z.id}
                              className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-3 flex items-center justify-between"
                            >
                              <div>
                                <div className="font-mono text-xs font-bold text-white">{z.name}</div>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span
                                    className={`px-1.5 py-0.2 text-[9px] font-mono rounded ${
                                      z.zone_type === 'RESTRICTED'
                                        ? 'bg-rose-950/60 text-[#FF1118]'
                                        : 'bg-amber-950/60 text-amber-400'
                                    }`}
                                  >
                                    {z.zone_type}
                                  </span>
                                  <span className="text-[10px] font-mono text-[#A3A3A3]">
                                    {z.enabled ? '● ENABLED' : '○ DISABLED'}
                                  </span>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleToggleZone(z)}
                                  className="text-[10px] font-mono px-2 py-1 rounded bg-[#151515] border border-[#2A2A2A] text-[#A3A3A3] hover:text-white"
                                >
                                  {z.enabled ? 'DISABLE' : 'ENABLE'}
                                </button>
                                <button
                                  onClick={() => handleDeleteZone(z)}
                                  className="p-1 text-rose-400 hover:text-rose-300"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ======================================================= */}
              {/* 4. ALERTS SECTION                                       */}
              {/* ======================================================= */}
              {activeSection === 'alerts' && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-4">
                    <div>
                      <h2 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                        ALERT DELIVERY & OPERATOR COOLDOWN
                      </h2>
                      <p className="text-xs text-[#A3A3A3] font-mono mt-0.5">
                        Configure dispatch cooldowns, audio alarms, and minimum broadcast severity.
                      </p>
                    </div>
                    <button
                      onClick={() => handleResetCategory('alerts')}
                      className="px-3 py-1.5 rounded bg-[#1D1D1D] hover:bg-[#2A2A2A] text-xs font-mono text-[#A3A3A3] hover:text-white transition-colors border border-[#2A2A2A] flex items-center gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      RESET TO DEFAULTS
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Minimum Severity */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-2">
                      <label className="text-xs font-mono font-bold text-white block">
                        Minimum Alert Dispatch Severity
                      </label>
                      <select
                        value={settings.alert_min_severity}
                        onChange={(e) =>
                          setSettings((prev) => ({ ...prev, alert_min_severity: e.target.value }))
                        }
                        className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                      >
                        <option value="INFO">INFO (Broadcast All Events)</option>
                        <option value="WARNING">WARNING (Exclude Info Items)</option>
                        <option value="HIGH">HIGH (Loitering & Intrusions Only)</option>
                        <option value="CRITICAL">CRITICAL (Restricted Intrusions Only)</option>
                      </select>
                      <p className="text-[10px] font-mono text-[#A3A3A3]">
                        Controls the threshold for real-time WebSocket distribution to connected operators.
                      </p>
                    </div>

                    {/* Alert Cooldown */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-mono font-bold text-white">Alert Cooldown Deduplication</label>
                        <span className="text-xs font-mono font-bold text-[#FF1118] px-2 py-0.5 rounded bg-[#151515] border border-[#2A2A2A]">
                          {settings.alert_cooldown_sec}s
                        </span>
                      </div>
                      <input
                        type="number"
                        min="1"
                        max="3600"
                        value={settings.alert_cooldown_sec}
                        onChange={(e) =>
                          setSettings((prev) => ({
                            ...prev,
                            alert_cooldown_sec: Math.max(1, Math.min(3600, parseFloat(e.target.value) || 1)),
                          }))
                        }
                        className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                      />
                      <p className="text-[10px] font-mono text-[#A3A3A3]">
                        Prevents duplicate alerts from flooding the operator for the same ongoing track and zone.
                      </p>
                    </div>

                    {/* Evidence Snapshot Toggle */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">Evidence Snapshot Capture</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Automatically saves JPEG evidence images to disk on alert generation.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({
                            ...prev,
                            evidence_capture_enabled: !prev.evidence_capture_enabled,
                          }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.evidence_capture_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.evidence_capture_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* Sound Alerts */}
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                      <div>
                        <div className="font-mono text-xs font-bold text-white">Sound Alerts</div>
                        <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                          Emits audible audio alarm on critical security incidents.
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSettings((prev) => ({
                            ...prev,
                            alert_sound_enabled: !prev.alert_sound_enabled,
                          }))
                        }
                        className={`w-12 h-6 rounded-full p-1 transition-colors ${
                          settings.alert_sound_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            settings.alert_sound_enabled ? 'translate-x-6' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* ======================================================= */}
              {/* 5. NIGHT SCHEDULE SECTION                               */}
              {/* ======================================================= */}
              {activeSection === 'night' && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-4">
                    <div>
                      <h2 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                        NIGHT-TIME MOVEMENT SURVEILLANCE SCHEDULE
                      </h2>
                      <p className="text-xs text-[#A3A3A3] font-mono mt-0.5">
                        Configure curfew windows for elevated suspicious movement tracking during off-hours.
                      </p>
                    </div>
                    <button
                      onClick={() => handleResetCategory('night')}
                      className="px-3 py-1.5 rounded bg-[#1D1D1D] hover:bg-[#2A2A2A] text-xs font-mono text-[#A3A3A3] hover:text-white transition-colors border border-[#2A2A2A] flex items-center gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      RESET TO DEFAULTS
                    </button>
                  </div>

                  <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 flex items-center justify-between">
                    <div>
                      <div className="font-mono text-xs font-bold text-white">Night Movement Detection</div>
                      <div className="text-[11px] text-[#A3A3A3] font-mono mt-0.5">
                        Triggers NIGHT_MOVEMENT events for any human or vehicle movement during the configured window.
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        setSettings((prev) => ({
                          ...prev,
                          night_movement_enabled: !prev.night_movement_enabled,
                        }))
                      }
                      className={`w-12 h-6 rounded-full p-1 transition-colors ${
                        settings.night_movement_enabled ? 'bg-[#FF1118]' : 'bg-[#2A2A2A]'
                      }`}
                    >
                      <div
                        className={`w-4 h-4 rounded-full bg-white transition-transform ${
                          settings.night_movement_enabled ? 'translate-x-6' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-2">
                      <label className="text-xs font-mono font-bold text-white block">Start Time (HH:MM)</label>
                      <input
                        type="time"
                        value={settings.night_start_time}
                        onChange={(e) =>
                          setSettings((prev) => ({ ...prev, night_start_time: e.target.value }))
                        }
                        className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                      />
                    </div>

                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-2">
                      <label className="text-xs font-mono font-bold text-white block">End Time (HH:MM)</label>
                      <input
                        type="time"
                        value={settings.night_end_time}
                        onChange={(e) =>
                          setSettings((prev) => ({ ...prev, night_end_time: e.target.value }))
                        }
                        className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                      />
                    </div>

                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-2">
                      <label className="text-xs font-mono font-bold text-white block">Deduplication Cooldown (s)</label>
                      <input
                        type="number"
                        min="1"
                        max="3600"
                        value={settings.night_cooldown_sec}
                        onChange={(e) =>
                          setSettings((prev) => ({
                            ...prev,
                            night_cooldown_sec: Math.max(1, parseFloat(e.target.value) || 1),
                          }))
                        }
                        className="w-full bg-[#151515] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                      />
                    </div>
                  </div>

                  <div className="p-3 bg-[#1D1D1D] border border-[#2A2A2A] rounded text-xs font-mono text-[#A3A3A3]">
                    <span className="font-bold text-white">Schedule Behavior:</span> Supports same-day (e.g. 18:00 → 23:00) and midnight-crossing (e.g. 22:00 → 05:00) windows.
                  </div>
                </div>
              )}

              {/* ======================================================= */}
              {/* 6. SYSTEM HEALTH SECTION                                */}
              {/* ======================================================= */}
              {activeSection === 'system' && (
                <div className="space-y-6">
                  <div className="border-b border-[#2A2A2A] pb-4">
                    <h2 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                      SYSTEM METRICS & HARDWARE STATUS
                    </h2>
                    <p className="text-xs text-[#A3A3A3] font-mono mt-0.5">
                      Live operational diagnostics, model versioning, and storage telemetry.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-1">
                      <span className="text-[10px] font-mono text-[#A3A3A3] uppercase">IBVAP Core Version</span>
                      <div className="font-mono text-base font-bold text-white">{systemInfo?.app_version || 'v0.1.0'}</div>
                      <span className="text-[10px] font-mono text-emerald-400">Environment: {systemInfo?.environment || 'Production'}</span>
                    </div>

                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-1">
                      <span className="text-[10px] font-mono text-[#A3A3A3] uppercase">Primary Object Detector</span>
                      <div className="font-mono text-base font-bold text-white">{systemInfo?.detector_model || 'YOLOX-Tiny (ONNX)'}</div>
                      <span className="text-[10px] font-mono text-[#A3A3A3]">Input: 416x416 · Apache-2.0</span>
                    </div>

                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-1">
                      <span className="text-[10px] font-mono text-[#A3A3A3] uppercase">Face Detector</span>
                      <div className="font-mono text-base font-bold text-white">{systemInfo?.face_model || 'YuNet (OpenCV DNN)'}</div>
                      <span className="text-[10px] font-mono text-[#A3A3A3]">5-Point Landmarks · MIT</span>
                    </div>

                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-1">
                      <span className="text-[10px] font-mono text-[#A3A3A3] uppercase">ANPR / OCR Engine</span>
                      <div className="font-mono text-base font-bold text-white">{systemInfo?.ocr_model || 'RapidOCR + PP-OCRv4'}</div>
                      <span className="text-[10px] font-mono text-[#A3A3A3]">Dual-Stage ONNX · Apache-2.0</span>
                    </div>

                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-1">
                      <span className="text-[10px] font-mono text-[#A3A3A3] uppercase">Inference Hardware</span>
                      <div className="font-mono text-base font-bold text-white">{systemInfo?.inference_device || 'CPU / Accelerated'}</div>
                      <span className="text-[10px] font-mono text-emerald-400">● Latency: Nominal</span>
                    </div>

                    <div className="bg-[#1D1D1D] border border-[#2A2A2A] rounded p-4 space-y-1">
                      <span className="text-[10px] font-mono text-[#A3A3A3] uppercase">Database & Storage</span>
                      <div className="font-mono text-base font-bold text-white">{systemInfo?.database_type || 'SQLite (WAL Mode)'}</div>
                      <span className="text-[10px] font-mono text-emerald-400">● Status: {systemInfo?.database_status || 'Connected'}</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ======================================================= */}
      {/* MODAL: ADD CAMERA                                       */}
      {/* ======================================================= */}
      {showAddCameraModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#151515] border border-[#2A2A2A] rounded w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-3">
              <h3 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                REGISTER NEW CAMERA STREAM
              </h3>
              <button
                onClick={() => {
                  setShowAddCameraModal(false);
                  setProbeResult(null);
                }}
                className="text-[#A3A3A3] hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCamera} className="space-y-4">
              <div>
                <label className="text-xs font-mono text-[#A3A3A3] block mb-1">Camera Name</label>
                <input
                  type="text"
                  value={newCamName}
                  onChange={(e) => setNewCamName(e.target.value)}
                  placeholder="e.g. North Gate BOP-03"
                  className="w-full bg-[#1D1D1D] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-mono text-[#A3A3A3] block mb-1">Source Type</label>
                <select
                  value={newCamSourceType}
                  onChange={(e) => setNewCamSourceType(e.target.value)}
                  className="w-full bg-[#1D1D1D] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                >
                  <option value="VIDEO_FILE">VIDEO FILE (MP4 Demo)</option>
                  <option value="RTSP">RTSP (CCTV Network Stream)</option>
                  <option value="WEBCAM">WEBCAM (Direct Hardware Device)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-mono text-[#A3A3A3] block mb-1">Source URI / Path</label>
                <input
                  type="text"
                  value={newCamSourceUri}
                  onChange={(e) => setNewCamSourceUri(e.target.value)}
                  placeholder={
                    newCamSourceType === 'RTSP'
                      ? 'rtsp://user:pass@192.168.1.100:554/stream1'
                      : './data/demo/sample_cctv.mp4'
                  }
                  className="w-full bg-[#1D1D1D] border border-[#2A2A2A] rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-[#FF1118]"
                  required
                />
              </div>

              <div className="flex items-center justify-between py-1">
                <span className="text-xs font-mono text-[#A3A3A3]">Auto-start stream worker immediately:</span>
                <button
                  type="button"
                  onClick={() => setNewCamEnabled(!newCamEnabled)}
                  className={`px-2.5 py-1 rounded text-xs font-mono border ${
                    newCamEnabled
                      ? 'bg-emerald-950/60 border-emerald-800 text-emerald-400'
                      : 'bg-[#1D1D1D] border-[#2A2A2A] text-[#A3A3A3]'
                  }`}
                >
                  {newCamEnabled ? 'ENABLED' : 'DISABLED'}
                </button>
              </div>

              {/* Probe Test Connection Button & Result */}
              <div className="pt-2 border-t border-[#2A2A2A]">
                <div className="flex items-center justify-between mb-2">
                  <button
                    type="button"
                    onClick={() => handleProbeConnection(newCamSourceType, newCamSourceUri)}
                    disabled={testingProbe}
                    className="px-3 py-1.5 rounded bg-[#1D1D1D] hover:bg-[#2A2A2A] text-xs font-mono text-white border border-[#2A2A2A] flex items-center gap-1.5 transition-colors"
                  >
                    {testingProbe ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#FF1118]" /> : <Radio className="w-3.5 h-3.5" />}
                    TEST CONNECTION
                  </button>

                  {probeResult && (
                    <span
                      className={`px-2 py-0.5 text-[10px] font-mono rounded ${
                        probeResult.success
                          ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800'
                          : 'bg-rose-950/60 text-[#FF1118] border border-rose-900'
                      }`}
                    >
                      {probeResult.status}
                    </span>
                  )}
                </div>

                {probeResult && (
                  <p className="text-[11px] font-mono text-[#A3A3A3] bg-[#090909] p-2 rounded border border-[#2A2A2A]">
                    {probeResult.message}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#2A2A2A]">
                <button
                  type="button"
                  onClick={() => setShowAddCameraModal(false)}
                  className="px-4 py-2 rounded bg-[#1D1D1D] text-xs font-mono text-[#A3A3A3] hover:text-white"
                >
                  CANCEL
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-[#FF1118] hover:bg-[#D90E14] text-xs font-mono font-bold text-white"
                >
                  REGISTER CAMERA
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================= */}
      {/* MODAL: DESTRUCTIVE ACTION CONFIRMATION                  */}
      {/* ======================================================= */}
      {confirmModal.isOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#151515] border border-[#2A2A2A] rounded w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-500">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-sm font-bold font-mono uppercase text-white tracking-wider">
                {confirmModal.title}
              </h3>
            </div>
            <p className="text-xs font-mono text-[#A3A3A3] leading-relaxed">
              {confirmModal.message}
            </p>
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#2A2A2A]">
              <button
                onClick={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
                className="px-3 py-1.5 rounded bg-[#1D1D1D] text-xs font-mono text-[#A3A3A3] hover:text-white border border-[#2A2A2A]"
              >
                CANCEL
              </button>
              <button
                onClick={confirmModal.onConfirm}
                className="px-4 py-1.5 rounded bg-[#FF1118] hover:bg-[#D90E14] text-xs font-mono font-bold text-white shadow-lg"
              >
                {confirmModal.actionText}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
