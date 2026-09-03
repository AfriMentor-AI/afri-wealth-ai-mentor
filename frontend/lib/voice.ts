/**
 * Client-side Voice Recording & Transcription module.
 *
 * Implements high-reliability voice capture:
 * 1. Native Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`) for instant real-time transcription.
 * 2. Uncompressed 16kHz mono 16-bit PCM WAV capture via Web Audio API.
 * 3. Guaranteed `AudioContext.resume()` to prevent Chrome autoplay suspension (which causes silence).
 * 4. Backend transcription fallback via voice-service (`POST /api/v1/voice/stt`).
 */

import { apiFetch } from "./session";

export interface ActiveRecording {
  stop: () => Promise<string>;
  cancel: () => void;
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

/**
 * Encodes raw Float32 audio samples into standard 16-bit mono PCM WAV.
 */
function encodeWAV(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([view], { type: "audio/wav" });
}

/**
 * Starts recording audio and returns a controller that resolves to the transcribed text.
 * Uses browser-native recognition when available and falls back to voice-service backend.
 */
export async function startAudioRecording(
  onInterimText?: (text: string) => void
): Promise<ActiveRecording> {
  if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("Microphone access is not supported by this browser.");
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  // 1. Check for browser native SpeechRecognition
  const SpeechRec =
    (window as unknown as { SpeechRecognition?: any }).SpeechRecognition ||
    (window as unknown as { webkitSpeechRecognition?: any }).webkitSpeechRecognition;

  let nativeRecognition: any = null;
  let nativeTranscript = "";

  if (SpeechRec) {
    try {
      nativeRecognition = new SpeechRec();
      nativeRecognition.continuous = true;
      nativeRecognition.interimResults = true;
      nativeRecognition.lang = "en-US";

      nativeRecognition.onresult = (event: any) => {
        let current = "";
        for (let i = 0; i < event.results.length; i++) {
          current += event.results[i][0].transcript;
        }
        nativeTranscript = current;
        onInterimText?.(current);
      };

      nativeRecognition.onerror = (err: any) => {
        console.warn("Native speech recognition notice:", err.error || err);
      };

      nativeRecognition.start();
    } catch (e) {
      console.warn("Could not start native recognition, using audio backend:", e);
      nativeRecognition = null;
    }
  }

  // 2. Setup Web Audio API PCM WAV recorder
  const AudioContextClass =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

  const audioContext = new AudioContextClass({ sampleRate: 16000 });
  
  // Crucial: resume audio context to prevent Chrome suspension / silent recording
  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }

  const source = audioContext.createMediaStreamSource(stream);
  const processor = audioContext.createScriptProcessor(4096, 1, 1);

  const sampleChunks: Float32Array[] = [];
  let totalLength = 0;
  let maxAmplitude = 0;

  processor.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0);
    const chunk = new Float32Array(input);
    sampleChunks.push(chunk);
    totalLength += chunk.length;

    for (let i = 0; i < chunk.length; i++) {
      const abs = Math.abs(chunk[i]);
      if (abs > maxAmplitude) maxAmplitude = abs;
    }
  };

  source.connect(processor);
  processor.connect(audioContext.destination);

  const cleanup = () => {
    try {
      if (nativeRecognition) {
        nativeRecognition.stop();
      }
    } catch {}
    try {
      processor.disconnect();
      source.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      audioContext.close().catch(() => {});
    } catch {}
  };

  const stop = async (): Promise<string> => {
    // Wait briefly for native recognition to finalize if it got results
    cleanup();

    if (nativeTranscript.trim()) {
      return nativeTranscript.trim();
    }

    // Fallback: If native speech didn't catch it, send WAV to voice-service
    if (totalLength === 0) {
      return "";
    }

    const samples = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of sampleChunks) {
      samples.set(chunk, offset);
      offset += chunk.length;
    }

    const wavBlob = encodeWAV(samples, audioContext.sampleRate || 16000);
    try {
      return await transcribeAudio(wavBlob);
    } catch (err) {
      console.warn("Backend transcription fallback failed:", err);
      return nativeTranscript.trim();
    }
  };

  const cancel = () => {
    cleanup();
  };

  return { stop, cancel };
}

/**
 * Sends recorded WAV audio to the voice-service Speech-to-Text endpoint.
 */
export async function transcribeAudio(audioBlob: Blob): Promise<string> {
  const formData = new FormData();
  formData.append("file", audioBlob, "speech.wav");

  const res = await apiFetch("/api/v1/voice/stt", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Voice transcription failed with status: ${res.status}`);
  }

  const data = await res.json();
  if (data.error) {
    throw new Error(data.error);
  }
  return (data.text || "").trim();
}

/**
 * Text-to-Speech: sends text to voice-service and plays audio back.
 */
export async function playTextToSpeech(text: string, persona = "chioma"): Promise<HTMLAudioElement> {
  const res = await apiFetch("/api/v1/voice/tts", {
    method: "POST",
    body: JSON.stringify({ text, persona }),
  });

  if (!res.ok) {
    throw new Error(`Text-to-speech failed with status: ${res.status}`);
  }

  const blob = await res.blob();
  const audioUrl = URL.createObjectURL(blob);
  const audio = new Audio(audioUrl);
  audio.onended = () => URL.revokeObjectURL(audioUrl);
  await audio.play();
  return audio;
}
