"""
Abstract Base Class for Vision Deepfake Backends
=================================================
Defines the standard interface for all deepfake detection backends in FraudShield.
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BaseVisionBackend(ABC):
    """
    Standard interface for deepfake video/frame classification backends.
    All backends must output calibrated fake probability in range [0.0, 1.0],
    where 0.0 = Authentic/Pristine, 1.0 = Fully Synthetic/Manipulated.
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Returns the canonical name of the backend (e.g., 'hybrid_phase2', 'ms_eff_gcvit')."""
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Returns the model checkpoint or repository identifier."""
        pass

    @abstractmethod
    def predict_frame(self, frame_path_or_img) -> float:
        """
        Runs inference on a single face crop image or path.
        Returns:
            float: Calibrated fake probability in [0.0, 1.0].
        """
        pass

    @abstractmethod
    def predict_batch(self, frame_paths: List[str]) -> List[float]:
        """
        Runs inference across a sequence of face crop frames.
        Returns:
            List[float]: Frame-level fake probabilities in [0.0, 1.0].
        """
        pass

    def generate_heatmap(self, frame_path: str) -> Optional[str]:
        """
        Generates explainability saliency heatmap as a data URI base64 JPEG.
        Returns None or empty string if not supported by the backend architecture.
        """
        return None

    def close(self):
        """Release GPU VRAM / system resources."""
        pass
