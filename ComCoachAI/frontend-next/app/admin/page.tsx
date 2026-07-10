"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const [authorizedToken, setAuthorizedToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [activeTab, setActiveTab] = useState<"trainers" | "tests" | "participants">("trainers");
  const [trainerEmail, setTrainerEmail] = useState("");
  const [trainerPassword, setTrainerPassword] = useState("");
  const [selectedTrainer, setSelectedTrainer] = useState("");
  const [selectedTest, setSelectedTest] = useState("");

  const overviewQuery = useQuery({
    queryKey: ["admin-overview", authorizedToken],
    queryFn: () => api.adminOverview(authorizedToken),
    enabled: !!authorizedToken,
    retry: false,
  });
  const trainersQuery = useQuery({
    queryKey: ["admin-trainers", authorizedToken],
    queryFn: () => api.adminTrainers(authorizedToken),
    enabled: !!authorizedToken && activeTab === "trainers",
    retry: false,
  });
  const testsQuery = useQuery({
    queryKey: ["admin-tests", authorizedToken],
    queryFn: () => api.adminTests(authorizedToken),
    enabled: !!authorizedToken && activeTab === "tests",
    retry: false,
  });
  const participantsQuery = useQuery({
    queryKey: ["admin-participants", authorizedToken],
    queryFn: () => api.adminParticipants(authorizedToken),
    enabled: !!authorizedToken && activeTab === "participants",
    retry: false,
  });

  const createTrainer = useMutation({
    mutationFn: () => api.createAdminTrainer(authorizedToken, trainerEmail, trainerPassword),
    onSuccess: () => {
      setTrainerEmail("");
      setTrainerPassword("");
      queryClient.invalidateQueries({ queryKey: ["admin-trainers", authorizedToken] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview", authorizedToken] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: (active: boolean) => api.setTrainerStatus(authorizedToken, Number(selectedTrainer), active),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-trainers", authorizedToken] }),
  });

  const deleteTest = useMutation({
    mutationFn: () => api.deleteAdminTest(authorizedToken, Number(selectedTest)),
    onSuccess: () => {
      setSelectedTest("");
      queryClient.invalidateQueries({ queryKey: ["admin-tests", authorizedToken] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview", authorizedToken] });
    },
  });

  const overview = overviewQuery.data;

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Admin Dashboard</h1>
          <p className="text-muted-foreground">Use the admin token to manage trainers, tests, and participants.</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Admin Access</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Input
                value={token}
                type={showToken ? "text" : "password"}
                onChange={(event) => {
                  setToken(event.target.value);
                  if (authorizedToken) setAuthorizedToken("");
                }}
                placeholder="Admin Token"
                className="pr-11"
              />
              <button
                type="button"
                aria-label={showToken ? "Hide admin token" : "Show admin token"}
                className="absolute right-2 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                onClick={() => setShowToken((value) => !value)}
              >
                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <Button onClick={() => setAuthorizedToken(token.trim())} disabled={!token.trim()}>
              Enter Admin Center
            </Button>
          </CardContent>
        </Card>

        {!authorizedToken ? <p className="text-sm text-muted-foreground">Enter your admin token to load dashboard data.</p> : null}
        {overviewQuery.isError ? <p className="text-sm text-destructive">Unauthorized or admin API unavailable.</p> : null}

        {overview ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries({
                Trainers: overview.trainers,
                Tests: overview.tests,
                Participants: overview.participants,
                Completed: overview.completed_submissions,
              }).map(([label, value]) => (
                <div key={label} className="rounded-lg border bg-card p-4">
                  <p className="text-sm text-muted-foreground">{label}</p>
                  <p className="mt-1 text-2xl font-semibold">{String(value)}</p>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button variant={activeTab === "trainers" ? "default" : "outline"} onClick={() => setActiveTab("trainers")}>
                Trainers
              </Button>
              <Button variant={activeTab === "tests" ? "default" : "outline"} onClick={() => setActiveTab("tests")}>
                Tests
              </Button>
              <Button variant={activeTab === "participants" ? "default" : "outline"} onClick={() => setActiveTab("participants")}>
                Participants
              </Button>
            </div>

            {activeTab === "trainers" ? (
              <section className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Create Trainer</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid gap-3 md:grid-cols-2">
                      <Input value={trainerEmail} onChange={(event) => setTrainerEmail(event.target.value)} placeholder="Trainer Email" type="email" />
                      <Input value={trainerPassword} onChange={(event) => setTrainerPassword(event.target.value)} placeholder="Trainer Password" type="password" />
                    </div>
                    <Button disabled={!trainerEmail.trim() || !trainerPassword.trim() || createTrainer.isPending} onClick={() => createTrainer.mutate()}>
                      Create Trainer
                    </Button>
                    {createTrainer.isError ? <p className="text-sm text-destructive">Failed to create trainer.</p> : null}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Existing Trainers</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <DataTable rows={trainersQuery.data || []} />
                    {trainersQuery.data?.length ? (
                      <div className="flex flex-col gap-3 sm:flex-row">
                        <Select value={selectedTrainer} onChange={(event) => setSelectedTrainer(event.target.value)}>
                          <option value="">Select trainer</option>
                          {trainersQuery.data.map((trainer) => (
                            <option key={String(trainer.id)} value={String(trainer.id)}>
                              {String(trainer.name)} ({String(trainer.email)}) [ID: {String(trainer.id)}]
                            </option>
                          ))}
                        </Select>
                        <Button variant="outline" disabled={!selectedTrainer || statusMutation.isPending} onClick={() => statusMutation.mutate(false)}>
                          Mark Inactive
                        </Button>
                        <Button variant="outline" disabled={!selectedTrainer || statusMutation.isPending} onClick={() => statusMutation.mutate(true)}>
                          Mark Active
                        </Button>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              </section>
            ) : null}

            {activeTab === "tests" ? (
              <Card>
                <CardHeader>
                  <CardTitle>Tests</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <DataTable rows={testsQuery.data || []} />
                  {testsQuery.data?.length ? (
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <Select value={selectedTest} onChange={(event) => setSelectedTest(event.target.value)}>
                        <option value="">Select test to delete</option>
                        {testsQuery.data.map((test) => (
                          <option key={String(test.id)} value={String(test.id)}>
                            {String(test.test_title || "Untitled")} ({String(test.test_code)}) [ID: {String(test.id)}]
                          </option>
                        ))}
                      </Select>
                      <Button variant="destructive" disabled={!selectedTest || deleteTest.isPending} onClick={() => deleteTest.mutate()}>
                        Delete Selected Test
                      </Button>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            ) : null}

            {activeTab === "participants" ? (
              <Card>
                <CardHeader>
                  <CardTitle>Participants</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataTable rows={participantsQuery.data || []} />
                </CardContent>
              </Card>
            ) : null}
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
