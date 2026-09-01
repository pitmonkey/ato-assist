"""Fixture values shared across test modules."""

from ato_assist import scaffold

SPEC = scaffold.Spec(
    name="Example System",
    short_name="exs",
    owner="business.owner@agency.gov.au",
    assessor="pete",
    data="OFFICIAL:Sensitive",
    environment="PROTECTED",
    marking="PROTECTED",
)
