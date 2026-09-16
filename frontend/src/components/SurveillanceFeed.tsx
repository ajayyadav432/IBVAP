import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Maximize2, Minimize2, Video, AlertCircle, RefreshCw, Loader2 } from 'lucide-react';

interface CameraInfo {
  id: number;
  name: string;
  status?: string;
  enabled?: boolean;
  resolution?: string;
  measured_fps?: number;
  inference_latency_ms?: number;
  inference_device?: string;
}

interface SurveillanceFeedProps {
  camera: CameraInfo | null | undefined;
  className?: string;
  showTopHUD?: boolean;
  aspectRatioClass?: string;
}

export const SurveillanceFeed: React.FC<SurveillanceFeedProps> = ({
  camera,
  className = '',
  showTopHUD = true,
  aspectRatioClass = 'aspect-video',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [streamState, setStreamState] = useState<'LOADING' | 'STREAMING' | 'OFFLINE' | 'ERROR'>('LOADING');
  const [retryNonce, setRetryNonce] = useState<number>(Date.now());
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Handle stream state when camera changes
  useEffect(() => {
    if (!camera || camera.enabled === false || camera.status === 'OFFLINE') {
      setStreamState('OFFLINE');
    } else {
      setStreamState('LOADING');
      setErrorMessage('');
      setRetryNonce(Date.now());
    }
  }, [camera?.id, camera?.enabled, camera?.status]);

  // Synchronize Fullscreen API state
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isCurrentElemFullscreen = !!(
        document.fullscreenElement &&
        containerRef.current &&
        document.fullscreenElement === containerRef.current
      );
      setIsFullscreen(isCurrentElemFullscreen);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
    };
  }, []);

  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return;

    try {
      if (!document.fullscreenElement) {
        if (containerRef.current.requestFullscreen) {
          await containerRef.current.requestFullscreen();
        } else if ((containerRef.current as any).webkitRequestFullscreen) {
          await (containerRef.current as any).webkitRequestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if ((document as any).webkitExitFullscreen) {
          await (document as any).webkitExitFullscreen();
        }
      }
    } catch (err) {
      console.error('Fullscreen toggle failed:', err);
    }
  }, []);

  const handleImageLoad = () => {
    setStreamState('STREAMING');
    setErrorMessage('');
  };

  const handleImageError = () => {
    if (camera?.status === 'OFFLINE' || !camera?.enabled) {
      setStreamState('OFFLINE');
    } else {
      setStreamState('ERROR');
      setErrorMessage('Unable to load live surveillance stream. Camera may be reconnecting or offline.');
    }
  };

  const handleRetry = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setStreamState('LOADING');
    setErrorMessage('');
    setRetryNonce(Date.now());
  };

  if (!camera) {
    return (
      <div className={`relative ${aspectRatioClass} bg-black flex flex-col items-center justify-center text-secondary border border-border rounded ${className}`}>
        <Video className="w-10 h-10 opacity-30 mb-2" />
        <p className="text-xs font-mono">No camera stream selected</p>
      </div>
    );
  }

  const isOffline = streamState === 'OFFLINE' || !camera.enabled || camera.status === 'OFFLINE';
  const streamUrl = `/api/cameras/${camera.id}/stream?t=${retryNonce}`;

  return (
    <div
      ref={containerRef}
      className={`relative bg-black flex items-center justify-center overflow-hidden select-none ${
        isFullscreen ? 'w-screen h-screen fixed inset-0 z-[9999] bg-black' : `${aspectRatioClass} rounded ${className}`
      }`}
    >
      {/* 1. Active Stream Image */}
      {!isOffline && (
        <img
          key={`${camera.id}-${retryNonce}`}
          src={streamUrl}
          alt={camera.name}
          className={`w-full h-full object-contain transition-opacity duration-300 ${
            streamState === 'STREAMING' ? 'opacity-100' : 'opacity-0'
          }`}
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
      )}

      {/* 2. LOADING Overlay */}
      {streamState === 'LOADING' && !isOffline && (
        <div className="absolute inset-0 bg-black/90 flex flex-col items-center justify-center gap-3 z-10">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <div className="text-center font-mono">
            <p className="text-xs font-bold text-primary tracking-wide">CONNECTING TO CAMERA #{camera.id}...</p>
            <p className="text-[10px] text-secondary mt-1">{camera.name}</p>
          </div>
        </div>
      )}

      {/* 3. ERROR Overlay */}
      {streamState === 'ERROR' && !isOffline && (
        <div className="absolute inset-0 bg-black/90 flex flex-col items-center justify-center gap-3 z-10 p-6 text-center">
          <AlertCircle className="w-8 h-8 text-amber-400 animate-pulse" />
          <div className="font-mono max-w-sm">
            <p className="text-xs font-bold text-amber-400">UNABLE TO LOAD LIVE FEED</p>
            <p className="text-[10px] text-secondary mt-1">{errorMessage}</p>
          </div>
          <button
            onClick={handleRetry}
            className="mt-2 flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface hover:bg-elevated text-primary text-xs font-mono border border-border transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5 text-accent" />
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* 4. OFFLINE Overlay */}
      {isOffline && (
        <div className="absolute inset-0 bg-black/95 flex flex-col items-center justify-center gap-2.5 z-10 text-center font-mono">
          <Video className="w-10 h-10 text-secondary opacity-30" />
          <p className="text-xs font-bold text-secondary">CAMERA OFFLINE</p>
          <p className="text-[10px] text-[#737373]">Stream feed is disabled or source is disconnected</p>
        </div>
      )}

      {/* 5. Top Left HUD Overlay */}
      {showTopHUD && (
        <div className="absolute top-3 left-3 flex items-center gap-2 bg-black/80 px-2.5 py-1 rounded border border-border text-[10px] font-mono text-white backdrop-blur-sm z-20">
          <span className={`w-1.5 h-1.5 rounded-full ${streamState === 'STREAMING' ? 'bg-accent animate-ping' : 'bg-secondary'}`} />
          <span>
            {streamState === 'STREAMING' ? 'REC • ' : ''}CH-0{camera.id} • {camera.name}
          </span>
        </div>
      )}

      {/* 6. Top Right Controls (FPS & Fullscreen Toggle) */}
      <div className="absolute top-3 right-3 flex items-center gap-2 z-20">
        {showTopHUD && (
          <div className="bg-black/80 px-2.5 py-1 rounded border border-border text-[10px] font-mono text-secondary backdrop-blur-sm">
            {camera.resolution || '720p'} @ {camera.measured_fps?.toFixed(1) || '0.0'} FPS
          </div>
        )}

        {/* Fullscreen Toggle Button */}
        <button
          type="button"
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen (ESC)' : 'Fullscreen View'}
          className="bg-black/80 hover:bg-elevated/90 p-1.5 rounded border border-border text-primary hover:text-accent transition-colors backdrop-blur-sm flex items-center justify-center shadow-lg"
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      {/* 7. Bottom Fullscreen Exit Helper Bar (visible only in fullscreen) */}
      {isFullscreen && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/80 px-3 py-1 rounded-full border border-border text-[10px] font-mono text-secondary backdrop-blur-sm z-20 flex items-center gap-2">
          <span>Press <kbd className="px-1.5 py-0.5 rounded bg-surface border border-border text-primary">ESC</kbd> or click</span>
          <button onClick={toggleFullscreen} className="text-accent underline font-bold">Exit Fullscreen</button>
        </div>
      )}
    </div>
  );
};
