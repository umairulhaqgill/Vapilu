// Port of Orchestrator/local_vad.py's energy-based VAD, so the browser
// test client exercises the same client-first barge-in model a real call
// uses (see CLAUDE.md "Barge-in is client-first") instead of silently
// relying on the server-side STT backstop, which is OFF by default
// (STT_BARGE_IN=false) precisely because it's noisier and slower.
export type VadEvent = "speech_start" | "speech_end" | null;

export class LocalVAD {
  threshold: number;
  private speechFramesRequired: number;
  private silenceFramesRequired: number;
  private consecutiveSpeech = 0;
  private consecutiveSilence = 0;
  private _speechActive = false;

  constructor(threshold = 1200, speechFramesRequired = 5, silenceFramesRequired = 25) {
    this.threshold = threshold;
    this.speechFramesRequired = speechFramesRequired;
    this.silenceFramesRequired = silenceFramesRequired;
  }

  static rms(frame: Int16Array): number {
    if (frame.length === 0) return 0;
    let sumSquares = 0;
    for (let i = 0; i < frame.length; i++) sumSquares += frame[i] * frame[i];
    return Math.sqrt(sumSquares / frame.length);
  }

  process(frame: Int16Array, muted = false): VadEvent {
    const level = LocalVAD.rms(frame);
    const isLoud = level > this.threshold;

    if (isLoud && !muted) {
      this.consecutiveSpeech += 1;
      this.consecutiveSilence = 0;
    } else {
      this.consecutiveSilence += 1;
      this.consecutiveSpeech = 0;
    }

    if (!this._speechActive && this.consecutiveSpeech >= this.speechFramesRequired) {
      this._speechActive = true;
      return "speech_start";
    }
    if (this._speechActive && this.consecutiveSilence >= this.silenceFramesRequired) {
      this._speechActive = false;
      return "speech_end";
    }
    return null;
  }

  get speechActive(): boolean {
    return this._speechActive;
  }

  reset(): void {
    this.consecutiveSpeech = 0;
    this.consecutiveSilence = 0;
    this._speechActive = false;
  }
}
