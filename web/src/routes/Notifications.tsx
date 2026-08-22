import { Link } from "react-router-dom"
import { IconBell } from "../ui/icons"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "../api/client"
import { useI18n } from "../i18n"
import { usePatient } from "../hooks/useAuth"
import { Card, Chip, EmptyState, ErrorState, ListSkeleton, Notice } from "../ui"

/**
 * Messages, and which ones you get.
 *
 * History and preferences on one screen deliberately: the moment somebody
 * wants to turn a message off is the moment they are looking at it.
 */
export function Notifications() {
  const { t } = useI18n()
  const patient = usePatient()
  const queryClient = useQueryClient()

  const history = useQuery({
    queryKey: ["notifications"],
    queryFn: api.notifications,
    enabled: patient !== null,
    staleTime: 30_000,
  })

  const preferences = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: api.notificationPreferences,
    enabled: patient !== null,
    staleTime: 5 * 60_000,
  })

  const update = useMutation({
    mutationFn: ({ kind, enabled }: { kind: string; enabled: boolean }) =>
      api.updateNotificationPreference(kind, enabled),
    onSuccess: (data) =>
      queryClient.setQueryData(["notification-preferences"], data),
  })

  if (!patient) {
    return (
      <div className="ml-page py-6">
        <h1 className="mb-4 text-h1">{t("notifications_title")}</h1>
        <EmptyState icon={<IconBell size={20} />}
          title={t("sign_in_to_track")}
          action={
            <Link to="/sign-in" className="ml-btn-primary ml-btn-sm">
              {t("sign_in")}
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-6 pb-24">
      <h1 className="text-h1">{t("notifications_title")}</h1>

      {/* --------------------------------------------------- preferences */}
      <section className="mt-6">
        <h2 className="ml-label mb-3">{t("which_messages")}</h2>

        {preferences.isLoading && <ListSkeleton rows={1} />}

        <Card className="divide-y divide-line">
          {preferences.data?.results.map((preference) => (
            <div
              key={preference.kind}
              className="flex items-center justify-between gap-4 px-4 py-3"
            >
              <span className="min-w-0">
                <span className="block text-body">{preference.label}</span>
                {!preference.can_disable && (
                  <span className="block text-small text-ink-muted">
                    {t("always_sent")}
                  </span>
                )}
                {preference.kind === "called" && preference.enabled && (
                  <span className="block text-small text-warning">
                    {t("called_off_warning")}
                  </span>
                )}
              </span>

              {preference.can_disable ? (
                <label className="flex shrink-0 items-center gap-2">
                  <span className="sr-only">{preference.label}</span>
                  <input
                    type="checkbox"
                    className="h-6 w-6 accent-primary"
                    checked={preference.enabled}
                    disabled={update.isPending}
                    onChange={(e) =>
                      update.mutate({
                        kind: preference.kind,
                        enabled: e.target.checked,
                      })
                    }
                  />
                </label>
              ) : (
                // Rendered as fixed, not as a toggle that does nothing.
                <Chip tone="neutral">{t("always_on")}</Chip>
              )}
            </div>
          ))}
        </Card>

        {update.isError && (
          <div className="mt-3">
            <ErrorState title={t("error_generic")} />
          </div>
        )}

        <p className="mt-3 text-caption text-ink-subtle">
          {t("preferences_note")}
        </p>
      </section>

      {/* ------------------------------------------------------- history */}
      <section className="ml-section">
        <h2 className="ml-label mb-3">{t("messages_sent")}</h2>

        {history.isLoading && <ListSkeleton rows={3} />}

        {history.data?.count === 0 && (
          <EmptyState icon={<IconBell size={20} />} title={t("no_messages")} body={t("no_messages_body")} />
        )}

        <ul className="space-y-2">
          {history.data?.results.map((message) => (
            <li key={message.id}>
              <Card className="p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <Chip tone="neutral">{message.kind_label}</Chip>
                  <time
                    className="shrink-0 text-caption text-ink-subtle"
                    dateTime={message.sent_at ?? undefined}
                  >
                    {message.sent_at
                      ? new Date(message.sent_at).toLocaleString(undefined, {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : ""}
                  </time>
                </div>
                <p className="mt-2 text-body">{message.body}</p>
              </Card>
            </li>
          ))}
        </ul>

        {(history.data?.count ?? 0) > 0 && (
          <div className="mt-4">
            <Notice tone="info">{t("sms_note")}</Notice>
          </div>
        )}
      </section>
    </div>
  )
}
