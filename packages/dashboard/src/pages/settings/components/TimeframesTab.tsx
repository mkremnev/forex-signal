import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Label, Input, Button } from "../../../shared/ui";
import { timeframesSchema, type TimeframesFormData } from "../lib/validation";
import { useSettings } from "../../../shared/api/hooks";
import type { AppConfig } from "../../../shared/api/types";

interface TimeframesTabProps {
  settings: AppConfig;
}

// Common timeframes
const COMMON_TIMEFRAMES = ["1", "5", "15", "30", "60", "240", "1440"];

export function TimeframesTab({ settings }: TimeframesTabProps) {
  const { updateSettings } = useSettings();

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<TimeframesFormData>({
    resolver: zodResolver(timeframesSchema),
    defaultValues: {
      timeframes: settings.timeframes,
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: "timeframes",
  });

  const onSubmit = async (data: TimeframesFormData) => {
    await updateSettings(data);
  };

  const addTimeframe = (timeframe: string) => {
    // Check if timeframe already exists
    const exists = fields.some((field) => field.timeframe === timeframe);
    if (!exists) {
      append({
        timeframe,
        poll_interval_seconds: 60,
      });
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-semibold mb-6">Конфигурация таймфреймов</h2>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Quick Add Common Timeframes */}
        <div className="space-y-2">
          <Label>Добавить стандартный таймфрейм</Label>
          <div className="flex flex-wrap gap-2">
            {COMMON_TIMEFRAMES.map((tf) => {
              const exists = fields.some((field) => field.timeframe === tf);
              return (
                <button
                  key={tf}
                  type="button"
                  onClick={() => addTimeframe(tf)}
                  disabled={exists}
                  className={`px-4 py-2 rounded-md text-sm font-medium ${
                    exists
                      ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                      : "bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-300"
                  }`}
                >
                  {tf === "1440"
                    ? "Daily"
                    : tf === "240"
                      ? "4H"
                      : tf === "60"
                        ? "1H"
                        : `${tf}M`}
                  {exists && " ✓"}
                </button>
              );
            })}
          </div>
          <p className="text-sm text-gray-500">
            1 = 1 минута, 5 = 5 минут, 60 = 1 час, 1440 = 1 день
          </p>
        </div>

        {/* Timeframes List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Настроенные таймфреймы</Label>
            <Button
              type="button"
              onClick={() =>
                append({ timeframe: "5", poll_interval_seconds: 60 })
              }
              variant="outline"
              size="sm"
            >
              + Добавить
            </Button>
          </div>

          {fields.length === 0 && (
            <div className="text-center py-8 border-2 border-dashed border-gray-300 rounded-md">
              <p className="text-gray-500">
                Нет настроенных таймфреймов. Добавьте хотя бы один.
              </p>
            </div>
          )}

          {fields.map((field, index) => (
            <div
              key={field.id}
              className="p-4 border border-gray-200 rounded-md space-y-4"
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-gray-900">
                  Таймфрейм #{index + 1}
                </h4>
                <button
                  type="button"
                  onClick={() => remove(index)}
                  className="text-red-600 hover:text-red-800 text-sm font-medium"
                >
                  Удалить
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Timeframe */}
                <div className="space-y-2">
                  <Label htmlFor={`timeframes.${index}.timeframe`}>
                    Таймфрейм (минуты)
                  </Label>
                  <Input
                    id={`timeframes.${index}.timeframe`}
                    type="text"
                    placeholder="5"
                    {...register(`timeframes.${index}.timeframe`)}
                  />
                  {errors.timeframes?.[index]?.timeframe && (
                    <p className="text-sm text-red-600">
                      {errors.timeframes[index]?.timeframe?.message}
                    </p>
                  )}
                </div>

                {/* Poll Interval */}
                <div className="space-y-2">
                  <Label htmlFor={`timeframes.${index}.poll_interval_seconds`}>
                    Интервал опроса (сек)
                  </Label>
                  <Input
                    id={`timeframes.${index}.poll_interval_seconds`}
                    type="number"
                    min={10}
                    max={3600}
                    step={10}
                    placeholder="60"
                    {...register(`timeframes.${index}.poll_interval_seconds`, {
                      valueAsNumber: true,
                    })}
                  />
                  {errors.timeframes?.[index]?.poll_interval_seconds && (
                    <p className="text-sm text-red-600">
                      {
                        errors.timeframes[index]?.poll_interval_seconds
                          ?.message
                      }
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}

          {errors.timeframes && typeof errors.timeframes.message === "string" && (
            <p className="text-sm text-red-600">{errors.timeframes.message}</p>
          )}
        </div>

        {/* Info */}
        <div className="bg-orange-50 border border-orange-200 rounded-md p-4">
          <p className="text-sm text-orange-800">
            <strong>Важно:</strong> Изменение таймфреймов требует перезапуска
            агента. Интервал опроса определяет, как часто агент проверяет новые
            данные для каждого таймфрейма.
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