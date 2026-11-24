import { useEffect, useRef, useState } from "react";

import { useApi } from "../../api/ApiContext";
import { useObjectUrl } from "../../ui";

/* La imagen (versión grande) pide sesión: se descarga cuando la carta se va a ver. */
export function useLazyCardImage<T extends HTMLElement>(cardImageUrl: string) {
  const { playerCatalog } = useApi();
  const element = useRef<T>(null);
  const [visible, setVisible] = useState(false);
  const [image, setImage] = useState<Blob | null>(null);
  const [failed, setFailed] = useState(false);
  const imageUrl = useObjectUrl(image);

  useEffect(() => {
    if (!element.current || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) setVisible(true);
      },
      { rootMargin: "200px" },
    );
    observer.observe(element.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    playerCatalog.image(cardImageUrl).then(
      (blob) => {
        if (!cancelled) setImage(blob);
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [visible, playerCatalog, cardImageUrl]);

  return {
    element,
    imageUrl,
    imageHint: failed ? "No se pudo cargar la imagen" : "Cargando imagen…",
  };
}
