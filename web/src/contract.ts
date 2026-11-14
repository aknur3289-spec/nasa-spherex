export type Coordinates = { ra_deg: number; dec_deg: number };
export type Frame = {
  width_px?: number; height_px?: number;
  id: string; png: string; fits?: string; obs_time_utc: string; mjd: number;
  survey_pass: number; detector: number; band?: string; wavelength_um: number;
  center: Coordinates; bad_pixel_fraction: number;
  stretch: { kind: 'asinh'; lo: number; hi: number; unit: string };
  source_url: string; obs_id: string; processing_version: string;
};
export type Pair = { a: string; b: string; dlambda_frac: number; dt_days: number; trust: 'high' | 'medium' | 'low'; diff_png?: string };
export type Dial = {
  reference_frame: string; model: string; search_radius_px: number;
  steps: { distance_au: number; frame: string; pred: Coordinates; snr: number; offset_px: number }[];
  peak_distance_au: number; truth: { distance_au: number; source: string }; negative_control_field: string;
};
export type Provenance = {
  mission: string; archive: string; collections: string[]; doi: string;
  downloaded_utc: string; pipeline_commit: string; cached: boolean; synthetic: boolean;
};

export type FieldKind = 'static' | 'dial';
export type TimelineEntry = { frame_id: string; obs_time_utc: string; mjd: number };
export type FieldSummary = {
  field_id: string; kind: FieldKind; title: string; thumbnail: string;
  thumbnail_px?: { width: number; height: number };
  n_frames?: number;
  date_range?: { start_utc: string; end_utc: string };
  status?: 'ready' | 'pending';
  synthetic?: boolean;
};
type FieldBase = {
  field_id: string; kind: FieldKind; title: string; description: string; center: Coordinates;
  size_arcmin: number; pixel_scale_arcsec: number; pairs: Pair[];
  dial?: Dial; provenance: Provenance;
};
export type Field = FieldBase & (
  | { schema_version: '1.0'; frames: Frame[] }
  | { schema_version: '1.1'; frames: (Frame & { width_px: number; height_px: number })[] }
);
