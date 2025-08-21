'use client';

import { useState, useEffect } from 'react';
import { RefreshCw, Download, Search, Filter, Clock, FileText } from 'lucide-react';

interface CloudWatchLogEntry {
  timestamp: string;
  message: string;
  log_stream: string;
}

interface CloudWatchLogsProps {
  podId: number;
  token: string;
  isVisible: boolean;
}

export default function CloudWatchLogs({ podId, token, isVisible }: CloudWatchLogsProps) {
  const [logs, setLogs] = useState<CloudWatchLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [limit, setLimit] = useState(100);

  const fetchCloudWatchLogs = async () => {
    if (!isVisible) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/v1/logs/pods/${podId}/cloudwatch?limit=${limit}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setLogs(data.log_entries || []);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to fetch CloudWatch logs');
      }
    } catch (err) {
      setError('Network error while fetching logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isVisible) {
      fetchCloudWatchLogs();
    }
  }, [isVisible, podId, limit]);

  const filteredLogs = logs.filter(log => 
    log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.log_stream.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  if (!isVisible) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center">
          <FileText className="w-5 h-5 mr-2" />
          CloudWatch Logs
        </h3>
        <div className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Search logs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="px-3 py-1 border rounded text-sm"
          />
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="px-3 py-1 border rounded text-sm"
          >
            <option value={50}>50 logs</option>
            <option value={100}>100 logs</option>
            <option value={500}>500 logs</option>
            <option value={1000}>1000 logs</option>
          </select>
          <button
            onClick={fetchCloudWatchLogs}
            disabled={loading}
            className="btn-secondary text-sm flex items-center"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-8 text-gray-500">
          <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
          Loading CloudWatch logs...
        </div>
      )}

      {!loading && !error && logs.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <FileText className="w-8 h-8 mx-auto mb-2" />
          No CloudWatch logs found for this pod
        </div>
      )}

      {!loading && !error && filteredLogs.length > 0 && (
        <div className="bg-gray-50 rounded border overflow-hidden">
          <div className="bg-gray-100 px-4 py-2 border-b text-sm font-medium text-gray-700">
            {filteredLogs.length} log entries
          </div>
          <div className="max-h-96 overflow-y-auto">
            {filteredLogs.map((log, index) => (
              <div key={index} className="border-b last:border-b-0 p-3 hover:bg-gray-100">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-xs text-gray-500 font-mono">
                        {formatTimestamp(log.timestamp)}
                      </span>
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                        {log.log_stream}
                      </span>
                    </div>
                    <div className="text-sm text-gray-800 font-mono whitespace-pre-wrap break-words">
                      {log.message}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

