import { useState } from 'react';
import { api } from '../api';
import './ExportImportModal.css';

export default function ExportImportModal({ onClose }) {
  const [activeTab, setActiveTab] = useState('export');
  const [exportInProgress, setExportInProgress] = useState(false);
  const [importInProgress, setImportInProgress] = useState(false);
  const [importStatus, setImportStatus] = useState(null);
  const [importFile, setImportFile] = useState(null);
  const [exportOptions, setExportOptions] = useState({
    conversations: true,
    settings: true,
  });

  const handleExport = async () => {
    setExportInProgress(true);
    try {
      const data = await api.exportData();
      const exportData = {};
      if (exportOptions.conversations) exportData.conversations = data.conversations;
      if (exportOptions.settings) exportData.settings = data.settings;
      exportData.version = data.version;
      exportData.exported_at = data.exported_at;
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      a.download = `ai-counsel-backup-${timestamp}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      setImportStatus({ type: 'error', message: 'Export failed. Check console for details.' });
    } finally {
      setExportInProgress(false);
    }
  };

  const handleImportFileChange = (e) => {
    const file = e.target.files[0];
    if (file) setImportFile(file);
  };

  const handleImport = async () => {
    if (!importFile) return;
    setImportInProgress(true);
    setImportStatus(null);
    try {
      const text = await importFile.text();
      const data = JSON.parse(text);
      const result = await api.importData(data);
      if (result.status === 'ok') {
        setImportStatus({
          type: 'success',
          message: `Import complete. ${result.imported_count} conversation(s) imported.`,
        });
      } else {
        setImportStatus({ type: 'error', message: 'Import failed.' });
      }
    } catch (err) {
      setImportStatus({ type: 'error', message: `Import error: ${err.message}` });
    } finally {
      setImportInProgress(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="export-import-modal" onClick={(e) => e.stopPropagation()}>
        <div className="eim-header">
          <h2>Export / Import</h2>
          <button className="eim-close" onClick={onClose}>×</button>
        </div>

        <div className="eim-tabs">
          <button
            className={`eim-tab ${activeTab === 'export' ? 'active' : ''}`}
            onClick={() => setActiveTab('export')}
          >
            Export
          </button>
          <button
            className={`eim-tab ${activeTab === 'import' ? 'active' : ''}`}
            onClick={() => setActiveTab('import')}
          >
            Import
          </button>
        </div>

        <div className="eim-body">
          {activeTab === 'export' ? (
            <div className="eim-export-section">
              <p className="eim-description">
                Download all conversations and settings as a JSON backup file.
              </p>

              <div className="eim-options">
                <label className="eim-option">
                  <input
                    type="checkbox"
                    checked={exportOptions.conversations}
                    onChange={() => setExportOptions(o => ({ ...o, conversations: !o.conversations }))}
                  />
                  <span>Conversations</span>
                </label>
                <label className="eim-option">
                  <input
                    type="checkbox"
                    checked={exportOptions.settings}
                    onChange={() => setExportOptions(o => ({ ...o, settings: !o.settings }))}
                  />
                  <span>Settings (includes API keys)</span>
                </label>
              </div>

              <button
                className="eim-action-btn"
                onClick={handleExport}
                disabled={exportInProgress || (!exportOptions.conversations && !exportOptions.settings)}
              >
                {exportInProgress ? 'Downloading...' : '⬇ Download Backup'}
              </button>
            </div>
          ) : (
            <div className="eim-import-section">
              <p className="eim-description">
                Restore conversations and settings from a previously exported backup file.
              </p>

              <div className="eim-file-picker">
                <input
                  type="file"
                  accept=".json"
                  onChange={handleImportFileChange}
                />
              </div>

              <button
                className="eim-action-btn"
                onClick={handleImport}
                disabled={importInProgress || !importFile}
              >
                {importInProgress ? 'Importing...' : '⬆ Restore Backup'}
              </button>

              {importStatus && (
                <div className={`eim-status eim-status--${importStatus.type}`}>
                  {importStatus.message}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
