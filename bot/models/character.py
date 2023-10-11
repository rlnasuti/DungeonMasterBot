import json

class Character:
    def __init__(
        self, 
        name, 
        character_class, 
        race, 
        level, 
        background,
        alignment,
        experience_points,
        strength,
        dexterity,
        constitution,
        intelligence,
        wisdom,
        charisma, 
        proficiency_bonus, 
        skills, 
        saving_throws, 
        max_hit_points,
        hit_dice,
        death_saves,
        equipment, 
        spells,
        languages,
        features_and_traits,
        notes,
        spell_slots_level_1_max=None,
        spells_slots_level_1_used=None,
        current_hit_points=None,
    ):
        self.name = name
        self.character_class = character_class
        self.race = race
        self.level = level
        self.background = background
        self.alignment = alignment
        self.experience_points = experience_points
        self.strength = strength
        self.dexterity = dexterity
        self.constitution = constitution
        self.intelligence = intelligence
        self.wisdom = wisdom
        self.charisma = charisma
        self.proficiency_bonus = proficiency_bonus
        self.skills = skills
        self.saving_throws = saving_throws
        self.max_hit_points = max_hit_points
        self.current_hit_points = current_hit_points or max_hit_points
        self.hit_dice = hit_dice
        self.death_saves = death_saves
        self.equipment = equipment
        self.spells = spells
        self.languages = languages
        self.features_and_traits = features_and_traits
        self.notes = notes
        self.spell_slots_level_1_max = spell_slots_level_1_max or self.lookup_spell_slots(character_class, level)
        self.spells_slots_level_1_used = spells_slots_level_1_used or 0

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.__dict__, f, indent=4)

    @classmethod
    def load(cls, character_name):
        filename=f"characters/{character_name}_character.json"
        with open(filename, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    def lookup_spell_slots(self, character_class, level):
        # Lookup table for level 1 spell slots, for example
        lookup_table = {
            'Wizard': {1: 2, 2: 3, 3: 4, 4: 4, 5: 4},
            'Cleric': {1: 2, 2: 3, 3: 4, 4: 4, 5: 4},
        }
        
        # Default to 0 if class or level not found
        return lookup_table.get(character_class, {}).get(level, 0)
