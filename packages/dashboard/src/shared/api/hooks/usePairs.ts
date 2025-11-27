import useSWR, { type SWRConfiguration } from "swr";
import { fetcher, type FetchError } from "../fetcher.ts";

// Example types for forex signals
export interface Signal {
  id: string;
  pair: string;
  timeframe: string;
  kind: string;
  message: string;
  importance: number;
  timestamp: string;
}

export interface SignalsResponse {
  signals: Signal[];
  total: number;
}

/**
 * Hook to fetch forex pairs
 * @param config - SWR configuration options
 * @returns SWR response with signals data
 */
export function usePairs(config?: SWRConfiguration) {
  const { data, error, isLoading, mutate } = useSWR<SignalsResponse, FetchError>(
    "/dashboard-api/pairs/get-all",
    fetcher,
    {
      refreshInterval: 30000, // Refresh every 30 seconds
      revalidateOnFocus: true,
      ...config,
    }
  );

  return {
    signals: data?.signals,
    total: data?.total,
    isLoading,
    isError: error,
    mutate,
  };
}
