(() => {
  'use strict';
  const message = document.getElementById('message');
  const install = document.getElementById('install');
  const apkInfo = document.getElementById('apk-info');
  // Only Android-labelled GitHub Release APKs are eligible; no arbitrary
  // file from a Windows-only release can become a phone install link.
  async function findPublishedAndroidApk() {
    try {
      const response = await fetch('https://api.github.com/repos/almogbell/DID-Character-Sheet/releases?per_page=30', {
        headers: { Accept: 'application/vnd.github+json' }
      });
      if (!response.ok) throw new Error('GitHub API unavailable');
      const releases = await response.json();
      if (!Array.isArray(releases)) throw new Error('Bad release metadata');
      const available = [];
      for (const release of releases) {
        if (release.draft || release.prerelease) continue;
        const version = String(release.tag_name || '').match(/(\d+)\.(\d+)\.(\d+)/);
        if (!version || !Array.isArray(release.assets)) continue;
        for (const asset of release.assets) {
          const name = String(asset.name || '');
          // Releases may use the standard Gradle output name app-release.apk.
          // Never offer debug/test/unsigned builds as production installs.
          if (!/\.apk$/i.test(name) || /(?:debug|unsigned|test)/i.test(name)) continue;
          const recognizable = /^(?:app-release|pocket[-_ ]?did[-_a-z0-9.]*|android[-_a-z0-9.]*|did[-_a-z0-9.]*)\.apk$/i.test(name);
          const androidMime = String(asset.content_type || '').toLowerCase() === 'application/vnd.android.package-archive';
          if (!recognizable && !androidMime) continue;
          let uri;
          try { uri = new URL(asset.browser_download_url); } catch (_) { continue; }
          if (uri.protocol !== 'https:' || uri.hostname !== 'github.com' ||
              !uri.pathname.startsWith('/almogbell/DID-Character-Sheet/releases/download/')) continue;
          available.push({ version: version.slice(1).map(Number), display: version[0], url: uri.href });
        }
      }
      available.sort((a, b) => {
        for (let i = 0; i < 3; i++) {
          if (a.version[i] !== b.version[i]) return b.version[i] - a.version[i];
        }
        return 0;
      });
      if (available.length) {
        const latest = available[0];
        install.href = latest.url;
        install.textContent = 'Download Pocket DID ' + latest.display + ' APK (install or update)';
        apkInfo.textContent = 'Latest published Android APK found on GitHub Releases.';
      } else {
        apkInfo.textContent = 'No Android APK was found in published releases yet. Check GitHub Releases once it has been uploaded.';
      }
    } catch (_) {
      apkInfo.textContent = 'Could not check GitHub automatically. Use the Releases link to find the newest Pocket DID APK.';
    }
  }
  findPublishedAndroidApk();
  const launch = document.getElementById('open-app');
  const hash = location.hash.startsWith('#did=') ? location.hash.slice(5) : '';
  // The fragment is never sent to the hosting server or GitHub. Remove it
  // from visible address/history as soon as this page has read it.
  history.replaceState(null, '', location.pathname);
  if (!hash || hash.length > 2048 || !/^[A-Za-z0-9_-]+$/.test(hash)) {
    message.textContent = 'No valid pairing code was found. Start pairing on Windows and scan its QR code.';
    return;
  }
  let data;
  try {
    const bytes = atob(hash.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - hash.length % 4) % 4));
    data = JSON.parse(decodeURIComponent([...bytes].map(c => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join('')));
  } catch (_) {
    message.textContent = 'This pairing code could not be read. Generate a fresh QR on Windows.';
    return;
  }
  const valid = data && data.type === 'did_pairing' && Number.isInteger(data.expires_at) &&
    data.expires_at > Date.now() / 1000 && data.expires_at < Date.now() / 1000 + 3600 &&
    typeof data.pairing_token === 'string' && data.pairing_token.length >= 24 &&
    typeof data.host === 'string' && /^(\d{1,3}\.){3}\d{1,3}$/.test(data.host) &&
    Number.isInteger(data.port) && data.port > 0 && data.port <= 65535;
  if (!valid) {
    message.textContent = 'The pairing code has expired or is invalid. Start pairing again on Windows.';
    return;
  }
  // The Android application must register this scheme and parse data as
  // base64url-encoded UTF-8 DID pairing JSON. The app must enforce expiry.
  launch.href = 'didcharactersheet://pair?data=' + encodeURIComponent(hash);
  launch.hidden = false;
  message.textContent = 'Pocket DID installed? Choose Open Pocket DID. Otherwise install the APK below and scan a fresh code.';
})();
