"""Citation validation and grounding enforcement."""

from dataclasses import dataclass, field
import re

from app.assistant.outputs import GroundedAnswer, Citation
from app.assistant.deps import TurnRegistry


@dataclass
class ValidationResult:
    """Result of citation validation."""
    ok: bool
    errors: list[str] = field(default_factory=list)


class GroundingValidator:
    """Multi-stage validator for grounded answers.

    Validates:
    1. Content exists
    2. insufficient_evidence consistency with citations
    3. At least one citation if not insufficient_evidence
    4. Citation indices are 1-based, unique, contiguous
    5. [n] markers in answer match citation indices
    6. All chunk_ids exist in registry
    """

    def __init__(self, openai_client=None):
        """Initialize validator with optional OpenAI client for semantic judging."""
        self.openai_client = openai_client

    def validate(self, answer: GroundedAnswer, registry: TurnRegistry) -> ValidationResult:
        """Validate a grounded answer against the citation registry."""
        errors = []

        # Stage 1: content exists
        if not answer.answer.strip():
            errors.append("Answer text is empty")
            return ValidationResult(ok=False, errors=errors)

        # Stage 2: insufficient_evidence consistency
        if answer.insufficient_evidence and answer.citations:
            errors.append(
                "insufficient_evidence=True but citations are present; "
                "must have empty citations when insufficient evidence"
            )

        # Stage 3: at least one citation if not insufficient_evidence
        if not answer.insufficient_evidence and not answer.citations:
            errors.append(
                "No citations provided and insufficient_evidence=False; "
                "must cite all claims or set insufficient_evidence=True"
            )

        if errors:
            return ValidationResult(ok=False, errors=errors)

        # Stages 4-6 only apply if citations exist
        if answer.citations:
            # Stage 4: citation indices are 1-based, unique, contiguous
            indices = [c.citation_index for c in answer.citations]
            if not indices:
                return ValidationResult(ok=True, errors=[])

            if any(i < 1 for i in indices):
                errors.append("Citation indices must be 1-based (≥1)")
                return ValidationResult(ok=False, errors=errors)

            sorted_indices = sorted(set(indices))
            expected = list(range(1, len(sorted_indices) + 1))
            if sorted_indices != expected:
                errors.append(
                    f"Citation indices not contiguous: have {sorted_indices}, "
                    f"expected {expected}"
                )
                return ValidationResult(ok=False, errors=errors)

            # Stage 5: [n] markers in answer match citation indices
            markers = set(int(m) for m in re.findall(r'\[(\d+)\]', answer.answer))
            if markers != set(indices):
                errors.append(
                    f"[n] markers in answer {markers} don't match citation indices {set(indices)}"
                )
                return ValidationResult(ok=False, errors=errors)

            # Stage 6: all chunk_ids exist in registry
            for citation in answer.citations:
                if registry.get(str(citation.chunk_id)) is None:
                    errors.append(
                        f"Citation references chunk {citation.chunk_id} which is not in the registry"
                    )

        return ValidationResult(ok=len(errors) == 0, errors=errors)
