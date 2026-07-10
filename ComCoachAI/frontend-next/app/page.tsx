import Link from "next/link";
import { Sparkles, Users, UserRoundCog } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <AppShell>
      <section className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-normal sm:text-4xl">ComCoach AI</h1>
          <p className="mt-2 text-lg text-muted-foreground">AI-Powered Communication Evaluation System</p>
        </div>

        <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 text-sm text-orange-950">
          <div className="flex gap-3">
            <Sparkles className="mt-0.5 h-5 w-5 shrink-0" />
            <p>
              ComCoach AI helps trainers run structured communication assessments and gives participants fast, focused
              feedback they can use to speak with more clarity, confidence, and professionalism.
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserRoundCog className="h-5 w-5 text-primary" />
                For Trainers
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
                <li>Create custom communication tests</li>
                <li>Define evaluation rubrics</li>
                <li>View participant results</li>
                <li>Download analytics reports</li>
              </ul>
              <Button asChild className="w-full">
                <Link href="/trainer">Go to Trainer Dashboard</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-primary" />
                For Participants
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
                <li>Take communication tests</li>
                <li>Record your responses</li>
                <li>Get instant AI feedback</li>
                <li>See detailed scores</li>
              </ul>
              <Button asChild className="w-full">
                <Link href="/participant">Go to Participant Portal</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
