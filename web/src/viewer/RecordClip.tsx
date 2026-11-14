import { useEffect, useRef, useState } from 'react';

export function RecordClip({ stage }: { stage: React.RefObject<HTMLDivElement | null> }) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState('');
  const cleanup = useRef<() => void>(undefined);
  useEffect(() => () => cleanup.current?.(), []);
  if (typeof MediaRecorder === 'undefined' || !HTMLCanvasElement.prototype.captureStream ||
      !MediaRecorder.isTypeSupported('video/webm')) return null;

  function record() {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 594;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.imageSmoothingEnabled = false;
    const stream = canvas.captureStream(24);
    const chunks: Blob[] = [];
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
      recorder.start();
    } catch {
      stream.getTracks().forEach(track => track.stop());
      setError('Clip recording is unavailable.');
      return;
    }
    setError('');
    setRecording(true);
    const draw = () => {
      const img = stage.current?.querySelector('img');
      if (!img?.naturalWidth) return;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, 594, 594);
      const factor = Math.max(1, Math.floor(594 / Math.max(img.naturalWidth, img.naturalHeight)));
      const width = img.naturalWidth * factor;
      const height = img.naturalHeight * factor;
      ctx.drawImage(img, Math.floor((594-width)/2), Math.floor((594-height)/2), width, height);
      ctx.fillStyle = '#fff';
      ctx.font = '20px monospace';
      ctx.fillText(stage.current?.querySelector('time')?.textContent ?? '', 16, 565);
    };
    draw();
    const interval = window.setInterval(draw, 42);
    const timeout = window.setTimeout(() => { if (recorder.state !== 'inactive') recorder.stop(); }, 8000);
    const stop = () => {
      clearInterval(interval);
      clearTimeout(timeout);
      stream.getTracks().forEach(track => track.stop());
    };
    cleanup.current = () => {
      recorder.onstop = null;
      if (recorder.state !== 'inactive') recorder.stop();
      stop();
    };
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
    recorder.onerror = () => setError('The recording could not be completed.');
    recorder.onstop = () => {
      stop();
      cleanup.current = undefined;
      setRecording(false);
      if (!chunks.length) return;
      const url = URL.createObjectURL(new Blob(chunks, { type: 'video/webm' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'parallax-dial.webm';
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
  }
  return <><button disabled={recording} onClick={record}>{recording ? 'Recording…' : 'Record clip'}</button>
    {error && <span role="status">{error}</span>}</>;
}
