'use client';

import { useState, useEffect } from 'react';
import { Play, Trash2, FileText, Eye, Plus, Search, Filter, Terminal, Globe } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import GPUCatalog from './GPUCatalog';
import WebTerminal from './WebTerminal';
import SSHConnectionGuide from './SSHConnectionGuide';
import LogViewer from './LogViewer';
import { clientLogger as logger } from '../utils/logger';

interface Pod {
  id: number;
  status: string;
  public_ip: string | null;
  template: string | null;
  hourly_rate_cents: number;
  instance_id: string | null;
  instance_type?: string;
  created_at?: string;
}

interface CatalogItem {
  id: string;
  instance_type: string;
  category: string;
  gpu: any;
  vcpus: number;
  memory_gb: number;
  hourly_usd: number;
  price_with_markup_usd: number;
}

export default function PodManager() {
  const { token } = useAuth();
  const [pods, setPods] = useState<Pod[]>([]);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [showTerminalModal, setShowTerminalModal] = useState(false);
  const [showSSHGuideModal, setShowSSHGuideModal] = useState(false);
  const [showLogViewerModal, setShowLogViewerModal] = useState(false);
  const [selectedInstance, setSelectedInstance] = useState<CatalogItem | null>(null);
  const [selectedPod, setSelectedPod] = useState<Pod | null>(null);

  const API_BASE = ''; // Use relative URLs, nginx will proxy to API backend

  // Fetch pods from your backend
  const fetchPods = async () => {
    logger.info('Starting pods fetch', { hasToken: !!token, timestamp: new Date().toISOString() });
    if (!token) return;
    
    try {
      const response = await fetch(`${API_BASE}/v1/pods`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      logger.info('Pods API response received', { 
        status: response.status, 
        ok: response.ok,
        timestamp: new Date().toISOString()
      });
      
      if (response.ok) {
        const data = await response.json();
        logger.info('Pods data parsed successfully', { 
          podCount: data.length,
          timestamp: new Date().toISOString()
        });
        setPods(data);
      }
    } catch (error) {
      logger.error('Error fetching pods', { 
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
        timestamp: new Date().toISOString()
      });
      // Fallback to mock data for now
      setPods([
        {
          id: 12,
          status: 'running',
          public_ip: '18.208.251.45',
          template: null,
          hourly_rate_cents: 3,
          instance_id: 'i-00280e58876e5bbf8',
          instance_type: 't1.micro',
          created_at: '2025-08-15T01:12:20'
        }
      ]);
    }
  };

  // Fetch catalog from your backend
  const fetchCatalog = async () => {
    try {
      const response = await fetch(`${API_BASE}/v1/catalog/aws`);
      if (response.ok) {
        const data = await response.json();
        setCatalog(data);
      }
    } catch (error) {
      console.error('Error fetching catalog:', error);
      // Fallback to mock data
      setCatalog([
        {
          id: 'aws:us-east-1:t1.micro',
          instance_type: 't1.micro',
          category: 'CPU',
          gpu: null,
          vcpus: 1,
          memory_gb: 1,
          hourly_usd: 0.02,
          price_with_markup_usd: 0.03
        }
      ]);
    }
  };

  // Update security group to allow SSH access
  const updateSecurityGroup = async (instanceId: string, userIp: string) => {
    try {
      const response = await fetch(`${API_BASE}/v1/pods/${selectedPod?.id}/security-group/update`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ user_ip: userIp })
      });

      if (response.ok) {
        logger.info('Security group updated successfully', { instanceId, userIp });
      } else {
        logger.error('Failed to update security group', { instanceId, userIp, status: response.status });
      }
    } catch (error) {
      logger.error('Error updating security group', { error, instanceId, userIp });
    }
  };

  // Launch a new pod
  const launchPod = async (instanceId: string) => {
    if (!token) return;
    
    try {
      const response = await fetch(`${API_BASE}/v1/catalog/aws/launch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ id: instanceId })
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Pod launched:', data);
        // Refresh pods list
        fetchPods();
        setShowDeployModal(false);
      } else {
        const error = await response.json();
        console.error('Launch failed:', error);
        alert(`Launch failed: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error launching pod:', error);
      alert('Error launching pod');
    }
  };



  // Start a stopped pod
  const startPod = async (podId: number) => {
    if (!token) return;
    
    try {
      // Show loading state
      setPods(prevPods => 
        prevPods.map(pod => 
          pod.id === podId 
            ? { ...pod, status: 'starting' }
            : pod
        )
      );
      
      const response = await fetch(`${API_BASE}/v1/pods/${podId}/start`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        console.log('Pod started');
        // Refresh pods list to get updated status
        fetchPods();
      } else {
        const error = await response.json();
        console.error('Start failed:', error);
        // Revert status on error
        setPods(prevPods => 
          prevPods.map(p => 
            p.id === podId 
              ? { ...p, status: 'stopped' }
              : p
          )
        );
        alert(`Start failed: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error starting pod:', error);
      // Revert status on error
      setPods(prevPods => 
        prevPods.map(p => 
          p.id === podId 
            ? { ...p, status: 'stopped' }
            : p
        )
      );
      alert('Error starting pod');
    }
  };

  // Stop a running pod
  const stopPod = async (podId: number) => {
    if (!token) return;
    
    try {
      // Show stopping state
      setPods(prevPods => 
        prevPods.map(pod => 
          pod.id === podId 
            ? { ...pod, status: 'stopping' }
            : pod
        )
      );
      
      const response = await fetch(`${API_BASE}/v1/pods/${podId}/stop`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        console.log('Pod stopped');
        fetchPods();
      } else {
        // Revert status on error
        setPods(prevPods => 
          prevPods.map(pod => 
            pod.id === podId 
              ? { ...pod, status: 'running' }
              : pod
          )
        );
      }
    } catch (error) {
      console.error('Error stopping pod:', error);
      // Revert status on error
      setPods(prevPods => 
        prevPods.map(pod => 
          pod.id === podId 
            ? { ...pod, status: 'running' }
            : pod
        )
      );
    }
  };

  useEffect(() => {
    if (token) {
      fetchPods();
      fetchCatalog();
    }
    setLoading(false);
  }, [token]);

  // Auto-refresh pods every 10 seconds to keep status updated
  useEffect(() => {
    if (!token) return;
    
    const interval = setInterval(() => {
      fetchPods();
    }, 10000);
    
    return () => clearInterval(interval);
  }, [token]);

  const filteredPods = pods.filter(pod =>
    pod.instance_id?.includes(searchTerm) ||
    pod.status.includes(searchTerm)
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'text-green-400';
      case 'stopped': return 'text-yellow-400';
      case 'exited': return 'text-gray-400';
      case 'pending': return 'text-blue-400';
      case 'starting': return 'text-blue-400';
      case 'stopping': return 'text-orange-400';
      case 'error': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <div className="w-3 h-3 bg-green-400 rounded-full" />;
      case 'stopped': return <div className="w-3 h-3 bg-yellow-400 rounded-full" />;
      case 'exited': return <div className="w-3 h-3 bg-gray-400 rounded-full" />;
      case 'pending': return <div className="w-3 h-3 bg-blue-400 rounded-full animate-pulse" />;
      case 'starting': return <div className="w-3 h-3 bg-blue-400 rounded-full animate-pulse" />;
      case 'stopping': return <div className="w-3 h-3 bg-orange-400 rounded-full animate-pulse" />;
      case 'error': return <div className="w-3 h-3 bg-red-400 rounded-full" />;
      default: return <div className="w-3 h-3 bg-gray-400 rounded-full" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading pods...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button 
            onClick={() => {
              logger.info('Deploy button clicked in PodManager', { timestamp: new Date().toISOString() });
              setShowDeployModal(true);
            }}
            className="btn-primary"
          >
            <Plus className="w-4 h-4 mr-2" />
            Deploy
          </button>
          
          <button 
            onClick={() => {
              logger.info('Log viewer button clicked', { timestamp: new Date().toISOString() });
              setShowLogViewerModal(true);
            }}
            className="btn-secondary"
          >
            <FileText className="w-4 h-4 mr-2" />
            View Logs
          </button>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name, id, gpu"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>
          
          <button className="btn-secondary">
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Pods List */}
      <div className="space-y-4">
        {filteredPods.map((pod) => (
          <div key={pod.id} className="card">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">
                  Pod {pod.id}
                </h3>
                <div className="text-sm text-gray-400">
                  ID: {pod.instance_id || 'N/A'}
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                {getStatusIcon(pod.status)}
                <span className={getStatusColor(pod.status)}>
                  {pod.status.charAt(0).toUpperCase() + pod.status.slice(1)}
                </span>
                {pod.status === 'stopped' && !pod.instance_type && (
                  <span className="text-xs text-gray-500 ml-2">
                    (Legacy pod - cannot restart)
                  </span>
                )}
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div className="space-y-2">
                <div className="text-gray-300">
                  <strong>Instance Type:</strong> {pod.instance_type || 'Unknown (legacy pod)'}
                </div>
                <div className="text-gray-300">
                  <strong>Public IP:</strong> {pod.public_ip || 'N/A'}
                </div>
                <div className="text-gray-300">
                  <strong>Created:</strong> {pod.created_at ? new Date(pod.created_at).toLocaleString() : 'N/A'}
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="text-gray-300">
                  <strong>Hourly Rate:</strong> ${(pod.hourly_rate_cents / 100).toFixed(2)}
                </div>
                <div className="text-gray-300">
                  <strong>Per Minute:</strong> ${(pod.hourly_rate_cents / 6000).toFixed(4)}
                </div>
              </div>
            </div>
            
            <div className="flex space-x-3">
              {pod.status === 'running' ? (
                <button 
                  onClick={() => stopPod(pod.id)}
                  disabled={false}
                  className="btn-danger text-sm"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Stop
                </button>
              ) : (
                <button 
                  onClick={() => startPod(pod.id)}
                  disabled={pod.status === 'starting' || !pod.instance_type}
                  className={`btn-primary text-sm ${(pod.status === 'starting' || !pod.instance_type) ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <Play className="w-4 h-4 mr-2" />
                  {pod.status === 'starting' ? 'Starting...' : 'Start'}
                </button>
              )}
              <button className="btn-secondary text-sm">
                <FileText className="w-4 h-4 mr-2" />
                Logs
              </button>
              <button className="btn-secondary text-sm">
                <Eye className="w-4 h-4 mr-2" />
                View
              </button>
              
              {/* Terminal and SSH Access Buttons */}
              {pod.status === 'running' && pod.public_ip && (
                <>
                  <button
                    onClick={() => {
                      setSelectedPod(pod);
                      setShowTerminalModal(true);
                    }}
                    className="btn-secondary text-sm bg-green-600 hover:bg-green-700"
                    title="Open Web Terminal"
                  >
                    <Terminal className="w-4 h-4 mr-2" />
                    Terminal
                  </button>
                  <button
                    onClick={() => {
                      setSelectedPod(pod);
                      setShowSSHGuideModal(true);
                    }}
                    className="btn-secondary text-sm bg-blue-600 hover:bg-blue-700"
                    title="SSH Connection Guide"
                  >
                    <Globe className="w-4 h-4 mr-2" />
                    SSH
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
        
        {filteredPods.length === 0 && (
          <div className="text-center text-gray-400 py-8">
            No pods found. Deploy your first instance to get started!
          </div>
        )}
      </div>

      {/* GPU Catalog Modal */}
      <GPUCatalog
        isOpen={showDeployModal}
        onClose={() => {
          logger.info('GPUCatalog modal closing', { timestamp: new Date().toISOString() });
          setShowDeployModal(false);
        }}
        onDeploy={(instanceId) => {
          logger.info('GPUCatalog onDeploy called', { instanceId, timestamp: new Date().toISOString() });
          launchPod(instanceId);
          setShowDeployModal(false);
        }}
      />

      {/* Web Terminal Modal */}
      {selectedPod && (
                <WebTerminal 
          podId={selectedPod.id}
          instanceId={selectedPod.instance_id || ''}
          publicIp={selectedPod.public_ip || ''}
          instanceType={selectedPod.instance_type || ''}
          isOpen={showTerminalModal}
          onClose={() => {
            setShowTerminalModal(false);
            setSelectedPod(null);
          }}
          onSecurityGroupUpdate={updateSecurityGroup}
          token={token || undefined}
        />
      )}

      {/* SSH Connection Guide Modal */}
      {selectedPod && (
        <SSHConnectionGuide
          podId={selectedPod.id}
          instanceId={selectedPod.instance_id || ''}
          publicIp={selectedPod.public_ip || ''}
          instanceType={selectedPod.instance_type || ''}
          isOpen={showSSHGuideModal}
          onClose={() => {
            setShowSSHGuideModal(false);
            setSelectedPod(null);
          }}
          onSecurityGroupUpdate={updateSecurityGroup}
          token={token || undefined}
        />
      )}
      
      {/* Log Viewer Modal */}
      <LogViewer
        isOpen={showLogViewerModal}
        onClose={() => setShowLogViewerModal(false)}
      />
    </div>
  );
}
