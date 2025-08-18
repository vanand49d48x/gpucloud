'use client';

import { useState, useEffect, useRef } from 'react';
import { FileText, Search, Filter, Download, RefreshCw, Eye, EyeOff, Play, Square, X } from 'lucide-react';
import { clientLogger as logger } from '../utils/logger';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  data?: any;
  app?: string;
  source?: string;
}

interface LogViewerProps {
  isOpen: boolean;
  onClose: () => void;
  appName?: string; // Specific app to show logs for
  podId?: number; // Specific pod ID to show logs for
  token?: string; // Authentication token
}

export default function LogViewer({ isOpen, onClose, appName, podId, token }: LogViewerProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filteredLogs, setFilteredLogs] = useState<LogEntry[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedLevels, setSelectedLevels] = useState<string[]>(['INFO', 'WARN', 'ERROR', 'FATAL']);
  const [isFollowing, setIsFollowing] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(5000); // 5 seconds
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Available log levels
  const logLevels = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL'];

  // Auto-scroll to bottom when following
  useEffect(() => {
    if (isFollowing && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [filteredLogs, isFollowing]);

  // Auto-refresh logs
  useEffect(() => {
    if (autoRefresh && isOpen) {
      refreshIntervalRef.current = setInterval(() => {
        fetchLogs();
      }, refreshInterval);
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, refreshInterval, isOpen]);

  // Fetch logs from backend
  const fetchLogs = async () => {
    if (isLoading) return;
    
    setIsLoading(true);
    try {
      let endpoint = '/v1/logs';
      
      // If we have a podId, fetch pod-specific activity logs
      if (podId) {
        endpoint = `/v1/pods/${podId}/activity-logs`;
      } else if (appName) {
        endpoint += `/${appName}`;
      }
      
      const headers: HeadersInit = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch(endpoint, { headers });
      if (response.ok) {
        const data = await response.json();
        
        if (podId && data.activity_logs) {
          // Handle pod activity logs
          const podLogs = data.activity_logs.map((log: any) => ({
            timestamp: log.timestamp,
            level: 'INFO',
            message: log.message,
            data: {
              action: log.action,
              status: log.status,
              instance_id: log.instance_id,
              instance_type: log.instance_type,
              public_ip: log.public_ip
            },
            app: `Pod ${podId}`,
            source: 'pod-activity'
          }));
          setLogs(podLogs);
          logger.info('Pod activity logs fetched successfully', { count: podLogs.length, podId });
        } else {
          // Handle regular logs
          setLogs(data.logs || []);
          logger.info('Logs fetched successfully', { count: data.logs?.length || 0 });
        }
      } else {
        logger.warn('Failed to fetch logs from backend, using local logs');
        // Fallback to local logs
        const localLogs = logger.getLogs().map(logStr => {
          try {
            return JSON.parse(logStr);
          } catch {
            return null;
          }
        }).filter(Boolean);
        setLogs(localLogs);
      }
    } catch (error) {
      logger.error('Error fetching logs', { error });
      // Fallback to local logs
      const localLogs = logger.getLogs().map(logStr => {
        try {
          return JSON.parse(logStr);
        } catch {
          return null;
        }
      }).filter(Boolean);
      setLogs(localLogs);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter logs based on search and level filters
  useEffect(() => {
    let filtered = logs;

    // Filter by level
    if (selectedLevels.length > 0) {
      filtered = filtered.filter(log => selectedLevels.includes(log.level));
    }

    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(log => 
        log.message.toLowerCase().includes(term) ||
        log.data?.toString().toLowerCase().includes(term) ||
        log.source?.toLowerCase().includes(term)
      );
    }

    setFilteredLogs(filtered);
  }, [logs, searchTerm, selectedLevels]);

  // Initial fetch
  useEffect(() => {
    if (isOpen) {
      fetchLogs();
    }
  }, [isOpen]);

  // Toggle log level filter
  const toggleLevel = (level: string) => {
    setSelectedLevels(prev => 
      prev.includes(level) 
        ? prev.filter(l => l !== level)
        : [...prev, level]
    );
  };

  // Clear all logs
  const clearLogs = () => {
    setLogs([]);
    setFilteredLogs([]);
    logger.clearLogs();
  };

  // Download logs
  const downloadLogs = () => {
    const logContent = filteredLogs.map(log => 
      `[${log.timestamp}] ${log.level}: ${log.message}${log.data ? ` | ${JSON.stringify(log.data)}` : ''}`
    ).join('\n');
    
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${podId ? `pod-${podId}` : appName || 'all'}-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Get level color
  const getLevelColor = (level: string) => {
    const colors = {
      DEBUG: 'text-blue-400',
      INFO: 'text-green-400',
      WARN: 'text-yellow-400',
      ERROR: 'text-red-400',
      FATAL: 'text-purple-400'
    };
    return colors[level as keyof typeof colors] || 'text-gray-400';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-7xl h-[95vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center space-x-4">
            <FileText className="w-6 h-6 text-blue-400" />
            <div>
              <h2 className="text-lg font-semibold text-white">
                {podId ? `Pod ${podId} Activity Logs` : `Log Viewer ${appName ? `- ${appName}` : ''}`}
              </h2>
              <p className="text-sm text-gray-400">
                {filteredLogs.length} of {logs.length} logs • Auto-refresh: {autoRefresh ? 'ON' : 'OFF'}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {/* Follow Toggle */}
            <button
              onClick={() => setIsFollowing(!isFollowing)}
              className={`p-2 rounded ${isFollowing ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300'}`}
              title={isFollowing ? 'Following logs' : 'Not following'}
            >
              {isFollowing ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>
            
            {/* Auto-refresh Toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`p-2 rounded ${autoRefresh ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
              title={autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
            >
              <RefreshCw className={`w-4 h-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            </button>
            
            {/* Action Buttons */}
            <button
              onClick={fetchLogs}
              disabled={isLoading}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded disabled:opacity-50"
              title="Refresh logs"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            
            <button
              onClick={downloadLogs}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
              title="Download logs"
            >
              <Download className="w-4 h-4" />
            </button>
            
            <button
              onClick={clearLogs}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
              title="Clear logs"
            >
              <Square className="w-4 h-4" />
            </button>
            
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
              title="Close log viewer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Controls */}
        <div className="p-4 border-b border-gray-700 bg-gray-800">
          <div className="flex flex-wrap gap-4 items-center">
            {/* Search */}
            <div className="flex-1 min-w-64">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search logs..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400"
                />
              </div>
            </div>

            {/* Level Filters */}
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300">Levels:</span>
              {logLevels.map(level => (
                <button
                  key={level}
                  onClick={() => toggleLevel(level)}
                  className={`px-2 py-1 text-xs rounded ${
                    selectedLevels.includes(level)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>

            {/* Refresh Interval */}
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-300">Refresh:</span>
              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
              >
                <option value={1000}>1s</option>
                <option value={5000}>5s</option>
                <option value={10000}>10s</option>
                <option value={30000}>30s</option>
                <option value={60000}>1m</option>
              </select>
            </div>
          </div>
        </div>

        {/* Logs Display */}
        <div className="flex-1 overflow-hidden">
          <div className="h-full overflow-y-auto font-mono text-sm bg-black p-4">
            {filteredLogs.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <FileText className="w-12 h-12 mx-auto mb-4 text-gray-600" />
                <p>No logs found</p>
                {searchTerm && <p className="text-sm">Try adjusting your search or filters</p>}
              </div>
            ) : (
              filteredLogs.map((log, index) => (
                <div key={index} className="mb-1 hover:bg-gray-800 p-1 rounded">
                  <span className="text-gray-500 text-xs">[{log.timestamp}]</span>
                  <span className={`ml-2 font-bold ${getLevelColor(log.level)}`}>
                    {log.level}
                  </span>
                  <span className="ml-2 text-white">{log.message}</span>
                  {log.data && (
                    <span className="ml-2 text-gray-400 text-xs">
                      | {typeof log.data === 'object' ? JSON.stringify(log.data) : log.data}
                    </span>
                  )}
                  {log.source && (
                    <span className="ml-2 text-blue-400 text-xs">[{log.source}]</span>
                  )}
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-gray-700 bg-gray-800 text-xs text-gray-400">
          <div className="flex justify-between items-center">
            <span>
              Showing {filteredLogs.length} of {logs.length} logs
              {searchTerm && ` • Filtered by: "${searchTerm}"`}
            </span>
            <span>
              {isFollowing ? 'Following' : 'Not following'} • 
              Auto-refresh: {autoRefresh ? `${refreshInterval / 1000}s` : 'OFF'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
