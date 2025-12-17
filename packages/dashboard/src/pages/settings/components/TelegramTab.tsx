import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Label, Input, Slider, Button } from "../../../shared/ui";
import { telegramSchema, type TelegramFormData } from "../lib/validation";
import { useSettings } from "../../../shared/api/hooks";
import type { AppConfig } from "../../../shared/api/types";

interface TelegramTabProps {
  settings: AppConfig;
}

export function TelegramTab({ settings }: TelegramTabProps) {
  const { updateSettings } = useSettings();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    watch,
    setValue,
  } = useForm<TelegramFormData>({
    resolver: zodResolver(telegramSchema),
    defaultValues: {
      bot_token: settings.telegram.bot_token,
      chat_id: settings.telegram.chat_id,
      message_cooldown_minutes: settings.telegram.message_cooldown_minutes,
    },
  });

  const cooldownValue = watch("message_cooldown_minutes");

  const onSubmit = async (data: TelegramFormData) => {
    await updateSettings({
      telegram: data,
    });
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-semibold mb-6">Настройки Telegram</h2>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Bot Token */}
        <div className="space-y-2">
          <Label htmlFor="bot_token">Bot Token</Label>
          <Input
            id="bot_token"
            type="password"
            placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
            {...register("bot_token")}
          />
          {errors.bot_token && (
            <p className="text-sm text-red-600">{errors.bot_token.message}</p>
          )}
          <p className="text-sm text-gray-500">
            Токен бота Telegram, полученный от @BotFather
          </p>
        </div>

        {/* Chat ID */}
        <div className="space-y-2">
          <Label htmlFor="chat_id">Chat ID</Label>
          <Input
            id="chat_id"
            type="text"
            placeholder="-1001234567890"
            {...register("chat_id")}
          />
          {errors.chat_id && (
            <p className="text-sm text-red-600">{errors.chat_id.message}</p>
          )}
          <p className="text-sm text-gray-500">
            ID чата или канала для отправки уведомлений
          </p>
        </div>

        {/* Message Cooldown */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="message_cooldown_minutes">
              Интервал сообщений
            </Label>
            <span className="text-sm font-medium text-gray-700">
              {cooldownValue} мин
            </span>
          </div>
          <Slider
            id="message_cooldown_minutes"
            min={1}
            max={1440}
            step={1}
            value={[cooldownValue]}
            onValueChange={(value) =>
              setValue("message_cooldown_minutes", value[0])
            }
          />
          {errors.message_cooldown_minutes && (
            <p className="text-sm text-red-600">
              {errors.message_cooldown_minutes.message}
            </p>
          )}
          <p className="text-sm text-gray-500">
            Минимальный интервал между сообщениями (1-1440 минут)
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