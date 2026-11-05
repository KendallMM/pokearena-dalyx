interface Props {
  name: string;
  description: string;
  /* Datos cortos que van como etiquetas, por ejemplo el límite de cartas. */
  tags: string[];
  effect?: string;
  imageUrl?: string | null;
}

/* Ubicación del juego. Solo muestra lo que recibe; no conoce la API. */
export function LocationCard({ name, description, tags, effect, imageUrl }: Props) {
  return (
    <article className="location-card">
      <h2 className="location-card__name">{name}</h2>
      <div className="location-card__picture">
        {imageUrl ? (
          <img className="location-card__art" src={imageUrl} alt="" />
        ) : (
          <div className="location-card__empty">Aquí se verá la imagen</div>
        )}
      </div>
      <div className="location-card__panel">
        {effect && <p className="location-card__effect">{effect}</p>}
        {description && <p className="location-card__description">{description}</p>}
        {tags.length > 0 && (
          <div className="location-card__tags">
            {tags.map((tag) => (
              <span key={tag} className="location-card__tag">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
