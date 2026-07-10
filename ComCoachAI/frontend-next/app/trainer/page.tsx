"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Download, LogOut, RefreshCw, Save } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { FeedbackCards, SkillFeedbackCards, splitImprovements } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { getTrainerSession, setTrainerSession } from "@/lib/session";
import type { DashboardStats, TestInfo, TrainerSession } from "@/lib/types";

const DEFAULT_SKILLS = [
  "Select a skill...",
  "Clarity",
  "Professional Tone",
  "Structure",
  "Confidence",
  "Customer Empathy",
  "Logical Flow",
  "Problem Solving",
  "Vocabulary",
  "Conciseness",
  "Accountability",
  "Integrity",
  "Ownership",
  "Adaptability",
  "Critical Thinking",
  "Other (custom)",
];

type SkillDraft = { dropdown: string; custom: string; points: number; description: string };

function metric(label: string, value: string | number) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

export default function TrainerPage() {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<TrainerSession | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [activeTab, setActiveTab] = useState<"create" | "view">("create");
  const [title, setTitle] = useState("");
  const [scenario, setScenario] = useState("");
  const [difficulty, setDifficulty] = useState("Easy");
  const [skills, setSkills] = useState<SkillDraft[]>([
    { dropdown: "Clarity", custom: "", points: 10, description: "" },
    { dropdown: "Professional Tone", custom: "", points: 10, description: "" },
    { dropdown: "Structure", custom: "", points: 10, description: "" },
  ]);
  const [createdCode, setCreatedCode] = useState("");
  const [codeCopied, setCodeCopied] = useState(false);

  useEffect(() => setSession(getTrainerSession()), []);

  const loginMutation = useMutation({
    mutationFn: () => api.trainerLogin(email, password),
    onSuccess: (data) => {
      const nextSession = { trainer_id: data.trainer_id, name: data.name, role: data.role || "trainer" };
      setTrainerSession(nextSession);
      setSession(nextSession);
    },
  });

  const testsQuery = useQuery({
    queryKey: ["trainer-tests", session?.trainer_id],
    queryFn: () => api.trainerTests(session!.trainer_id),
    enabled: !!session,
  });

  const rubric = useMemo(() => {
    const values: Record<string, number> = {};
    const descriptions: Record<string, string> = {};
    skills.forEach((draft) => {
      const skill = draft.custom.trim() || (draft.dropdown !== "Select a skill..." && draft.dropdown !== "Other (custom)" ? draft.dropdown : "");
      if (skill) {
        values[skill] = draft.points;
        if (draft.description.trim()) descriptions[skill] = draft.description.trim();
      }
    });
    return { values, descriptions };
  }, [skills]);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createTest(session!.trainer_id, {
        test_title: title.trim(),
        scenario: scenario.trim(),
        rubric: rubric.values,
        rubric_descriptions: rubric.descriptions,
        difficulty_level: difficulty,
      }),
    onSuccess: (data) => {
      setCreatedCode(data.test_code || "");
      setCodeCopied(false);
      setTitle("");
      setScenario("");
      queryClient.invalidateQueries({ queryKey: ["trainer-tests", session?.trainer_id] });
    },
  });

  if (!session) {
    return (
      <AppShell>
        <Card className="mx-auto max-w-md">
          <CardHeader>
            <CardTitle>Trainer Dashboard Login</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" type="email" />
            <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" type="password" />
            <Button onClick={() => loginMutation.mutate()} disabled={!email || !password || loginMutation.isPending} className="w-full">
              {loginMutation.isPending ? "Logging in..." : "Login"}
            </Button>
            {loginMutation.isError ? <p className="text-sm text-destructive">Invalid credentials</p> : null}
          </CardContent>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold">Trainer Dashboard</h1>
            <p className="text-muted-foreground">Welcome, {session.name}.</p>
          </div>
          <Button
            variant="outline"
            onClick={() => {
              setTrainerSession(null);
              setSession(null);
            }}
          >
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>

        <div className="flex gap-2">
          <Button variant={activeTab === "create" ? "default" : "outline"} onClick={() => setActiveTab("create")}>
            Create Test
          </Button>
          <Button variant={activeTab === "view" ? "default" : "outline"} onClick={() => setActiveTab("view")}>
            View Tests
          </Button>
        </div>

        {activeTab === "create" ? (
          <Card>
            <CardHeader>
              <CardTitle>Create New Test</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Test Title" />
              <Textarea value={scenario} onChange={(event) => setScenario(event.target.value)} placeholder="Scenario" />
              <Select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                <option>Easy</option>
                <option>Medium</option>
                <option>Hard</option>
              </Select>
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">Define Rubric with Descriptions</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSkills((current) => [...current, { dropdown: "Select a skill...", custom: "", points: 10, description: "" }].slice(0, 10))}
                  >
                    Add Skill
                  </Button>
                </div>
                {skills.map((skill, index) => (
                  <div key={index} className="space-y-3 rounded-lg border p-3">
                    <div className="grid gap-3 md:grid-cols-[1fr_1fr_120px]">
                      <Select
                        value={skill.dropdown}
                        onChange={(event) => setSkills((current) => current.map((item, i) => (i === index ? { ...item, dropdown: event.target.value } : item)))}
                      >
                        {DEFAULT_SKILLS.map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </Select>
                      <Input
                        value={skill.custom}
                        onChange={(event) => setSkills((current) => current.map((item, i) => (i === index ? { ...item, custom: event.target.value } : item)))}
                        placeholder="Custom skill name"
                      />
                      <Input
                        value={skill.points}
                        min={1}
                        max={20}
                        type="number"
                        onChange={(event) => setSkills((current) => current.map((item, i) => (i === index ? { ...item, points: Number(event.target.value) } : item)))}
                      />
                    </div>
                    <Textarea
                      value={skill.description}
                      onChange={(event) => setSkills((current) => current.map((item, i) => (i === index ? { ...item, description: event.target.value } : item)))}
                      placeholder="Evaluation guidelines for this skill (optional)"
                    />
                  </div>
                ))}
              </div>
              <Button
                onClick={() => createMutation.mutate()}
                disabled={!title.trim() || !scenario.trim() || !Object.keys(rubric.values).length || createMutation.isPending}
              >
                {createMutation.isPending ? "Creating..." : "Create Test"}
              </Button>
              {createdCode ? (
                <div className="flex flex-col gap-3 rounded-lg border bg-blue-50 p-3 text-sm text-blue-950 sm:flex-row sm:items-center sm:justify-between">
                  <p>
                    <span className="font-medium">Test Code:</span> {createdCode}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      await navigator.clipboard.writeText(createdCode);
                      setCodeCopied(true);
                    }}
                  >
                    {codeCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    {codeCopied ? "Copied" : "Copy Code"}
                  </Button>
                </div>
              ) : null}
              {createMutation.isError ? <p className="text-sm text-destructive">Test creation failed.</p> : null}
            </CardContent>
          </Card>
        ) : (
          <section className="space-y-4">
            {testsQuery.isLoading ? <p className="text-sm text-muted-foreground">Loading tests...</p> : null}
            {testsQuery.data?.length === 0 ? <p className="text-sm text-muted-foreground">No tests created yet.</p> : null}
            {testsQuery.data?.map((test) => (
              <TrainerTestCard key={test.id} test={test} session={session} />
            ))}
          </section>
        )}
      </div>
    </AppShell>
  );
}

function TrainerTestCard({ test, session }: { test: TestInfo; session: TrainerSession }) {
  const queryClient = useQueryClient();
  const isActive = test.is_active ?? true;
  const [open, setOpen] = useState(false);
  const [selectedParticipant, setSelectedParticipant] = useState(0);
  const [editedTitle, setEditedTitle] = useState(test.test_title || test.training_name || "");
  const [editedScenario, setEditedScenario] = useState(test.scenario);
  const [editedDifficulty, setEditedDifficulty] = useState(test.difficulty_level);
  const [editedCode, setEditedCode] = useState(test.test_code || "");
  const [editedRubric, setEditedRubric] = useState(test.rubric || {});
  const [editedDescriptions, setEditedDescriptions] = useState(test.rubric_descriptions || {});

  const statsQuery = useQuery({
    queryKey: ["test-stats", test.test_code],
    queryFn: () => api.testStats(test.test_code!),
    enabled: open && !!test.test_code,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateTest(session.trainer_id, test.id!, {
        test_title: editedTitle,
        scenario: editedScenario,
        rubric: editedRubric,
        rubric_descriptions: editedDescriptions,
        difficulty_level: editedDifficulty,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer-tests", session.trainer_id] }),
  });

  const codeMutation = useMutation({
    mutationFn: () => api.updateTestCode(session.trainer_id, test.id!, editedCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer-tests", session.trainer_id] }),
  });

  const statusMutation = useMutation({
    mutationFn: () => api.updateTestStatus(session.trainer_id, test.id!, !isActive),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer-tests", session.trainer_id] }),
  });

  return (
    <Card>
      <CardHeader>
        <button className="flex w-full items-center justify-between text-left" onClick={() => setOpen((value) => !value)}>
          <CardTitle>
            {test.test_title || test.training_name || "Untitled"} ({test.test_code})
          </CardTitle>
          <span className="text-sm text-muted-foreground">{open ? "Hide" : "Show"}</span>
        </button>
      </CardHeader>
      {open ? (
        <CardContent className="space-y-6">
          <div className="rounded-lg border bg-secondary/45 p-4 text-sm">
            <p>
              <b>Difficulty:</b> {test.difficulty_level} · <b>Created:</b> {test.created_at}
            </p>
            <p className="mt-1">{test.has_participants ? "This test is locked because a participant has started it." : "This test can still be edited."}</p>
            <p className="mt-1">
              Test code status: <b>{isActive ? "Active" : "Inactive"}</b>
            </p>
            <p className="mt-1">Only admins can delete tests.</p>
          </div>
          <div className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="font-semibold">Test Code Availability</h3>
              <p className="text-sm text-muted-foreground">
                {isActive ? "Participants can use this test code." : "Participants cannot start this test code."}
              </p>
            </div>
            <Button variant={isActive ? "outline" : "default"} disabled={statusMutation.isPending} onClick={() => statusMutation.mutate()}>
              {statusMutation.isPending ? "Updating..." : isActive ? "Deactivate" : "Activate"}
            </Button>
          </div>

          <div className="space-y-3">
            <h3 className="font-semibold">Edit Test Details</h3>
            <Input value={editedTitle} disabled={!test.can_edit} onChange={(event) => setEditedTitle(event.target.value)} />
            <Textarea value={editedScenario} disabled={!test.can_edit} onChange={(event) => setEditedScenario(event.target.value)} />
            <Select value={editedDifficulty} disabled={!test.can_edit} onChange={(event) => setEditedDifficulty(event.target.value)}>
              <option>Easy</option>
              <option>Medium</option>
              <option>Hard</option>
            </Select>
            {Object.entries(editedRubric).map(([skill, points]) => (
              <div key={skill} className="grid gap-3 md:grid-cols-[1fr_120px]">
                <Input
                  value={skill}
                  disabled={!test.can_edit}
                  onChange={(event) => {
                    const next = { ...editedRubric };
                    delete next[skill];
                    next[event.target.value] = points;
                    setEditedRubric(next);
                  }}
                />
                <Input
                  value={points}
                  type="number"
                  disabled={!test.can_edit}
                  onChange={(event) => setEditedRubric((current) => ({ ...current, [skill]: Number(event.target.value) }))}
                />
                <Textarea
                  className="md:col-span-2"
                  value={editedDescriptions[skill] || ""}
                  disabled={!test.can_edit}
                  onChange={(event) => setEditedDescriptions((current) => ({ ...current, [skill]: event.target.value }))}
                  placeholder={`Guidelines for ${skill}`}
                />
              </div>
            ))}
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button disabled={!test.can_edit || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
                <Save className="h-4 w-4" />
                Save Test Changes
              </Button>
              <Input value={editedCode} disabled={!test.can_edit} onChange={(event) => setEditedCode(event.target.value)} className="sm:max-w-52" />
              <Button variant="outline" disabled={!test.can_edit || codeMutation.isPending} onClick={() => codeMutation.mutate()}>
                Update Test Code
              </Button>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
            <div>
              <h3 className="mb-2 font-semibold">Scenario</h3>
              <p className="rounded-lg border bg-secondary/45 p-4 text-sm">{test.scenario}</p>
            </div>
            <div>
              <h3 className="mb-2 font-semibold">Rubric</h3>
              <div className="space-y-2 text-sm">
                {Object.entries(test.rubric || {}).map(([skill, points]) => (
                  <p key={skill}>
                    {skill}: {points} pts
                  </p>
                ))}
              </div>
            </div>
          </div>

          {statsQuery.data ? <StatsPanel stats={statsQuery.data} test={test} selectedParticipant={selectedParticipant} setSelectedParticipant={setSelectedParticipant} /> : null}
          {statsQuery.isLoading ? <p className="text-sm text-muted-foreground">Loading stats...</p> : null}
          {statsQuery.isError ? <p className="text-sm text-destructive">Failed to load stats for this test.</p> : null}
        </CardContent>
      ) : null}
    </Card>
  );
}

function StatsPanel({
  stats,
  test,
  selectedParticipant,
  setSelectedParticipant,
}: {
  stats: DashboardStats;
  test: TestInfo;
  selectedParticipant: number;
  setSelectedParticipant: (index: number) => void;
}) {
  const participant = stats.participants[selectedParticipant];
  const improvements = splitImprovements(participant?.improvements);
  const rows = stats.participants.map((p) => {
    const row: Record<string, unknown> = {
      Name: p.name,
      Email: p.email || "-",
      "Total Score": `${(p.total_score || 0).toFixed(1)}%`,
      Completed: p.completed_at || "-",
    };
    Object.keys(test.rubric || {}).forEach((skill) => {
      row[skill] = p.scores?.[skill] ?? p.scores?.[skill.toLowerCase()] ?? 0;
    });
    return row;
  });

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-3">
        {metric("Participants", stats.total_participants)}
        {metric("Average Score", `${stats.average_score.toFixed(1)}%`)}
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Weakest Areas</p>
          <div className="mt-1 text-sm">
            {stats.weak_areas.slice(0, 2).map((area) => (
              <p key={area.skill}>{`${area.skill}: ${area.average.toFixed(1)}`}</p>
            ))}
          </div>
        </div>
      </div>
      {stats.total_participants === 0 ? (
        <p className="rounded-lg border bg-blue-50 p-4 text-sm text-blue-950">No participants yet. Share this test code: {test.test_code}</p>
      ) : (
        <>
          <DataTable rows={rows} />
          <div className="space-y-3">
            <h3 className="font-semibold">View Individual Details</h3>
            <Select value={selectedParticipant} onChange={(event) => setSelectedParticipant(Number(event.target.value))}>
              {stats.participants.map((p, index) => (
                <option value={index} key={index}>
                  {p.name} ({(p.total_score || 0).toFixed(1)}%)
                </option>
              ))}
            </Select>
          </div>
          {participant ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Participant Info</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p>Name: {participant.name}</p>
                  <p>Email: {participant.email || "-"}</p>
                  <p>Total Score: {(participant.total_score || 0).toFixed(1)}%</p>
                  <p>Completed: {participant.completed_at || "-"}</p>
                  <h4 className="pt-2 font-semibold">Skill Scores</h4>
                  {Object.entries(test.rubric || {}).map(([skill, max]) => {
                    const score = participant.scores?.[skill] ?? 0;
                    const pct = max > 0 ? Math.round((score / max) * 100) : 0;
                    return <p key={skill}>{`${skill}: ${score}/${max} (${pct}%)`}</p>;
                  })}
                  {participant.id ? (
                    <Button variant="outline" onClick={() => api.approveRetake(participant.id!).then((r) => window.alert(r.message))}>
                      <RefreshCw className="h-4 w-4" />
                      Approve Retake
                    </Button>
                  ) : null}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Transcript</CardTitle>
                </CardHeader>
                <CardContent>
                  <Textarea value={participant.transcript || "No transcript available"} disabled className="min-h-36" />
                  <p className="mt-2 text-sm text-muted-foreground">Word count: {(participant.transcript || "").split(/\s+/).filter(Boolean).length}</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Strengths</CardTitle>
                </CardHeader>
                <CardContent>
                  <FeedbackCards text={participant.strengths} color="green" />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Areas for Improvement</CardTitle>
                </CardHeader>
                <CardContent>
                  <FeedbackCards text={improvements.main} color="orange" />
                </CardContent>
              </Card>
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Rubric Wise Feedback</CardTitle>
                </CardHeader>
                <CardContent>
                  <SkillFeedbackCards text={improvements.rubric} />
                </CardContent>
              </Card>
              <div className="lg:col-span-2">
                <Button asChild>
                  <a href={api.downloadReportUrl(test.test_code!)} target="_blank" rel="noreferrer">
                    <Download className="h-4 w-4" />
                    Download Excel Report
                  </a>
                </Button>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
