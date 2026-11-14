import type { Frame, Pair } from '../contract';

export function PairPicker({ frames, pairs, selected, onChange }: {
  frames: Frame[];
  pairs: Pair[];
  selected: number;
  onChange: (index: number) => void;
}) {
  if (!pairs.length) return null;
  const date = (id: string) => {
    const frame = frames.find(frame => frame.id === id);
    return frame ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
      .format(new Date(frame.obs_time_utc)) : 'Unknown date';
  };
  return <label>Observation pair <select value={selected} onChange={event => onChange(Number(event.target.value))}>
    {pairs.map((pair, index) => <option key={index} value={index}>{date(pair.a)} → {date(pair.b)} · {pair.dt_days} days</option>)}
  </select></label>;
}
