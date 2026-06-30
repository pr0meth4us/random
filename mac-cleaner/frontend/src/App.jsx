import { useState, useEffect } from 'react';
import './index.css';

const API_BASE = 'http://localhost:8000/api';

function formatBytes(bytes, decimals = 2) {
  if (bytes === undefined || bytes === null || isNaN(bytes) || bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

const DEV_CACHES = ['ms-playwright', 'ms-playwright-go', 'pip', 'Homebrew', 'node-gyp', 'next-swc', 'typescript', 'NPM Cache', 'Pip Cache'];

function isDeveloperCache(category, itemName) {
  if (category === 'NPM Cache' || category === 'Pip Cache') return true;
  return DEV_CACHES.includes(itemName);
}

export default function App() {
  const [activeTab, setActiveTab] = useState('smart-scan');
  const [sysInfo, setSysInfo] = useState(null);
  
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [scanResults, setScanResults] = useState([]);
  
  const [selectedPaths, setSelectedPaths] = useState(new Set());
  const [cleaning, setCleaning] = useState(false);

  // Space Lens state
  const [inspectPath, setInspectPath] = useState('~/Documents');
  const [inspecting, setInspecting] = useState(false);
  const [inspectResults, setInspectResults] = useState(null);
  const [inspectError, setInspectError] = useState(null);

  // Duplicates state
  const [duplicatePath, setDuplicatePath] = useState('~/Downloads');
  const [scanningDups, setScanningDups] = useState(false);
  const [duplicateResults, setDuplicateResults] = useState(null);
  const [duplicateError, setDuplicateError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/system-info`)
      .then(res => res.json())
      .then(data => setSysInfo(data))
      .catch(err => console.error("Failed to fetch sys info", err));
  }, []);

  const handleScan = async () => {
    setScanning(true);
    setScanned(false);
    setSelectedPaths(new Set());
    
    try {
      const res = await fetch(`${API_BASE}/scan`);
      const data = await res.json();
      setScanResults(data.scanResults || []);
      
      const allPaths = new Set();
      (data.scanResults || []).forEach(cat => {
        cat.items.forEach(item => {
          if (!isDeveloperCache(cat.category, item.name)) {
            allPaths.add(item.path);
          }
        });
      });
      setSelectedPaths(allPaths);
      
    } catch (err) {
      console.error("Scan failed", err);
    } finally {
      setScanning(false);
      setScanned(true);
    }
  };

  const handleInspect = async () => {
    if (!inspectPath.trim()) return;
    setInspecting(true);
    setInspectError(null);
    setInspectResults(null);
    try {
      const res = await fetch(`${API_BASE}/inspect?path=${encodeURIComponent(inspectPath)}`);
      if (!res.ok) {
        throw new Error("Directory not found or permission denied");
      }
      const data = await res.json();
      setInspectResults(data);
    } catch (err) {
      setInspectError(err.message);
    } finally {
      setInspecting(false);
    }
  };

  const handleScanDuplicates = async () => {
    if (!duplicatePath.trim()) return;
    setScanningDups(true);
    setDuplicateError(null);
    setDuplicateResults(null);
    try {
      const res = await fetch(`${API_BASE}/duplicates?path=${encodeURIComponent(duplicatePath)}`);
      if (!res.ok) {
        throw new Error("Directory not found or permission denied");
      }
      const data = await res.json();
      setDuplicateResults(data);
      
      // Auto-select all but the first item in each duplicate group
      const pathsToDelete = new Set(selectedPaths);
      (data.duplicateGroups || []).forEach(group => {
        for (let i = 1; i < group.items.length; i++) {
          pathsToDelete.add(group.items[i].path);
        }
      });
      setSelectedPaths(pathsToDelete);
    } catch (err) {
      setDuplicateError(err.message);
    } finally {
      setScanningDups(false);
    }
  };

  const toggleSelection = (path) => {
    const newSet = new Set(selectedPaths);
    if (newSet.has(path)) {
      newSet.delete(path);
    } else {
      newSet.add(path);
    }
    setSelectedPaths(newSet);
  };

  const handleClean = async () => {
    if (selectedPaths.size === 0) return;
    
    if (!confirm(`Are you sure you want to permanently delete ${selectedPaths.size} items?`)) return;

    setCleaning(true);
    try {
      const res = await fetch(`${API_BASE}/clean`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: Array.from(selectedPaths) })
      });
      const data = await res.json();
      
      alert(`Cleaned up ${formatBytes(data.deletedSizeBytes)}!`);
      setScanned(false);
      setScanResults([]);
      setSelectedPaths(new Set());
      
      fetch(`${API_BASE}/system-info`)
        .then(res => res.json())
        .then(data => setSysInfo(data));
        
    } catch (err) {
      console.error("Clean failed", err);
      alert("Failed to clean some files.");
    } finally {
      setCleaning(false);
    }
  };

  const totalJunkSize = scanResults.reduce((acc, cat) => acc + cat.totalSizeBytes, 0);

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="url(#gradient)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <defs>
              <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#ff5e9c" />
                <stop offset="100%" stopColor="#ff9b6a" />
              </linearGradient>
            </defs>
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
            <line x1="12" y1="22.08" x2="12" y2="12"></line>
          </svg>
          Mac Cleaner
        </div>
        
        <div 
          className={`nav-item ${activeTab === 'smart-scan' ? 'active' : ''}`}
          onClick={() => setActiveTab('smart-scan')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          Smart Scan
        </div>
        <div 
          className={`nav-item ${activeTab === 'system-junk' ? 'active' : ''}`}
          onClick={() => setActiveTab('system-junk')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          System Junk
        </div>
        <div 
          className={`nav-item ${activeTab === 'space-lens' ? 'active' : ''}`}
          onClick={() => setActiveTab('space-lens')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          Space Lens
        </div>
        <div 
          className={`nav-item ${activeTab === 'duplicates' ? 'active' : ''}`}
          onClick={() => setActiveTab('duplicates')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          Duplicates
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        <div className="dashboard-header">
          <h1>
            {activeTab === 'smart-scan' && 'Smart Scan'}
            {activeTab === 'system-junk' && 'System Junk'}
            {activeTab === 'space-lens' && 'Space Lens'}
            {activeTab === 'duplicates' && 'Duplicates'}
          </h1>
          <p>
            {activeTab === 'space-lens' 
              ? 'Inspect any folder to see what is taking up space.' 
              : activeTab === 'duplicates'
              ? 'Find and remove identical files to free up space.'
              : 'Safely remove unnecessary files and regain space.'}
          </p>
        </div>

        {(activeTab === 'smart-scan' || activeTab === 'system-junk') && (
          <>
            {sysInfo && !scanned && !scanning && (
              <div className="gauge-container">
                <div className="scan-ring">
                  <div className="ring-content">
                    <div className="ring-title">Free Space</div>
                    <div className="ring-value">{formatBytes(sysInfo.free)}</div>
                  </div>
                </div>
              </div>
            )}

            {scanning && (
              <div className="gauge-container">
                <div className="scan-ring scanning">
                  <div className="ring-content">
                    <div className="ring-title">Scanning...</div>
                    <div className="ring-value" style={{ fontSize: '2rem', color: 'var(--text-secondary)' }}>Searching for junk</div>
                  </div>
                </div>
              </div>
            )}

            {!scanned && !scanning && (
              <button className="action-btn" onClick={handleScan}>
                Scan Now
              </button>
            )}

            {scanned && !scanning && scanResults.length === 0 && (
              <div style={{textAlign: 'center', marginTop: '60px'}}>
                <h2 style={{color: 'var(--success-color)'}}>Your Mac is clean!</h2>
                <p style={{color: 'var(--text-secondary)', marginTop: '10px'}}>No junk files found in targeted directories.</p>
                <button className="action-btn" onClick={() => setScanned(false)}>Back</button>
              </div>
            )}

            {scanned && scanResults.length > 0 && (
              <div className="results-container">
                <div className="flex justify-between items-center mb-4">
                  <h2>Found {formatBytes(totalJunkSize)} of junk</h2>
                  <button 
                    className="action-btn clean" 
                    style={{ margin: 0, padding: '10px 24px', fontSize: '1rem' }}
                    onClick={handleClean}
                    disabled={selectedPaths.size === 0 || cleaning}
                  >
                    {cleaning ? 'Cleaning...' : `Clean Selected`}
                  </button>
                </div>

                {scanResults.map((cat, i) => (
                  <div key={i} className="category-block">
                    <div className="category-header">
                      <div className="category-title">{cat.category}</div>
                      <div className="category-size">{formatBytes(cat.totalSizeBytes)}</div>
                    </div>
                    <div className="item-list">
                      {cat.items.map((item, j) => {
                        const isDev = isDeveloperCache(cat.category, item.name);
                        return (
                          <div key={j} className="file-item">
                            <div className="flex items-center gap-3">
                              <input 
                                type="checkbox" 
                                className="custom-checkbox"
                                checked={selectedPaths.has(item.path)}
                                onChange={() => toggleSelection(item.path)}
                              />
                              <div className="file-info">
                                <span className="file-name">
                                  {item.name}
                                  {isDev && (
                                    <span style={{
                                      marginLeft: '8px',
                                      fontSize: '0.75rem',
                                      color: 'var(--warning-color)',
                                      background: 'rgba(241, 250, 140, 0.1)',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      fontWeight: '600'
                                    }}>
                                      ⚠️ Dev Cache (Slows down next build)
                                    </span>
                                  )}
                                </span>
                                <span className="file-path">{item.path}</span>
                              </div>
                            </div>
                            <div className="file-size">{formatBytes(item.sizeBytes)}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Space Lens Tab Content */}
        {activeTab === 'space-lens' && (
          <div>
            <div style={{ display: 'flex', gap: '16px', marginBottom: '32px' }}>
              <input 
                type="text" 
                value={inspectPath}
                onChange={(e) => setInspectPath(e.target.value)}
                placeholder="Enter path (e.g. ~/Documents)"
                style={{
                  flex: 1,
                  padding: '16px 20px',
                  borderRadius: '12px',
                  border: '1px solid var(--glass-border)',
                  background: 'var(--glass-bg)',
                  color: 'white',
                  fontSize: '1.1rem',
                  outline: 'none'
                }}
              />
              <button 
                className="action-btn" 
                style={{ margin: 0, borderRadius: '12px', padding: '16px 32px' }}
                onClick={handleInspect}
                disabled={inspecting}
              >
                {inspecting ? 'Inspecting...' : 'Inspect'}
              </button>
            </div>

            {inspectError && (
              <div style={{ color: 'var(--danger-color)', background: 'rgba(255, 85, 85, 0.1)', padding: '16px', borderRadius: '12px' }}>
                {inspectError}
              </div>
            )}

            {inspectResults && (
              <div className="results-container">
                <div className="flex justify-between items-center mb-4">
                  <h2>Directory Size: {formatBytes(inspectResults.totalSizeBytes)}</h2>
                </div>
                
                <div className="category-block">
                  <div className="item-list">
                    {inspectResults.items.length === 0 ? (
                      <p style={{color: 'var(--text-secondary)', padding: '16px'}}>This directory is empty.</p>
                    ) : (
                      inspectResults.items.map((item, j) => (
                        <div key={j} className="file-item" style={{cursor: 'pointer'}} onClick={() => {
                          // Allow clicking on a folder to drill down
                          setInspectPath(item.path);
                          // Auto trigger inspect for the new path
                          // We'll need a useEffect for clean drilldown, but for now just update input
                        }}>
                          <div className="flex items-center gap-3">
                            <div className="file-info">
                              <span className="file-name" style={{fontSize: '1rem', fontWeight: 500}}>{item.name}</span>
                            </div>
                          </div>
                          <div className="file-size" style={{fontWeight: 600, color: 'var(--text-primary)'}}>{formatBytes(item.sizeBytes)}</div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Duplicates Tab Content */}
        {activeTab === 'duplicates' && (
          <div>
            <div style={{ display: 'flex', gap: '16px', marginBottom: '32px' }}>
              <input 
                type="text" 
                value={duplicatePath}
                onChange={(e) => setDuplicatePath(e.target.value)}
                placeholder="Enter path (e.g. ~/Downloads)"
                style={{
                  flex: 1,
                  padding: '16px 20px',
                  borderRadius: '12px',
                  border: '1px solid var(--glass-border)',
                  background: 'var(--glass-bg)',
                  color: 'white',
                  fontSize: '1.1rem',
                  outline: 'none'
                }}
              />
              <button 
                className="action-btn" 
                style={{ margin: 0, borderRadius: '12px', padding: '16px 32px' }}
                onClick={handleScanDuplicates}
                disabled={scanningDups}
              >
                {scanningDups ? 'Scanning...' : 'Scan'}
              </button>
            </div>

            {duplicateError && (
              <div style={{ color: 'var(--danger-color)', background: 'rgba(255, 85, 85, 0.1)', padding: '16px', borderRadius: '12px' }}>
                {duplicateError}
              </div>
            )}

            {duplicateResults && (
              <div className="results-container">
                <div className="flex justify-between items-center mb-4">
                  <h2>Found {formatBytes(duplicateResults.totalWastedBytes)} in duplicates</h2>
                  <button 
                    className="action-btn clean" 
                    style={{ margin: 0, padding: '10px 24px', fontSize: '1rem' }}
                    onClick={handleClean}
                    disabled={selectedPaths.size === 0 || cleaning}
                  >
                    {cleaning ? 'Cleaning...' : `Clean Selected`}
                  </button>
                </div>
                
                {duplicateResults.duplicateGroups.length === 0 ? (
                  <p style={{color: 'var(--success-color)', padding: '16px'}}>No large duplicate files found!</p>
                ) : (
                  duplicateResults.duplicateGroups.map((group, i) => (
                    <div key={i} className="category-block" style={{ borderBottom: '1px solid var(--glass-border)', paddingBottom: '16px' }}>
                      <div className="category-header">
                        <div className="category-title" style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                          Identical Files (Size: {formatBytes(group.sizeBytes)})
                        </div>
                        <div className="category-size" style={{ color: 'var(--warning-color)' }}>
                          Wasted: {formatBytes(group.totalWastedBytes)}
                        </div>
                      </div>
                      <div className="item-list">
                        {group.items.map((item, j) => (
                          <div key={j} className="file-item">
                            <div className="flex items-center gap-3">
                              <input 
                                type="checkbox" 
                                className="custom-checkbox"
                                checked={selectedPaths.has(item.path)}
                                onChange={() => toggleSelection(item.path)}
                              />
                              <div className="file-info">
                                <span className="file-name">{item.name}</span>
                                <span className="file-path">{item.path}</span>
                              </div>
                            </div>
                            {j === 0 && (
                              <span style={{ fontSize: '0.8rem', color: 'var(--success-color)', background: 'rgba(80, 250, 123, 0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                                Kept Safe
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
