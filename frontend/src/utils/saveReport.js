function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function sanitizeFilename(name) {
  return String(name)
    .replace(/[^a-zA-Z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase() || 'report';
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function getTimestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function getFilename(title, ext) {
  const safe = sanitizeFilename(title || 'verdict');
  const ts = getTimestamp();
  return `${safe}-verdict-${ts}.${ext}`;
}

function saveTxt(content, title) {
  const blob = new Blob([content], { type: 'text/plain' });
  downloadBlob(blob, getFilename(title, 'txt'));
}

function saveMarkdown(content, title) {
  const blob = new Blob([content], { type: 'text/markdown' });
  downloadBlob(blob, getFilename(title, 'md'));
}

function saveJson(content, title, model) {
  const data = {
    title: title || 'Council Report',
    model: model || '',
    verdict: content,
    timestamp: new Date().toISOString(),
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  downloadBlob(blob, getFilename(title, 'json'));
}

function savePdf(content, title, model) {
  const win = window.open('', '_blank');
  if (!win) return;

  const timestamp = new Date().toLocaleString();
  const safeTitle = escapeHtml(title || 'Council Report');
  const safeModelName = escapeHtml(model || '');
  const safeContent = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');

  win.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${safeTitle}</title>
  <style>
    @page { margin: 2cm; }
    body {
      font-family: Georgia, 'Times New Roman', Times, serif;
      font-size: 12pt;
      line-height: 1.6;
      color: #1a1a1a;
      max-width: 700px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      font-size: 18pt;
      border-bottom: 2px solid #d4a843;
      padding-bottom: 8px;
      margin-bottom: 4px;
    }
    .subtitle {
      font-size: 10pt;
      color: #666;
      margin-bottom: 24px;
    }
    .content {
      white-space: pre-wrap;
    }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
    th { background: #f5f5f5; }
    @media print {
      body { padding: 0; }
    }
  </style>
</head>
<body>
  <h1>${safeTitle}</h1>
  <div class="subtitle">
    Chairman's Verdict &mdash; ${safeModelName}<br>
    ${timestamp}
  </div>
  <div class="content">${safeContent}</div>
  <script>window.onload = () => window.print();</script>
</body>
</html>`);
  win.document.close();
}

export function saveReport(format, content, title, model) {
  if (!content) return;

  switch (format) {
    case 'txt':
      saveTxt(content, title);
      break;
    case 'md':
      saveMarkdown(content, title);
      break;
    case 'json':
      saveJson(content, title, model);
      break;
    case 'pdf':
      savePdf(content, title, model);
      break;
    default:
      console.warn('Unknown save format:', format);
  }
}
