import os
from bot.models.character import Character


def create_sample_character():
    return Character(
        name="Test",
        character_class="Wizard",
        race="Human",
        level=1,
        background="Acolyte",
        alignment="Neutral Good",
        experience_points=0,
        strength=10,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
        proficiency_bonus=2,
        skills={},
        saving_throws={},
        max_hit_points=10,
        hit_dice="1d6",
        death_saves={"successes": 0, "failures": 0},
        equipment=[],
        spells=[],
        languages=[],
        features_and_traits="",
        notes="",
    )


def test_character_save_load_round_trip(tmp_path):
    char = create_sample_character()
    data_dir = tmp_path / "data" / "characters"
    data_dir.mkdir(parents=True)
    file_path = data_dir / "Test_character.json"

    char.save(file_path)

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        loaded = Character.load("Test")
    finally:
        os.chdir(cwd)

    assert loaded.__dict__ == char.__dict__


def test_lookup_spell_slots_default():
    char = create_sample_character()
    assert char.lookup_spell_slots("Rogue", 1) == 0
    assert char.lookup_spell_slots("Wizard", 99) == 0
