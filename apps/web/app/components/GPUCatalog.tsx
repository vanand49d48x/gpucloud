'use client';

import { useState, useEffect } from 'react';
import { X, Star, Search, Filter, HelpCircle, Cpu, MemoryStick, Zap } from 'lucide-react';
import { clientLogger as logger } from '../utils/logger';

interface AWSInstance {
  id: string;
  instance_type: string;
  category: string;
  gpu: any;
  vcpus: number;
  memory_gb: number;
  hourly_usd: number;
  price_with_markup_usd: number;
}

interface GPUCatalogProps {
  isOpen: boolean;
  onClose: () => void;
  onDeploy: (instanceId: string) => void;
}

export default function GPUCatalog({ isOpen, onClose, onDeploy }: GPUCatalogProps) {
  const [selectedInstance, setSelectedInstance] = useState<AWSInstance | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [catalog, setCatalog] = useState<AWSInstance[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch real AWS catalog data
  useEffect(() => {
    logger.info('GPUCatalog useEffect triggered', { isOpen, timestamp: new Date().toISOString() });
    if (isOpen) {
      fetchCatalog();
    }
  }, [isOpen]);

  const fetchCatalog = async () => {
    logger.info('Starting catalog fetch', { timestamp: new Date().toISOString() });
    try {
      const response = await fetch('http://127.0.0.1:8080/v1/catalog/aws');
      logger.info('Catalog API response received', { 
        status: response.status, 
        ok: response.ok,
        timestamp: new Date().toISOString()
      });
      
      if (response.ok) {
        const data = await response.json();
        logger.info('Catalog data parsed successfully', { 
          instanceCount: data.length,
          timestamp: new Date().toISOString()
        });
        setCatalog(data);
      } else {
        logger.warn('Catalog API returned error status, using fallback data', { 
          status: response.status,
          timestamp: new Date().toISOString()
        });
        // Fallback to mock data if API fails
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
          },
          {
            id: 'aws:us-east-1:c7gd.medium',
            instance_type: 'c7gd.medium',
            category: 'CPU',
            gpu: null,
            vcpus: 1,
            memory_gb: 2,
            hourly_usd: 0.0681,
            price_with_markup_usd: 0.0681
          },
          {
            id: 'aws:us-east-1:r6g.medium',
            instance_type: 'r6g.medium',
            category: 'CPU',
            gpu: null,
            vcpus: 1,
            memory_gb: 8,
            hourly_usd: 0.0756,
            price_with_markup_usd: 0.0756
          }
        ]);
      }
    } catch (error) {
      logger.error('Error fetching catalog', { 
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
      logger.info('Catalog fetch completed', { timestamp: new Date().toISOString() });
    }
  };

  // Filter instances based on search and category
  const filteredInstances = catalog.filter(instance => {
    const matchesSearch = instance.instance_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         instance.category.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || instance.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // Group instances by category
  const groupedInstances = filteredInstances.reduce((groups, instance) => {
    const category = instance.category;
    if (!groups[category]) {
      groups[category] = [];
    }
    groups[category].push(instance);
    return groups;
  }, {} as Record<string, AWSInstance[]>);

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'GPU': return <Zap className="w-4 h-4" />;
      case 'CPU': return <Cpu className="w-4 h-4" />;
      case 'Memory': return <MemoryStick className="w-4 h-4" />;
      default: return <Cpu className="w-4 h-4" />;
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'GPU': return 'text-purple-400';
      case 'CPU': return 'text-blue-400';
      case 'Memory': return 'text-green-400';
      default: return 'text-gray-400';
    }
  };

  if (!isOpen) {
    logger.debug('GPUCatalog not open, returning null', { timestamp: new Date().toISOString() });
    return null;
  }

  logger.debug('GPUCatalog rendering', { 
    catalogLength: catalog.length, 
    loading, 
    selectedInstance: selectedInstance?.id,
    timestamp: new Date().toISOString()
  });

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-7xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h1 className="text-2xl font-bold text-gray-900">Deploy a Pod</h1>
          <div className="flex items-center space-x-4">
            <button className="text-blue-600 hover:text-blue-700 text-sm">Help</button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center space-x-4 mb-4">
            <button 
              onClick={() => setSelectedCategory('All')}
              className={`px-4 py-2 rounded-lg font-medium ${
                selectedCategory === 'All' 
                  ? 'bg-blue-100 text-blue-700' 
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              All Types
            </button>
            {Array.from(new Set(catalog.map(i => i.category))).map(category => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  selectedCategory === category 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {category} ▼
              </button>
            ))}
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">
              Any Region ▼
            </button>
            <div className="flex items-center space-x-2">
              <input type="checkbox" className="rounded" />
              <span className="text-sm text-gray-600">Global Networking</span>
            </div>
            <button className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">
              Additional Filters ▼
            </button>
            <button className="ml-auto px-6 py-2 bg-gray-600 text-white rounded-lg font-medium">
              Select an Instance
            </button>
          </div>

          {/* Search */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 flex-1">
              <Search className="w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search by instance type, category, or specs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded text-sm w-full max-w-md"
              />
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {loading ? (
            <div className="text-center py-8">
              <div className="text-gray-500">Loading instances...</div>
            </div>
          ) : (
            Object.entries(groupedInstances).map(([category, instances]) => (
              <div key={category} className="mb-8">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-2">
                    {getCategoryIcon(category)}
                    <h2 className="text-lg font-semibold text-gray-900">{category} Instances</h2>
                    <span className="text-sm text-gray-500">({instances.length})</span>
                  </div>
                  <button className="text-gray-500 hover:text-gray-700">▼</button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {instances.map((instance) => (
                    <div
                      key={instance.id}
                      className={`p-4 border rounded-lg cursor-pointer transition-all hover:shadow-md ${
                        selectedInstance?.id === instance.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                      }`}
                                             onClick={() => {
                         logger.info('Instance selected', { 
                           instanceId: instance.id, 
                           instanceType: instance.instance_type,
                           timestamp: new Date().toISOString()
                         });
                         setSelectedInstance(instance);
                       }}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="font-semibold text-gray-900">{instance.instance_type}</h3>
                        <span className={`text-xs px-2 py-1 rounded-full ${getCategoryColor(category)} bg-gray-100`}>
                          {category}
                        </span>
                      </div>
                      
                      <div className="text-sm text-gray-600 mb-3">
                        <div className="flex items-center space-x-4">
                          <span className="flex items-center space-x-1">
                            <Cpu className="w-3 h-3" />
                            <span>{instance.vcpus} vCPU</span>
                          </span>
                          <span className="flex items-center space-x-1">
                            <MemoryStick className="w-3 h-3" />
                            <span>{instance.memory_gb} GB RAM</span>
                          </span>
                        </div>
                        {instance.gpu && (
                          <div className="mt-1 text-purple-600">
                            <Zap className="w-3 h-3 inline mr-1" />
                            {instance.gpu.gpu_count}x {instance.gpu.gpu_model}
                          </div>
                        )}
                      </div>
                      
                      <div className="text-right">
                        <div className="text-lg font-bold text-gray-900">
                          ${instance.price_with_markup_usd}/hr
                        </div>
                        <div className="text-sm text-gray-500">
                          ${(instance.price_with_markup_usd / 60).toFixed(4)}/min
                        </div>
                        {instance.hourly_usd !== instance.price_with_markup_usd && (
                          <div className="text-xs text-gray-400 line-through">
                            Base: ${instance.hourly_usd}/hr
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
          
          {!loading && filteredInstances.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              No instances found matching your criteria.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center">
            {/* Debug Panel */}
            <div className="flex items-center space-x-2">
              <button
                onClick={() => {
                  const logs = logger.getLogs();
                  console.log('=== FRONTEND LOGS ===');
                  logs.forEach(log => console.log(log));
                  console.log('=== END LOGS ===');
                }}
                className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                View Logs
              </button>
              <button
                onClick={() => {
                  const logs = logger.exportLogs();
                  const blob = new Blob([logs], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `frontend-logs-${new Date().toISOString()}.txt`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Export Logs
              </button>
            </div>
            
            {/* Action Buttons */}
            <div className="flex space-x-3">
              <button
                onClick={onClose}
                className="px-6 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (selectedInstance) {
                    logger.info('Deploy button clicked', { 
                      instanceId: selectedInstance.id, 
                      instanceType: selectedInstance.instance_type,
                      timestamp: new Date().toISOString()
                    });
                    onDeploy(selectedInstance.id);
                  }
                }}
                disabled={!selectedInstance}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Deploy Instance
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
