"""Small facade joining campaign loading, projection, gates, and commands."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from bot.director.commands import CommandFactory
from bot.director.gates import RevealEvaluation, evaluate_reveal_gates
from bot.director.loader import load_campaign
from bot.director.models import Campaign
from bot.director.projection import (
    CampaignStartBrief,
    PerformerBrief,
    ProjectionContext,
    build_performer_brief,
    build_safe_campaign_start_brief,
)


class CampaignDirector:
    """Read-only campaign authority. Persistence remains the game engine's job."""

    def __init__(self, campaign: Campaign) -> None:
        self._campaign = campaign
        self.commands = CommandFactory(campaign)

    @classmethod
    def from_json(cls, path: str | Path) -> "CampaignDirector":
        return cls(load_campaign(path))

    @property
    def canonical_campaign(self) -> Campaign:
        """Private server-side model; never serialize this property to clients."""

        return self._campaign

    def campaign_start_brief(self) -> CampaignStartBrief:
        return build_safe_campaign_start_brief(self._campaign)

    def performer_brief(self, context: ProjectionContext) -> PerformerBrief:
        return build_performer_brief(self._campaign, context)

    def evaluate_reveals(
        self,
        *,
        committed_event_ids: Iterable[str] = (),
        committed_clue_ids: Iterable[str] = (),
        current_scene_id: str | None = None,
        already_revealed_fact_ids: Iterable[str] = (),
    ) -> RevealEvaluation:
        return evaluate_reveal_gates(
            self._campaign,
            committed_event_ids=committed_event_ids,
            committed_clue_ids=committed_clue_ids,
            current_scene_id=current_scene_id,
            already_revealed_fact_ids=already_revealed_fact_ids,
        )
