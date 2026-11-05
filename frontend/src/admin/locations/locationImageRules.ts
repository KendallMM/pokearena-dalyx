import { checkImageFile, readImageSize, type ImageSize } from "../cards/imageRules";

/* Requisitos de la imagen de una ubicación (4:3, mínimo 800 × 600, hasta 5 MB). */
export const LOCATION_IMAGE = {
  accept: "image/png,image/jpeg,image/webp",
  ratio: { width: 4, height: 3 },
  minWidth: 800,
  minHeight: 600,
} as const;

/* Proporción exacta 4:3 y resolución mínima. */
export function checkLocationImageSize({ width, height }: ImageSize): string | null {
  if (width * LOCATION_IMAGE.ratio.height !== height * LOCATION_IMAGE.ratio.width) {
    return `La imagen debe tener proporción horizontal 4:3 (la tuya mide ${width} × ${height}).`;
  }
  if (width < LOCATION_IMAGE.minWidth || height < LOCATION_IMAGE.minHeight) {
    return `La imagen debe medir al menos ${LOCATION_IMAGE.minWidth} × ${LOCATION_IMAGE.minHeight} píxeles (la tuya mide ${width} × ${height}).`;
  }
  return null;
}

/* Revisa todo lo que se puede saber de la imagen sin ir al servidor. */
export async function inspectLocationImage(
  file: File,
  readSize: (file: File) => Promise<ImageSize> = readImageSize,
): Promise<string | null> {
  const fileProblem = checkImageFile(file);
  if (fileProblem) return fileProblem;
  try {
    return checkLocationImageSize(await readSize(file));
  } catch {
    return "No se pudo leer la imagen. Elige otro archivo.";
  }
}
