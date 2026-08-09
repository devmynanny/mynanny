"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiFetch, apiJson } from "@/lib/api";
import {
  Check,
  Clock3,
  LoaderCircle,
  PlayCircle,
  RotateCcw,
  ShieldCheck,
  Square,
  Upload,
  Video,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

const questions = [
  "Tell families a little about yourself.",
  "Why do you enjoy caring for children?",
  "How would you handle a difficult or unexpected situation?",
  "What does a great day with a child look like to you?",
];
type Clip = { question_index: number; url: string; uploaded_at: string };
type Screening = {
  clips: Clip[];
  video_screening_complete: boolean;
  submitted_at?: string | null;
  resubmission_requested?: boolean;
};
const cameraConstraints: MediaStreamConstraints = {
  video: {
    width: { ideal: 854, max: 854 },
    height: { ideal: 480, max: 480 },
    frameRate: { ideal: 24, max: 24 },
  },
  audio: { channelCount: 1, sampleRate: 32000 },
};

export default function Interview() {
  const [step, setStep] = useState(0);
  const [clips, setClips] = useState<Clip[]>([]);
  const [recording, setRecording] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [screeningLoaded, setScreeningLoaded] = useState(false);
  const [message, setMessage] = useState("");
  const [resubmissionRequested, setResubmissionRequested] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(60);
  const previewRef = useRef<HTMLVideoElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    apiJson<Screening>("/nannies/me/video-screening")
      .then((data) => {
        setClips(data.clips || []);
        setSubmitted(data.video_screening_complete);
        setResubmissionRequested(Boolean(data.resubmission_requested));
        setScreeningLoaded(true);
      })
      .catch(() =>
        setMessage("Unable to verify your interview status. Camera access has not been requested."),
      );
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);
  useEffect(() => {
    if (!screeningLoaded || submitted) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      return;
    }
    let cancelled = false;
    async function prepareCamera() {
      try {
        const stream =
          streamRef.current ||
          (await navigator.mediaDevices.getUserMedia(cameraConstraints));
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (previewRef.current) {
          previewRef.current.srcObject = stream;
          await previewRef.current.play();
        }
      } catch {
        // A clear permission error is shown if the nanny starts recording.
      }
    }
    void prepareCamera();
    return () => {
      cancelled = true;
    };
  }, [step, clips, screeningLoaded, submitted]);
  async function ensureCamera() {
    let stream = streamRef.current;
    if (
      !stream ||
      stream.getTracks().some((track) => track.readyState === "ended")
    ) {
      stream = await navigator.mediaDevices.getUserMedia(cameraConstraints);
      streamRef.current = stream;
    }
    if (previewRef.current) {
      // The preview element is replaced by playback after each answer.
      // Reattach the retained stream whenever recording starts again.
      previewRef.current.srcObject = stream;
      await previewRef.current.play();
    }
    return stream;
  }
  async function start() {
    if (!screeningLoaded || submitted) return;
    setMessage("");
    setSecondsLeft(60);
    try {
      const stream = await ensureCamera();
      const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
        ? "video/webm;codecs=vp9,opus"
        : "video/webm";
      const recorder = new MediaRecorder(stream, {
        mimeType: mime,
        videoBitsPerSecond: 500_000,
        audioBitsPerSecond: 64_000,
      });
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () =>
        void upload(new Blob(chunksRef.current, { type: "video/webm" }));
      recorderRef.current = recorder;
      recorder.start(1000);
      setRecording(true);
      timerRef.current = setInterval(() => {
        setSecondsLeft((value) => {
          if (value <= 1) {
            if (timerRef.current) clearInterval(timerRef.current);
            setTimeout(stop, 0);
            return 0;
          }
          return value - 1;
        });
      }, 1000);
    } catch (err) {
      setMessage(
        err instanceof Error
          ? err.message
          : "Camera and microphone access is required.",
      );
    }
  }
  function stop() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    setRecording(false);
  }
  async function upload(blob: Blob) {
    setUploading(true);
    setMessage("Uploading your answer...");
    try {
      const form = new FormData();
      form.append("file", blob, `question-${step + 1}.webm`);
      const response = await apiFetch(
        `/nannies/me/video-screening/clips?question_index=${step}`,
        { method: "POST", body: form },
      );
      if (!response.ok) {
        const body = await response
          .json()
          .catch(() => ({ detail: "Upload failed" }));
        throw new Error(
          typeof body.detail === "string" ? body.detail : "Upload failed",
        );
      }
      const data = (await response.json()) as { clips: Clip[] };
      setClips(data.clips);
      setMessage("Answer saved. You can replay or record it again.");
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Unable to upload the recording.",
      );
    } finally {
      setUploading(false);
    }
  }
  async function submit() {
    const missingCount = questions.filter(
      (_, index) => !clips.some((clip) => clip.question_index === index),
    ).length;
    if (missingCount > 0) {
      setMessage(
        `Please record all four answers before submitting. ${missingCount} answer${missingCount === 1 ? " is" : "s are"} still outstanding.`,
      );
      return;
    }
    setUploading(true);
    setMessage("");
    try {
      await apiJson("/nannies/me/video-screening/complete", {
        method: "POST",
        body: "{}",
      });
      setSubmitted(true);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      setMessage("Your interview has been submitted for review.");
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Unable to submit your interview.",
      );
    } finally {
      setUploading(false);
    }
  }
  async function requestResubmission() {
    setUploading(true);
    setMessage("");
    try {
      await apiJson("/nannies/me/video-screening/resubmission-request", {
        method: "POST",
        body: "{}",
      });
      setResubmissionRequested(true);
      setMessage("Your request has been sent to the My Nanny team.");
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Unable to send request.",
      );
    } finally {
      setUploading(false);
    }
  }
  const current = clips.find((clip) => clip.question_index === step);
  const allAnswersComplete = questions.every((_, index) =>
    clips.some((clip) => clip.question_index === index),
  );
  return (
    <AuthenticatedPage>
      {(role) =>
        role !== "nanny" ? (
          <div className="card mx-auto max-w-xl p-8 text-center">
            <h1 className="text-2xl font-bold">Nanny access only</h1>
          </div>
        ) : (
          <div className="mx-auto max-w-5xl">
            <div className="eyebrow">Video screening</div>
            <h1 className="display mt-2 text-4xl sm:text-5xl">
              Let families meet the real you.
            </h1>
            <p className="mt-3 max-w-2xl text-[var(--muted)]">
              Record four short answers of up to one minute each. You can replay
              and replace any answer before submitting.
            </p>
            {submitted && (
              <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-emerald-50 p-4 text-emerald-900">
                <span className="flex items-center gap-3">
                  <Check />
                  Interview submitted. You can view your answers, but they are
                  locked.
                </span>
                <button
                  className="btn-secondary"
                  disabled={uploading || resubmissionRequested}
                  onClick={requestResubmission}
                >
                  {resubmissionRequested
                    ? "New attempt requested"
                    : "Request new interview attempt"}
                </button>
              </div>
            )}
            <div className="mt-7 grid gap-6 lg:grid-cols-[.68fr_1.32fr]">
              <aside className="card p-5">
                <div className="mb-5 flex items-center gap-3 rounded-2xl bg-[var(--blue-pale)] p-4">
                  <Clock3 className="text-[var(--blue-dark)]" />
                  <div>
                    <div className="font-bold">Maximum 1 minute per answer</div>
                    <div className="text-xs text-[var(--muted)]">
                      Private until approved
                    </div>
                  </div>
                </div>
                <ol className="grid gap-2">
                  {questions.map((question, index) => (
                    <li key={question}>
                      <button
                        onClick={() => setStep(index)}
                        disabled={recording || uploading}
                        className={`flex w-full gap-3 rounded-xl p-3 text-left text-sm ${index === step ? "bg-[var(--blue-dark)] text-white" : clips.some((clip) => clip.question_index === index) ? "text-[var(--green)]" : "text-[var(--muted)]"}`}
                      >
                        <span className="font-bold">
                          {clips.some(
                            (clip) => clip.question_index === index,
                          ) ? (
                            <Check size={17} />
                          ) : (
                            index + 1
                          )}
                        </span>
                        <span>{question}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              </aside>
              <section className="card p-5 sm:p-7">
                <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-[20px] bg-[var(--ink)] text-white">
                  {current && !recording ? (
                    <video
                      key={current.url}
                      src={current.url}
                      controls
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <video
                      ref={previewRef}
                      muted
                      playsInline
                      className={`h-full w-full object-cover transition duration-300 ${recording ? "blur-none" : "scale-105 blur-xl"}`}
                    />
                  )}
                  {!current && !recording && (
                    <div className="absolute rounded-2xl bg-[var(--ink)]/65 px-7 py-5 text-center backdrop-blur-sm">
                      <Video className="mx-auto h-12 w-12 text-[#a8d9ea]" />
                      <div className="mt-4 font-bold">Get ready</div>
                      <div className="mt-1 text-sm text-white/55">
                        You are not recording yet
                      </div>
                    </div>
                  )}
                  {recording && (
                    <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full bg-red-600 px-3 py-1.5 text-xs font-bold">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                      Recording · 0:{String(secondsLeft).padStart(2, "0")}
                    </div>
                  )}
                </div>
                <div className="mt-6">
                  <div className="eyebrow">
                    Question {step + 1} of {questions.length}
                  </div>
                  <h2 className="mt-2 text-2xl font-bold">{questions[step]}</h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                    Speak naturally. Recording stops automatically after 60
                    seconds and is optimised to reduce data and storage use.
                  </p>
                </div>
                {!submitted && (
                  <div className="mt-6 flex flex-wrap gap-3">
                    {recording ? (
                      <button
                        className="btn-primary !bg-red-600"
                        onClick={stop}
                      >
                        <Square size={17} />
                        Stop and save
                      </button>
                    ) : (
                      <button
                        className="btn-primary"
                        onClick={start}
                        disabled={uploading || submitted}
                      >
                        {current ? (
                          <RotateCcw size={18} />
                        ) : (
                          <PlayCircle size={18} />
                        )}{" "}
                        {current ? "Record again" : "Start recording"}
                      </button>
                    )}
                    {uploading && (
                      <span className="flex items-center gap-2 text-sm text-[var(--muted)]">
                        <LoaderCircle className="animate-spin" size={17} />
                        Working...
                      </span>
                    )}
                    {step < 3 && current && (
                      <button
                        onClick={() => setStep(step + 1)}
                        className="btn-secondary ml-auto"
                      >
                        Next question
                      </button>
                    )}
                  </div>
                )}
                {message && (
                  <div
                    role="status"
                    className="mt-4 rounded-xl bg-[var(--blue-pale)] p-3 text-sm"
                  >
                    {message}
                  </div>
                )}
              </section>
            </div>
            {allAnswersComplete && !submitted && (
              <div className="mt-6 flex flex-col gap-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-950 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-emerald-700 shadow-sm">
                    <Check size={21} />
                  </span>
                  <div>
                    <h2 className="font-bold">All four answers are ready</h2>
                    <p className="mt-1 text-sm text-emerald-800">
                      Please submit your interview so the My Nanny team can
                      review it.
                    </p>
                  </div>
                </div>
                <button
                  className="btn-primary shrink-0"
                  disabled={uploading}
                  onClick={submit}
                >
                  <Upload size={17} />
                  Submit interview
                </button>
              </div>
            )}
            <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--line)] bg-white p-4">
              <div className="flex items-start gap-3 text-sm text-[var(--muted)]">
                <ShieldCheck
                  className="shrink-0 text-[var(--green)]"
                  size={20}
                />
                <span>
                  Admin reviews all four answers. Parents only see approved
                  profile content.
                </span>
              </div>
              {!allAnswersComplete && !submitted && (
                <button
                  className="btn-primary"
                  disabled={uploading || submitted}
                  onClick={submit}
                >
                  <Upload size={17} />
                  {submitted ? "Submitted" : "Submit interview"}
                </button>
              )}
            </div>
          </div>
        )
      }
    </AuthenticatedPage>
  );
}
