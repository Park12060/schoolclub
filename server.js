const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = 8765;
const BASE_DIR = __dirname;

const MIME = {
  '.html':'text/html;charset=utf-8',
  '.js':'application/javascript;charset=utf-8',
  '.css':'text/css',
  '.csv':'text/csv;charset=utf-8',
  '.json':'application/json',
  '.png':'image/png','.ico':'image/x-icon'
};

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname  = parsedUrl.pathname;

  // ── Nominatim proxy ──────────────────────────────────────
  if (pathname === '/geocode') {
    const q = parsedUrl.query.q || '';
    const apiUrl = `https://nominatim.openstreetmap.org/search?format=json&limit=1&accept-language=ko&q=${encodeURIComponent(q)}`;

    const options = {
      hostname: 'nominatim.openstreetmap.org',
      path: `/search?format=json&limit=1&accept-language=ko&q=${encodeURIComponent(q)}`,
      headers: {
        'User-Agent': 'DaejeonPharmacyMap/1.0 (educational project)',
        'Accept': 'application/json'
      }
    };

    https.get(options, (proxyRes) => {
      let data = '';
      proxyRes.on('data', chunk => data += chunk);
      proxyRes.on('end', () => {
        res.writeHead(200, {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        });
        res.end(data);
      });
    }).on('error', err => {
      res.writeHead(500); res.end('{}');
    });
    return;
  }

  // ── Static file server ───────────────────────────────────
  let filePath = path.join(BASE_DIR, pathname === '/' ? 'pharmacy_map.html' : pathname);
  // security: prevent path traversal
  if (!filePath.startsWith(BASE_DIR)) { res.writeHead(403); res.end(); return; }

  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    const ext = path.extname(filePath);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'text/plain' });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log(`\n💊 대전 약국 지도 서버 실행 중`);
  console.log(`   → http://127.0.0.1:${PORT}/pharmacy_map.html\n`);
  console.log(`   Nominatim 프록시: http://127.0.0.1:${PORT}/geocode?q=주소\n`);
});
