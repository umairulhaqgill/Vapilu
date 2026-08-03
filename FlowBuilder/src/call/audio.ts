// Mic capture and TTS playback for the browser call-test page. There's no
// telephony transport here - this talks to the Orchestrator's WebSocket
// directly, so it plays the same role test_call_mic.py does, but as a
// browser tab instead of a Python client with a real mic device.
//
// Browser AEC note (see CLAUDE.md "No echo cancellation"): unlike the
// Python mic client, requesting echoCancellation via getUserMedia gets
// real acoustic echo cancellation from the browser/OS, so - unlike the
// Python client - this one doesn't strictly require headphones. It's
// still recommended for reliable barge-in testing.

function floatTo16BitPCM(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

export class MicCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private carry: number[] = [];
  private watchdog: ReturnType<typeof setInterval> | null = null;
  private readonly frameSize: number;
  private readonly sampleRate: number;
  private readonly onFrame: (frame: Int16Array) => void;

  constructor(sampleRate: number, onFrame: (frame: Int16Array) => void) {
    this.sampleRate = sampleRate;
    this.onFrame = onFrame;
    this.frameSize = Math.round(sampleRate * 0.02); // 20ms frames, matching the Python client
  }

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    this.ctx = new AudioContext({ sampleRate: this.sampleRate });
    await this.ctx.resume();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    // ScriptProcessorNode is deprecated in favor of AudioWorklet, but needs
    // no separate module file to load - simplest option for a dev tool.
    this.processor = this.ctx.createScriptProcessor(2048, 1, 1);
    this.processor.onaudioprocess = (e) => {
      const int16 = floatTo16BitPCM(e.inputBuffer.getChannelData(0));
      for (let i = 0; i < int16.length; i++) this.carry.push(int16[i]);
      while (this.carry.length >= this.frameSize) {
        this.onFrame(Int16Array.from(this.carry.splice(0, this.frameSize)));
      }
      // Never write to the output - we don't want the mic looping back
      // out the speakers on top of whatever the bot is saying.
      e.outputBuffer.getChannelData(0).fill(0);
    };
    this.source.connect(this.processor);
    // Some browsers only fire onaudioprocess if the node is part of a
    // live graph reaching the destination.
    this.processor.connect(this.ctx.destination);

    // Chrome can quietly suspend an AudioContext that's been producing
    // nothing but silence on its output for a while - and that's exactly
    // what this one does by design (see the fill(0) above, so the mic
    // never loops back out the speakers). Symptom without this: mic
    // capture just stops after a long-enough stretch of call audio, with
    // no error anywhere - the call looks "connected" but the server never
    // hears anything again. Both a reactive listener and a periodic
    // poll, since suspension can happen without a statechange event
    // firing in every browser.
    this.ctx.onstatechange = () => {
      if (this.ctx?.state === "suspended") void this.ctx.resume();
    };
    this.watchdog = setInterval(() => {
      if (this.ctx?.state === "suspended") void this.ctx.resume();
    }, 2000);
  }

  stop(): void {
    if (this.watchdog !== null) clearInterval(this.watchdog);
    this.watchdog = null;
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.ctx = null;
    this.carry = [];
  }
}

// Queue-based playback, mirroring test_call_mic.py's AudioPlayer: audio
// chunks are scheduled back-to-back on the Web Audio timeline rather than
// played immediately, so flush() (barge-in) can actually cancel what
// hasn't played yet instead of racing a device buffer it doesn't control.
export class PlaybackScheduler {
  private ctx: AudioContext;
  private nextStart: number;
  private activeSources: AudioBufferSourceNode[] = [];
  private readonly sampleRate: number;
  private readonly channels: number;

  constructor(sampleRate: number, channels: number) {
    this.sampleRate = sampleRate;
    this.channels = channels;
    this.ctx = new AudioContext({ sampleRate });
    this.nextStart = this.ctx.currentTime;
  }

  async resume(): Promise<void> {
    await this.ctx.resume();
  }

  enqueue(bytes: ArrayBuffer): void {
    const int16 = new Int16Array(bytes);
    const frameCount = Math.floor(int16.length / this.channels);
    if (frameCount === 0) return;
    const buffer = this.ctx.createBuffer(this.channels, frameCount, this.sampleRate);
    for (let ch = 0; ch < this.channels; ch++) {
      const channelData = buffer.getChannelData(ch);
      for (let i = 0; i < frameCount; i++) {
        channelData[i] = int16[i * this.channels + ch] / 0x8000;
      }
    }
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);
    const startAt = Math.max(this.nextStart, this.ctx.currentTime);
    source.start(startAt);
    this.nextStart = startAt + buffer.duration;
    this.activeSources.push(source);
    source.onended = () => {
      this.activeSources = this.activeSources.filter((s) => s !== source);
    };
  }

  get isPlaying(): boolean {
    return this.activeSources.length > 0;
  }

  flush(): void {
    for (const s of this.activeSources) {
      try {
        s.onended = null;
        s.stop();
      } catch {
        // already stopped/ended - fine
      }
    }
    this.activeSources = [];
    this.nextStart = this.ctx.currentTime;
  }

  close(): void {
    this.flush();
    void this.ctx.close();
  }
}
