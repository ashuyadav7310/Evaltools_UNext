"use client";

import type { TrainerSession } from "@/lib/types";

const TRAINER_KEY = "comcoach.trainer.session";
const ADMIN_KEY = "comcoach.admin.token";

export function getTrainerSession(): TrainerSession | null {
  try {
    const raw = window.localStorage.getItem(TRAINER_KEY);
    return raw ? (JSON.parse(raw) as TrainerSession) : null;
  } catch {
    return null;
  }
}

export function setTrainerSession(session: TrainerSession | null) {
  if (!session) {
    window.localStorage.removeItem(TRAINER_KEY);
    return;
  }
  window.localStorage.setItem(TRAINER_KEY, JSON.stringify(session));
}

export function getAdminToken() {
  return window.localStorage.getItem(ADMIN_KEY) || "";
}

export function setAdminToken(token: string) {
  window.localStorage.setItem(ADMIN_KEY, token);
}
