"""
MelodyMachine Audio Deepfake Detector Backend
=============================================
Default production audio deepfake detection backend in FraudShield.
Model: MelodyMachine/Deepfake-Audio-Detection-V2
"""
import torch
import numpy as np
from typing import Optional
from transformers import Wav2Vec2FeatureExtractor, AutoModelForAudioClassification

from src.stages.audio_backends.base import BaseAudioBackend


class MelodyMachineAudioBackend(BaseAudioBackend):
    """Adapter for MelodyMachine/Deepfake-Audio-Detection-V2."""

    def __init__(
        self,
        model_id: str = "MelodyMachine/Deepfake-Audio-Detection-V2",
        device: str = "cpu",
        threshold: float = 0.5,
    ):
        super().__init__(name="melodymachine", model_id=model_id, device=device, threshold=threshold)
        self._load_model()

    def _load_model(self):
        print(f"[AUDIO BACKEND] Loading MelodyMachine model: {self.model_id} on {self.device}...")
        self.processor = Wav2Vec2FeatureExtractor.from_pretrained(self.model_id)
        self.model = AutoModelForAudioClassification.from_pretrained(
            self.model_id,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
        ).to(self.device)
        self.model.eval()

        self.fake_index = 0
        if self.model.config.id2label:
            for k, v in self.model.config.id2label.items():
                if "fake" in v.lower() or "spoof" in v.lower():
                    self.fake_index = k
                    break
        print(f"[AUDIO BACKEND] MelodyMachine loaded. Fake class index: {self.fake_index} (id2label: {self.model.config.id2label})")

    def predict_chunk(self, chunk: np.ndarray, sample_rate: int = 16000) -> float:
        proc_out = self.processor(chunk, sampling_rate=sample_rate, return_tensors="pt", padding=True)
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
