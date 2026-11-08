"use client";
import { useEffect, useState, type ReactNode } from "react";
export function Resource<T>({
  load,
  children,
}: {
  load: (signal: AbortSignal) => Promise<T>;
  children: (data: T) => ReactNode;
}) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  const [attempt, setAttempt] = useState(0);
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setState({});
    setSlow(false);
    const timer = setTimeout(() => setSlow(true), 3000);
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ data });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState({ error: error.message });
      })
      .finally(() => clearTimeout(timer));
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [load, attempt]);
  if (state.error)
    return (
      <div className="panel error" role="alert">
        <h2>Couldn’t load this view</h2>
        <p>{state.error}</p>
        <button onClick={() => setAttempt(attempt + 1)}>Try again</button>
      </div>
    );
  if (state.data === undefined)
    return (
      <div aria-live="polite" aria-busy="true">
        <p>
          {slow
            ? "Waking up the server… Free hosting can take a moment."
            : "Loading the data snapshot…"}
        </p>
        <div className="skeleton-grid">
          {[1, 2, 3].map((x) => (
            <div className="skeleton" key={x} />
          ))}
        </div>
      </div>
    );
  return <>{children(state.data)}</>;
}
