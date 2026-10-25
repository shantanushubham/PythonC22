import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

export interface FetchState<T> {
  data: T | undefined;
  error: ApiError | Error | undefined;
  loading: boolean;
  /** Fetch again. Pass `quiet` to keep the current data on screen instead of showing a spinner. */
  reload: (quiet?: boolean) => Promise<void>;
  setData: (data: T) => void;
}

/** Runs `fn` on mount and whenever `deps` change. Ignores answers from stale or unmounted requests. */
export function useFetch<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[] = []): FetchState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError | Error>();
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const run = useRef(0);

  const load = useCallback(async (quiet = false, signal?: AbortSignal) => {
    const id = ++run.current;
    if (!quiet) setLoading(true);
    try {
      const result = await fnRef.current(signal ?? new AbortController().signal);
      if (id !== run.current) return;
      setData(result);
      setError(undefined);
    } catch (e) {
      if (id !== run.current || (e instanceof DOMException && e.name === "AbortError")) return;
      setError(e as Error);
    } finally {
      if (id === run.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(false, controller.signal);
    return () => {
      controller.abort();
      run.current++;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const reload = useCallback((quiet = false) => load(quiet), [load]);
  return { data, error, loading, reload, setData };
}
