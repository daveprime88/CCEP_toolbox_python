"""Versioned ANTs candidate recipes; parameter choices are not SPM acceptance."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegistrationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    recipe: Literal["ants-defaults-v1", "explicit-v1"] = "ants-defaults-v1"
    aff_metric: Literal["mattes", "GC", "meansquares"] = "mattes"
    aff_sampling: int = Field(default=32, ge=2)
    aff_random_sampling_rate: float = Field(default=0.2, gt=0, le=1)
    aff_iterations: tuple[int, ...] = (2100, 1200, 1200, 10)
    aff_shrink_factors: tuple[int, ...] = (6, 4, 2, 1)
    aff_smoothing_sigmas: tuple[float, ...] = (3, 2, 1, 0)
    syn_metric: Literal["mattes", "CC", "meansquares"] = "mattes"
    syn_sampling: int = Field(default=32, ge=1)
    reg_iterations: tuple[int, ...] = (40, 20, 0)
    grad_step: float = Field(default=0.2, gt=0)
    flow_sigma: float = Field(default=3, ge=0)
    total_sigma: float = Field(default=0, ge=0)
    smoothing_in_mm: bool = False
    singleprecision: bool = True
    use_legacy_histogram_matching: bool = False
    initialization: Literal["center-of-mass", "identity"] = "center-of-mass"

    @model_validator(mode="after")
    def schedules(self) -> "RegistrationSettings":
        if (
            not self.aff_iterations
            or len(
                {
                    len(self.aff_iterations),
                    len(self.aff_shrink_factors),
                    len(self.aff_smoothing_sigmas),
                }
            )
            != 1
        ):
            raise ValueError("Affine schedules must be nonempty and have equal lengths")
        if (
            any(
                i < 0
                for i in (
                    *self.aff_iterations,
                    *self.reg_iterations,
                    *self.aff_smoothing_sigmas,
                )
            )
            or any(i < 1 for i in self.aff_shrink_factors)
            or not self.reg_iterations
        ):
            raise ValueError("Invalid registration schedule")
        return self

    def arguments(self) -> dict[str, object]:
        result = self.model_dump(exclude={"recipe", "initialization"})
        result["initial_transform"] = (
            "Identity" if self.initialization == "identity" else None
        )
        return result

    def effective(self, transform: str) -> dict[str, object]:
        result = self.model_dump(mode="json")
        if transform == "SyN" and self.recipe == "ants-defaults-v1":
            result.update(
                aff_iterations=[2100, 1200, 1200, 0],
                aff_shrink_factors=[4, 2, 2, 1],
                aff_smoothing_sigmas=[3, 2, 1, 0],
                smoothing_in_mm=False,
                stages="ANTs built-in SyN affine + nonlinear; affine schedules hardcoded by backend",
            )
        elif transform == "SyN":
            result["stages"] = (
                "Explicit Affine then SyNOnly initialized with fitted affine"
            )
        else:
            result["stages"] = transform
        return result
