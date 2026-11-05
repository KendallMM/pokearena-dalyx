import { useCallback, useEffect, useRef, useState } from "react";

import { useApi } from "../../api/ApiContext";
import { ApiError } from "../../api/errors";
import type { CreateLocationResult } from "../../api/types";
import { useSession } from "../../session/SessionContext";
import { Alert, Button, Spinner } from "../../ui";
import { accessDeniedMessage } from "../accessMessages";
import { BackToMenu } from "../BackToMenu";
import type { ImageSize } from "../cards/imageRules";
import { useOperationKey } from "../cards/operationId";
import { useReferences } from "../cards/useReferences";
import { CreateLocationForm } from "./CreateLocationForm";
import { inspectLocationImage } from "./locationImageRules";
import { LocationPreview } from "./LocationPreview";
import {
  EMPTY_LOCATION_FORM,
  formFieldFromApi,
  parameterField,
  toCreateLocationInput,
  validateLocationValues,
  type EffectParameterValue,
  type LocationFormErrors,
  type LocationFormField,
  type LocationFormValues,
  type LocationValueField,
} from "./locationRules";

interface Props {
  /* Lector del tamaño de la imagen. Las pruebas lo reemplazan porque jsdom no decodifica imágenes. */
  readImageSize?: (file: File) => Promise<ImageSize>;
}

const RETRY_MESSAGE =
  "No se pudo completar la operación. Puedes volver a intentarlo: si la ubicación ya se había creado, no se duplicará.";

/* Convierte un error del envío en el mensaje o el campo que debe ver el administrador. */
function describeSubmitError(error: unknown): {
  field?: LocationFormField;
  message: string;
} {
  const denied = accessDeniedMessage(error);
  if (denied) return { message: denied };
  if (error instanceof ApiError) {
    if (error.status === 400) {
      const field = formFieldFromApi(error.field);
      return field ? { field, message: error.message } : { message: error.message };
    }
    if (error.status === 409) return { message: error.message };
    if (error.isNetworkError || error.isServerError) return { message: RETRY_MESSAGE };
    return { message: error.message };
  }
  return { message: RETRY_MESSAGE };
}

/* Pantalla Crear ubicación. */
export function CreateLocationPage({ readImageSize }: Props) {
  const { locations } = useApi();
  const { hasToken } = useSession();
  const { state, reload } = useReferences();
  const operationKey = useOperationKey();

  const [values, setValues] = useState<LocationFormValues>(EMPTY_LOCATION_FORM);
  const [errors, setErrors] = useState<LocationFormErrors>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CreateLocationResult | null>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  const [focusSummary, setFocusSummary] = useState(0);
  const imageCheck = useRef(0);

  // El error y el resultado eran de la sesión anterior. Lo que se estaba escribiendo se
  // conserva, para no perderlo si solo había vencido el token.
  useEffect(() => {
    setGeneralError(null);
    if (result) createAnother();
    // Solo debe correr cuando cambia la sesión.
  }, [hasToken]);

  // Al fallar el envío, el resumen de errores recibe el foco.
  useEffect(() => {
    if (focusSummary > 0) summaryRef.current?.focus();
  }, [focusSummary]);

  const handleChange = useCallback(
    <K extends LocationValueField>(field: K, value: LocationFormValues[K]) => {
      setValues((current) => ({
        ...current,
        [field]: value,
        // Cada efecto tiene sus propios parámetros: los del anterior ya no aplican.
        ...(field === "effectType" ? { effectParameters: {} } : {}),
      }));
      setErrors((current) => {
        const next: LocationFormErrors = { ...current, [field]: undefined };
        if (field === "effectType") {
          for (const key of Object.keys(next) as LocationFormField[]) {
            if (key.startsWith("parameter:")) delete next[key];
          }
        }
        // El máximo de energía depende de la modalidad.
        if (field === "energyMode") next.energyAmount = undefined;
        return next;
      });
      setGeneralError(null);
      // Un formulario distinto es una operación distinta: nueva llave.
      operationKey.reset();

      if (field === "image") {
        const check = ++imageCheck.current;
        const file = value as File | null;
        if (!file) return;
        void inspectLocationImage(file, readImageSize).then((problem) => {
          // Solo cuenta la revisión de la imagen más reciente.
          if (check === imageCheck.current && problem) {
            setErrors((current) => ({ ...current, image: problem }));
          }
        });
      }
    },
    [operationKey, readImageSize],
  );

  const handleParameterChange = useCallback(
    (name: string, value: EffectParameterValue) => {
      setValues((current) => ({
        ...current,
        effectParameters: { ...current.effectParameters, [name]: value },
      }));
      setErrors((current) => ({ ...current, [parameterField(name)]: undefined }));
      setGeneralError(null);
      operationKey.reset();
    },
    [operationKey],
  );

  async function handleSubmit() {
    if (state.status !== "ready") return;
    const effectTypes = state.references.location_effect_types;
    const found = validateLocationValues(values, effectTypes);
    // La imagen también debe cumplir su revisión (formato, peso y medidas).
    if (!found.image && values.image) {
      const problem = await inspectLocationImage(values.image, readImageSize);
      if (problem) found.image = problem;
    }
    if (Object.values(found).some(Boolean)) {
      setErrors(found);
      setGeneralError(null);
      setFocusSummary((n) => n + 1);
      return;
    }

    setErrors({});
    setGeneralError(null);
    setSubmitting(true);
    try {
      const created = await locations.create(
        toCreateLocationInput(values, effectTypes),
        operationKey.current(),
      );
      setResult(created);
      operationKey.reset();
    } catch (error) {
      const problem = describeSubmitError(error);
      if (problem.field) setErrors({ [problem.field]: problem.message });
      else setGeneralError(problem.message);
      setFocusSummary((n) => n + 1);
    } finally {
      setSubmitting(false);
    }
  }

  function createAnother() {
    setValues(EMPTY_LOCATION_FORM);
    setErrors({});
    setGeneralError(null);
    setResult(null);
    operationKey.reset();
  }

  return (
    <section aria-labelledby="create-location-title" className="page">
      <h1 id="create-location-title">Crear ubicación</h1>
      <p className="page__intro">
        Completa los datos de la ubicación. Todos los campos son obligatorios, menos el
        efecto.
      </p>

      {state.status === "loading" && (
        <Spinner label="Cargando opciones del formulario…" />
      )}

      {state.status === "error" && (
        <>
          <Alert
            variant="error"
            title={
              accessDeniedMessage(state.error)
                ? "Acceso denegado"
                : "No se pudieron cargar las opciones"
            }
          >
            <p>
              {accessDeniedMessage(state.error) ??
                "No pudimos cargar los tipos de efecto y de carta. Inténtalo de nuevo."}
            </p>
          </Alert>
          <div className="form__actions">
            <Button variant="secondary" onClick={reload}>
              Reintentar
            </Button>
            <BackToMenu />
          </div>
        </>
      )}

      {state.status === "ready" && (
        <div className="page__columns">
          {result ? (
            <div className="page__result">
              <Alert variant="success" title={result.message}>
                <p>
                  Identificador de la ubicación: <strong>{result.id}</strong>
                </p>
                {result.replayed && (
                  <p>Esta ubicación ya estaba registrada, así que no se creó otra.</p>
                )}
                <p>
                  La versión pequeña de la imagen se está generando. La ubicación podrá
                  usarse en partidas cuando termine.
                </p>
              </Alert>
              <div className="form__actions">
                <Button onClick={createAnother}>Crear otra ubicación</Button>
                <BackToMenu />
              </div>
            </div>
          ) : (
            <CreateLocationForm
              ref={summaryRef}
              references={state.references}
              values={values}
              errors={errors}
              generalError={generalError}
              submitting={submitting}
              onChange={handleChange}
              onParameterChange={handleParameterChange}
              onSubmit={() => void handleSubmit()}
            />
          )}
          <LocationPreview
            references={state.references}
            values={values}
            done={result !== null}
          />
        </div>
      )}
    </section>
  );
}
