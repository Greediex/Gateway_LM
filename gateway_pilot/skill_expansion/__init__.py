"""Read-only, opt-in Gateway_LM skill-catalog proposal.

Importing this module loads metadata helpers only. The opt-in synthetic
provider/bridge are separate modules; they never approve or modify live
registries and route execution through an operator-owned Core runtime.
"""
from .catalog import SkillCatalog, CatalogError, Skill, Relation
from .retrieval import SkillRetriever

__all__ = ["SkillCatalog", "CatalogError", "Skill", "Relation", "SkillRetriever"]
