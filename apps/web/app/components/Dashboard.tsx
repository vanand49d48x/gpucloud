'use client';

import { useState } from 'react';
import { 
  Home, 
  Search, 
  Server, 
  Database, 
  Settings, 
  ChevronUp,
  ChevronDown,
  HelpCircle,
  LogOut
} from 'lucide-react';

import PodManager from './PodManager';
import { useAuth } from '../contexts/AuthContext';

export default function Dashboard() {
  const { logout } = useAuth();
  const [manageExpanded, setManageExpanded] = useState(true);
  const [accountExpanded, setAccountExpanded] = useState(true);



  return (
    <div className="flex h-screen bg-black">
      {/* Left Sidebar */}
      <div className="w-64 bg-gray-900 border-r border-gray-800 p-4 flex flex-col">
        {/* Top Section */}
        <div className="mb-8">
          <h1 className="text-xl font-bold text-white mb-2">vsl.and</h1>
          <div className="text-2xl font-bold text-white mb-1">$2.41</div>
          <div className="text-sm text-gray-400 mb-3">1d 18h left at current spend rate</div>
          <button className="w-full btn-primary text-sm">
            $ Refer & Earn
          </button>
        </div>

        {/* Navigation */}
        <nav className="space-y-2">
          <a href="#" className="sidebar-item">
            <Home className="w-5 h-5 mr-3" />
            Home
          </a>
          
          <a href="#" className="sidebar-item">
            <Search className="w-5 h-5 mr-3" />
            Explore
          </a>
          
          <a href="#" className="sidebar-item">
            <Server className="w-5 h-5 mr-3" />
            Hub
          </a>

          {/* Manage Section */}
          <div>
            <button
              onClick={() => setManageExpanded(!manageExpanded)}
              className="sidebar-item w-full justify-between"
            >
              <span className="flex items-center">
                <Database className="w-5 h-5 mr-3" />
                Manage
              </span>
              {manageExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            
            {manageExpanded && (
              <div className="ml-8 mt-2 space-y-1">
                <a href="#" className="sidebar-item text-sm">Serverless</a>
                <a href="#" className="sidebar-item text-sm active">Pods</a>
                <a href="#" className="sidebar-item text-sm">Fine Tuning</a>
                <a href="#" className="sidebar-item text-sm">Instant Clusters</a>
                <a href="#" className="sidebar-item text-sm">Storage</a>
                <a href="#" className="sidebar-item text-sm">My Templates</a>
                <a href="#" className="sidebar-item text-sm">Secrets</a>
              </div>
            )}
          </div>

          {/* Account Section */}
          <div>
            <button
              onClick={() => setAccountExpanded(!accountExpanded)}
              className="sidebar-item w-full justify-between"
            >
              <span className="flex items-center">
                <Settings className="w-5 h-5 mr-3" />
                Account
              </span>
              {accountExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            
            {accountExpanded && (
              <div className="ml-8 mt-2 space-y-1">
                <a href="#" className="sidebar-item text-sm">Settings</a>
                <a href="#" className="sidebar-item text-sm">Billing</a>
                <a href="#" className="sidebar-item text-sm">Savings Plans</a>
                <a href="#" className="sidebar-item text-sm">Team</a>
                <a href="#" className="sidebar-item text-sm">Audit Logs</a>
                <a href="#" className="sidebar-item text-sm">Remote Access</a>
              </div>
            )}
          </div>
          
          {/* Logout Button */}
          <div className="mt-auto pt-8">
            <button
              onClick={logout}
              className="sidebar-item w-full text-red-400 hover:text-red-300"
            >
              <LogOut className="w-5 h-5 mr-3" />
              Logout
            </button>
          </div>
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">Pods</h1>
          <button className="btn-secondary">
            <HelpCircle className="w-4 h-4 mr-2" />
            Help
          </button>
        </div>

        {/* Pod Manager - Real Integration */}
        <PodManager />

        {/* Footer */}
        <div className="text-sm text-gray-400 mt-6">
          Note: All pod prices are updated weekly at Monday, 8:00 PM EDT to match standard prices on deploy page.
        </div>
      </div>
    </div>
  );
}
