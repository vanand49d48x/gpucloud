'use client';

import React, { useState, useEffect } from 'react';
import { X, HardDrive, Plus, RefreshCw, Server, Cpu, HardDrive as HardDriveIcon } from 'lucide-react';
import { clientLogger as logger } from '../utils/logger';

interface VolumeInfo {
  volume_id: string;
  size_gb: number;
  type?: string;
  iops?: number;
  throughput?: number;
  device_name?: string;
}

interface PodConfig {
  pod_id: number;
  status: string;
  instance_id: string | null;
  instance_type?: string | null;
  public_ip?: string | null;
  gpu_type?: string | null;
  vram_gb?: number | null;
  volumes?: VolumeInfo[];
}

interface InstanceConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  podId: number;
  token?: string;
}

export default function InstanceConfigModal({ isOpen, onClose, podId, token }: InstanceConfigModalProps) {
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<PodConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanding, setExpanding] = useState(false);
  const [mode, setMode] = useState<'additional' | 'absolute'>('additional');
  const [additionalGb, setAdditionalGb] = useState<number>(10);
  const [newSizeGb, setNewSizeGb] = useState<number>(50);
  const [lastMessage, setLastMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    fetchConfig();
  }, [isOpen, podId]);

  const fetchConfig = async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/v1/pods/${podId}/config`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Failed to load config (${resp.status}): ${text}`);
      }
      const data = await resp.json();
      setConfig(data);
      logger.info('Instance config loaded', { podId, volumes: data.volumes?.length || 0 });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      logger.error('Error loading instance config', { podId, error: msg });
    } finally {
      setLoading(false);
    }
  };

  const submitExpand = async () => {
    if (!token) return;
    
    setExpanding(true);
    setLastMessage('');
    setError(''); // Clear any previous errors
    
    try {
      const response = await fetch(`/v1/pods/${podId}/storage/expand`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          mode: mode,
          additional_gb: mode === 'additional' ? additionalGb : undefined,
          new_size_gb: mode === 'absolute' ? newSizeGb : undefined
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
        setError(`Failed to expand storage: ${errorMessage}`);
        return;
      }

      const result = await response.json();
      setLastMessage(result.message || 'Storage expansion requested successfully!');
      
      // Reset form
      if (mode === 'additional') {
        setAdditionalGb(10);
      } else {
        setNewSizeGb(50);
      }
      
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`Failed to expand storage: ${errorMsg}`);
    } finally {
      setExpanding(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50 p-4">
      <div className="bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-600 rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-600 bg-gradient-to-r from-gray-800 to-gray-700">
          <div className="flex items-center space-x-4">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <HardDrive className="w-7 h-7 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Instance Configuration</h2>
              <p className="text-sm text-blue-300 font-medium">Pod {podId}</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-all duration-200" 
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(90vh-120px)]">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="flex items-center space-x-3 text-blue-300">
                <RefreshCw className="w-6 h-6 animate-spin" />
                <span className="text-lg">Loading configuration...</span>
              </div>
            </div>
          )}

          {config && (
            <>
              {/* Instance Details Cards */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-800/50 border border-gray-600 rounded-lg p-5">
                  <h3 className="text-white font-semibold mb-4 flex items-center space-x-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                    <span>Instance Details</span>
                  </h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center py-2 border-b border-gray-600/50">
                      <span className="text-gray-300">Status</span>
                      <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                        config.status === 'running' ? 'bg-green-900/30 text-green-300' :
                        config.status === 'stopped' ? 'bg-yellow-900/30 text-yellow-300' :
                        config.status === 'starting' ? 'bg-blue-900/30 text-blue-300' :
                        'bg-gray-700/50 text-gray-300'
                      }`}>
                        {config.status}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-gray-600/50">
                      <span className="text-gray-300">Instance ID</span>
                      <span className="text-white font-mono text-sm">{config.instance_id || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-gray-600/50">
                      <span className="text-gray-300">Instance Type</span>
                      <span className="text-white font-medium">{config.instance_type || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center py-2">
                      <span className="text-gray-300">Public IP</span>
                      <span className="text-white font-mono text-sm">{config.public_ip || 'N/A'}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-800/50 border border-gray-600 rounded-lg p-5">
                  <h3 className="text-white font-semibold mb-4 flex items-center space-x-2">
                    <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                    <span>Hardware Specs</span>
                  </h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center py-2 border-b border-gray-600/50">
                      <span className="text-gray-300">GPU Type</span>
                      <span className="text-white font-medium">{config.gpu_type || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center py-2">
                      <span className="text-gray-300">VRAM</span>
                      <span className="text-white font-medium">{config.vram_gb ? `${config.vram_gb} GB` : 'N/A'}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Volumes Section */}
              <div className="bg-gray-800/50 border border-gray-600 rounded-lg p-5">
                <h3 className="text-white font-semibold mb-4 flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span>Storage Volumes</span>
                </h3>
                {(!config.volumes || config.volumes.length === 0) && (
                  <div className="text-gray-400 text-center py-8">No volumes found</div>
                )}
                {config.volumes && config.volumes.length > 0 && (
                  <div className="space-y-3">
                    {config.volumes.map((v) => (
                      <div key={v.volume_id} className="bg-gray-700/50 border border-gray-500/50 rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <div className="flex-1">
                            <div className="flex items-center space-x-3 mb-2">
                              <HardDrive className="w-5 h-5 text-green-400" />
                              <span className="text-white font-medium">{v.device_name || 'Root Volume'}</span>
                              <span className="text-green-400 font-mono text-sm">{v.volume_id}</span>
                            </div>
                            <div className="grid grid-cols-3 gap-4 text-xs text-gray-400">
                              <div>Type: <span className="text-gray-300">{v.type || 'n/a'}</span></div>
                              <div>IOPS: <span className="text-gray-300">{v.iops ?? 'n/a'}</span></div>
                              <div>Throughput: <span className="text-gray-300">{v.throughput ?? 'n/a'}</span></div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-2xl font-bold text-green-400">{v.size_gb}</div>
                            <div className="text-xs text-gray-400">GB</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Expand Storage Section */}
              <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 border border-blue-500/30 rounded-xl p-6">
                <div className="flex items-center space-x-3 mb-4">
                  <div className="p-2 bg-blue-500/20 rounded-lg">
                    <HardDrive className="w-5 h-5 text-blue-300" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-blue-100">Expand Storage</h3>
                    <p className="text-sm text-blue-300">Increase your pod's storage capacity</p>
                  </div>
                </div>

                {/* Error Display - Now inside the Expand Storage section */}
                {error && (
                  <div className="mb-4 bg-red-900/30 border border-red-500/50 rounded-lg p-4 text-red-300 text-sm">
                    <div className="flex items-center space-x-2 mb-2">
                      <div className="w-2 h-2 bg-red-500 rounded-full animate-ping"></div>
                      <span className="font-medium">Storage Expansion Failed</span>
                    </div>
                    <p className="text-red-200 mb-2">{error}</p>
                    <div className="text-xs text-red-300">
                      <p className="font-medium mb-1">Common reasons:</p>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Volume was modified recently (AWS requires 6 hours between modifications)</li>
                        <li>Volume is currently being optimized by AWS</li>
                        <li>Insufficient permissions or AWS service issues</li>
                      </ul>
                    </div>
                  </div>
                )}

                {/* Automated Storage Management Info */}
                <div className="mb-4 bg-green-900/20 border border-green-500/30 rounded-lg p-4">
                  <div className="flex items-start space-x-3">
                    <div className="w-2 h-2 bg-green-400 rounded-full mt-2"></div>
                    <div className="text-green-200 text-sm">
                      <p className="font-medium mb-1">✅ Fully Automated Storage Management</p>
                      <p>Storage expansion is completely automated! AWS handles volume optimization, and our system automatically resizes the filesystem. No manual commands needed - everything happens seamlessly in the background.</p>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex space-x-4">
                    <label className="flex items-center space-x-2">
                      <input
                        type="radio"
                        value="additional"
                        checked={mode === 'additional'}
                        onChange={(e) => setMode(e.target.value as 'additional' | 'absolute')}
                        className="text-blue-400 bg-blue-900/50 border-blue-500/50 focus:ring-blue-500"
                      />
                      <span className="text-blue-200">Increase by (GB)</span>
                    </label>
                    <label className="flex items-center space-x-2">
                      <input
                        type="radio"
                        value="absolute"
                        checked={mode === 'absolute'}
                        onChange={(e) => setMode(e.target.value as 'additional' | 'absolute')}
                        className="text-blue-400 bg-blue-900/50 border-blue-500/50 focus:ring-blue-500"
                      />
                      <span className="text-blue-200">Set new size (GB)</span>
                    </label>
                  </div>

                  {mode === 'additional' ? (
                    <div className="flex items-center gap-4">
                      <div className="relative">
                        <input
                          type="number"
                          min={1}
                          max={1000}
                          value={additionalGb}
                          onChange={(e) => setAdditionalGb(Number(e.target.value))}
                          className="w-32 px-4 py-3 bg-gray-700 border border-gray-500 rounded-lg text-white text-center font-medium focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                          placeholder="10"
                        />
                        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 text-sm">GB</div>
                      </div>
                      <button 
                        onClick={submitExpand} 
                        disabled={expanding} 
                        className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-all duration-200 flex items-center space-x-2 shadow-lg hover:shadow-xl" 
                        title="Increase root volume by the specified amount"
                      >
                        <Plus className="w-5 h-5" />
                        <span>{expanding ? 'Requesting...' : 'Increase Storage'}</span>
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-4">
                      <div className="relative">
                        <input
                          type="number"
                          min={1}
                          max={1000}
                          value={newSizeGb}
                          onChange={(e) => setNewSizeGb(Number(e.target.value))}
                          className="w-32 px-4 py-3 bg-gray-700 border border-gray-500 rounded-lg text-white text-center font-medium focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                          placeholder="50"
                        />
                        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 text-sm">GB</div>
                      </div>
                      <button 
                        onClick={submitExpand} 
                        disabled={expanding} 
                        className="px-6 py-3 bg-gradient-to-r from-purple-500 to-blue-600 hover:from-purple-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-all duration-200 flex items-center space-x-2 shadow-lg hover:shadow-xl" 
                        title="Set root volume to the specified target size"
                      >
                        <Plus className="w-5 h-5" />
                        <span>{expanding ? 'Requesting...' : 'Resize Storage'}</span>
                      </button>
                    </div>
                  )}

                  {lastMessage && (
                    <div className="mt-4 bg-green-900/20 border border-green-500/50 rounded-lg p-4">
                      <div className="flex items-center space-x-2 text-green-300">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span className="text-sm font-medium">{lastMessage}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}



