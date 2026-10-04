const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../chrome-extension/background.js'), 'utf8');

function extension(cookies) {
  const result = {};
  const chrome = {
    action: {
      onClicked: { addListener(callback) { result.click = callback; } },
      async setBadgeText({ text }) { result.badge = text; },
      async setTitle({ title }) { result.title = title; },
    },
    cookies: { async getAll({ domain }) { assert.equal(domain, 'google.com'); return cookies; } },
    downloads: { async download(options) { result.download = options; return 1; } },
  };
  vm.runInNewContext(source, { chrome, encodeURIComponent });
  return result;
}

test('exports only Google cookies with Netscape HttpOnly and session fields', async () => {
  const cookie = { domain: '.google.com', name: 'SID', value: 'synthetic', path: '/', secure: true, httpOnly: true };
  const app = extension([cookie, { ...cookie, domain: '.example.com' }]);
  await app.click();
  const content = decodeURIComponent(app.download.url.split(',')[1]);
  assert.ok(content.startsWith('# Netscape HTTP Cookie File\n'));
  assert.ok(content.includes('#HttpOnly_.google.com\tTRUE\t/\tTRUE\t\tSID\tsynthetic\n'));
  assert.ok(!content.includes('example.com'));
  assert.equal(app.download.saveAs, true);
  assert.equal(app.badge, 'OK');
});

test('does not produce a session file when Google cookies are absent', async () => {
  const app = extension([]);
  await app.click();
  assert.equal(app.download, undefined);
  assert.equal(app.badge, 'ERRO');
});

test('rejects cookie fields that would corrupt the Netscape file', async () => {
  const app = extension([{ domain: '.google.com', name: 'SID', value: 'bad\nvalue', path: '/', secure: true }]);
  await app.click();
  assert.equal(app.download, undefined);
  assert.equal(app.badge, 'ERRO');
});
