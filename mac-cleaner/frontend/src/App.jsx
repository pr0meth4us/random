import { useState } from 'react';
import './index.css';

const API_BASE = 'http://localhost:8000/api';

// Categories that are genuinely safe to bulk-select as "junk."
// Personal folders (Documents, Downloads, Applications) are deliberately
// excluded — they should never be pre-checked for deletion.
const SAFE_JUNK_CATEGORIES = new Set(['User Caches', 'Trash', 'NPM Cache', 'Pip Cache']);
const DEV_CACHE_NAMES = new Set(['ms-playwright', 'ms-playwright-go', 'pip', 'Homebrew', 'node-gyp', 'next-swc', 'typescript']);

const CATEGORY_STYLE = {
  'User Caches':        { color: '#8e8e93', icon: 'cache' },
  'Trash':               { color: '#ff453a', icon: 'trash' },
  'NPM Cache':           { color: '#ff9f0a', icon: 'terminal' },
  'Pip Cache':           { color: '#ff9f0a', icon: 'terminal' },
  'Documents':           { color: '#0a84ff', icon: 'doc' },
  'Downloads':           { color: '#0a84ff', icon: 'doc' },
  'System Applications': { color: '#bf5af2', icon: 'app' },
  'User Applications':   { color: '#bf5af2', icon: 'app' },
};
const FALLBACK_COLORS = ['#8e8e93', '#0a84ff', '#ff9f0a', '#32d74b', '#bf5af2', '#ff453a'];

function categoryStyle(name, index) {
  return CATEGORY_STYLE[name] || { color: FALLBACK_COLORS[index % FALLBACK_COLORS.length], icon: 'cache' };
}

function isDeveloperCache(category, itemName) {
  if (category === 'NPM Cache' || category === 'Pip Cache') return true;
  return DEV_CACHE_NAMES.has(itemName);
}

function formatBytes(bytes) {
  if (!bytes) return '0 KB';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/* ---------------- icons ---------------- */
const Icon = {
  scan: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M9 3H5a2 2 0 0 0-2 2v4M15 3h4a2 2 0 0 1 2 2v4M9 21H5a2 2 0 0 1-2-2v-4M15 21h4a2 2 0 0 0 2-2v-4" /></svg>,
  junk: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6" /></svg>,
  lens: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>,
  dup: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>,
  large: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>,
  cache: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="9" {...p} /><path d="M12 7v5l3 2" {...p} /></svg>,
  trash: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13" {...p} /></svg>,
  terminal: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m5 7 5 5-5 5M12 17h7" {...p} /></svg>,
  doc: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6" {...p} /></svg>,
  app: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="4" {...p} /></svg>,
  info: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" {...p} /><path d="M12 8h.01M11 12h1v4h1" {...p} /></svg>,
  checkCircle: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="9" /><path d="m8.5 12.5 2.5 2.5 5-5" /></svg>,
};

function RowIcon({ category, index }) {
  const style = categoryStyle(category, index);
  const IconComp = Icon[style.icon] || Icon.cache;
  return (
    <div className="row-icon" style={{ background: `${style.color}26`, color: style.color }}>
      <IconComp />
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState('smart-scan');

  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [scanResults, setScanResults] = useState([]);
  const [selectedPaths, setSelectedPaths] = useState(new Set());
  const [cleaning, setCleaning] = useState(false);

  // Space Lens
  const [inspectInput, setInspectInput] = useState('~/Documents');
  const [inspecting, setInspecting] = useState(false);
  const [inspectResults, setInspectResults] = useState(null);
  const [inspectError, setInspectError] = useState(null);

  // Duplicates
  const [duplicatePath, setDuplicatePath] = useState('~/Downloads');
  const [scanningDups, setScanningDups] = useState(false);
  const [duplicateResults, setDuplicateResults] = useState(null);
  const [duplicateError, setDuplicateError] = useState(null);
  const [dupKeep, setDupKeep] = useState({}); // hash -> path kept

  // Large files
  const [largeFilesPath, setLargeFilesPath] = useState('~/');
  const [scanningLarge, setScanningLarge] = useState(false);
  const [largeFilesResults, setLargeFilesResults] = useState(null);
  const [largeFilesError, setLargeFilesError] = useState(null);

  const togglePath = (path) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  };

  const clearSelection = () => setSelectedPaths(new Set());

  /* ---------------- Smart Scan / System Junk ---------------- */
  const handleScan = async () => {
    setScanning(true);
    setScanned(false);
    clearSelection();
    try {
      const res = await fetch(`${API_BASE}/scan`);
      const data = await res.json();
      setScanResults(data.scanResults || []);
    } finally {
      setScanning(false);
      setScanned(true);
    }
  };

  const selectSafeJunk = () => {
    const next = new Set();
    scanResults.forEach((cat) => {
      if (!SAFE_JUNK_CATEGORIES.has(cat.category)) return;
      cat.items.forEach((item) => next.add(item.path));
    });
    setSelectedPaths(next);
  };

  const totalJunkSize = scanResults.reduce((acc, c) => acc + c.totalSizeBytes, 0);
  const totalScanSize = scanResults.reduce((acc, c) => acc + c.totalSizeBytes, 0);

  /* ---------------- Space Lens ---------------- */
  const runInspect = async (rawPath) => {
    if (!rawPath.trim()) return;
    setInspecting(true);
    setInspectError(null);
    try {
      const res = await fetch(`${API_BASE}/inspect?path=${encodeURIComponent(rawPath)}`);
      if (!res.ok) throw new Error('Folder not found, or permission was denied.');
      const data = await res.json();
      setInspectResults(data);
      setInspectInput(data.path);
    } catch (err) {
      setInspectError(err.message);
      setInspectResults(null);
    } finally {
      setInspecting(false);
    }
  };

  const breadcrumbSegments = () => {
    if (!inspectResults) return [];
    const parts = inspectResults.path.split('/').filter(Boolean);
    return parts.map((part, i) => ({
      label: part,
      fullPath: '/' + parts.slice(0, i + 1).join('/'),
    }));
  };

  /* ---------------- Duplicates ---------------- */
  const handleScanDuplicates = async () => {
    if (!duplicatePath.trim()) return;
    setScanningDups(true);
    setDuplicateError(null);
    setDuplicateResults(null);
    setDupKeep({});
    try {
      const res = await fetch(`${API_BASE}/duplicates?path=${encodeURIComponent(duplicatePath)}`);
      if (!res.ok) throw new Error('Folder not found, or permission was denied.');
      const data = await res.json();
      setDuplicateResults(data);
      const keep = {};
      (data.duplicateGroups || []).forEach((g) => { keep[g.hash] = g.items[0].path; });
      setDupKeep(keep);
    } catch (err) {
      setDuplicateError(err.message);
    } finally {
      setScanningDups(false);
    }
  };

  const selectSuggestedDuplicates = () => {
    const next = new Set(selectedPaths);
    (duplicateResults?.duplicateGroups || []).forEach((group) => {
      const keepPath = dupKeep[group.hash];
      group.items.forEach((item) => {
        if (item.path !== keepPath) next.add(item.path);
        else next.delete(item.path);
      });
    });
    setSelectedPaths(next);
  };

  /* ---------------- Large files ---------------- */
  const handleScanLargeFiles = async () => {
    if (!largeFilesPath.trim()) return;
    setScanningLarge(true);
    setLargeFilesError(null);
    setLargeFilesResults(null);
    try {
      const res = await fetch(`${API_BASE}/large-files?path=${encodeURIComponent(largeFilesPath)}`);
      if (!res.ok) throw new Error('Folder not found, or permission was denied.');
      const data = await res.json();
      setLargeFilesResults(data);
    } catch (err) {
      setLargeFilesError(err.message);
    } finally {
      setScanningLarge(false);
    }
  };

  /* ---------------- Clean action ---------------- */
  const handleClean = async () => {
    if (selectedPaths.size === 0) return;
    if (!confirm(`Move ${selectedPaths.size} item(s) to the Trash? You can restore them from Trash afterward.`)) return;

    setCleaning(true);
    try {
      const res = await fetch(`${API_BASE}/clean`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: Array.from(selectedPaths) }),
      });
      const data = await res.json();
      clearSelection();
      setScanned(false);
      setScanResults([]);
      setDuplicateResults(null);
      setLargeFilesResults(null);
      alert(`Moved ${formatBytes(data.deletedSizeBytes)} to Trash.`);
    } catch (err) {
      alert('Something went wrong while cleaning up. No files were removed.');
    } finally {
      setCleaning(false);
    }
  };

  const NAV_ITEMS = [
    { id: 'smart-scan', label: 'Smart Scan', icon: Icon.scan },
    { id: 'system-junk', label: 'System Junk', icon: Icon.junk },
    { id: 'space-lens', label: 'Space Lens', icon: Icon.lens },
    { id: 'duplicates', label: 'Duplicates', icon: Icon.dup },
    { id: 'large-files', label: 'Large Files', icon: Icon.large },
  ];

  const PAGE_COPY = {
    'smart-scan': ['Smart Scan', 'One scan, everything that\u2019s safe to remove.'],
    'system-junk': ['System Junk', 'Review each category and choose exactly what to remove.'],
    'space-lens': ['Space Lens', 'Browse any folder to see what\u2019s using space.'],
    'duplicates': ['Duplicates', 'Find identical files and keep only one copy.'],
    'large-files': ['Large Files', 'Find large files taking up space, sorted by size.'],
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Icon.scan className="brand-mark" />
          Cleaner
        </div>
        <nav className="nav-list">
          {NAV_ITEMS.map((item) => (
            <div
              key={item.id}
              className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              <item.icon className="nav-icon" />
              {item.label}
            </div>
          ))}
        </nav>
      </aside>

      <div className="main-wrap">
        <main className="main">
          <header className="page-header">
            <h1 className="page-title">{PAGE_COPY[activeTab][0]}</h1>
            <p className="page-subtitle">{PAGE_COPY[activeTab][1]}</p>
          </header>

          <div className="panel">
            {activeTab === 'smart-scan' && (
              <SmartScanView
                scanning={scanning}
                scanned={scanned}
                scanResults={scanResults}
                totalScanSize={totalScanSize}
                onScan={handleScan}
                onSelectSafeJunk={selectSafeJunk}
                selectedPaths={selectedPaths}
              />
            )}

            {activeTab === 'system-junk' && (
              <SystemJunkView
                scanning={scanning}
                scanned={scanned}
                scanResults={scanResults}
                onScan={handleScan}
                selectedPaths={selectedPaths}
                togglePath={togglePath}
              />
            )}

            {activeTab === 'space-lens' && (
              <SpaceLensView
                inspectInput={inspectInput}
                setInspectInput={setInspectInput}
                inspecting={inspecting}
                inspectResults={inspectResults}
                inspectError={inspectError}
                runInspect={runInspect}
                breadcrumbSegments={breadcrumbSegments}
              />
            )}

            {activeTab === 'duplicates' && (
              <DuplicatesView
                duplicatePath={duplicatePath}
                setDuplicatePath={setDuplicatePath}
                scanningDups={scanningDups}
                duplicateResults={duplicateResults}
                duplicateError={duplicateError}
                onScan={handleScanDuplicates}
                dupKeep={dupKeep}
                setDupKeep={setDupKeep}
                onSelectSuggested={selectSuggestedDuplicates}
                selectedPaths={selectedPaths}
                togglePath={togglePath}
              />
            )}

            {activeTab === 'large-files' && (
              <LargeFilesView
                largeFilesPath={largeFilesPath}
                setLargeFilesPath={setLargeFilesPath}
                scanningLarge={scanningLarge}
                largeFilesResults={largeFilesResults}
                largeFilesError={largeFilesError}
                onScan={handleScanLargeFiles}
                selectedPaths={selectedPaths}
                togglePath={togglePath}
              />
            )}
          </div>
        </main>

        {selectedPaths.size > 0 && (
          <div className="clean-bar">
            <div className="clean-bar-info">
              <div className="clean-bar-count">{selectedPaths.size} item{selectedPaths.size === 1 ? '' : 's'} selected</div>
              <div className="clean-bar-size">Ready to move to Trash</div>
            </div>
            <div className="clean-bar-actions">
              <button className="btn btn-secondary" onClick={clearSelection}>Clear</button>
              <button className="btn btn-danger" onClick={handleClean} disabled={cleaning}>
                {cleaning ? 'Moving to Trash…' : 'Clean'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Smart Scan — hero storage bar + one-click safe clean
   ============================================================ */
function SmartScanView({ scanning, scanned, scanResults, totalScanSize, onScan, onSelectSafeJunk, selectedPaths }) {
  if (!scanned && !scanning) {
    return (
      <div className="hero-card" style={{ textAlign: 'center', padding: '48px 28px' }}>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 20, fontSize: 13 }}>
          Scans caches, logs, and known junk locations. Nothing is removed until you review and confirm.
        </p>
        <button className="btn btn-primary btn-lg" onClick={onScan}>Scan Now</button>
      </div>
    );
  }

  if (scanning) {
    return <div className="loading-state">Scanning your Mac…</div>;
  }

  if (scanResults.length === 0) {
    return (
      <div className="empty-clean-state">
        <Icon.checkCircle className="empty-clean-icon" />
        <div className="empty-clean-title">Nothing to clean</div>
        <div className="empty-clean-sub">No junk found in the scanned locations.</div>
        <button className="btn btn-secondary" style={{ marginTop: 20 }} onClick={onScan}>Scan Again</button>
      </div>
    );
  }

  const safeCategories = scanResults.filter((c) => SAFE_JUNK_CATEGORIES.has(c.category));
  const safeTotal = safeCategories.reduce((a, c) => a + c.totalSizeBytes, 0);

  return (
    <div className="hero-card">
      <div className="hero-figure">{formatBytes(totalScanSize)}</div>
      <div className="hero-label">found across {scanResults.length} location{scanResults.length === 1 ? '' : 's'}</div>

      <div className="storage-bar">
        {scanResults.map((cat, i) => {
          const style = categoryStyle(cat.category, i);
          const pct = Math.max((cat.totalSizeBytes / totalScanSize) * 100, 1.5);
          return <div key={cat.category} className="storage-segment" style={{ flexBasis: `${pct}%`, background: style.color }} />;
        })}
      </div>

      <div className="storage-legend">
        {scanResults.map((cat, i) => {
          const style = categoryStyle(cat.category, i);
          return (
            <div key={cat.category} className="legend-item">
              <span className="legend-dot" style={{ background: style.color }} />
              {cat.category} <span className="legend-size">{formatBytes(cat.totalSizeBytes)}</span>
            </div>
          );
        })}
      </div>

      <div className="hero-actions">
        <button className="btn btn-primary" onClick={onSelectSafeJunk} disabled={safeTotal === 0}>
          Select Safe Junk ({formatBytes(safeTotal)})
        </button>
        <button className="btn btn-ghost" onClick={onScan}>Rescan</button>
      </div>

      {scanResults.some((c) => !SAFE_JUNK_CATEGORIES.has(c.category)) && (
        <div className="protected-note">
          <Icon.info />
          Documents, Downloads, and Applications are shown for context but are never auto-selected. Review those in System Junk if you want to remove anything from them.
        </div>
      )}
    </div>
  );
}

/* ============================================================
   System Junk — granular per-category review
   ============================================================ */
function SystemJunkView({ scanning, scanned, scanResults, onScan, selectedPaths, togglePath }) {
  if (!scanned && !scanning) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 0' }}>
        <button className="btn btn-primary btn-lg" onClick={onScan}>Scan Now</button>
      </div>
    );
  }
  if (scanning) return <div className="loading-state">Scanning your Mac…</div>;
  if (scanResults.length === 0) {
    return (
      <div className="empty-clean-state">
        <Icon.checkCircle className="empty-clean-icon" />
        <div className="empty-clean-title">Nothing to clean</div>
        <button className="btn btn-secondary" style={{ marginTop: 20 }} onClick={onScan}>Scan Again</button>
      </div>
    );
  }

  return (
    <div>
      {scanResults.map((cat, ci) => {
        const isPersonal = !SAFE_JUNK_CATEGORIES.has(cat.category);
        return (
          <div className="group-block" key={cat.category}>
            <div className="group-header">
              <span className="group-title">{cat.category}</span>
              <span className="group-size">{formatBytes(cat.totalSizeBytes)}</span>
            </div>
            <div className="group-card">
              {cat.items.map((item, j) => {
                const isDev = isDeveloperCache(cat.category, item.name);
                return (
                  <label className="row" key={item.path}>
                    <input
                      type="checkbox"
                      checked={selectedPaths.has(item.path)}
                      onChange={() => togglePath(item.path)}
                    />
                    <RowIcon category={cat.category} index={ci} />
                    <div className="row-main">
                      <span className="row-name">
                        {item.name}
                        {isDev && <span className="badge badge-warning">Rebuild will repopulate this</span>}
                        {isPersonal && <span className="badge badge-info">Personal file</span>}
                      </span>
                      <span className="row-path">{item.path}</span>
                    </div>
                    <span className="row-size">{formatBytes(item.sizeBytes)}</span>
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ============================================================
   Space Lens — folder drilldown with breadcrumb
   ============================================================ */
function SpaceLensView({ inspectInput, setInspectInput, inspecting, inspectResults, inspectError, runInspect, breadcrumbSegments }) {
  return (
    <div>
      <div className="path-toolbar">
        <input
          className="path-input"
          value={inspectInput}
          onChange={(e) => setInspectInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && runInspect(inspectInput)}
          placeholder="~/Documents"
        />
        <button className="btn btn-primary" onClick={() => runInspect(inspectInput)} disabled={inspecting}>
          {inspecting ? 'Loading…' : 'Go'}
        </button>
      </div>

      {inspectError && <div className="error-banner">{inspectError}</div>}

      {inspectResults && (
        <>
          <div className="breadcrumb">
            {breadcrumbSegments().map((seg, i, arr) => (
              <span key={seg.fullPath} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span
                  className={`breadcrumb-item ${i === arr.length - 1 ? 'current' : ''}`}
                  onClick={() => i !== arr.length - 1 && runInspect(seg.fullPath)}
                >
                  {seg.label}
                </span>
                {i < arr.length - 1 && <span className="breadcrumb-sep">/</span>}
              </span>
            ))}
          </div>

          <div className="group-header" style={{ padding: '0 4px 8px' }}>
            <span className="group-title">Contents</span>
            <span className="group-size">{formatBytes(inspectResults.totalSizeBytes)} total</span>
          </div>

          <div className="group-card">
            {inspectResults.items.length === 0 ? (
              <div className="empty-state">This folder is empty.</div>
            ) : (
              inspectResults.items.map((item) => (
                <div className="row clickable" key={item.path} onClick={() => runInspect(item.path)}>
                  <RowIcon category="Documents" index={0} />
                  <div className="row-main">
                    <span className="row-name">{item.name}</span>
                  </div>
                  <span className="row-size">{formatBytes(item.sizeBytes)}</span>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}

/* ============================================================
   Duplicates — suggested keep/remove, still user-confirmed
   ============================================================ */
function DuplicatesView({ duplicatePath, setDuplicatePath, scanningDups, duplicateResults, duplicateError, onScan, dupKeep, setDupKeep, onSelectSuggested, selectedPaths, togglePath }) {
  return (
    <div>
      <div className="path-toolbar">
        <input
          className="path-input"
          value={duplicatePath}
          onChange={(e) => setDuplicatePath(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onScan()}
          placeholder="~/Downloads"
        />
        <button className="btn btn-primary" onClick={onScan} disabled={scanningDups}>
          {scanningDups ? 'Scanning…' : 'Scan'}
        </button>
      </div>

      {duplicateError && <div className="error-banner">{duplicateError}</div>}
      {scanningDups && <div className="loading-state">Comparing files…</div>}

      {duplicateResults && (
        <>
          {duplicateResults.duplicateGroups.length === 0 ? (
            <div className="empty-clean-state">
              <Icon.checkCircle className="empty-clean-icon" />
              <div className="empty-clean-title">No duplicates found</div>
            </div>
          ) : (
            <>
              <div className="flex justify-between items-center mb-4">
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {formatBytes(duplicateResults.totalWastedBytes)} could be freed
                </span>
                <button className="btn btn-primary" onClick={onSelectSuggested}>
                  Select Suggested Copies to Remove
                </button>
              </div>

              {duplicateResults.duplicateGroups.map((group) => (
                <div className="group-block" key={group.hash}>
                  <div className="group-header">
                    <span className="group-title">{formatBytes(group.sizeBytes)} each · {group.items.length} copies</span>
                  </div>
                  <div className="group-card">
                    {group.items.map((item) => {
                      const isKept = dupKeep[group.hash] === item.path;
                      return (
                        <div className="row" key={item.path}>
                          <input
                            type="checkbox"
                            checked={selectedPaths.has(item.path)}
                            onChange={() => togglePath(item.path)}
                          />
                          <RowIcon category="Duplicates" index={0} />
                          <div className="row-main">
                            <span className="row-name">
                              {item.name}
                              {isKept && <span className="badge badge-success">Suggested keep</span>}
                            </span>
                            <span className="row-path">{item.path}</span>
                          </div>
                          {!isKept && (
                            <button
                              className="btn btn-ghost"
                              style={{ fontSize: 11, padding: '5px 8px' }}
                              onClick={() => setDupKeep((prev) => ({ ...prev, [group.hash]: item.path }))}
                            >
                              Keep this one instead
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}

/* ============================================================
   Large Files
   ============================================================ */
function LargeFilesView({ largeFilesPath, setLargeFilesPath, scanningLarge, largeFilesResults, largeFilesError, onScan, selectedPaths, togglePath }) {
  return (
    <div>
      <div className="path-toolbar">
        <input
          className="path-input"
          value={largeFilesPath}
          onChange={(e) => setLargeFilesPath(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onScan()}
          placeholder="~/ or ~/Downloads"
        />
        <button className="btn btn-primary" onClick={onScan} disabled={scanningLarge}>
          {scanningLarge ? 'Scanning…' : 'Scan'}
        </button>
      </div>

      {largeFilesError && <div className="error-banner">{largeFilesError}</div>}
      {scanningLarge && <div className="loading-state">Looking for large files…</div>}

      {largeFilesResults && (
        <>
          {largeFilesResults.items.length === 0 ? (
            <div className="empty-clean-state">
              <Icon.checkCircle className="empty-clean-icon" />
              <div className="empty-clean-title">No large files found</div>
            </div>
          ) : (
            <div className="group-card">
              {largeFilesResults.items.map((item) => (
                <label className="row" key={item.path}>
                  <input
                    type="checkbox"
                    checked={selectedPaths.has(item.path)}
                    onChange={() => togglePath(item.path)}
                  />
                  <RowIcon category="Large" index={0} />
                  <div className="row-main">
                    <span className="row-name">{item.name}</span>
                    <span className="row-path">{item.path}</span>
                  </div>
                  <span className="row-size">{formatBytes(item.sizeBytes)}</span>
                </label>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}