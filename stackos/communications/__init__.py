"""Provider-neutral communication processing primitives."""

from stackos.communications.contracts import (
    CommunicationDecision,
    CommunicationProcessingResult,
    NormalizedInboundEvent,
    NormalizedResourcePatch,
    NormalizedResourceWrite,
)
from stackos.communications.policy import (
    CommunicationInteractionCheck,
    CommunicationPolicyEvent,
    CommunicationPolicyProfile,
    candidate_refs,
    config_nested,
    config_policy,
    config_refs,
    config_string_list,
    evaluate_inbound_policy,
)
from stackos.communications.processor import process_inbound_event
from stackos.communications.resources import communication_record_by_external_id

__all__ = [
    "CommunicationDecision",
    "CommunicationInteractionCheck",
    "CommunicationPolicyEvent",
    "CommunicationPolicyProfile",
    "CommunicationProcessingResult",
    "NormalizedInboundEvent",
    "NormalizedResourcePatch",
    "NormalizedResourceWrite",
    "candidate_refs",
    "communication_record_by_external_id",
    "config_nested",
    "config_policy",
    "config_refs",
    "config_string_list",
    "evaluate_inbound_policy",
    "process_inbound_event",
]
