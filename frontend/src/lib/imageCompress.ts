// Compression d'une image dans le navigateur avant envoi (session du
// 2026-11-03) : redimensionnée pour tenir dans MAX_WIDTH×MAX_HEIGHT, encodée
// en WebP, qualité abaissée jusqu'à passer sous TARGET_BYTES. Une photo de
// plusieurs Mo devient ~50 Ko — c'est ce qui rend le stockage en base viable.
const MAX_WIDTH = 960;
const MAX_HEIGHT = 640;
const TARGET_BYTES = 200 * 1024;
const QUALITIES = [0.82, 0.7, 0.58, 0.45];

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/webp", quality));
}

export async function compressImage(file: File): Promise<Blob> {
  if (!file.type.startsWith("image/")) throw new Error("Ce fichier n'est pas une image.");
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("Image illisible — essayez un fichier JPEG, PNG ou WebP.");
  }
  const scale = Math.min(1, MAX_WIDTH / bitmap.width, MAX_HEIGHT / bitmap.height);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  for (const quality of QUALITIES) {
    const blob = await toBlob(canvas, quality);
    if (blob && blob.type === "image/webp" && blob.size <= TARGET_BYTES) return blob;
  }
  throw new Error("Impossible de réduire suffisamment cette image.");
}
