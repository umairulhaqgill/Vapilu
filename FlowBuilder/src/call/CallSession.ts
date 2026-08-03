import { MicCapture, PlaybackScheduler } from "./audio";
import { LocalVAD } from "./vad";

export type CallStatus = "idle" | "connecting" | "connected" | "ended" | "error";

export interface CallLogEntry {
  id: number;
  kind: "caller" | "bot" | "system" | "error";
  text: string;
  at: number;
}

export interface CallSessionCallbacks {
  onStatusChange: (status: CallStatus) => void;
  onLog: (entry: CallLogEntry) => void;
  onBotPartial?: (text: string) => void;
  onLevel?: (rms: number) => void;
}

const DEFAULT_URL = "ws://localhost:8001/ws/call";
const MIC_SAMPLE_RATE = 16000;

// Plays the same role as Orchestrator/test_call_mic.py, but as a browser
// tab: connects to the Orchestrator's call WebSocket, streams mic audio
// in, plays synthesized speech back, and runs the same client-first local
// VAD barge-in the real client uses (see local_vad.py / CallSession).
export class CallSession {
  private ws: WebSocket | null = null;
  private mic: MicCapture | null = null;
  private playback: PlaybackScheduler | null = null;
  private readonly vad = new LocalVAD();
  private botPartial = "";
  private nextLogId = 1;
  private readonly callbacks: CallSessionCallbacks;

  constructor(callbacks: CallSessionCallbacks) {
    this.callbacks = callbacks;
  }

  set vadThreshold(threshold: number) {
    this.vad.threshold = threshold;
  }

  async start(tenantId: string): Promise<void> {
    this.callbacks.onStatusChange("connecting");

    const base = import.meta.env.VITE_ORCHESTRATOR_URL ?? DEFAULT_URL;
    const token = import.meta.env.VITE_ORCHESTRATOR_TOKEN ?? "";
    const params = new URLSearchParams({ token });
    if (tenantId) params.set("tenant_id", tenantId);

    const ws = new WebSocket(`${base}?${params.toString()}`);
    ws.binaryType = "arraybuffer";
    this.ws = ws;

    ws.onopen = () => {
      this.callbacks.onStatusChange("connected");
      this.startMic().catch((e) => {
        this.log("error", `Microphone error: ${e instanceof Error ? e.message : String(e)}`);
      });
    };
    ws.onclose = () => {
      this.callbacks.onStatusChange("ended");
      this.teardownLocal();
    };
    ws.onerror = () => {
      this.callbacks.onStatusChange("error");
      this.log("error", "WebSocket connection error - is the Orchestrator running on port 8001?");
    };
    ws.onmessage = (evt) => {
      if (evt.data instanceof ArrayBuffer) {
        this.playback?.enqueue(evt.data);
        return;
      }
      try {
        this.handleServerEvent(JSON.parse(evt.data));
      } catch {
        // ignore malformed frames
      }
    };
  }

  end(): void {
    this.ws?.close();
    this.teardownLocal();
  }

  private async startMic(): Promise<void> {
    this.mic = new MicCapture(MIC_SAMPLE_RATE, (frame) => {
      if (this.ws?.readyState !== WebSocket.OPEN) return;
      this.ws.send(frame.buffer as ArrayBuffer);
      this.callbacks.onLevel?.(LocalVAD.rms(frame));

      const event = this.vad.process(frame);
      if (event === "speech_start") {
        if (this.playback?.isPlaying) {
          this.playback.flush();
          this.log("system", "you interrupted the bot (local barge-in)");
        }
        this.ws.send(JSON.stringify({ event: "client_speech_start" }));
      }
    });
    await this.mic.start();
  }

  private handleServerEvent(data: Record<string, unknown>): void {
    const event = data.event as string | undefined;

    switch (event) {
      case "audio_format": {
        const sampleRate = data.sample_rate as number;
        const channels = data.channels as number;
        this.playback = new PlaybackScheduler(sampleRate, channels);
        void this.playback.resume();
        break;
      }
      case "bot_speech":
        this.log("bot", data.text as string);
        break;
      case "bot_speech_chunk":
        this.botPartial += data.text as string;
        this.callbacks.onBotPartial?.(this.botPartial);
        break;
      case "bot_speech_end":
        this.flushBotPartial();
        break;
      case "caller_transcript":
        this.log("caller", data.text as string);
        break;
      case "bot_interrupted":
        this.playback?.flush();
        this.flushBotPartial();
        this.log("system", "bot interrupted (server-side)");
        break;
      case "flow_action": {
        const values = JSON.stringify(data.values);
        this.log("system", `[action] ${data.flow_id}: ${data.connector}.${data.operation}(${values})`);
        break;
      }
      case "handoff": {
        const phone = data.escalation_phone ? ` -> ${data.escalation_phone}` : "";
        this.log("system", `[handoff] flow ${data.flow_id}${phone}`);
        break;
      }
      case "flow_complete":
        this.log("system", `[flow complete] ${data.flow_id}: ${JSON.stringify(data.values)}`);
        break;
      case "caller_speaking":
        break; // already reflected client-side, far earlier, via local VAD
      default:
        // The one message shape with no "event" key: {"error", "detail"}.
        if (typeof data.error === "string") {
          this.log("error", `${data.error}: ${(data.detail as string) ?? ""}`);
        }
        break;
    }
  }

  private flushBotPartial(): void {
    if (this.botPartial) {
      this.log("bot", this.botPartial);
      this.botPartial = "";
      this.callbacks.onBotPartial?.("");
    }
  }

  private log(kind: CallLogEntry["kind"], text: string): void {
    this.callbacks.onLog({ id: this.nextLogId++, kind, text, at: Date.now() });
  }

  private teardownLocal(): void {
    this.mic?.stop();
    this.mic = null;
    this.playback?.close();
    this.playback = null;
  }
}
