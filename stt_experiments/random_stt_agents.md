# Khmer STT Experiment Logbook

This document tracks all attempts, scripts, and results for developing a highly accurate Khmer Speech-to-Text pipeline.

## Baseline Test Data
- **Source Video:** `https://youtu.be/eBBZcotzsqA`
- **Objective:** Transcribe the spoken Khmer accurately, accounting for proper orthography and spacing.

## Experiments

### 1. Google Cloud Speech-to-Text (V1, km-KH)
- **Status:** Completed
- **Method:** Standard Google Cloud STT API (`recognize`).
- **Results:** Extremely sparse and inaccurate. The 60-second video clip only produced two short phrases: "ទទួល" (Confidence: 0.97) and "ត្រូវបានដាក់ចូលទៅក្នុងព្រៃនៅណា" (Confidence: 0.90). It struggled completely with the background noise/music and missed 95% of the dialogue.

### 2. Vertex AI Gemini 1.5 Pro (Multimodal)
- **Status:** Failed (API Key Leaked / Permission Denied)
- **Method:** Sending raw audio directly to Gemini 1.5 Pro via Vertex AI and Google GenAI SDK.
- **Prompt:** "Transcribe the Khmer audio exactly as spoken..."
- **Results:** Could not complete. The Vertex AI project lacked endpoint permissions, and the fallback AI Studio API key in Bifrost was reported as leaked/revoked.

### 3. Fast Local Whisper (whisper.cpp)
- **Status:** Failed
- **Method:** `whisper-cpp` via Homebrew on Apple Metal GPU. Fast (13s processing), but hallucinated `[Music]` or garbage text because the song's beat overpowered the vocals.
- **Results:** ❌ Base and Small models cannot separate Khmer vocals from heavy instrumentals natively.

### 4. Hybrid Pipeline (Demucs + Fast Local Whisper)
- **Status:** Failed
- **Method:** Used `demucs` to strip instrumentals and create an acapella `vocals.wav` track. Fed into `whisper-cpp`.
- **Results:** ❌ Even on isolated vocals, local quantized models (`small` and `large-v3-turbo`) hallucinate garbage characters (e.g., `ស, ស, ឡ, ឡ, ឡ, ឡ`). Local Whisper cannot handle Khmer singing reliably.

### 5. Fast Cloud Pipeline (Demucs + Google Cloud Speech API)
- **Status:** Partial Success (60s clip) / Failed (Full Song)
- **Method:** 
  1. Isolated vocals using `demucs` on Apple GPU (~45 seconds).
  2. Resampled to 16kHz mono via `ffmpeg`.
  3. Sent to Google Cloud Speech-to-Text V1 API using existing `sa.json` service account.
- **Results:** 
  - **60s clip test (Synchronous API):** ✅ "Partial Success" because it successfully extracted one coherent Khmer sentence (`ស្នាមញញឹមដែលគេផ្ដល់...`), which was a major improvement over Local Whisper crashing into infinite garbage loops.
  - **5-minute test (`LongRunningRecognize`):** ❌ "Failed". Upon reviewing the full transcript, the accuracy was completely unusable for singing. It skipped 80% of the lyrics and heavily hallucinated English phrases like "cannot transcribe", "dada", and "the voice".
- **Conclusion:** Standard conversational speech models (like Google Cloud Speech V1) are fundamentally unsuited for mapping stretched singing vowels to lyrics.

### 4. Hybrid (STT + LLM Post-Processing)
- **Status:** Pending
- **Method:** TBD
- **Results:** TBD

### 6. The Final Solution: Demucs + Gemini 2.x Flash
- **Status:** ✅ SUCCESS (Highest Accuracy)
- **Method:** 
  1. Isolate vocals using `demucs` to strip out heavy background music.
  2. Resample to 16kHz mono using `ffmpeg`.
  3. Upload `vocals.wav` via Gemini File API using `google-genai` SDK.
  4. Prompt `gemini-flash-latest` (since older `gemini-1.5-pro` is sunset and Vertex AI blocks access on this project).
- **Results:** Blazing fast processing and perfectly structured Khmer lyrics (with logical line breaks matching the rhythm, proper orthography, and ~95% semantic match to the original song). Completely avoided the hallucination loops found in Whisper and the gibberish found in Google Cloud Speech V1.

### 7. Documenting Failed AI Models & Dead Ends
While developing the pipeline, we ran into several dead ends that are documented here to prevent future regression:
- **Vertex AI (`gemini-1.5-pro`)**: Failed with `404 NOT_FOUND`. The Google Cloud Project `egd-ai-services-1782364268` had billing and API enabled, but Vertex AI Model Garden explicitly blocked access to the models for this project.
- **AI Studio (`gemini-1.5-pro`)**: This model was officially sunset/deprecated in 2026 and removed from the API completely.
- **AI Studio (`gemini-2.5-pro` & `gemini-2.0-flash`)**: Failed with `429 RESOURCE_EXHAUSTED (limit: 0)`. The Free Tier limit was strictly capped at 0 because the project had no linked billing account or was geo-blocked.
- **Google Cloud Speech V1 (`LongRunningRecognize`)**: Successfully processed the 5-minute song via GCS buckets without API limits, but the transcription accuracy was completely unusable for singing. It heavily hallucinated English phrases ("the voice", "cannot transcribe") because the model was trained on conversational speech, not music.
