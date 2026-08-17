"""Use cases: one class per creative operation the engine can perform."""

from creative_brain.application.use_cases.competing import (
    ApproveCreativeProject,
    DevelopWinner,
    JudgeFinalists,
    RunCreativeTournament,
)
from creative_brain.application.use_cases.evaluating import (
    CalculateCreativeDistance,
    EvaluateConcepts,
    EvaluateNovelty,
    RunCriticSociety,
    concept_text,
)
from creative_brain.application.use_cases.generating import (
    BuildCreativeConcepts,
    GenerateCreativeSeeds,
    ProposeTitles,
)
from creative_brain.application.use_cases.learning import (
    AnalyseObsessions,
    ConsolidateMemory,
    RunMetaCognition,
    UpdateEvolvingDna,
)
from creative_brain.application.use_cases.observing import (
    CaptureObservation,
    GenerateCreativeQuestions,
    RunResearch,
)
from creative_brain.application.use_cases.subconscious import (
    MutateRejectedConcepts,
    StartDreamCycle,
)

__all__ = [
    "AnalyseObsessions",
    "ApproveCreativeProject",
    "BuildCreativeConcepts",
    "CalculateCreativeDistance",
    "CaptureObservation",
    "ConsolidateMemory",
    "DevelopWinner",
    "EvaluateConcepts",
    "EvaluateNovelty",
    "GenerateCreativeQuestions",
    "GenerateCreativeSeeds",
    "JudgeFinalists",
    "MutateRejectedConcepts",
    "ProposeTitles",
    "RunCreativeTournament",
    "RunCriticSociety",
    "RunMetaCognition",
    "RunResearch",
    "StartDreamCycle",
    "UpdateEvolvingDna",
    "concept_text",
]
