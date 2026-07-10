export type TrainerSession = {
  trainer_id: number;
  name: string;
  role: string;
};

export type TestInfo = {
  test_id?: number;
  id?: number;
  test_code?: string;
  training_name?: string;
  test_title?: string;
  scenario: string;
  rubric?: Record<string, number>;
  rubric_descriptions?: Record<string, string>;
  difficulty_level: string;
  created_at?: string;
  has_participants?: boolean;
  has_completed_attempts?: boolean;
  can_edit?: boolean;
  can_delete?: boolean;
  is_active?: boolean;
};

export type ParticipantResult = {
  participant_id?: number;
  id?: number;
  name?: string;
  email?: string | null;
  transcript?: string | null;
  scores?: Record<string, number> | null;
  total_score?: number | null;
  strengths?: string | null;
  improvements?: string | null;
  completed_at?: string | null;
  audio_analysis?: Record<string, unknown> | null;
};

export type DashboardStats = {
  total_participants: number;
  average_score: number;
  weak_areas: Array<{ skill: string; average: number }>;
  participants: ParticipantResult[];
};

export type AdminOverview = {
  trainers: number;
  tests: number;
  participants: number;
  completed_submissions: number;
};
