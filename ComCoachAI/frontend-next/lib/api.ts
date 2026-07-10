import type { DashboardStats, TestInfo, TrainerSession } from "@/lib/types";

export const API_BASE_URL = (
  process.env.COMCOACH_API_BASE_URL ||
  process.env.API_BASE_URL ||
  "http://127.0.0.1:8000/api"
).replace(/\/$/, "");

type RequestOptions = RequestInit & {
  adminToken?: string;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.adminToken) headers.set("x-admin-token", options.adminToken);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  trainerLogin(email: string, password: string) {
    return request<TrainerSession & { message: string }>("/trainer/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  createTest(trainerId: number, data: Omit<TestInfo, "scenario" | "difficulty_level"> & Pick<TestInfo, "scenario" | "difficulty_level">) {
    return request<TestInfo>(`/trainer/create-test?trainer_id=${trainerId}`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  updateTest(trainerId: number, testId: number, data: Partial<TestInfo>) {
    return request<{ message: string; test: TestInfo }>(`/trainer/update-test/${testId}?trainer_id=${trainerId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
  updateTestCode(trainerId: number, testId: number, newTestCode: string) {
    return request<{ message: string; test_code: string }>(`/trainer/update-test-code/${testId}?trainer_id=${trainerId}`, {
      method: "PUT",
      body: JSON.stringify({ new_test_code: newTestCode }),
    });
  },
  updateTestStatus(trainerId: number, testId: number, isActive: boolean) {
    return request<{ message: string; test: TestInfo }>(`/trainer/tests/${testId}/status?trainer_id=${trainerId}`, {
      method: "PUT",
      body: JSON.stringify({ is_active: isActive }),
    });
  },
  trainerTests(trainerId: number) {
    return request<TestInfo[]>(`/trainer/tests/${trainerId}`);
  },
  testStats(testCode: string) {
    return request<DashboardStats>(`/dashboard/stats/${testCode}`);
  },
  participantTest(testCode: string) {
    return request<TestInfo>(`/participant/test/${encodeURIComponent(testCode)}`);
  },
  startParticipant(testCode: string, name: string, email: string) {
    const body = new FormData();
    body.set("test_code", testCode);
    body.set("name", name);
    body.set("email", email);
    return request<{ participant_id: number; message: string }>("/participant/start", {
      method: "POST",
      body,
    });
  },
  retakeStatus(participantId: number) {
    return request<{ retake_allowed: boolean }>(`/participant/retake-status/${participantId}`);
  },
  approveRetake(participantId: number) {
    return request<{ message: string }>(`/participant/approve-retake/${participantId}`, { method: "POST" });
  },
  adminOverview(adminToken: string) {
    return request<Record<string, number>>("/admin/overview", { adminToken });
  },
  adminTrainers(adminToken: string) {
    return request<Array<Record<string, unknown>>>("/admin/trainers", { adminToken });
  },
  createAdminTrainer(adminToken: string, email: string, password: string) {
    return request<Record<string, unknown>>("/admin/trainers", {
      method: "POST",
      adminToken,
      body: JSON.stringify({ email, password }),
    });
  },
  setTrainerStatus(adminToken: string, trainerId: number, active: boolean) {
    return request<{ message: string }>(`/admin/trainers/${trainerId}/${active ? "activate" : "deactivate"}`, {
      method: "PUT",
      adminToken,
    });
  },
  adminTests(adminToken: string) {
    return request<Array<Record<string, unknown>>>("/admin/tests", { adminToken });
  },
  deleteAdminTest(adminToken: string, testId: number) {
    return request<{ message: string }>(`/admin/tests/${testId}`, {
      method: "DELETE",
      adminToken,
    });
  },
  adminParticipants(adminToken: string) {
    return request<Array<Record<string, unknown>>>("/admin/participants", { adminToken });
  },
  downloadReportUrl(testCode: string) {
    return `${API_BASE_URL}/dashboard/download-report/${encodeURIComponent(testCode)}`;
  },
};
