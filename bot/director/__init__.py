"""Server-only campaign Director and safe voice-performer projections."""

from bot.director.commands import (
    AdjustNpcRelationshipCommand,
    CommandFactory,
    DirectorCommand,
    RecordClueCommand,
    RecordRevealCommand,
    RequestRollCommand,
    TransitionSceneCommand,
)
from bot.director.director import CampaignDirector
from bot.director.errors import CampaignValidationError, DirectorError, ProjectionError
from bot.director.gates import RevealEvaluation, evaluate_reveal_gates
from bot.director.loader import campaign_from_dict, load_campaign
from bot.director.models import Campaign
from bot.director.projection import (
    CampaignStartBrief,
    PerformerBrief,
    ProjectionContext,
    build_performer_brief,
    build_safe_campaign_start_brief,
)

__all__ = [
    "AdjustNpcRelationshipCommand",
    "Campaign",
    "CampaignDirector",
    "CampaignStartBrief",
    "CampaignValidationError",
    "CommandFactory",
    "DirectorCommand",
    "DirectorError",
    "PerformerBrief",
    "ProjectionContext",
    "ProjectionError",
    "RecordClueCommand",
    "RecordRevealCommand",
    "RequestRollCommand",
    "RevealEvaluation",
    "TransitionSceneCommand",
    "build_performer_brief",
    "build_safe_campaign_start_brief",
    "campaign_from_dict",
    "evaluate_reveal_gates",
    "load_campaign",
]
