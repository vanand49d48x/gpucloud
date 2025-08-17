'use client';

import { useState, useEffect } from 'react';
import { Terminal, Copy, ExternalLink, Download, Code, Monitor, Smartphone, Globe } from 'lucide-react';
import { clientLogger as logger } from '../utils/logger';

interface SSHConnectionGuideProps {
  podId: number;
  instanceId: string;
  publicIp: string;
  instanceType: string;
  isOpen: boolean;
  onClose: () => void;
  onSecurityGroupUpdate?: (instanceId: string, userIp: string) => void;
  token?: string; // Add token prop
}

interface SSHInfo {
  ssh_command: string;
  username: string;
  port: number;
  key_name: string;
}

export default function SSHConnectionGuide({ 
  podId, 
  instanceId, 
  publicIp, 
  instanceType, 
  isOpen, 
  onClose,
  onSecurityGroupUpdate,
  token
}: SSHConnectionGuideProps) {
  const [sshInfo, setSshInfo] = useState<SSHInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [userIp, setUserIp] = useState<string>('');
  const [securityGroupUpdated, setSecurityGroupUpdated] = useState(false);
  const [activeTab, setActiveTab] = useState<'terminal' | 'vscode' | 'other'>('terminal');

  useEffect(() => {
    if (isOpen) {
      fetchSSHInfo();
      getUserIP();
    }
  }, [isOpen, podId]);

  const fetchSSHInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://127.0.0.1:8080/v1/pods/${podId}/ssh-info`, {
        headers: {
          'Authorization': `Bearer ${token || localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setSshInfo(data);
        logger.info('SSH info fetched successfully', { podId, data });
      } else {
        logger.error('Failed to fetch SSH info', { podId, status: response.status });
      }
    } catch (error) {
      logger.error('Error fetching SSH info', { error, podId });
    } finally {
      setLoading(false);
    }
  };

  const getUserIP = async () => {
    try {
      const response = await fetch('https://api.ipify.org?format=json');
      const data = await response.json();
      setUserIp(data.ip);
    } catch (error) {
      setUserIp('unknown');
    }
  };

  const updateSecurityGroup = async () => {
    if (!userIp || !onSecurityGroupUpdate) return;
    
    try {
      setLoading(true);
      onSecurityGroupUpdate(instanceId, userIp);
      setSecurityGroupUpdated(true);
      
      // Auto-hide success message after 5 seconds
      setTimeout(() => setSecurityGroupUpdated(false), 5000);
      
      logger.info('Security group updated for SSH access', { instanceId, userIp });
    } catch (error) {
      logger.error('Failed to update security group', { error, instanceId, userIp });
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    logger.info('SSH command copied to clipboard', { text });
  };

  const downloadSSHConfig = () => {
    if (!sshInfo) return;
    
    const config = `Host gpucloud-pod-${podId}
    HostName ${publicIp}
    User ${sshInfo.username}
    Port ${sshInfo.port}
    IdentityFile ~/.ssh/${sshInfo.key_name}
    ServerAliveInterval 60
    ServerAliveCountMax 3
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null`;

    const blob = new Blob([config], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ssh-config-pod-${podId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    
    logger.info('SSH config downloaded', { podId });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center space-x-4">
            <Terminal className="w-8 h-8 text-green-400" />
            <div>
              <h2 className="text-2xl font-bold text-white">Connect to Pod {podId}</h2>
              <p className="text-gray-400">{instanceType} • {publicIp}</p>
            </div>
          </div>
          
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Security Group Update */}
        {!securityGroupUpdated && (
          <div className="p-4 bg-blue-900/20 border-b border-blue-700">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Globe className="w-5 h-5 text-blue-400" />
                <div>
                  <p className="text-blue-300 font-medium">Enable SSH Access</p>
                  <p className="text-blue-400 text-sm">
                    Your IP: {userIp} • Click below to allow SSH access from your location
                  </p>
                </div>
              </div>
              
              <button
                onClick={updateSecurityGroup}
                disabled={loading || !userIp || userIp === 'unknown'}
                className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Updating...' : 'Allow SSH Access'}
              </button>
            </div>
          </div>
        )}

        {securityGroupUpdated && (
          <div className="p-4 bg-green-900/20 border-b border-green-700">
            <div className="flex items-center space-x-3">
              <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <p className="text-green-300">
                SSH access enabled for your IP ({userIp}). Access will expire in 1 hour.
              </p>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setActiveTab('terminal')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'terminal'
                ? 'text-white border-b-2 border-green-400 bg-gray-800'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            <Terminal className="w-4 h-4 inline mr-2" />
            Web Terminal
          </button>
          
          <button
            onClick={() => setActiveTab('vscode')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'vscode'
                ? 'text-white border-b-2 border-green-400 bg-gray-800'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            <Code className="w-4 h-4 inline mr-2" />
            VSCode & IDEs
          </button>
          
          <button
            onClick={() => setActiveTab('other')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'other'
                ? 'text-white border-b-2 border-green-400 bg-gray-800'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            <Monitor className="w-4 h-4 inline mr-2" />
            Other Tools
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6 overflow-y-auto max-h-96">
          {/* Web Terminal Tab */}
          {activeTab === 'terminal' && (
            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-white mb-3">Web Terminal Access</h3>
                <p className="text-gray-300 mb-4">
                  Access your instance directly through the browser. No SSH client setup required.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">✅ Advantages</h4>
                    <ul className="text-sm text-gray-300 space-y-1">
                      <li>• No software installation needed</li>
                      <li>• Works from any device/browser</li>
                      <li>• No IP restrictions</li>
                      <li>• Built-in command history</li>
                      <li>• Easy file upload/download</li>
                    </ul>
                  </div>
                  
                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">⚠️ Limitations</h4>
                    <ul className="text-sm text-gray-300 space-y-1">
                      <li>• Basic terminal features only</li>
                      <li>• No advanced IDE integration</li>
                      <li>• Limited file management</li>
                      <li>• Connection may timeout</li>
                    </ul>
                  </div>
                </div>
                
                <div className="mt-4 p-4 bg-green-900/20 border border-green-700 rounded-lg">
                  <p className="text-green-300 text-sm">
                    <strong>Perfect for:</strong> Quick commands, monitoring, debugging, and basic file operations.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* VSCode & IDEs Tab */}
          {activeTab === 'vscode' && (
            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-white mb-3">VSCode & IDE Integration</h3>
                <p className="text-gray-300 mb-4">
                  Connect your favorite IDE for full development experience with syntax highlighting, debugging, and more.
                </p>
                
                {sshInfo && (
                  <div className="bg-gray-700 rounded-lg p-4 mb-4">
                    <h4 className="font-medium text-white mb-2">SSH Connection Details</h4>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Host:</span>
                        <span className="text-white font-mono">{publicIp}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Username:</span>
                        <span className="text-white font-mono">{sshInfo.username}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Port:</span>
                        <span className="text-white font-mono">{sshInfo.port}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-300">Key:</span>
                        <span className="text-white font-mono">~/.ssh/{sshInfo.key_name}</span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="space-y-4">
                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">VSCode Remote-SSH Extension</h4>
                    <ol className="text-sm text-gray-300 space-y-2 list-decimal list-inside">
                      <li>Install "Remote - SSH" extension in VSCode</li>
                      <li>Press <kbd className="px-2 py-1 bg-gray-600 rounded text-xs">Ctrl+Shift+P</kbd> (or <kbd className="px-2 py-1 bg-gray-600 rounded text-xs">Cmd+Shift+P</kbd> on Mac)</li>
                      <li>Type "Remote-SSH: Connect to Host"</li>
                      <li>Enter: <code className="bg-gray-600 px-2 py-1 rounded text-xs">{sshInfo?.username}@{publicIp}</code></li>
                      <li>Select your SSH key when prompted</li>
                    </ol>
                  </div>

                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">PyCharm Professional</h4>
                    <ol className="text-sm text-gray-300 space-y-2 list-decimal list-inside">
                      <li>Go to Tools → Deployment → Configuration</li>
                      <li>Add new SFTP configuration</li>
                      <li>Set host to <code className="bg-gray-600 px-2 py-1 rounded text-xs">{publicIp}</code></li>
                      <li>Set username to <code className="bg-gray-600 px-2 py-1 rounded text-xs">{sshInfo?.username}</code></li>
                      <li>Set authentication to "Key pair"</li>
                      <li>Select your private key file</li>
                    </ol>
                  </div>

                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">SSH Config File</h4>
                    <p className="text-sm text-gray-300 mb-2">
                      Add this to your <code className="bg-gray-600 px-2 py-1 rounded text-xs">~/.ssh/config</code>:
                    </p>
                    <div className="bg-gray-600 rounded p-3 font-mono text-sm text-white">
                      Host gpucloud-pod-{podId}<br/>
                      &nbsp;&nbsp;HostName {publicIp}<br/>
                      &nbsp;&nbsp;User {sshInfo?.username}<br/>
                      &nbsp;&nbsp;Port {sshInfo?.port}<br/>
                      &nbsp;&nbsp;IdentityFile ~/.ssh/{sshInfo?.key_name}<br/>
                      &nbsp;&nbsp;ServerAliveInterval 60
                    </div>
                    <button
                      onClick={downloadSSHConfig}
                      className="mt-2 btn-secondary text-sm"
                    >
                      <Download className="w-4 h-4 inline mr-2" />
                      Download SSH Config
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Other Tools Tab */}
          {activeTab === 'other' && (
            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-white mb-3">Other Connection Methods</h3>
                
                <div className="space-y-4">
                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">Command Line SSH</h4>
                    <div className="bg-gray-600 rounded p-3 font-mono text-sm text-white mb-3">
                      {sshInfo?.ssh_command || `ssh -i ~/.ssh/gpucloud-mvp-key ubuntu@${publicIp}`}
                    </div>
                    <button
                      onClick={() => copyToClipboard(sshInfo?.ssh_command || `ssh -i ~/.ssh/gpucloud-mvp-key ubuntu@${publicIp}`)}
                      className="btn-secondary text-sm"
                    >
                      <Copy className="w-4 h-4 inline mr-2" />
                      Copy Command
                    </button>
                  </div>

                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">File Transfer (SCP/SFTP)</h4>
                    <div className="space-y-2 text-sm text-gray-300">
                      <p><strong>Upload file:</strong></p>
                      <div className="bg-gray-600 rounded p-2 font-mono text-xs text-white">
                        scp -i ~/.ssh/gpucloud-mvp-key file.txt ubuntu@{publicIp}:~/
                      </div>
                      
                      <p className="mt-2"><strong>Download file:</strong></p>
                      <div className="bg-gray-600 rounded p-2 font-mono text-xs text-white">
                        scp -i ~/.ssh/gpucloud-mvp-key ubuntu@{publicIp}:~/file.txt ./
                      </div>
                      
                      <p className="mt-2"><strong>Sync directory:</strong></p>
                      <div className="bg-gray-600 rounded p-2 font-mono text-xs text-white">
                        rsync -avz -e "ssh -i ~/.ssh/gpucloud-mvp-key" ./project/ ubuntu@{publicIp}:~/project/
                      </div>
                    </div>
                  </div>

                  <div className="bg-gray-700 rounded-lg p-4">
                    <h4 className="font-medium text-white mb-2">Mobile Apps</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="flex items-center space-x-3 p-3 bg-gray-600 rounded">
                        <Smartphone className="w-5 h-5 text-blue-400" />
                        <div>
                          <p className="text-white font-medium">Termius</p>
                          <p className="text-gray-300 text-xs">iOS & Android</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-3 p-3 bg-gray-600 rounded">
                        <Smartphone className="w-5 h-5 text-green-400" />
                        <div>
                          <p className="text-white font-medium">JuiceSSH</p>
                          <p className="text-gray-300 text-xs">Android</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-3 p-3 bg-gray-600 rounded">
                        <Smartphone className="w-5 h-5 text-purple-400" />
                        <div>
                          <p className="text-white font-medium">Prompt</p>
                          <p className="text-gray-300 text-xs">iOS</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-3 p-3 bg-gray-600 rounded">
                        <Smartphone className="w-5 h-5 text-orange-400" />
                        <div>
                          <p className="text-white font-medium">iTerminal</p>
                          <p className="text-gray-300 text-xs">iOS</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-700 bg-gray-800">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-400">
              <p>💡 <strong>Pro Tip:</strong> Use the web terminal for quick access, SSH for full IDE integration</p>
            </div>
            
            <div className="flex space-x-3">
              <button
                onClick={onClose}
                className="btn-secondary"
              >
                Close
              </button>
              
              <button
                onClick={() => window.open(`https://${publicIp}:22`, '_blank')}
                className="btn-primary"
              >
                <ExternalLink className="w-4 h-4 inline mr-2" />
                Test Connection
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
