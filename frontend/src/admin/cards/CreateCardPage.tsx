import { useCallback, useEffect, useRef, useState } from "react";

import { useApi } from "../../api/ApiContext";
import { ApiError } from "../../api/errors";
import type { CreateCardResult } from "../../api/types";
import { useSession } from "../../session/SessionContext";
import { Alert, Button, Spinner } from "../../ui";
import { accessDeniedMessage } from "../accessMessages";
import {
  EMPTY_CARD_FORM,
  formFieldFromApi,
  toCreateCardInput,
  validateCardValues,
  type CardFormErrors,
  type CardFormField,
  type CardFormValues,
} from "./cardRules";
import { CardPreview } from "./CardPreview";
import { CreateCardForm } from "./CreateCardForm";
import { inspectCardImage, type ImageSize } from "./imageRules";
import { useOperationKey } from "./operationId";
import { useReferences } from "./useReferences";

interface Props {
  /* Lector del tamaño de la imagen. Las pruebas lo reemplazan porque jsdom no decodifica imágenes. */
  readImageSize?: (file: File) => Promise<ImageSize>;
}

const RETRY_MESSAGE =
  "No se pudo completar la operación. Puedes volver a intentarlo: si la carta ya se había creado, no se duplicará.";

/* Convierte un error del envío en el mensaje o el campo que debe ver el administrador. */
function describeSubmitError(error: unknown): {
  field?: CardFormField;
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

/* Pantalla Crear carta (secuencia "Crear carta", partes A y B). */
export function CreateCardPage({ readImageSize }: Props) {
  const { cards } = useApi();
  const { hasToken } = useSession();
  const { state, reload } = useReferences();
  const operationKey = useOperationKey();

  const [values, setValues] = useState<CardFormValues>(EMPTY_CARD_FORM);
  const [errors, setErrors] = useState<CardFormErrors>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CreateCardResult | null>(null);
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
    <K extends CardFormField>(field: K, value: CardFormValues[K]) => {
      setValues((current) => ({ ...current, [field]: value }));
      setErrors((current) => ({ ...current, [field]: undefined }));
      setGeneralError(null);
      // Un formulario distinto es una operación distinta: nueva llave.
      operationKey.reset();

      if (field === "image") {
        const check = ++imageCheck.current;
        const file = value as File | null;
        if (!file) return;
        void inspectCardImage(file, readImageSize).then((problem) => {
          // Solo cuenta la revisión de la imagen más reciente.
          if (check === imageCheck.current && problem) {
            setErrors((current) => ({ ...current, image: problem }));
          }
        });
      }
    },
    [operationKey, readImageSize],
  );

  async function handleSubmit() {
    const found = validateCardValues(values);
    // La imagen también debe cumplir su revisión (formato, peso y medidas).
    if (!found.image && values.image) {
      const problem = await inspectCardImage(values.image, readImageSize);
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
      const created = await cards.create(
        toCreateCardInput(values),
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
    setValues(EMPTY_CARD_FORM);
    setErrors({});
    setGeneralError(null);
    setResult(null);
    operationKey.reset();
  }

  return (
    <section aria-labelledby="create-card-title" className="page">
      <h1 id="create-card-title">Crear carta</h1>
      <p className="page__intro">
        Completa los datos de la carta. Todos los campos son obligatorios.
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
                "No pudimos cargar los tipos, rarezas y habilidades. Inténtalo de nuevo."}
            </p>
          </Alert>
          <div className="form__actions">
            <Button variant="secondary" onClick={reload}>
              Reintentar
            </Button>
          </div>
        </>
      )}

      {state.status === "ready" && (
        <div className="page__columns">
          {result ? (
            <div className="page__result">
              <Alert variant="success" title={result.message}>
                <p>
                  Código de la carta: <strong>{result.code}</strong>
                </p>
                {result.replayed && (
                  <p>Esta carta ya estaba registrada, así que no se creó otra.</p>
                )}
                <p>
                  La versión pequeña de la imagen se está generando. La carta estará
                  disponible para los jugadores cuando termine.
                </p>
              </Alert>
              <div className="form__actions">
                <Button onClick={createAnother}>Crear otra carta</Button>
              </div>
            </div>
          ) : (
            <CreateCardForm
              ref={summaryRef}
              references={state.references}
              values={values}
              errors={errors}
              generalError={generalError}
              submitting={submitting}
              onChange={handleChange}
              onSubmit={() => void handleSubmit()}
            />
          )}
          <CardPreview
            references={state.references}
            values={values}
            done={result !== null}
          />
        </div>
      )}
    </section>
  );
}
