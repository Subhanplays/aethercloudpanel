export const API_URL =
  import.meta.env.VITE_API_URL ?? window.location.origin;

export type Vps = {
  id: number;
  vps_id: string;
  instance_name: string;
  owner_id: number;
  status: string;
  cpu_cores: number;
  ram_mb: number;
  storage_gb: number;
  ip_address?: string;
  expires_at?: string;
  created_at: string;
};

export type ResourceSummary = {
  host_cpu_cores: number;
  host_ram_mb: number;
  host_storage_gb: number;
  allocated_cpu_cores: number;
  allocated_ram_mb: number;
  allocated_storage_gb: number;
  available_cpu_cores: number;
  available_ram_mb: number;
  available_storage_gb: number;
};

export type OSImage = { id: number; label: string; lxd_alias: string; enabled: boolean };

export function token() {
  return localStorage.getItem("aether-token");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(token() ? { authorization: `Bearer ${token()}` } : {}),
      ...(init.headers ?? {})
    }
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
