export const copy = {
  title: 'Parallax Dial', subtitle: 'SPHEREx sky viewer', search: 'Search fields…',
  fields: 'Sky fields', all: 'All fields', static: 'Sky field', dial: 'Distance dial',
  sortName: 'Sort by name', sortDate: 'Sort by date', loading: 'Loading observations…',
  empty: 'No matching fields.', noFrames: 'This field has no frames.', soon: 'coming soon',
  previous: 'Previous', next: 'Next', details: 'Details', what: 'What you see',
  explanation: 'These infrared images show the same patch of sky on different dates. Play the sequence or compare two observations.',
  why: 'Why these frames?', trust: 'The default pair is the first high-trust pair, or the closest wavelength match when no high-trust pair is available.',
  lowTrust: 'Different wavelengths: the difference can come from the filters and does not establish a change over time.',
  noPair: 'This field has no documented pair.', changes: 'Bright spots = things that changed between the two dates.',
  synthetic: 'Synthetic data', source: 'Open source file at IRSA', detector: 'Detector',
  planet: 'Could SPHEREx see Planet X?', hint: 'Press ▶ to see this patch of sky change',
  play: 'Play', compare: 'Compare', change: 'Changes', distance: 'Distance',
  pause: 'Pause playback', start: 'Start playback', scrub: 'Observation date',
  before: 'Before', after: 'After', split: 'Before and after divider', more: 'Playback options',
  speed: 'Playback speed', unavailable: 'Image unavailable', modes: 'Viewing mode',
  earth: 'About six months later, Earth views the sky from the other side of its orbit.',
  align: 'Turn the dial to see where the object lines up.', seen: 'The first observation was on',
};
export const day = (time: string) => new Intl.DateTimeFormat('en-GB', {
  day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
}).format(new Date(time));
