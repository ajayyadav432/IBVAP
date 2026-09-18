import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Link2,
  Lock,
  Search,
  RefreshCw,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  Layers,
  Database,
  Fingerprint,
  FileCheck,
  Clock,
  Camera,
} from 'lucide-react';


interface BlockchainBlock {
  index: number;
  timestamp: string;
  data: {
    image_hash?: string;
    camera_id?: number;
    event_id?: number;
    event_type?: string;
    type?: string;
    message?: string;
    authority?: string;
    [key: string]: any;
  };
  previous_hash: string;
  hash: string;
}

interface LedgerResponse {
  total_blocks: number;
  chain_valid: boolean;
  integrity_message?: string;
  latest_block_hash: string;
  blocks: BlockchainBlock[];
}

interface VerificationResult {
  is_authentic: boolean;
  status: 'AUTHENTIC' | 'TAMPERED' | 'NOT_FOUND';
  image_hash: string;
  block_index?: number;
  block_timestamp?: string;
  camera_id?: number;
  previous_hash?: string;
  block_hash?: string;
  chain_valid: boolean;
  message: string;
}

export const BlockchainLedgerPage: React.FC = () => {
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedBlock, setSelectedBlock] = useState<BlockchainBlock | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'explorer' | 'verifier' | 'logger'>('explorer');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [auditingChain, setAuditingChain] = useState<boolean>(false);
  const [auditMessage, setAuditMessage] = useState<string | null>(null);

  // Verifier State
  const [verifyFile, setVerifyFile] = useState<File | null>(null);
  const [verifyPreviewUrl, setVerifyPreviewUrl] = useState<string | null>(null);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [verifyResult, setVerifyResult] = useState<VerificationResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Logger Form State
  const [logFile, setLogFile] = useState<File | null>(null);
  const [logPreviewUrl, setLogPreviewUrl] = useState<string | null>(null);
  const [logCameraId, setLogCameraId] = useState<number>(1);
  const [logEventType, setLogEventType] = useState<string>('PERIMETER_BREACH');
  const [logSeverity, setLogSeverity] = useState<string>('HIGH');
  const [logReason, setLogReason] = useState<string>('Perimeter sensor line crossed after hours');
  const [loggingAlert, setLoggingAlert] = useState<boolean>(false);
  const [logSuccessMessage, setLogSuccessMessage] = useState<string | null>(null);
  const logFileInputRef = useRef<HTMLInputElement>(null);

  // 1. Fetch live ledger state
  const fetchLedger = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/blockchain/ledger');
      if (res.ok) {
        const data: LedgerResponse = await res.json();
        setLedger(data);
        if (!selectedBlock && data.blocks.length > 0) {
          setSelectedBlock(data.blocks[data.blocks.length - 1]);
        }
      }
    } catch (err) {
      console.error('Failed to load blockchain ledger:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  // 2. Audit Chain Cryptographic Linkage
  const handleAuditChain = async () => {
    setAuditingChain(true);
    setAuditMessage(null);
    try {
      const res = await fetch('/api/blockchain/verify', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setAuditMessage(
          data.chain_valid
            ? `Cryptographic Audit PASSED: ${data.total_blocks} blocks mathematically verified. Zero tampering detected.`
            : `Cryptographic Audit FAILED: ${data.detail}`
        );
        fetchLedger();
      }
    } catch (err) {
      setAuditMessage('Network error during cryptographic chain audit.');
    } finally {
      setAuditingChain(false);
    }
  };

  // 3. Copy to clipboard helper
  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // 4. Handle Verify Upload
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setVerifyFile(f);
      setVerifyPreviewUrl(URL.createObjectURL(f));
      setVerifyResult(null);
    }
  };

  const handleRunVerification = async (fileToVerify: File) => {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const formData = new FormData();
      formData.append('file', fileToVerify);

      const res = await fetch('/api/alerts/verify', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const result: VerificationResult = await res.json();
        setVerifyResult(result);
      } else {
        const err = await res.json();
        setVerifyResult({
          is_authentic: false,
          status: 'TAMPERED',
          image_hash: 'ERROR_COMPUTING_HASH',
          chain_valid: true,
          message: err.detail || 'Verification request failed',
        });
      }
    } catch (err) {
      setVerifyResult({
        is_authentic: false,
        status: 'TAMPERED',
        image_hash: 'NETWORK_ERROR',
        chain_valid: false,
        message: 'Could not connect to verification endpoint.',
      });
    } finally {
      setVerifying(false);
    }
  };

  // 5. Tamper Simulation for Judges
  const handleSimulateTamper = async () => {
    if (!verifyFile) return;
    try {
      const buffer = await verifyFile.arrayBuffer();
      const uint8 = new Uint8Array(buffer);
      // Corrupt byte 10 to demonstrate avalanche effect
      uint8[Math.min(10, uint8.length - 1)] ^= 0xff;
      const corruptedBlob = new Blob([uint8], { type: verifyFile.type });
      const corruptedFile = new File([corruptedBlob], 'tampered_' + verifyFile.name, {
        type: verifyFile.type,
      });
      await handleRunVerification(corruptedFile);
    } catch (err) {
      console.error('Failed to simulate tampering:', err);
    }
  };

  // 6. Handle Manual Alert Logging
  const handleLogSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!logFile) return;
    setLoggingAlert(true);
    setLogSuccessMessage(null);
    try {
      const formData = new FormData();
      formData.append('file', logFile);
      formData.append('camera_id', String(logCameraId));
      formData.append('event_type', logEventType);
      formData.append('severity', logSeverity);
      formData.append('reason', logReason);

      const res = await fetch('/api/alerts/log', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setLogSuccessMessage(
          `Evidence successfully anchored in Block #${data.blockchain_block.index}! Hash: ${data.image_hash.slice(0, 16)}...`
        );
        setLogFile(null);
        setLogPreviewUrl(null);
        fetchLedger();
      } else {
        const err = await res.json();
        alert('Failed to log alert: ' + (err.detail || 'Unknown error'));
      }
    } catch (err) {
      alert('Error communicating with backend');
    } finally {
      setLoggingAlert(false);
    }
  };

  // Filter blocks
  const filteredBlocks = ledger?.blocks.filter((b) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    const matchesIndex = String(b.index).includes(q);
    const matchesHash = b.hash.toLowerCase().includes(q);
    const matchesPrev = b.previous_hash.toLowerCase().includes(q);
    const matchesCam = b.data?.camera_id && String(b.data.camera_id).includes(q);
    const matchesImgHash = b.data?.image_hash && b.data.image_hash.toLowerCase().includes(q);
    const matchesType = b.data?.event_type && b.data.event_type.toLowerCase().includes(q);
    return matchesIndex || matchesHash || matchesPrev || matchesCam || matchesImgHash || matchesType;
  }) || [];

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#0A0D14] text-neutral-100 font-sans">
      {/* Top Telemetry Bar */}
      <div className="border-b border-slate-800 bg-[#0F1420] px-6 py-3 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-950/60 border border-emerald-800/50 text-emerald-400">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-wider uppercase text-white font-mono">
                Chain of Custody • Immutable Evidence Ledger
              </h1>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/50">
                SHA-256 PERMISSIONED
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Off-chain snapshot storage with cryptographic block chaining to mathematically prevent operator tampering.
            </p>
          </div>
        </div>

        {/* Global Chain Health Badges */}
        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 rounded-lg bg-[#141A28] border border-slate-800 flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[11px] text-slate-400">Total Blocks:</span>
            <span className="text-xs font-mono font-bold text-white">
              {ledger ? ledger.total_blocks : '--'}
            </span>
          </div>

          <div
            className={`px-3 py-1.5 rounded-lg border flex items-center gap-2 ${
              ledger?.chain_valid
                ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
                : 'bg-red-950/40 border-red-800/60 text-red-300'
            }`}
          >
            {ledger?.chain_valid ? (
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
            )}
            <span className="text-[11px] font-mono font-bold">
              {ledger?.chain_valid ? 'CHAIN VERIFIED (INTACT)' : 'CHAIN INTEGRITY ALERT'}
            </span>
          </div>

          <button
            onClick={handleAuditChain}
            disabled={auditingChain}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors border border-slate-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${auditingChain ? 'animate-spin' : ''}`} />
            <span>Audit Chain</span>
          </button>
        </div>
      </div>

      {/* Audit Banner if triggered */}
      {auditMessage && (
        <div
          className={`px-6 py-2 text-xs font-mono border-b flex items-center justify-between ${
            auditMessage.includes('PASSED')
              ? 'bg-emerald-950/80 border-emerald-800 text-emerald-200'
              : 'bg-red-950/80 border-red-800 text-red-200'
          }`}
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{auditMessage}</span>
          </div>
          <button
            onClick={() => setAuditMessage(null)}
            className="text-xs underline hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Sub-Tabs Navigation */}
      <div className="border-b border-slate-800 bg-[#0B0F19] px-6 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveSubTab('explorer')}
            className={`px-3 py-1.5 rounded text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 ${
              activeSubTab === 'explorer'
                ? 'bg-slate-800 text-white border border-slate-700'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Ledger Block Explorer</span>
            {ledger && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-900 text-slate-300">
                {ledger.total_blocks}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveSubTab('verifier')}
            className={`px-3 py-1.5 rounded text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 ${
              activeSubTab === 'verifier'
                ? 'bg-slate-800 text-white border border-slate-700'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <Fingerprint className="w-3.5 h-3.5 text-cyan-400" />
            <span>Evidence Verification Lab</span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/50">
              Interactive
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab('logger')}
            className={`px-3 py-1.5 rounded text-xs font-semibold tracking-wide transition-colors flex items-center gap-2 ${
              activeSubTab === 'logger'
                ? 'bg-slate-800 text-white border border-slate-700'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <UploadCloud className="w-3.5 h-3.5 text-amber-400" />
            <span>Anchor New Evidence</span>
          </button>
        </div>

        {activeSubTab === 'explorer' && (
          <div className="relative w-72">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by block #, camera, hash..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#141A28] border border-slate-800 rounded-lg pl-9 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>
        )}
      </div>

      {/* Tab 1: Ledger Explorer */}
      {activeSubTab === 'explorer' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left Block List */}
          <div className="w-96 border-r border-slate-800 flex flex-col bg-[#0B0F19] overflow-hidden shrink-0">
            <div className="p-3 border-b border-slate-800/80 bg-[#0E1322] flex items-center justify-between text-xs text-slate-400 font-mono">
              <span>CHAIN SEQUENCE (GENESIS &rarr; LATEST)</span>
              <span>{filteredBlocks.length} BLOCKS</span>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
              {loading && (
                <div className="py-12 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-cyan-400" />
                  <span>Loading ledger blocks from disk...</span>
                </div>
              )}

              {!loading && filteredBlocks.length === 0 && (
                <div className="py-12 text-center text-slate-500 text-xs">
                  No matching blocks found for &quot;{searchQuery}&quot;.
                </div>
              )}

              {!loading &&
                filteredBlocks.map((block) => {
                  const isSelected = selectedBlock?.index === block.index;
                  const isGenesis = block.index === 0;

                  return (
                    <div
                      key={block.index}
                      onClick={() => setSelectedBlock(block)}
                      className={`p-3 rounded-lg border transition-all cursor-pointer relative group ${
                        isSelected
                          ? 'bg-[#161D2F] border-cyan-500/80 shadow-[0_0_15px_rgba(6,182,212,0.15)]'
                          : 'bg-[#101524] border-slate-800/80 hover:border-slate-700 hover:bg-[#13192B]'
                      }`}
                    >
                      {/* Left indicator line */}
                      <div
                        className={`absolute left-0 top-2 bottom-2 w-1 rounded-r ${
                          isGenesis
                            ? 'bg-amber-500'
                            : isSelected
                            ? 'bg-cyan-400'
                            : 'bg-emerald-500/50 group-hover:bg-emerald-400'
                        }`}
                      />

                      <div className="pl-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded ${
                                isGenesis
                                  ? 'bg-amber-950 text-amber-400 border border-amber-800/40'
                                  : 'bg-slate-800 text-slate-200'
                              }`}
                            >
                              {isGenesis ? 'GENESIS BLOCK #0' : `BLOCK #${block.index}`}
                            </span>
                            {block.data?.event_type && (
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/40">
                                {block.data.event_type}
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {new Date(block.timestamp).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </span>
                        </div>

                        <div className="mt-2 space-y-1 text-[11px] font-mono">
                          <div className="flex items-center justify-between text-slate-400">
                            <span className="text-slate-500">Hash:</span>
                            <span className="text-slate-300">
                              {block.hash.slice(0, 10)}...{block.hash.slice(-8)}
                            </span>
                          </div>

                          {!isGenesis && block.data?.camera_id && (
                            <div className="flex items-center justify-between text-slate-400">
                              <span className="text-slate-500">Source:</span>
                              <span className="text-slate-300 flex items-center gap-1">
                                <Camera className="w-3 h-3 text-slate-500" />
                                Camera #{block.data.camera_id}
                              </span>
                            </div>
                          )}

                          {!isGenesis && block.data?.image_hash && (
                            <div className="flex items-center justify-between text-slate-400">
                              <span className="text-slate-500">Evidence SHA:</span>
                              <span className="text-emerald-400 font-semibold">
                                {block.data.image_hash.slice(0, 8)}...
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Right Detailed Block View */}
          <div className="flex-1 flex flex-col bg-[#070A10] overflow-y-auto p-6">
            {selectedBlock ? (
              <div className="max-w-4xl space-y-6">
                {/* Block Header Card */}
                <div className="p-5 rounded-xl bg-[#0F1422] border border-slate-800 flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="text-lg font-bold text-white font-mono">
                        {selectedBlock.index === 0
                          ? 'Genesis Block #0'
                          : `Block #${selectedBlock.index}`}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800/50 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        Cryptographically Sealed
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      Anchored on: {new Date(selectedBlock.timestamp).toUTCString()} ({selectedBlock.timestamp})
                    </p>
                  </div>

                  <button
                    onClick={() => {
                      if (selectedBlock.data?.image_hash) {
                        handleCopy(selectedBlock.data.image_hash, 'evidence_hash');
                      }
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-300 border border-slate-700 transition-colors"
                  >
                    {copiedHash === 'evidence_hash' ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                    <span>Copy Evidence Hash</span>
                  </button>
                </div>

                {/* Cryptographic Linkage Diagram */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Previous Hash Box */}
                  <div className="p-4 rounded-xl bg-[#0E1320] border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                      <span className="flex items-center gap-1.5">
                        <Link2 className="w-3.5 h-3.5 text-cyan-400" />
                        PREVIOUS BLOCK HASH (PARENT)
                      </span>
                      <button
                        onClick={() => handleCopy(selectedBlock.previous_hash, 'prev_hash')}
                        className="text-slate-400 hover:text-white"
                      >
                        {copiedHash === 'prev_hash' ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                    <div className="p-2.5 rounded bg-[#070A12] border border-slate-800/80 font-mono text-xs text-slate-300 break-all select-all">
                      {selectedBlock.previous_hash}
                    </div>
                    <p className="text-[11px] text-slate-500">
                      {selectedBlock.index === 0
                        ? 'Root genesis anchor with 64 zero-bytes.'
                        : `Cryptographically binds Block #${selectedBlock.index} to Block #${selectedBlock.index - 1}.`}
                    </p>
                  </div>

                  {/* Current Block Hash Box */}
                  <div className="p-4 rounded-xl bg-[#0E1320] border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                      <span className="flex items-center gap-1.5 text-emerald-400">
                        <Fingerprint className="w-3.5 h-3.5" />
                        BLOCK SIGNATURE (SHA-256)
                      </span>
                      <button
                        onClick={() => handleCopy(selectedBlock.hash, 'curr_hash')}
                        className="text-slate-400 hover:text-white"
                      >
                        {copiedHash === 'curr_hash' ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                    <div className="p-2.5 rounded bg-[#070A12] border border-emerald-900/40 font-mono text-xs text-emerald-300 break-all select-all font-semibold">
                      {selectedBlock.hash}
                    </div>
                    <p className="text-[11px] text-slate-500">
                      Calculated from index + timestamp + data payload + previous hash.
                    </p>
                  </div>
                </div>

                {/* Evidence Payload Specification */}
                <div className="p-5 rounded-xl bg-[#0F1422] border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4 text-cyan-400" />
                      <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-white">
                        Immutable Data Payload (Recorded on Ledger)
                      </h3>
                    </div>
                    <span className="text-[11px] text-slate-400 font-mono">
                      Zero Heavy Video Stored on Chain
                    </span>
                  </div>

                  {selectedBlock.index === 0 ? (
                    <div className="p-4 rounded-lg bg-[#070A12] border border-slate-800 text-xs font-mono space-y-2">
                      <div className="text-amber-400 font-bold">GENESIS AUTHORITY RECORD</div>
                      <div className="text-slate-300">
                        Authority: {selectedBlock.data?.authority || 'National Border Security Agency'}
                      </div>
                      <div className="text-slate-400">
                        Message: {selectedBlock.data?.message || 'Chain of Custody Initialized'}
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                      <div className="p-3.5 rounded-lg bg-[#070A12] border border-slate-800 space-y-1.5">
                        <span className="text-slate-500 uppercase text-[10px]">Evidence Image SHA-256</span>
                        <div className="text-cyan-300 font-bold break-all">
                          {selectedBlock.data?.image_hash || 'No image hash recorded'}
                        </div>
                      </div>

                      <div className="p-3.5 rounded-lg bg-[#070A12] border border-slate-800 space-y-1.5">
                        <span className="text-slate-500 uppercase text-[10px]">Associated Event & Camera</span>
                        <div className="text-slate-200">
                          Camera ID: <span className="text-white font-bold">{selectedBlock.data?.camera_id ?? '--'}</span>
                        </div>
                        <div className="text-slate-200">
                          Event Type:{' '}
                          <span className="text-amber-400 font-bold">
                            {selectedBlock.data?.event_type ?? '--'}
                          </span>
                        </div>
                        {selectedBlock.data?.event_id && (
                          <div className="text-slate-400">
                            SQLite Event ID: #{selectedBlock.data.event_id}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Raw Block JSON Inspector */}
                  <div className="space-y-1.5 pt-2">
                    <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">
                      Raw JSON Serialization (Audit Log)
                    </span>
                    <pre className="p-3.5 rounded-lg bg-[#05080E] border border-slate-900 text-[11px] font-mono text-slate-300 overflow-x-auto">
                      {JSON.stringify(selectedBlock, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
                Select a block from the chain on the left to inspect its cryptographic payload.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Evidence Verification Lab */}
      {activeSubTab === 'verifier' && (
        <div className="flex-1 flex overflow-y-auto p-8 justify-center bg-[#070A10]">
          <div className="max-w-3xl w-full space-y-6">
            {/* Header Description */}
            <div className="p-5 rounded-xl bg-[#0F1422] border border-slate-800 space-y-2">
              <div className="flex items-center gap-2.5">
                <Fingerprint className="w-5 h-5 text-cyan-400" />
                <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-white">
                  Mathematical Evidence Tamper Verification
                </h2>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Upload any surveillance snapshot to verify its mathematical chain-of-custody.
                The system computes its SHA-256 hash in real time and queries the permissioned blockchain ledger
                to verify that the evidence has not been edited, photoshopped, or replaced by a rogue operator.
              </p>
            </div>

            {/* Dropzone Card */}
            <div className="p-6 rounded-xl bg-[#0E1320] border border-slate-800 space-y-4">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept="image/*"
                className="hidden"
              />

              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-cyan-500 rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-colors bg-[#080C14] hover:bg-[#0C121E]"
              >
                {verifyPreviewUrl ? (
                  <div className="space-y-3 flex flex-col items-center">
                    <img
                      src={verifyPreviewUrl}
                      alt="Upload Preview"
                      className="max-h-56 rounded-lg border border-slate-700 object-contain shadow-md"
                    />
                    <div className="text-xs text-slate-300 font-mono flex items-center gap-2">
                      <FileCheck className="w-4 h-4 text-cyan-400" />
                      <span>{verifyFile?.name}</span> ({(verifyFile!.size / 1024).toFixed(1)} KB)
                    </div>
                    <span className="text-[11px] text-cyan-400 underline">
                      Click to choose a different snapshot
                    </span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3 text-center">
                    <div className="p-4 rounded-full bg-slate-800/80 text-slate-300">
                      <UploadCloud className="w-7 h-7" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">
                        Click or drag &amp; drop surveillance evidence snapshot
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1">
                        Supports JPEG, PNG, WEBP files captured from platform cameras
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {verifyFile && (
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => handleRunVerification(verifyFile)}
                    disabled={verifying}
                    className="flex-1 py-2.5 px-4 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-bold tracking-wider uppercase transition-colors shadow-lg shadow-cyan-900/30 flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <Fingerprint className={`w-4 h-4 ${verifying ? 'animate-spin' : ''}`} />
                    <span>{verifying ? 'Computing SHA-256 & Auditing Ledger...' : 'Verify Cryptographic Authenticity'}</span>
                  </button>

                  <button
                    onClick={handleSimulateTamper}
                    disabled={verifying}
                    title="Alters 1 byte of the image and re-runs verification to demonstrate mathematical tamper detection to judges"
                    className="py-2.5 px-4 rounded-lg bg-red-950 hover:bg-red-900 text-red-200 border border-red-800 text-xs font-mono font-semibold transition-colors flex items-center gap-2 disabled:opacity-50"
                  >
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                    <span>Simulate 1-Byte Tampering</span>
                  </button>
                </div>
              )}
            </div>

            {/* Verification Result Certificate */}
            {verifyResult && (
              <div
                className={`p-6 rounded-xl border transition-all ${
                  verifyResult.is_authentic
                    ? 'bg-emerald-950/30 border-emerald-800/80 shadow-[0_0_20px_rgba(16,185,129,0.15)]'
                    : 'bg-red-950/30 border-red-800/80 shadow-[0_0_20px_rgba(239,68,68,0.15)]'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div
                    className={`p-3 rounded-xl shrink-0 ${
                      verifyResult.is_authentic
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-700'
                        : 'bg-red-950 text-red-400 border border-red-700'
                    }`}
                  >
                    {verifyResult.is_authentic ? (
                      <ShieldCheck className="w-8 h-8" />
                    ) : (
                      <ShieldAlert className="w-8 h-8" />
                    )}
                  </div>

                  <div className="space-y-3 flex-1">
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                            verifyResult.is_authentic
                              ? 'bg-emerald-900/60 text-emerald-300'
                              : 'bg-red-900/60 text-red-300'
                          }`}
                        >
                          VERDICT: {verifyResult.status}
                        </span>
                        {verifyResult.block_index !== undefined && verifyResult.block_index !== null && (
                          <span className="text-xs font-mono text-slate-400">
                            Anchored in Block #{verifyResult.block_index}
                          </span>
                        )}
                      </div>
                      <h3 className="text-base font-bold text-white mt-1">
                        {verifyResult.is_authentic
                          ? 'Cryptographic Authenticity 100% Confirmed'
                          : 'Evidence Tampering / Integrity Breach Detected!'}
                      </h3>
                      <p className="text-xs text-slate-300 mt-1">{verifyResult.message}</p>
                    </div>

                    <div className="p-3 rounded-lg bg-[#070A12] border border-slate-800/80 space-y-1.5 font-mono text-xs">
                      <div className="flex items-center justify-between text-slate-400">
                        <span>Calculated SHA-256 Digest:</span>
                        <span className="text-cyan-400 font-semibold break-all text-[11px]">
                          {verifyResult.image_hash}
                        </span>
                      </div>
                      {verifyResult.block_timestamp && (
                        <div className="flex items-center justify-between text-slate-400">
                          <span>Ledger Anchor Timestamp:</span>
                          <span className="text-slate-200 text-[11px]">
                            {verifyResult.block_timestamp}
                          </span>
                        </div>
                      )}
                      {verifyResult.block_hash && (
                        <div className="flex items-center justify-between text-slate-400">
                          <span>Containing Block Hash:</span>
                          <span className="text-slate-300 text-[11px]">
                            {verifyResult.block_hash.slice(0, 20)}...
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Anchor New Evidence */}
      {activeSubTab === 'logger' && (
        <div className="flex-1 flex overflow-y-auto p-8 justify-center bg-[#070A10]">
          <form
            onSubmit={handleLogSubmit}
            className="max-w-2xl w-full space-y-6 bg-[#0E1320] p-6 rounded-xl border border-slate-800"
          >
            <div className="border-b border-slate-800 pb-4">
              <div className="flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-amber-400" />
                <h2 className="text-sm font-bold uppercase tracking-wider font-mono text-white">
                  Anchor New Surveillance Evidence Snapshot
                </h2>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Directly test the <code>POST /api/alerts/log</code> endpoint. Saves raw snapshot to disk, records event in SQLite,
                and writes ONLY the resulting SHA-256 hash to the permissioned blockchain ledger.
              </p>
            </div>

            {logSuccessMessage && (
              <div className="p-4 rounded-lg bg-emerald-950/70 border border-emerald-800 text-emerald-200 text-xs font-mono flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{logSuccessMessage}</span>
              </div>
            )}

            {/* File Upload Field */}
            <div className="space-y-2">
              <label className="text-xs font-mono text-slate-400 block uppercase">
                1. Evidence Snapshot Image *
              </label>
              <input
                type="file"
                ref={logFileInputRef}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    const f = e.target.files[0];
                    setLogFile(f);
                    setLogPreviewUrl(URL.createObjectURL(f));
                  }
                }}
                accept="image/*"
                className="hidden"
              />

              <div
                onClick={() => logFileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-amber-500 rounded-lg p-6 flex flex-col items-center justify-center cursor-pointer transition-colors bg-[#090D18]"
              >
                {logPreviewUrl ? (
                  <div className="flex items-center gap-4">
                    <img
                      src={logPreviewUrl}
                      alt="Preview"
                      className="w-24 h-24 object-cover rounded-lg border border-slate-700"
                    />
                    <div className="text-xs font-mono text-slate-300">
                      <div>{logFile?.name}</div>
                      <div className="text-slate-500">{(logFile!.size / 1024).toFixed(1)} KB</div>
                      <span className="text-amber-400 text-[11px] underline mt-1 inline-block">
                        Change image
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center text-xs text-slate-400">
                    <UploadCloud className="w-6 h-6 text-slate-500 mx-auto mb-2" />
                    <span>Select snapshot file to anchor into blockchain</span>
                  </div>
                )}
              </div>
            </div>

            {/* Form Fields Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-mono text-slate-400 block uppercase">
                  Camera Source ID
                </label>
                <select
                  value={logCameraId}
                  onChange={(e) => setLogCameraId(Number(e.target.value))}
                  className="w-full bg-[#141A28] border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                >
                  <option value={1}>Camera #1 - BOP-03 North Perimeter</option>
                  <option value={2}>Camera #2 - Sector 4 Fence Line</option>
                  <option value={3}>Camera #3 - Thermal Night Post</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-mono text-slate-400 block uppercase">
                  Event Classification
                </label>
                <select
                  value={logEventType}
                  onChange={(e) => setLogEventType(e.target.value)}
                  className="w-full bg-[#141A28] border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                >
                  <option value="PERIMETER_BREACH">PERIMETER_BREACH</option>
                  <option value="ZONE_INTRUSION">ZONE_INTRUSION</option>
                  <option value="LOITERING">LOITERING</option>
                  <option value="NIGHT_MOVEMENT">NIGHT_MOVEMENT</option>
                  <option value="UNAUTHORIZED_CROSSING">UNAUTHORIZED_CROSSING</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-mono text-slate-400 block uppercase">Severity</label>
                <select
                  value={logSeverity}
                  onChange={(e) => setLogSeverity(e.target.value)}
                  className="w-full bg-[#141A28] border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                >
                  <option value="CRITICAL">CRITICAL</option>
                  <option value="HIGH">HIGH</option>
                  <option value="WARNING">WARNING</option>
                  <option value="INFO">INFO</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-mono text-slate-400 block uppercase">
                  Detection Summary
                </label>
                <input
                  type="text"
                  value={logReason}
                  onChange={(e) => setLogReason(e.target.value)}
                  className="w-full bg-[#141A28] border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={!logFile || loggingAlert}
              className="w-full py-3 px-4 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-mono text-xs font-bold uppercase tracking-wider transition-colors disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-amber-900/30"
            >
              <Lock className={`w-4 h-4 ${loggingAlert ? 'animate-spin' : ''}`} />
              <span>{loggingAlert ? 'Generating Hash & Mining Block...' : 'Anchor Evidence into Private Blockchain'}</span>
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
