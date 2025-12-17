import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Label, Input, Switch, Button } from "../../../shared/ui";
import { systemSchema, type SystemFormData } from "../lib/validation";
import { useSettings } from "../../../shared/api/hooks";
import type { AppConfig } from "../../../shared/api/types";

interface SystemTabProps {
  settings: AppConfig;
}

export function SystemTab({ settings }: SystemTabProps) {
  const { updateSettings } = useSettings();

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
    watch,
  } = useForm<SystemFormData>({
    resolver: zodResolver(systemSchema),
    defaultValues: {
      sqlite_path: settings.sqlite_path,
      backtest: {
        enabled: settings.backtest.enabled,
        lookback_bars: settings.backtest.lookback_bars,
      },
    },
  });

  const backtestEnabled = watch("backtest.enabled");

  const onSubmit = async (data: SystemFormData) => {
    await updateSettings(data);
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-semibold mb-6">Системные настройки</h2>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* SQLite Path */}
        <div className="space-y-2">
          <Label htmlFor="sqlite_path">Путь к базе данных SQLite</Label>
          <Input
            id="sqlite_path"
            type="text"
            placeholder="./data/cache.db"
            {...register("sqlite_path")}
          />
          {errors.sqlite_path && (
            <p className="text-sm text-red-600">{errors.sqlite_path.message}</p>
          )}
          <p className="text-sm text-gray-500">
            Путь к файлу базы данных для кэширования
          </p>
        </div>

        {/* Backtest Section */}
        <div className="space-y-4 border-t border-gray-200 pt-6">
          <h3 className="text-lg font-semibold">Настройки бэктестинга</h3>

          {/* Backtest Enabled */}
          <div className="flex items-center justify-between p-4 border border-gray-200 rounded-md">
            <div className="space-y-1">
              <Label htmlFor="backtest.enabled">Включить бэктестинг</Label>
              <p className="text-sm text-gray-500">
                Тестирование стратегии на исторических данных
              </p>
            </div>
            <Controller
              name="backtest.enabled"
              control={control}
              render={({ field }) => (
                <Switch
                  id="backtest.enabled"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              )}
            />
          </div>

          {/* Lookback Bars */}
          {backtestEnabled && (
            <div className="space-y-2 ml-4">
              <Label htmlFor="backtest.lookback_bars">
                Количество баров для анализа
              </Label>
              <Input
                id="backtest.lookback_bars"
                type="number"
                min={100}
                max={10000}
                step={100}
                {...register("backtest.lookback_bars", { valueAsNumber: true })}
              />
              {errors.backtest?.lookback_bars && (
                <p className="text-sm text-red-600">
                  {errors.backtest.lookback_bars.message}
                </p>
              )}
              <p className="text-sm text-gray-500">
                Количество исторических баров для бэктеста (100-10000)
              </p>
            </div>
          )}
        </div>

        {/* Warning */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
          <p className="text-sm text-yellow-800">
            <strong>Внимание:</strong> Изменение системных настроек может
            потребовать перезапуска агента.
          </p>
        </div>

        {/* Submit Button */}
        <div className="pt-4">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Сохранение..." : "Сохранить изменения"}
          </Button>
        </div>
      </form>
    </div>
  );
}