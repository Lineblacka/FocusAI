function getBrowser(ua) {
  const matchers = [
    ['Edge', /Edg\/([\d.]+)/],
    ['Chrome', /Chrome\/([\d.]+)/],
    ['Firefox', /Firefox\/([\d.]+)/],
    ['Safari', /Version\/([\d.]+).*Safari/],
  ];
  for (const [name, pattern] of matchers) {
    const match = ua.match(pattern);
    if (match) return { browser: name, browser_version: match[1] };
  }
  return { browser: 'Unknown', browser_version: '' };
}

function getOS(ua) {
  if (/Windows/i.test(ua)) return 'Windows';
  if (/Android/i.test(ua)) return 'Android';
  if (/iPhone|iPad|iPod/i.test(ua)) return 'iOS';
  if (/Mac OS X|Macintosh/i.test(ua)) return 'macOS';
  if (/Linux/i.test(ua)) return 'Linux';
  return 'Unknown';
}

function getDeviceName(ua, os, deviceType) {
  if (/iPad/i.test(ua)) return 'iPad';
  if (/iPhone/i.test(ua)) return 'iPhone';
  if (/iPod/i.test(ua)) return 'iPod';
  if (/Android/i.test(ua) && /Mobile/i.test(ua)) return 'Android Phone';
  if (/Android/i.test(ua)) return 'Android Tablet';
  if (os === 'macOS') return 'Mac';
  if (os === 'Windows') return 'Windows PC';
  if (os === 'Linux') return 'Linux PC';
  if (deviceType === 'mobile') return 'Mobile Device';
  if (deviceType === 'tablet') return 'Tablet';
  return 'Desktop PC';
}

export function getDeviceInfo() {
  const ua = navigator.userAgent || '';
  const width = window.screen?.width || window.innerWidth || 0;
  const height = window.screen?.height || window.innerHeight || 0;
  const maxSide = Math.max(width, height);
  const minSide = Math.min(width, height);

  let deviceType = 'desktop';
  if (/Mobi|Android|iPhone|iPod/i.test(ua) || maxSide <= 900) deviceType = 'mobile';
  if (/iPad|Tablet/i.test(ua) || (minSide >= 700 && maxSide <= 1366 && /Macintosh|Android/i.test(ua))) deviceType = 'tablet';

  const { browser, browser_version } = getBrowser(ua);
  const os = getOS(ua);
  const device_name = getDeviceName(ua, os, deviceType);

  return {
    device_type: deviceType,
    device_name,
    browser,
    browser_version,
    os,
    screen_size: width && height ? `${width}x${height}` : '',
    viewport_size: window.innerWidth && window.innerHeight ? `${window.innerWidth}x${window.innerHeight}` : '',
    language: navigator.language || '',
    user_agent: ua.slice(0, 500),
  };
}
