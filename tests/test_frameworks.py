"""Framework vocabularies: what a control's `status` may say, per framework.

The shipped ISM file is loaded through the real loader rather than mirrored as a Python
literal, so a test asserting `alternate-control` is accepted is an assertion about what
actually ships.
"""

from pathlib import Path

from ato_assist import repo, schema

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SHIPPED = PLUGIN_ROOT / "config" / "frameworks"


def write(directory: Path, name: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yaml"
    path.write_text(text)
    return path


VALID = """schema: ato-assist/framework@1
id: demo
name: A Demonstration Framework
status:
  values: [not-assessed, ineffective, effective]
  unassessed: not-assessed
  uncited: [not-assessed]
  needs_claim: [effective]
retired:
  - {from: satisfied, to: effective}
"""


# --- the shipped ISM vocabulary ------------------------------------------------------


def test_the_shipped_ism_vocabulary_loads() -> None:
    vocabularies = repo.load_vocabularies(SHIPPED)
    assert vocabularies.problems == {}
    ism = vocabularies.get("ism")
    assert ism is not None
    assert ism.framework == "ism"


def test_the_ism_vocabulary_is_irap_effectiveness_not_the_old_words() -> None:
    ism = repo.load_vocabularies(SHIPPED).get("ism")
    assert ism is not None
    assert set(ism.values) == {
        "not-assessed",
        "ineffective",
        "alternate-control",
        "effective",
        "not-applicable",
    }
    assert ism.unassessed == "not-assessed"


def test_only_not_assessed_may_cite_nothing() -> None:
    ism = repo.load_vocabularies(SHIPPED).get("ism")
    assert ism is not None
    assert ism.uncited == ("not-assessed",)


def test_scoping_out_and_accepting_an_alternate_are_the_judgements_needing_a_claim() -> None:
    ism = repo.load_vocabularies(SHIPPED).get("ism")
    assert ism is not None
    assert set(ism.needs_claim) == {"not-applicable", "alternate-control"}


def test_every_word_of_the_old_vocabulary_is_retired_with_a_replacement() -> None:
    ism = repo.load_vocabularies(SHIPPED).get("ism")
    assert ism is not None
    retired = {r.old: r.new for r in ism.retired}
    assert retired == {
        "satisfied": "effective",
        "partially-satisfied": "ineffective",
        "not-satisfied": "ineffective",
        "inherited": "effective",
    }


def test_the_two_retirements_that_are_a_lean_rather_than_an_equivalence_say_so() -> None:
    """`inherited` and `partially-satisfied` have no IRAP equivalent — a human re-checks."""
    ism = repo.load_vocabularies(SHIPPED).get("ism")
    assert ism is not None
    flagged = {r.old: r for r in ism.retired if r.review}
    assert set(flagged) == {"inherited", "partially-satisfied"}
    assert "claim" in flagged["inherited"].note
    assert flagged["partially-satisfied"].note


# --- a vocabulary that cannot be used -------------------------------------------------


def test_a_missing_directory_yields_no_vocabularies_and_never_raises(tmp_path: Path) -> None:
    vocabularies = repo.load_vocabularies(tmp_path / "frameworks")
    assert vocabularies.by_framework == {}
    assert vocabularies.get("ism") is None


def test_the_problem_for_a_missing_file_names_the_file_and_where_to_get_it(
    tmp_path: Path,
) -> None:
    problem = repo.load_vocabularies(tmp_path / "frameworks").problem("ism")
    assert "frameworks/ism.yaml" in problem
    assert "config/frameworks" in problem


def test_unparseable_yaml_becomes_a_problem_rather_than_an_exception(tmp_path: Path) -> None:
    write(tmp_path, "demo", "status:\n\tvalues: [a]\n")  # a tab, outside the subset
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is None
    assert "demo.yaml" in vocabularies.problem("demo")


def test_a_valid_file_loads(tmp_path: Path) -> None:
    write(tmp_path, "demo", VALID)
    demo = repo.load_vocabularies(tmp_path).get("demo")
    assert demo is not None
    assert demo.values == ("not-assessed", "ineffective", "effective")
    assert demo.retired == (schema.Retirement("satisfied", "effective"),)


def test_a_vocabulary_with_no_values_is_a_problem(tmp_path: Path) -> None:
    write(tmp_path, "demo", VALID.replace("[not-assessed, ineffective, effective]", "[]"))
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is None
    assert "values" in vocabularies.problem("demo")


def test_an_unassessed_sentinel_outside_the_values_is_a_problem(tmp_path: Path) -> None:
    write(tmp_path, "demo", VALID.replace("unassessed: not-assessed", "unassessed: banana"))
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is None
    assert "unassessed" in vocabularies.problem("demo")


def test_a_needs_claim_value_outside_the_values_is_a_problem(tmp_path: Path) -> None:
    write(tmp_path, "demo", VALID.replace("needs_claim: [effective]", "needs_claim: [banana]"))
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is None
    assert "needs_claim" in vocabularies.problem("demo")


def test_a_value_both_exempt_from_citing_and_required_to_cite_a_claim_is_a_problem(
    tmp_path: Path,
) -> None:
    """Incoherent rather than merely odd: the two rules would contradict each other."""
    text = VALID.replace("needs_claim: [effective]", "needs_claim: [not-assessed]")
    write(tmp_path, "demo", text)
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is None
    problem = vocabularies.problem("demo")
    assert "uncited" in problem and "needs_claim" in problem


def test_a_retirement_pointing_at_a_value_that_does_not_exist_is_a_problem(
    tmp_path: Path,
) -> None:
    write(tmp_path, "demo", VALID.replace("to: effective}", "to: banana}"))
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is None
    assert "retired" in vocabularies.problem("demo")


def test_a_retirement_of_a_value_the_vocabulary_still_uses_is_a_problem(
    tmp_path: Path,
) -> None:
    """Retiring a live value would make every conformant file a migration finding."""
    write(tmp_path, "demo", VALID.replace("from: satisfied", "from: effective"))
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is None
    assert "retired" in vocabularies.problem("demo")


def test_one_bad_file_does_not_hide_a_good_one(tmp_path: Path) -> None:
    write(tmp_path, "demo", VALID)
    write(tmp_path, "broken", "\tnope\n")
    vocabularies = repo.load_vocabularies(tmp_path)
    assert vocabularies.get("demo") is not None
    assert vocabularies.get("broken") is None


def test_the_problem_for_a_framework_that_loaded_cleanly_is_empty(tmp_path: Path) -> None:
    write(tmp_path, "demo", VALID)
    assert repo.load_vocabularies(tmp_path).problem("demo") == ""


# --- the vocabulary shaping the control schema ----------------------------------------


def ism() -> schema.Vocabulary:
    vocabulary = repo.load_vocabularies(SHIPPED).get("ism")
    assert vocabulary is not None
    return vocabulary


def test_the_control_schema_takes_its_status_enum_from_the_framework() -> None:
    fields = {field.name: field for field in schema.control_schema(ism()).fields}
    assert fields["status"].enum == ism().values


def test_the_uncited_statuses_are_the_ones_excused_from_citing_anything() -> None:
    rule = schema.control_schema(ism()).any_of_when[0]
    assert rule.fields == ("claims", "evidence")
    assert rule.when_not_in == ism().uncited


def test_the_needs_claim_statuses_must_cite_a_claim_specifically() -> None:
    rule = schema.control_schema(ism()).any_of_when[1]
    assert rule.fields == ("claims",)
    assert rule.when_in == ism().needs_claim
    assert "claim" in rule.message


def test_the_control_schema_is_otherwise_the_one_structural_definition() -> None:
    """Only the status enum and the two citation rules are the framework's to set."""
    shaped = schema.control_schema(ism())
    assert shaped.kind == schema.CONTROL.kind
    assert shaped.directory == schema.CONTROL.directory
    assert [f.name for f in shaped.fields] == [f.name for f in schema.CONTROL.fields]


def test_the_module_level_control_schema_carries_no_frameworks_words() -> None:
    """A vocabulary is what makes a status checkable; the bare schema does not have one."""
    fields = {field.name: field for field in schema.CONTROL.fields}
    assert fields["status"].enum is None
    assert schema.CONTROL.any_of_when == ()


# --- the shipped phase gates must speak the shipped vocabulary ------------------------


def test_every_status_the_shipped_process_gates_on_is_a_status_the_ism_declares() -> None:
    """A gate naming a status no vocabulary has matches nothing, forever, in silence.

    `checks._matching` compares strings and knows nothing of frameworks — by design. That
    makes this the only place the two shipped files can be held to each other.
    """
    from ato_assist.miniyaml import loads

    process = loads((PLUGIN_ROOT / "config" / "process.yaml").read_text())
    gated = {
        criterion["args"]["where"]["status"]
        for phase in process["phases"]
        for criterion in phase["exit_criteria"]
        if isinstance(criterion.get("args", {}).get("where"), dict)
        and "status" in criterion["args"]["where"]
    }
    assert gated
    assert gated <= set(ism().values)
