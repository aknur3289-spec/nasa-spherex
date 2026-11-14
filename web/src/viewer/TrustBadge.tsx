import type { Pair } from '../contract';

export function TrustBadge({ pair }: { pair: Pair }) {
  const label = { high: 'High', medium: 'Medium', low: 'Low' }[pair.trust];
  return <p className={'trust ' + pair.trust}>
    {label} trust · wavelengths differ {Number((pair.dlambda_frac * 100).toFixed(3))}% · {pair.dt_days} days apart
  </p>;
}
