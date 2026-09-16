import { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { Navigation, NavTab } from './components/Navigation';
import { DashboardPage, RealtimeAlertItem } from './pages/DashboardPage';
import { CamerasPage } from './pages/CamerasPage';
import { EventsPage } from './pages/EventsPage';
import { ZonesPage } from './pages/ZonesPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { SettingsPage } from './pages/SettingsPage';

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [settingsSubtab, setSettingsSubtab] = useState<string>('cameras');
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [wsStatus, setWsStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting');
  const [realtimeAlerts, setRealtimeAlerts] = useState<RealtimeAlertItem[]>([]);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);

  // 1. Core API Health Check Polling
  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'ok') {
            setApiStatus('online');
            return;
          }
        }
        setApiStatus('offline');
      } catch (err) {
        setApiStatus('offline');
      }
    };

    checkApiHealth();
    const interval = setInterval(checkApiHealth, 8000);
    return () => clearInterval(interval);
  }, []);

  // 2. Synthesized Audio Beep for High/Critical Alerts
  const playAlertSound = () => {
    if (!soundEnabled) return;
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(880, ctx.currentTime); // A5 note
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.18); // sweep down

      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.18);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.2);
    } catch (e) {
      // Audio context might be restricted before user gesture
    }
  };

  // 3. Central WebSocket Event Listener
  useEffect(() => {
    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/api/ws/events`;

      setWsStatus('connecting');
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus('connected');
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.event_id && msg.event_type) {
            const newAlert: RealtimeAlertItem = {
              event_id: msg.event_id,
              timestamp: msg.timestamp || new Date().toISOString(),
              camera_id: msg.camera_id,
              camera_name: msg.camera_name,
              event_type: msg.event_type,
              severity: msg.severity || 'HIGH',
              object_type: msg.object_type,
              track_id: msg.track_id,
              zone_id: msg.zone_id,
              zone_name: msg.zone_name,
              confidence: msg.confidence,
              reason: msg.reason || 'Automated rule triggered.',
              evidence_path: msg.evidence_path,
              status: msg.status || 'NEW',
            };

            setRealtimeAlerts((prev) => [newAlert, ...prev.slice(0, 49)]);

            if (msg.severity === 'CRITICAL' || msg.severity === 'HIGH') {
              playAlertSound();
            }
          }
        } catch (err) {
          console.error('Error parsing WS event:', err);
        }
      };

      ws.onerror = () => {
        setWsStatus('disconnected');
      };

      ws.onclose = () => {
        setWsStatus('disconnected');
        // Reconnect after 4s
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 4000);
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [soundEnabled]);

  const activeAlertsCount = realtimeAlerts.filter(
    (a) => a.severity === 'CRITICAL' || a.severity === 'HIGH'
  ).length;

  const handleNavigateToSettings = (subtab: string = 'cameras') => {
    setSettingsSubtab(subtab);
    setActiveTab('settings');
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-primary">
      {/* Top Universal Header */}
      <Header
        apiStatus={apiStatus}
        wsStatus={wsStatus}
        activeAlertsCount={activeAlertsCount}
        soundEnabled={soundEnabled}
        onToggleSound={() => setSoundEnabled((prev) => !prev)}
      />

      {/* Main Layout Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Persistent Navigation */}
        <Navigation
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          activeAlertsCount={activeAlertsCount}
        />

        {/* Dynamic Page Content */}
        <main className="flex-1 flex flex-col overflow-hidden bg-background">
          {activeTab === 'dashboard' && (
            <DashboardPage
              realtimeAlerts={realtimeAlerts}
              onNavigateToTab={(tab) => setActiveTab(tab as NavTab)}
            />
          )}

          {activeTab === 'cameras' && <CamerasPage />}

          {activeTab === 'events' && <EventsPage />}

          {activeTab === 'zones' && (
            <ZonesPage onNavigateToSettings={handleNavigateToSettings} />
          )}

          {activeTab === 'analytics' && (
            <AnalyticsPage onNavigateToSettings={handleNavigateToSettings} />
          )}

          {activeTab === 'settings' && (
            <SettingsPage initialSubtab={settingsSubtab} />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
