import useSWR from "swr";
import toast from "react-hot-toast";
import { endpoints } from "../endpoints";
import { fetcher, axiosInstance } from "../fetcher";
import type { AppConfig } from "../types";

/**
 * Hook for fetching and managing application settings
 */
export function useSettings() {
  const { data, error, mutate, isLoading } = useSWR<AppConfig>(
    endpoints.mergedConfig,
    fetcher,
    {
      revalidateOnFocus: true,
      refreshInterval: 30000, // Refresh every 30 seconds
      onError: (err) => {
        console.error("Failed to load settings:", err);
        toast.error("Ошибка загрузки настроек");
      },
    }
  );

  /**
   * Update multiple settings at once
   */
  const updateSettings = async (updates: Partial<AppConfig>) => {
    const toastId = toast.loading("Сохранение настроек...");

    try {
      // Optimistic update
      mutate({ ...data!, ...updates }, false);

      // Make API request
      await axiosInstance.post(endpoints.bulkUpdate, { updates });

      // Revalidate
      await mutate();

      toast.success("Настройки успешно сохранены", { id: toastId });
      return true;
    } catch (err) {
      console.error("Failed to update settings:", err);

      // Rollback optimistic update
      await mutate();

      toast.error("Ошибка при сохранении настроек", { id: toastId });
      return false;
    }
  };

  /**
   * Update a single setting
   */
  const updateSetting = async (key: string, value: unknown) => {
    const toastId = toast.loading("Сохранение настройки...");

    try {
      await axiosInstance.put(endpoints.settingByKey(key), { value });
      await mutate();

      toast.success("Настройка сохранена", { id: toastId });
      return true;
    } catch (err) {
      console.error("Failed to update setting:", err);
      toast.error("Ошибка при сохранении настройки", { id: toastId });
      return false;
    }
  };

  /**
   * Reset a setting to its default value
   */
  const resetSetting = async (key: string) => {
    const toastId = toast.loading("Сброс настройки...");

    try {
      await axiosInstance.post(endpoints.resetSetting(key));
      await mutate();

      toast.success("Настройка сброшена к значению по умолчанию", {
        id: toastId,
      });
      return true;
    } catch (err) {
      console.error("Failed to reset setting:", err);
      toast.error("Ошибка при сбросе настройки", { id: toastId });
      return false;
    }
  };

  return {
    settings: data,
    isLoading,
    error,
    updateSettings,
    updateSetting,
    resetSetting,
    mutate,
  };
}