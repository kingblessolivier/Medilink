import type {
  FacilityDetail,
  Insurer,
  NearbyResponse,
  ServiceType,
} from "./types"

const BASE = "/api/v1"

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public type: string,
    message: string,
    public field?: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === "") continue
    url.searchParams.set(key, String(value))
  }

  const response = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  })

  if (!response.ok) {
    let type = "error"
    let detail = response.statusText
    let field: string | undefined
    try {
      const body = await response.json()
      type = body.type ?? type
      detail = body.detail ?? detail
      field = body.field
    } catch {
      // Non-JSON error body - keep the status text.
    }
    throw new ApiRequestError(response.status, type, detail, field)
  }

  return response.json() as Promise<T>
}

export const api = {
  nearby: (params: {
    lat: number
    lng: number
    radius?: number
    insurer?: string
    service?: string
    open_now?: boolean
    limit?: number
  }) => request<NearbyResponse>("/facilities/nearby", params),

  facility: (slug: string) => request<FacilityDetail>(`/facilities/${slug}`),

  insurers: () => request<{ results: Insurer[] }>("/insurers"),

  serviceTypes: () => request<{ results: ServiceType[] }>("/service-types"),

  districts: () => request<{ results: string[] }>("/districts"),
}
