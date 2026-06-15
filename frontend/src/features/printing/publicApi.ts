import { publicV1Request } from "../../lib/api";

export type PrintBucket = {
  id: number;
  name: string;
  description: string;
};

export type PrintStatus = {
  public_token: string;
  status: string;
  title: string;
  created_at: string;
  accepted_at: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type PrintUploadBody = {
  identifier: string;
  kind: "stl" | "screenshot";
  filename: string;
  content_type: string;
};

export type PrintUpload = {
  url: string;
  fields: Record<string, string>;
};

export type PrintRequestPayload = {
  website?: string;
  identifier: string;
  bucket_id: number;
  title: string;
  description?: string;
  project_brief?: string;
  preferred_settings?: string;
  material?: string;
  color?: string;
  quantity: number;
  source_link?: string;
  contact_email?: string;
  contact_phone?: string;
  file_ids: number[];
};

export function fetchPrintBuckets(slug: string) {
  return publicV1Request<PrintBucket[]>(`/printing/public/${slug}/buckets`);
}

export function verifyPrintCheckin(slug: string, identifier: string) {
  return publicV1Request<{ username: string; external_id: string }>(
    `/printing/public/${slug}/checkin/verify`,
    { method: "POST", body: JSON.stringify({ identifier }) },
  );
}

export function presignPrintUpload(slug: string, body: PrintUploadBody) {
  return publicV1Request<{ file_id: number; upload: PrintUpload }>(
    `/printing/public/${slug}/uploads`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function uploadToStorage(upload: PrintUpload, file: File) {
  const formData = new FormData();
  for (const [key, value] of Object.entries(upload.fields)) {
    formData.append(key, value);
  }
  formData.append("file", file);

  const res = await fetch(upload.url, { method: "POST", body: formData });
  if (!res.ok) {
    throw new Error(`Upload failed (${res.status})`);
  }
}

export function submitPrintRequest(slug: string, payload: PrintRequestPayload) {
  return publicV1Request<{ public_token: string; status: string }>(
    `/printing/public/${slug}/requests`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function fetchPrintStatus(publicToken: string) {
  return publicV1Request<PrintStatus>(
    `/printing/public/requests/${publicToken}/status`,
  );
}
