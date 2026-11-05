import { Alert, Button, Spinner } from "../ui";
import { accessDeniedMessage } from "./accessMessages";
import { BackToMenu } from "./BackToMenu";
import type { ReferencesState } from "./cards/useReferences";

interface Props {
  state: ReferencesState;
  reload: () => void;
  /* Qué decir si los catálogos fallan por otra razón que no sea el acceso. */
  errorMessage: string;
}

/* Lo que se ve mientras cargan los catálogos, o si fallan. Una vez listos no muestra nada. */
export function ReferencesStatus({ state, reload, errorMessage }: Props) {
  if (state.status === "loading") {
    return <Spinner label="Cargando opciones del formulario…" />;
  }
  if (state.status !== "error") return null;

  const denied = accessDeniedMessage(state.error);
  return (
    <>
      <Alert
        variant="error"
        title={denied ? "Acceso denegado" : "No se pudieron cargar las opciones"}
      >
        <p>{denied ?? errorMessage}</p>
      </Alert>
      <div className="form__actions">
        <Button variant="secondary" onClick={reload}>
          Reintentar
        </Button>
        <BackToMenu />
      </div>
    </>
  );
}
