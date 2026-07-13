r"""
Skill tools — list and read thinking disciplines (spec: method transfer).

Read-only on purpose: skills are seeded by Jack (or dropped in from a
frontier-model author) and refined by editing the files; FRIDAY authors
PLAYBOOKS for recurring tasks, but the domain-general disciplines are
curated, not self-written — keeping the library deliberate. The best-matching
skill is auto-injected per message (engine.respond), so these tools are for
explicit loads ("show me the trade-off skill") and browsing.
"""


def register_skill_tools(registry, skills):

    def list_skills() -> str:
        idx = skills.index_text()
        return idx or "No skills in brain/skills yet."

    def read_skill(name: str) -> str:
        return skills.read(name)

    registry.register(
        "list_skills",
        "Your skills: domain-general thinking disciplines (decomposition, "
        "trade-off analysis, self-verification...). The index is also in "
        "your context.",
        {"type": "object", "properties": {}},
        list_skills,
    )
    registry.register(
        "read_skill",
        "Read one thinking-discipline skill in full. The matching skill for "
        "a task is usually injected automatically — use this to load one "
        "explicitly by name.",
        {"type": "object", "properties": {"name": {"type": "string"}},
         "required": ["name"]},
        read_skill,
    )
