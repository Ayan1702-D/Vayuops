import type {
  AllBacktests,
  Backtest,
  Drift,
  Forecast,
  Health,
  History,
  Models,
  Split,
} from "./types";
const base = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:7860"
).replace(/\/$/, "");
async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(base + path, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.error?.message || `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
export const api = {
  health: (s?: AbortSignal) => get<Health>("/health", s),
  cities: (s?: AbortSignal) => get<{ cities: string[] }>("/cities", s),
  models: (s?: AbortSignal) => get<Models>("/models", s),
  drift: (s?: AbortSignal) => get<Drift>("/drift", s),
  forecast: (city: string, s?: AbortSignal) =>
    get<Forecast>("/forecast?city=" + encodeURIComponent(city), s),
  history: (city: string, s?: AbortSignal) =>
    get<History>("/history?days=60&city=" + encodeURIComponent(city), s),
  backtest: (city: string, split: Split, s?: AbortSignal) =>
    get<Backtest>(
      `/backtest?city=${encodeURIComponent(city)}&split=${split}`,
      s,
    ),
};
export async function allBacktests(
  signal?: AbortSignal,
): Promise<AllBacktests> {
  const { cities } = await api.cities(signal);
  const result: AllBacktests = [];
  // Bound concurrent requests to three while the host warms up.
  for (const city of cities) {
    result.push(
      ...(await Promise.all(
        (["val", "test_a", "test_b"] as Split[]).map((split) =>
          api.backtest(city, split, signal),
        ),
      )),
    );
  }
  return result;
}
