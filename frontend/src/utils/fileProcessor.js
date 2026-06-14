export const ALLOWED_TYPES = {
  'application/pdf': '.pdf',
  'text/plain': '.txt',
  'text/markdown': '.md',
  'text/x-markdown': '.md',
};

export const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.markdown'];
export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function loadPdfJs() {
  if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
    script.integrity = 'sha384-/1qUCSGwTur9vjf/z9lmu/eCUYbpOTgSjmpbMQZ1/CtX2v/WcAIKqRv+U1DUCG6e';
    script.crossOrigin = 'anonymous';
    script.onload = () => {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      resolve(window.pdfjsLib);
    };
    script.onerror = () => reject(new Error('Failed to load pdf.js'));
    document.head.appendChild(script);
  });
}

async function extractPdfText(file) {
  const pdfjsLib = await loadPdfJs();
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  const pages = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const textContent = await page.getTextContent();
    const text = textContent.items.map(item => item.str).join(' ');
    pages.push(text);
  }
  return pages.join('\n\n');
}

function fileToText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsText(file);
  });
}

export async function processFile(file) {
  if (file.size > MAX_FILE_SIZE) {
    throw new Error(`File "${file.name}" exceeds the 10MB size limit`);
  }

  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  const isText = file.type.startsWith('text/') ||
    file.name.toLowerCase().endsWith('.md') ||
    file.name.toLowerCase().endsWith('.markdown') ||
    file.name.toLowerCase().endsWith('.txt') ||
    file.name.toLowerCase().endsWith('.json');

  if (!isPdf && !isText) {
    throw new Error(`Unsupported file type: ${file.name}. Allowed: PDF, TXT, MD`);
  }

  let content;
  let type;
  if (isPdf) {
    content = await extractPdfText(file);
    type = 'pdf';
  } else {
    content = await fileToText(file);
    type = 'text';
  }

  return {
    name: file.name,
    type,
    content,
    mime_type: file.type,
    size: file.size,
  };
}

export async function processFiles(files) {
  const results = [];
  const errors = [];
  const fileList = Array.from(files);

  for (const file of fileList) {
    try {
      const processed = await processFile(file);
      results.push(processed);
    } catch (err) {
      errors.push({ name: file.name, error: err.message });
    }
  }

  return { results, errors };
}
