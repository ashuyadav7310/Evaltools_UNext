# backend/services/audio_analyzer.py
import wave
import struct
import math
import os
import subprocess

def _detect_reading_indicators(
    pauses: list,
    speech_ratio: float,
    duration: float,
    low_energy_ratio: float,
    num_pauses: int,
    avg_energy: float
) -> dict:
    """
    Detect if the speaker might be reading vs. speaking naturally.
    Returns: {"likely_reading": bool, "confidence": str, "indicators": list}
    """
    indicators = []
    reading_score = 0
    
    # 1. Very high speech ratio (> 85%) = possibly reading continuously
    if speech_ratio > 0.85:
        indicators.append("Very high speech ratio (85%+) - continuous delivery without natural pauses")
        reading_score += 2
    
    # 2. Very few pauses relative to duration
    pauses_per_30s = (num_pauses / duration) * 30 if duration > 0 else 0
    if pauses_per_30s < 1.5 and duration > 10:
        indicators.append("Very few pauses - less natural hesitation than expected")
        reading_score += 2
    
    # 3. All pauses are very short (no thinking pauses)
    if pauses:
        avg_pause_dur = sum(p['duration'] for p in pauses) / len(pauses)
        if avg_pause_dur < 0.7 and len(pauses) > 2:
            indicators.append("All pauses are brief (<0.7s) - no thinking pauses detected")
            reading_score += 1
    
    # 4. Very low energy variance (monotone - possible reading)
    if low_energy_ratio < 0.10 and speech_ratio > 0.70:
        indicators.append("Consistent energy throughout - possibly monotone reading pattern")
        reading_score += 1
    
    # 5. Estimate words per minute (if available from transcript)
    # This will be added when we call this function
    
    # 6. Very few long pauses (> 1.5s) = no thinking pauses
    long_pauses = [p for p in pauses if p['duration'] > 1.5]
    if len(long_pauses) == 0 and duration > 15:
        indicators.append("No long pauses (>1.5s) detected - minimal thinking time")
        reading_score += 1
    
    # Determine likelihood (more sensitive thresholds)
    if reading_score >= 4:
        likely = True
        confidence = "High"
    elif reading_score >= 2:  # ← Lowered from 3
        likely = True
        confidence = "Medium"
    elif reading_score >= 1:  # ← Lowered from 2
        likely = True
        confidence = "Low"
    else:
        likely = False
        confidence = "Natural"
    
    return {
        "likely_reading": likely,
        "confidence": confidence,
        "score": reading_score,
        "indicators": indicators
    }

def analyze_audio_quality(audio_path: str) -> dict:
    """
    Analyze audio file for pauses, energy, fluency.
    Uses only built-in Python wave module — NO librosa needed.
    """
    try:
        # Ensure we have a proper WAV file
        wav_path = _ensure_wav(audio_path)

        # Read WAV file
        with wave.open(wav_path, 'r') as wf:
            n_channels = wf.getnchannels()
            sampwidth  = wf.getsampwidth()
            framerate  = wf.getframerate()
            n_frames   = wf.getnframes()
            raw_data   = wf.readframes(n_frames)

        duration = n_frames / framerate

        if duration < 0.5:
            return _empty_result("Audio too short to analyze.")
        
        # ← ADD THIS NEW CHECK
        # ── Convert raw bytes to samples ─────────────────────
        if sampwidth == 2:
            fmt = f"{n_frames * n_channels}h"
        elif sampwidth == 1:
            fmt = f"{n_frames * n_channels}B"
        else:
            fmt = f"{n_frames * n_channels}h"

        samples = list(struct.unpack(fmt, raw_data))

        # Mono mix if stereo
        if n_channels == 2:
            samples = [
                (samples[i] + samples[i + 1]) // 2
                for i in range(0, len(samples) - 1, 2)
            ]

        if duration < 3.0:
            sample_count = min(16000, len(samples))
            if sample_count == 0:
                return _empty_result("No audio samples were found.")
            total_energy = sum(abs(s) for s in samples[:sample_count])
            if total_energy / sample_count < 100:
                return _empty_result("No speech detected - audio appears to be silent.")

        # ── Frame-level RMS energy analysis ──────────────────
        frame_size = int(framerate * 0.02)   # 20ms frames
        hop_size   = int(framerate * 0.01)   # 10ms hop

        energies = []
        for start in range(0, len(samples) - frame_size, hop_size):
            frame = samples[start:start + frame_size]
            rms   = math.sqrt(sum(s * s for s in frame) / len(frame))
            energies.append(rms)

        if not energies:
            return _empty_result("Could not extract audio energy frames.")

        avg_energy = sum(energies) / len(energies)
        max_energy = max(energies)

        # ── Dynamic silence threshold ─────────────────────────
        # 15% of max energy OR 20% of avg energy (whichever is larger)
        silence_threshold = max(
            avg_energy * 0.25,
            max_energy * 0.08,
            200  # Minimum absolute threshold
        )

        # ── Speech / silence labeling ─────────────────────────
        frame_duration_s = hop_size / framerate
        is_speech = [e > silence_threshold for e in energies]

        # Smooth labels (remove tiny blips)
        smoothed = _smooth_labels(is_speech, min_run=15)

        # ── Extract pauses ────────────────────────────────────
        pauses = []
        total_speech_frames = 0
        in_silence  = False
        silence_start_t = 0.0

        for i, speech in enumerate(smoothed):
            t = i * frame_duration_s
            if speech:
                total_speech_frames += 1
                if in_silence:
                    pause_dur = t - silence_start_t
                    # Ignore only leading silence and brief gaps between words.
                    if pause_dur >= 0.5 and silence_start_t > 0.3:
                        pauses.append({
                            "start":    round(silence_start_t, 2),
                            "end":      round(t, 2),
                            "duration": round(pause_dur, 2),
                            "severity": _pause_severity(pause_dur)
                        })
                    in_silence = False
            else:
                if not in_silence:
                    silence_start_t = t
                    in_silence = True

        # Trailing silence
        if in_silence:
            final_t   = len(smoothed) * frame_duration_s
            pause_dur = final_t - silence_start_t
            if pause_dur >= 0.5 and silence_start_t > 0.3:
                pauses.append({
                    "start":    round(silence_start_t, 2),
                    "end":      round(final_t, 2),
                    "duration": round(pause_dur, 2),
                    "severity": _pause_severity(pause_dur)
                })

        # ── Key metrics ───────────────────────────────────────
        total_speech_duration = total_speech_frames * frame_duration_s
        total_pause_duration  = sum(p['duration'] for p in pauses)
        speech_ratio          = total_speech_duration / duration if duration > 0 else 0
        num_pauses            = len(pauses)
        pauses_per_minute     = (num_pauses / duration) * 60 if duration > 0 else 0
        
        # ← ADD THIS NEW CHECK
        # If essentially no speech detected, return empty result
        if speech_ratio < 0.05:  # Less than 5% speech = blank audio
            return _empty_result(
                f"Insufficient speech detected. Only {speech_ratio*100:.1f}% of audio "
                "contained speech. Please record again and speak clearly."
            )

        avg_pause_duration    = total_pause_duration / num_pauses if num_pauses > 0 else 0

        low_energy_count = sum(
            1 for e in energies
            if 0 < e < silence_threshold * 1.5
        )
        low_energy_ratio = low_energy_count / len(energies) if energies else 0

        # ── Fluency score ─────────────────────────────────────
        fluency_score = _fluency_score(
            pauses_per_minute  = pauses_per_minute,
            speech_ratio       = speech_ratio,
            avg_pause_duration = avg_pause_duration,
            low_energy_ratio   = low_energy_ratio,
            avg_energy         = avg_energy
        )

        # ── Feedback ──────────────────────────────────────────
        feedback = _generate_feedback(
            pauses            = pauses,
            num_pauses        = num_pauses,
            total_pause_dur   = total_pause_duration,
            pauses_per_minute = pauses_per_minute,
            speech_ratio      = speech_ratio,
            fluency_score     = fluency_score,
            duration          = duration,
            low_energy_ratio  = low_energy_ratio
        )

        # ── Detect reading indicators ──────────────────────────
        reading_detection = _detect_reading_indicators(
            pauses=pauses,
            speech_ratio=speech_ratio,
            duration=duration,
            low_energy_ratio=low_energy_ratio,
            num_pauses=num_pauses,
            avg_energy=avg_energy
        )

        return {
            "duration_seconds":     round(duration, 2),
            "total_speech_seconds": round(total_speech_duration, 2),
            "total_pause_seconds":  round(total_pause_duration, 2),
            "speech_ratio_percent": round(speech_ratio * 100, 1),
            "num_pauses":           num_pauses,
            "avg_pause_duration":   round(avg_pause_duration, 2),
            "pauses_per_minute":    round(pauses_per_minute, 1),
            "pauses":               pauses,
            "fluency_score":        round(fluency_score, 1),
            "avg_energy":           round(avg_energy, 2),
            "low_energy_ratio":     round(low_energy_ratio, 3),
            "pitch_variation":      0,
            "feedback":             feedback,
            "reading_detection":    reading_detection,  # ← NEW
            "error":                None
        }
    except Exception as e:
        return _empty_result(f"Audio analysis failed: {str(e)}")


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _ensure_wav(audio_path: str) -> str:
    """
    Make sure the file is a valid WAV at 16kHz mono.
    Uses imageio_ffmpeg (already installed) for conversion.
    """
    if audio_path.endswith('.wav'):
        # Verify it opens OK
        try:
            with wave.open(audio_path, 'r'):
                pass
            return audio_path
        except Exception:
            pass  # Fall through to conversion

    # Convert using imageio_ffmpeg
    import imageio_ffmpeg as ffmpeg_lib
    ffmpeg_exe = ffmpeg_lib.get_ffmpeg_exe()
    out_path = audio_path.rsplit('.', 1)[0] + '_converted.wav'

    subprocess.run(
        [
            ffmpeg_exe,
            '-i', audio_path,
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', '16000',
            '-y', out_path
        ],
        check=True,
        capture_output=True
    )
    return out_path


def _smooth_labels(labels: list, min_run: int = 8) -> list:
    """Remove short blips of speech or silence."""
    result = list(labels)
    n = len(result)

    # Fill short silences inside speech
    i = 0
    while i < n:
        if not result[i]:
            j = i
            while j < n and not result[j]:
                j += 1
            if (j - i) < min_run and i > 0 and j < n:
                for k in range(i, j):
                    result[k] = True
            i = max(i + 1, j)
        else:
            i += 1

    # Remove short speech bursts in silence
    i = 0
    while i < n:
        if result[i]:
            j = i
            while j < n and result[j]:
                j += 1
            if (j - i) < min_run:
                for k in range(i, j):
                    result[k] = False
            i = max(i + 1, j)
        else:
            i += 1

    return result


def _pause_severity(duration: float) -> str:
    if duration >= 3.0:
        return "severe"
    elif duration >= 1.5:
        return "moderate"
    return "minor"


def _fluency_score(
    pauses_per_minute:  float,
    speech_ratio:       float,
    avg_pause_duration: float,
    low_energy_ratio:   float,
    avg_energy:         float
) -> float:
    score = 10.0

    # Pause frequency penalty
    #if pauses_per_minute > 12:
    #    score -= 4.0
    #elif pauses_per_minute > 8:
    #    score -= 3.0
    #elif pauses_per_minute > 6:
    #    score -= 2.0
    #elif pauses_per_minute > 3:
    #    score -= 1.0

    # Speech ratio penalty
    if speech_ratio < 0.50:
        score -= 3.5
    elif speech_ratio < 0.65:
        score -= 2.5
    elif speech_ratio < 0.75:
        score -= 1.5
    elif speech_ratio < 0.80:
        score -= 0.5

    # Average pause length penalty
    #if avg_pause_duration > 3.0:
    #    score -= 2.0
    #elif avg_pause_duration > 2.0:
    #    score -= 1.5
    #elif avg_pause_duration > 1.5:
    #    score -= 1.0
    #elif avg_pause_duration > 1.0:
    #    score -= 0.5

    # Low energy penalty
    if avg_energy < 200:
        score -= 1.5
    elif avg_energy < 500:
        score -= 0.5

    if low_energy_ratio > 0.40:
        score -= 1.5
    elif low_energy_ratio > 0.25:
        score -= 0.5

    return round(max(0.0, min(10.0, score)), 1)


def _generate_feedback(
    pauses:            list,
    num_pauses:        int,
    total_pause_dur:   float,
    pauses_per_minute: float,
    speech_ratio:      float,
    fluency_score:     float,
    duration:          float,
    low_energy_ratio:  float
) -> str:
    parts = []

    # Overall rating
    if fluency_score >= 8.5:
        parts.append("🟢 Excellent fluency — very smooth and confident delivery.")
    elif fluency_score >= 7.0:
        parts.append("🟢 Good fluency with minimal hesitations.")
    elif fluency_score >= 5.5:
        parts.append("🟡 Moderate fluency — some pauses and hesitations noticed.")
    elif fluency_score >= 4.0:
        parts.append("🟠 Below average fluency — frequent pauses affecting delivery.")
    else:
        parts.append("🔴 Poor fluency — excessive pauses and hesitations detected.")

    # Pause summary
    #if num_pauses == 0:
    #    parts.append("No significant pauses detected — great flow!")
    #elif num_pauses <= 2:
    #    parts.append(
    #        f"Only {num_pauses} pause(s) detected "
    #        f"({total_pause_dur:.1f}s total) — acceptable."
    #    )
    #else:
    #    parts.append(
    #        f"Detected {num_pauses} pauses totaling {total_pause_dur:.1f}s "
    #        f"out of {duration:.0f}s ({pauses_per_minute:.1f} pauses/min)."
    #    )

    # Speech ratio
    if speech_ratio < 0.55:
        parts.append(
            f"Only {speech_ratio*100:.0f}% active speech. "
            "Practice speaking more continuously."
        )
    elif speech_ratio < 0.70:
        parts.append(
            f"{speech_ratio*100:.0f}% active speech — aim for above 75%."
        )
    else:
        parts.append(
            f"{speech_ratio*100:.0f}% active speech — good engagement!"
        )

    # Notable pauses
    #severe   = [p for p in pauses if p['severity'] == 'severe']
    #moderate = [p for p in pauses if p['severity'] == 'moderate']

    #if severe:
    #    parts.append(
    #        "Long pauses (>3s) at: " +
    #        ", ".join([f"{p['start']}s ({p['duration']:.1f}s)" for p in severe[:3]])
    #    )
    #elif moderate:
    #    parts.append(
    #        "Moderate pauses at: " +
    #        ", ".join([f"{p['start']}s ({p['duration']:.1f}s)" for p in moderate[:3]])
    #    )

    # Mumbling
    if low_energy_ratio > 0.35:
        parts.append(
            "Voice energy drops detected — speak louder and more confidently."
        )

    # Tip
    #if pauses_per_minute > 6:
    #    parts.append(
    #        "Tip: Replace silent pauses with brief intentional pauses — "
    #        "don't fill gaps with 'um' or 'uh'."
    #    )

    return " ".join(parts)


def _empty_result(error_msg: str) -> dict:
    return {
        "duration_seconds":     0,
        "total_speech_seconds": 0,
        "total_pause_seconds":  0,
        "speech_ratio_percent": 0,
        "num_pauses":           0,
        "avg_pause_duration":   0,
        "pauses_per_minute":    0,
        "pauses":               [],
        "fluency_score":        0.0,
        "avg_energy":           0,
        "low_energy_ratio":     0,
        "pitch_variation":      0,
        "feedback":             error_msg,
        "error":                error_msg
    }
