'use client';

import { useState, useEffect, useRef } from 'react';
import { Terminal, X, Download, Upload, Settings, Play, Square } from 'lucide-react';
import { clientLogger as logger } from '../utils/logger';

interface WebTerminalProps {
  podId: number;
  instanceId: string;
  publicIp: string;
  instanceType: string;
  isOpen: boolean;
  onClose: () => void;
  token?: string; // Add token prop
}

interface TerminalMessage {
  type: 'input' | 'output' | 'error' | 'system';
  content: string;
  timestamp: string;
}

function WebTerminalComponent({ 
  podId, 
  instanceId, 
  publicIp, 
  instanceType, 
  isOpen, 
  onClose,
  token
}: WebTerminalProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [messages, setMessages] = useState<TerminalMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [terminalHistory, setTerminalHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [showSettings, setShowSettings] = useState(false);
  const [terminalConfig, setTerminalConfig] = useState({
    fontSize: 14,
    theme: 'dark',
    autoConnect: true
  });
  
  const terminalRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Auto-connect when terminal opens
  useEffect(() => {
    if (isOpen && terminalConfig.autoConnect && !isConnected) {
      connectToInstance();
    }
  }, [isOpen, terminalConfig.autoConnect]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input when connected
  useEffect(() => {
    if (isConnected && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isConnected]);

  const connectToInstance = async () => {
    if (isConnecting || isConnected) return;
    
    let connectionTimeout: NodeJS.Timeout | null = null;
    
    try {
      setIsConnecting(true);
      addMessage('system', 'Connecting to instance...');
      
      // For SSM-based terminals, no security group updates are needed
      addMessage('system', 'Connecting via AWS Systems Manager (SSM)...');

      // Connect to the instance via WebSocket proxy
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/v1/pods/${podId}/terminal/${instanceId}?token=${token || ''}`;
      
      const ws = new WebSocket(wsUrl);
      
      // Add connection timeout
      connectionTimeout = setTimeout(() => {
        if (ws.readyState === WebSocket.CONNECTING) {
          ws.close();
          addMessage('error', 'Connection timeout. Please try again.');
          setIsConnecting(false);
          setIsConnected(false);
        }
      }, 10000);
      
      ws.onopen = () => {
        try {
          if (connectionTimeout) clearTimeout(connectionTimeout);
          logger.info('WebSocket connection opened', { podId, instanceId });
          setIsConnected(true);
          setIsConnecting(false);
          addMessage('system', 'Connected to instance! Type your commands below.');
          addMessage('system', `Instance: ${instanceType} | IP: ${publicIp}`);
          addMessage('system', 'Type "help" for available commands or start using the terminal.');
        } catch (openError) {
          logger.error('Error in WebSocket onopen', { error: openError });
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'output') {
            addMessage('output', data.content);
          } else if (data.type === 'error') {
            addMessage('error', data.content);
          }
        } catch (e) {
          addMessage('output', event.data);
        }
      };

      ws.onerror = (error) => {
        try {
          if (connectionTimeout) clearTimeout(connectionTimeout);
          logger.error('WebSocket error', { error, podId, instanceId });
          addMessage('error', 'Connection error. Please try again.');
          setIsConnecting(false);
          setIsConnected(false);
        } catch (errorHandlerError) {
          logger.error('Error in WebSocket error handler', { error: errorHandlerError });
        }
      };

      ws.onclose = () => {
        try {
          if (connectionTimeout) clearTimeout(connectionTimeout);
          logger.info('WebSocket connection closed', { podId, instanceId });
          setIsConnected(false);
          addMessage('system', 'Connection closed. Click Connect to reconnect.');
        } catch (closeError) {
          logger.error('Error in WebSocket close handler', { error: closeError });
        }
      };

      wsRef.current = ws;

    } catch (error) {
      if (connectionTimeout) clearTimeout(connectionTimeout);
      logger.error('Failed to connect to instance', { error, podId, instanceId });
      addMessage('error', `Failed to connect: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsConnecting(false);
      setIsConnected(false);
    }
  };

  const disconnectFromInstance = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    addMessage('system', 'Disconnected from instance.');
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const addMessage = (type: TerminalMessage['type'], content: string) => {
    const message: TerminalMessage = {
      type,
      content,
      timestamp: new Date().toLocaleTimeString()
    };
    setMessages(prev => [...prev, message]);
  };

  const sendCommand = (command: string) => {
    if (!isConnected || !wsRef.current) {
      addMessage('error', 'Not connected to instance.');
      return;
    }

    if (!command.trim()) return;

    // Add command to history
    setTerminalHistory(prev => [...prev, command]);
    setHistoryIndex(-1);

    // Send command to instance
    wsRef.current.send(JSON.stringify({
      type: 'command',
      content: command
    }));

    // Display command in terminal
    addMessage('input', `$ ${command}`);
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      sendCommand(inputValue);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (historyIndex < terminalHistory.length - 1) {
        const newIndex = historyIndex + 1;
        setHistoryIndex(newIndex);
        setInputValue(terminalHistory[terminalHistory.length - 1 - newIndex]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setInputValue(terminalHistory[terminalHistory.length - 1 - newIndex]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setInputValue('');
      }
    }
  };

  const clearTerminal = () => {
    setMessages([]);
  };

  const downloadLogs = () => {
    const logContent = messages.map(msg => 
      `[${msg.timestamp}] ${msg.type.toUpperCase()}: ${msg.content}`
    ).join('\n');
    
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `terminal-logs-pod-${podId}-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-6xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center space-x-4">
            <Terminal className="w-6 h-6 text-green-400" />
            <div>
              <h2 className="text-lg font-semibold text-white">Terminal - Pod {podId}</h2>
              <p className="text-sm text-gray-400">{instanceType} • {publicIp}</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {/* Connection Status */}
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${
              isConnected ? 'bg-green-900 text-green-300' : 
              isConnecting ? 'bg-yellow-900 text-yellow-300' : 
              'bg-red-900 text-red-300'
            }`}>
              {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
            </div>
            
            {/* Action Buttons */}
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
            >
              <Settings className="w-4 h-4" />
            </button>
            
            <button
              onClick={downloadLogs}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
            >
              <Download className="w-4 h-4" />
            </button>
            
            <button
              onClick={clearTerminal}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
            >
              <Square className="w-4 h-4" />
            </button>
            
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="p-4 border-b border-gray-700 bg-gray-800">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Font Size</label>
                <input
                  type="range"
                  min="10"
                  max="24"
                  value={terminalConfig.fontSize}
                  onChange={(e) => setTerminalConfig(prev => ({ ...prev, fontSize: parseInt(e.target.value) }))}
                  className="w-full"
                />
                <span className="text-xs text-gray-400">{terminalConfig.fontSize}px</span>
              </div>
              
              <div>
                <label className="block text-sm text-gray-300 mb-1">Theme</label>
                <select
                  value={terminalConfig.theme}
                  onChange={(e) => setTerminalConfig(prev => ({ ...prev, theme: e.target.value }))}
                  className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                >
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                  <option value="green">Green</option>
                </select>
              </div>
              
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="autoConnect"
                  checked={terminalConfig.autoConnect}
                  onChange={(e) => setTerminalConfig(prev => ({ ...prev, autoConnect: e.target.checked }))}
                  className="mr-2"
                />
                <label htmlFor="autoConnect" className="text-sm text-gray-300">Auto-connect</label>
              </div>
            </div>
          </div>
        )}

        {/* Terminal Output */}
        <div 
          ref={terminalRef}
          className="flex-1 p-4 overflow-y-auto font-mono text-sm"
          style={{ fontSize: `${terminalConfig.fontSize}px` }}
        >
          {messages.length === 0 && !isConnecting && !isConnected && (
            <div className="text-center text-gray-500 py-8">
              <Terminal className="w-12 h-12 mx-auto mb-4 text-gray-600" />
              <p>Click Connect to start using the terminal</p>
            </div>
          )}
          
          {messages.map((message, index) => (
            <div key={index} className={`mb-1 ${
              message.type === 'input' ? 'text-green-400' :
              message.type === 'output' ? 'text-white' :
              message.type === 'error' ? 'text-red-400' :
              'text-blue-400'
            }`}>
              {message.content}
            </div>
          ))}
          
          {isConnecting && (
            <div className="text-yellow-400 animate-pulse">
              Connecting to instance...
            </div>
          )}
        </div>

        {/* Connection Controls */}
        {!isConnected && !isConnecting && (
          <div className="p-4 border-t border-gray-700 bg-gray-800">
            <button
              onClick={connectToInstance}
              className="btn-primary flex items-center space-x-2"
            >
              <Play className="w-4 h-4" />
              <span>Connect to Instance</span>
            </button>
          </div>
        )}

        {/* Input Area */}
        {isConnected && (
          <div className="p-4 border-t border-gray-700 bg-gray-800">
            <div className="flex items-center space-x-2">
              <span className="text-green-400 font-mono">$</span>
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your command here..."
                className="flex-1 bg-transparent border-none outline-none text-white font-mono"
                disabled={!isConnected}
              />
            </div>
            
            {isConnected && (
              <div className="mt-2 text-xs text-gray-500">
                Press Enter to send command • Use ↑↓ arrows for command history • Type 'help' for available commands
              </div>
            )}
          </div>
        )}

        {/* Disconnect Button */}
        {isConnected && (
          <div className="p-4 border-t border-gray-700 bg-gray-800">
            <button
              onClick={disconnectFromInstance}
              className="btn-secondary flex items-center space-x-2"
            >
              <Square className="w-4 h-4" />
              <span>Disconnect</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// Error boundary wrapper for WebTerminal
function WebTerminalErrorBoundary(props: WebTerminalProps) {
  try {
    return <WebTerminalComponent {...props} />;
  } catch (error) {
    console.error('WebTerminal crashed:', error);
    return (
      <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
        <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-6xl h-[90vh] flex flex-col items-center justify-center">
          <div className="text-center text-white">
            <Terminal className="w-16 h-16 mx-auto mb-4 text-red-400" />
            <h2 className="text-xl font-semibold mb-2">Terminal Error</h2>
            <p className="text-gray-400 mb-4">The terminal encountered an error and crashed.</p>
            <button
              onClick={props.onClose}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded"
            >
              Close Terminal
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default WebTerminalErrorBoundary;
