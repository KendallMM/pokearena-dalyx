/** Requisitos de la imagen de una carta (5:7, mínimo 600 × 840, hasta 5 MB). */
export const CARD_IMAGE = {
  allowedTypes: ["image/png", "image/jpeg", "image/webp"],
  accept: "image/png,image/jpeg,image/webp",
  maxBytes: 5 * 1024 * 1024,
  ratio: { width: 5, height: 7 },
  minWidth: 600,
  minHeight: 840,
} as const;

export interface ImageSize {
  width: number;
  height: number;
}

/** Formato y peso. Se detecta por el tipo que informa el navegador; el servidor lo comprueba con el contenido real. */
export function checkImageFile(file: File): string | null {
  if (!(CARD_IMAGE.allowedTypes as readonly string[]).includes(file.type)) {
    return "La imagen debe ser PNG, JPG o WebP.";
  }
  if (file.size > CARD_IMAGE.maxBytes) {
    return "La imagen no puede pesar más de 5 MB.";
  }
  return null;
}

/** Proporción exacta 5:7 y resolución mínima. */
export function checkImageSize({ width, height }: ImageSize): string | null {
  if (width * CARD_IMAGE.ratio.height !== height * CARD_IMAGE.ratio.width) {
    return `La imagen debe tener proporción vertical 5:7 (la tuya mide ${width} × ${height}).`;
  }
  if (width < CARD_IMAGE.minWidth || height < CARD_IMAGE.minHeight) {
    return `La imagen debe medir al menos ${CARD_IMAGE.minWidth} × ${CARD_IMAGE.minHeight} píxeles (la tuya mide ${width} × ${height}).`;
  }
  return null;
}

/** Lee el tamaño real de la imagen en el navegador. */
export function readImageSize(file: File): Promise<ImageSize> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: image.naturalWidth, height: image.naturalHeight });
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("No se pudo leer la imagen."));
    };
    image.src = url;
  });
}

/** Revisa todo lo que se puede saber de la imagen sin ir al servidor. */
export async function inspectCardImage(
  file: File,
  readSize: (file: File) => Promise<ImageSize> = readImageSize,
): Promise<string | null> {
  const fileProblem = checkImageFile(file);
  if (fileProblem) return fileProblem;
  try {
    return checkImageSize(await readSize(file));
  } catch {
    return "No se pudo leer la imagen. Elige otro archivo.";
  }
}
