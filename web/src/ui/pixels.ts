export const integerScale = (available: number, width: number) => Math.max(1, Math.floor(available / width));
export const pixelCentre = (coordinate: number, scale: number) => (Math.floor(coordinate) + .5) * scale;
