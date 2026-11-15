import { useEffect, useState } from 'react';

const steps = [
  ['#home', 'Watch the same patch of infrared sky across observation dates.'],
  ['#field/', 'Switch between Naive and Honest to compare how the pairs are chosen.'],
  ['#field/', 'Difference shows where the displayed pixels changed.'],
  ['#dial', 'Sweep through distance hypotheses and watch the focus curve.'],
  ['#limits', 'Change the number of frames to explore the illustrative limits.'],
];

export function GuidedTour({ fieldId }: { fieldId?: string }) {
  const [step, setStep] = useState<number>();
  function go(index: number) {
    const [route] = steps[index];
    window.location.hash = route === '#field/' ? route + fieldId : route;
    setStep(index);
    if (index === 2) window.setTimeout(() => document.querySelector<HTMLButtonElement>('[data-mode="Difference"]')?.click(), 150);
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setStep(undefined);
      if (event.key.toLowerCase() === 't' && !event.repeat && fieldId &&
        !(event.target instanceof Element && event.target.closest('input, textarea, select, [contenteditable]'))) go(0);
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [fieldId]);
  if (!fieldId) return null;
  if (step === undefined) return <button className="tour-launch glass" onClick={() => go(0)}>Start tour</button>;
  return <aside className="tour-caption glass" aria-label="Guided tour">
    <span>{step + 1} / {steps.length}</span>
    <p aria-live="polite">{steps[step][1]}</p>
    <div className="controls">
      <button disabled={!step} onClick={() => go(step - 1)}>Back</button>
      <button onClick={() => step < steps.length - 1 ? go(step + 1) : setStep(undefined)}>{step === steps.length - 1 ? 'Finish' : 'Next'}</button>
      <button onClick={() => setStep(undefined)}>Exit tour</button>
    </div>
  </aside>;
}
