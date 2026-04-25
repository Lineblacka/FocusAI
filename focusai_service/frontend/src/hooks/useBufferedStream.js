import { useCallback, useRef } from 'react';

export function useBufferedStream(onFlush) {
  const bufferRef = useRef('');
  const frameRef = useRef(null);

  const flush = useCallback(() => {
    frameRef.current = null;
    if (!bufferRef.current) return;
    const chunk = bufferRef.current;
    bufferRef.current = '';
    onFlush(chunk);
  }, [onFlush]);

  const push = useCallback((chunk) => {
    bufferRef.current += chunk;
    if (frameRef.current == null) frameRef.current = requestAnimationFrame(flush);
  }, [flush]);

  const cancel = useCallback(() => {
    if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    bufferRef.current = '';
  }, []);

  return { push, cancel, flush };
}
