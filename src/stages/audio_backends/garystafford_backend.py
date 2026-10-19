"""
Gary Stafford Wav2Vec2 Deepfake Voice Detector Backend
======================================================
Adapter for GitHub repository Model C:
garystafford/wav2vec2-deepfake-voice-detector (revision: c66306024a7ede0be291e9c4558b37634782dc4e)

Label Mapping:
  0: 'real' (bona fide)
  1: 'fake' (synthetic / cloned voice)
"""
import torch
import numpy as np
from typing import Optional, Dict, Any
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

from src.stages.audio_backends.base import BaseAudioBackend


class GaryStaffordWav2Vec2Backend(BaseAudioBackend):
    """Adapter for garystafford/wav2vec2-deepfake-voice-detector."""

    def __init__(
        self,
        model_id: str = "garystafford/wav2vec2-deepfake-voice-detector",
        revision: str = "c66306024a7ede0be291e9c4558b37634782dc4",
        device: str = "cpu",
        threshold: float = 0.5,
    ):
        super().__init__(name="wav2vec2_garystafford", model_id=model_id, device=device, threshold=threshold)
        self.revision = revision
        self._load_model()

    def _load_model(self):
        print(f"[AUDIO BACKEND] Loading GitHub Model C: {self.model_id} (rev: {self.revision[:8]}) on {self.device}...")
        self.processor = AutoFeatureExtractor.from_pretrained(self.model_id, revision=self.revision)
        self.model = AutoModelForAudioClassification.from_pretrained(
            self.model_id,
            revision=self.revision,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
        ).to(self.device)
        self.model.eval()

        self.fake_index = 1
        if self.model.config.id2label:
            for k, v in self.model.config.id2label.items():
                if "fake" in v.lower() or "spoof" in v.lower():
                    self.fake_index = k
                    break
        print(f"[AUDIO BACKEND] GitHub Model C loaded. Fake class index: {self.fake_index} (id2label: {self.model.config.id2label})")

    def predict_chunk(self, chunk: np.ndarray, sample_rate: int = 16000) -> float:
        """
        Infers fake probability on a single audio chunk.
        Safe against dimension mismatches and clamps strictly to [0.0, 1.0].
        """
        proc_out = self.processor(chunk, sampling_rate=sample_rate, return_tensors="pt")
        try:
            model_dtype = next(iter(self.model.parameters())).dtype
        except Exception:
            model_dtype = getattr(self.model, "dtype", torch.float32)

        inputs = {}
        for k, v in proc_out.items():
            if torch.is_tensor(v):
                inputs[k] = v.to(self.device).to(model_dtype) if v.is_floating_point() else v.to(self.device)
            else:
                inputs[k] = v

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)
            fake_prob = float(probs[0, self.fake_index].item())

        return max(0.0, min(1.0, fake_prob))

    def predict_waveform(self, audio: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Direct single-pass prediction on a waveform array (up to 10 seconds).
        Returns logit margin and probabilities matching GitHub adapter semantics.
        """
        proc_out = self.processor(audio, sampling_rate=sample_rate, return_tensors="pt")
        try:
            model_dtype = next(iter(self.model.parameters())).dtype
        except Exception:
            model_dtype = getattr(self.model, "dtype", torch.float32)

        inputs = {}
        for k, v in proc_out.items():
            if torch.is_tensor(v):
                inputs[k] = v.to(self.device).to(model_dtype) if v.is_floating_point() else v.to(self.device)
            else:
                inputs[k] = v

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            real_logit = float(logits[0, 0].item())
            fake_logit = float(logits[0, 1].item())
            margin = fake_logit - real_logit
            probs = torch.nn.functional.softmax(logits, dim=-1)
            fake_prob = float(probs[0, self.fake_index].item())
            real_prob = float(probs[0, 0].item())

        return {
            "model_id": self.model_id,
            "fake_prob": round(fake_prob, 5),
            "real_prob": round(real_prob, 5),
            "logit_margin": round(margin, 5),
            "pred": 1 if fake_prob >= self.threshold else 0,
        }
