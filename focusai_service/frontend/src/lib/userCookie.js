import { COOKIE_NAME } from './constants.js';
import { createId } from './id.js';

function readCookie(name) {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
    ?.split('=')[1];
}

export function getOrCreateUserId() {
  const existing = readCookie(COOKIE_NAME);
  if (existing) return decodeURIComponent(existing);

  const userId = createId('user');
  const maxAge = 60 * 60 * 24 * 365;
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(userId)}; Max-Age=${maxAge}; Path=/; SameSite=Lax`;
  return userId;
}
