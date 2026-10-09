import { classifyFailure, type Failure } from "../app/lib/connection";

/** Classify a non-2xx API response from its status and (FastAPI) JSON body. Never throws. */
export async function responseFailure(response: Response): Promise<Failure> {
  const body: unknown = await response.json().catch(() => null);
  return classifyFailure({ status: response.status, body });
}

/** Human-readable reason a non-2xx API response failed (FastAPI puts it in `detail`). */
export async function responseError(response: Response): Promise<string> {
  return (await responseFailure(response)).message;
}
