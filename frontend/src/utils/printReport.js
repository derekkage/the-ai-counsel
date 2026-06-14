function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function printReport(content, modelName, conversationTitle) {
  const win = window.open('', '_blank');
  if (!win) return;

  const timestamp = new Date().toLocaleString();
  const title = escapeHtml(conversationTitle || 'Council Report');
  const safeModelName = escapeHtml(modelName || '');
  const safeContent = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');

  win.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
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
  <h1>${title}</h1>
  <div class="subtitle">
    Chairman's Verdict &mdash; ${safeModelName}<br>
    ${timestamp}
  </div>
  <div class="content">${safeContent}</div>
  <script>window.onload = () => window.print();<\/script>
</body>
</html>`);
  win.document.close();
}
