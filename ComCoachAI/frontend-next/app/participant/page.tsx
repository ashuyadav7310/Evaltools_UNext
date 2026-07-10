"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Mic, PauseCircle, RefreshCw, WifiOff } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { FeedbackCards, SkillFeedbackCards, splitImprovements } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { clearRecording } from "@/lib/audio-store";
import { uploadParticipantAudio } from "@/lib/upload";
import type { ParticipantResult, TestInfo } from "@/lib/types";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";

export default function ParticipantPage() {
  const [testCode, setTestCode] = useState("");
  const [activeCode, setActiveCode] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [participantId, setParticipantId] = useState<number | null>(null);
  const [testInfo, setTestInfo] = useState<TestInfo | null>(null);
  const [result, setResult] = useState<ParticipantResult | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState("");
  const [attempts, setAttempts] = useState(0);
  const resultTopRef = useRef<HTMLDivElement | null>(null);
  const recorder = useAudioRecorder();

  const testQuery = useQuery({
    queryKey: ["participant-test", activeCode],
    queryFn: () => api.participantTest(activeCode),
    enabled: activeCode.length > 0 && !participantId,
    retry: false,
  });

  useEffect(() => {
    if (testQuery.data) setTestInfo(testQuery.data);
  }, [testQuery.data]);

  useEffect(() => {
    const onHidden = () => {
      if (document.hidden && recorder.status === "recording") {
        window.alert("Tab switching detected. Recording may be interrupted on mobile browsers.");
      }
    };
    document.addEventListener("visibilitychange", onHidden);
    return () => document.removeEventListener("visibilitychange", onHidden);
  }, [recorder.status]);

  const startMutation = useMutation({
    mutationFn: () => api.startParticipant(activeCode, name, email),
    onSuccess: (data) => setParticipantId(data.participant_id),
  });

  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!participantId || !recorder.recording) throw new Error("Recording is missing.");
      setUploadError("");
      setUploadProgress(0);
      setAttempts((value) => value + 1);
      return uploadParticipantAudio(participantId, recorder.recording.blob, recorder.recording.filename, setUploadProgress);
    },
    onSuccess: async (data) => {
      setResult(data);
      await clearRecording();
    },
    onError: (error) => setUploadError(error instanceof Error ? error.message : "Upload failed."),
  });

  const improvements = useMemo(() => splitImprovements(result?.improvements), [result?.improvements]);

  useEffect(() => {
    if (result) {
      requestAnimationFrame(() => resultTopRef.current?.scrollIntoView({ block: "start" }));
    }
  }, [result]);

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Participant Portal</h1>
          <p className="mt-1 text-muted-foreground">Enter your test code, register, record your response, and submit it for evaluation.</p>
        </div>

        {!participantId ? (
          <Card>
            <CardHeader>
              <CardTitle>Enter Test Code</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row">
                <Input value={testCode} onChange={(event) => setTestCode(event.target.value)} placeholder="e.g., abc123XYZ" />
                <Button onClick={() => setActiveCode(testCode.trim())} disabled={!testCode.trim() || testQuery.isFetching}>
                  {testQuery.isFetching ? "Checking..." : "Find Test"}
                </Button>
              </div>
              {testQuery.isError ? <p className="text-sm text-destructive">Invalid test code. Please check and try again.</p> : null}
              {testInfo ? (
                <div className="space-y-4 rounded-lg border bg-secondary/45 p-4">
                  <div>
                    <p className="font-medium">Test found</p>
                    <p className="text-sm text-muted-foreground">
                      {testInfo.test_title || testInfo.training_name} · {testInfo.difficulty_level}
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Your Full Name" />
                    <Input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="Email" />
                  </div>
                  <Button
                    onClick={() => startMutation.mutate()}
                    disabled={!name.trim() || !email.trim() || startMutation.isPending}
                    className="w-full sm:w-auto"
                  >
                    {startMutation.isPending ? "Starting..." : "Start Test"}
                  </Button>
                  {startMutation.isError ? <p className="text-sm text-destructive">{String(startMutation.error.message)}</p> : null}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ) : result ? (
          <section ref={resultTopRef} className="space-y-6">
            <Card className="border-emerald-200 bg-emerald-50">
              <CardContent className="pt-5">
                <p className="font-semibold text-emerald-950">Evaluation Complete. Your response is recorded.</p>
                <p className="mt-1 text-sm text-emerald-900">Review your personalized feedback below.</p>
              </CardContent>
            </Card>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Strengths</CardTitle>
                </CardHeader>
                <CardContent>
                  <FeedbackCards text={result.strengths} color="green" />
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
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Rubric Wise Feedback</CardTitle>
              </CardHeader>
              <CardContent>
                <SkillFeedbackCards text={improvements.rubric} />
              </CardContent>
            </Card>
            <Card className="border-red-200 bg-red-50">
              <CardContent className="space-y-3 pt-5">
                <p className="font-medium text-red-950">Test completed. You cannot retake this test without trainer approval.</p>
                <Button
                  variant="outline"
                  onClick={async () => {
                    const status = await api.retakeStatus(participantId);
                    window.alert(status.retake_allowed ? "Retake approved. Please refresh the page." : "Not yet approved. Ask your trainer.");
                  }}
                >
                  <RefreshCw className="h-4 w-4" />
                  Check Retake Approval
                </Button>
              </CardContent>
            </Card>
          </section>
        ) : (
          <section className="space-y-6">
            <Card className="border-emerald-200 bg-emerald-50">
              <CardContent className="pt-5">
                <p className="font-semibold text-emerald-950">Test Title: {testInfo?.test_title || testInfo?.training_name}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Your Scenario</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="rounded-lg border bg-secondary/45 p-4 text-sm leading-6">{testInfo?.scenario}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Submit Your Response</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="rounded-lg border bg-secondary/45 p-4 text-sm">
                  <ol className="list-decimal space-y-2 pl-5">
                    <li>Tap the microphone button to start recording.</li>
                    <li>If the browser asks for microphone permission, click Allow first, then start speaking.</li>
                    <li>Speak clearly into your device microphone.</li>
                    <li>Tap stop when finished and wait for the audio preview.</li>
                    <li>Submit the response and keep the page open while it uploads and analyzes.</li>
                  </ol>
                </div>

                {!recorder.support.secure ? (
                  <div className="flex gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950">
                    <WifiOff className="h-5 w-5 shrink-0" />
                    <p>Microphone access requires HTTPS on mobile browsers. Localhost and 127.0.0.1 are also allowed for development.</p>
                  </div>
                ) : null}

                <div className="flex flex-col gap-3 sm:flex-row">
                  {recorder.status === "recording" ? (
                    <Button variant="secondary" onClick={recorder.stop} className="bg-amber-400 text-slate-950 hover:bg-amber-500">
                      <PauseCircle className="h-4 w-4" />
                      Stop Recording ({recorder.seconds}s)
                    </Button>
                  ) : (
                    <Button onClick={recorder.start}>
                      <Mic className="h-4 w-4" />
                      Start Recording
                    </Button>
                  )}
                </div>

                {recorder.error ? <p className="text-sm text-destructive">{recorder.error}</p> : null}
                {recorder.recording ? (
                  <div className="space-y-3">
                    <p className="text-sm font-medium">Recording captured and saved locally until submission succeeds.</p>
                    <audio className="w-full" controls src={recorder.recording.url} />
                    <Button onClick={() => submitMutation.mutate()} disabled={submitMutation.isPending} className="w-full sm:w-auto">
                      {submitMutation.isPending ? "Submitting..." : "Submit Response"}
                    </Button>
                    {submitMutation.isPending ? (
                      <div className="space-y-2">
                        <div className="h-2 overflow-hidden rounded-full bg-secondary">
                          <div className="h-full bg-primary transition-all" style={{ width: `${uploadProgress}%` }} />
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Upload {uploadProgress}% · Attempt {attempts}. Analysis can take some time after upload finishes.
                        </p>
                      </div>
                    ) : null}
                    {uploadError ? (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
                        <p>{uploadError}</p>
                        <p className="mt-1">Your recording is still saved. Retry when the connection is stable.</p>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </section>
        )}
      </div>
    </AppShell>
  );
}
