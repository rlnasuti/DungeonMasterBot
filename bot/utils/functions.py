FUNCTIONS = [
    {
        "name": "consult_rulebook",
        "description": "This function takes as input a D&D related question so that it can consult documentation and return an answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The D&D related question that you would like an answer to."
                },
            },
            "required": ["question"]
        },
    },
    {
        "name": "create_and_save_character",
        "description": "This function is called to create a new D&D character and save its state. Call it to create a character on behalf of the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The character's name."
                },
                "character_class": {
                    "type": "string",
                    "description": "The character's class.",
                    "enum": ["Barbarian", "Bard", "Cleric", "Druid", "Fighter", "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard"]
                },
                "race": {
                    "type": "string",
                    "description": "The character's race.",
                    "enum": ["Dwarf", "Elf", "Halfling", "Human", "Dragonborn", "Gnome", "Half-Elf", "Half-Orc", "Tiefling"]
                },
                "level": {
                    "type": "integer",
                    "description": "The character's level. This should be between 1 and 20 inclusive."
                },
                "background": {
                    "type": "string",
                    "description": "The character's background, like Noble or Outlander.",
                    "enum": ["Acolyte", "Charlatan", "Criminal", "Entertainer", "Folk Hero", "Guild Artisan", "Hermit", "Noble", "Outlander", "Sage", "Sailor", "Soldier", "Urchin"]
                },
                "alignment": {
                    "type": "string",
                    "description": "The character's alignment, like 'Chaotic Good' or 'Neutral Evil'.",
                    "enum": ["Lawful Good", "Lawful Neutral", "Lawful Evil", "Neutral Good", "True Neutral", "Neutral Evil", "Chaotic Good", "Chaotic Neutral", "Chaotic Evil"]
                },
                "experience_points": {
                    "type": "integer",
                    "description": "The character's current XP total. This should be 0 for newly created level 1 characters. It should be the minimum experience points needed to achieve a level if the new character is above level 1."
                },
                "strength": {
                    "type": "integer",
                    "description": "The character's strength attribute."
                },
                "dexterity": {
                    "type": "integer",
                    "description": "The character's dexterity attribute."
                },
                "constitution": {
                    "type": "integer",
                    "description": "The character's constitution attribute."
                },
                "intelligence": {
                    "type": "integer",
                    "description": "The character's intelligence attribute."
                },
                "wisdom": {
                    "type": "integer",
                    "description": "The character's wisdom attribute."
                },
                "charisma": {
                    "type": "integer",
                    "description": "The character's charisma attribute."
                },
                "max_hit_points": {
                    "type": "integer",
                    "description": "The character's maximum hit points."
                },
                "proficiency_bonus": {
                    "type": "integer",
                    "description": "The character's proficiency bonus."
                },
                "skills": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception", "History", "Insight", "Intimidation", "Investigation", "Medicine", "Nature", "Perception", "Performance", "Persuasion", "Religion", "Sleight of Hand", "Stealth", "Survival"]
                    },
                    "description": "A list of skills that the character is proficient in."
                },
                "saving_throws": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]
                    },
                    "description": "A list of saving throws that the character is proficient in."
                },
                "hit_dice": {
                    "type": "string",
                    "description": "The total number and type of hit dice the character has."
                },
                "death_saves": {
                    "type": "object",
                    "properties": {
                        "successes": {
                            "type": "integer",
                            "description": "The number of successful death saving throws."
                        },
                        "failures": {
                            "type": "integer",
                            "description": "The number of failed death saving throws."
                        }
                    },
                    "description": "A dictionary with the number of successes and failures on death saving throws. This will be zero for most newly created characters."
                },
                "equipment": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "A list of the character's equipment."
                },
                "spells": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "A list of spells the character knows or has prepared, if applicable."
                },
                "languages": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "A list of languages the character knows."
                },
                "features_and_traits": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "A list of racial or class features and traits the character has."
                },
                "notes": {
                    "type": "string",
                    "description": "Any additional information you want to keep track of, such as the character's personal goals, NPCs they've met, or their backstory."
                }
            },
            "required": ["name", "character_class", "race", "level", "background", "alignment", "strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "max_hit_points", "proficiency_bonus", "skills", "saving_throws", "hit_dice", "death_saves", "equipment", "languages", "features_and_traits"]
        }
    },
    {
        "name": "update_character",
        "description": "Whenever the character gains experience, makes a death save, fails a death save, gains or loses hit points, or uses a spell - call this function to update the character's state. The return value is a serialized json object representing the character's new state.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the character who's state is being changed."
                },
                "additional_experience_points": {
                    "type": "integer",
                    "description": "When the character gains experience points, send the number of additional experieince points in this parameter."
                },
                "additional_death_saves_successes": {
                    "type": "integer",
                    "description": "When the character is making death saves and succeeds, send the number of successes in this parameter. If the character rolled a 20, be sure to set this parameter to 2."
                },
                "additional_death_saves_failures": {
                    "type": "integer",
                    "description": "When the character is making death saves and fails, send the number of failures in this parameter. If the character rolled a 1, be sure to set this parameter to 2."
                },
                "delta_hit_points": {
                    "type": "integer",
                    "description": "When the character's hit points change, send the number of hit points gained or lost in this parameter. If the hit points were gained, send a positive integer. If the hit points were lost, send a negative integer."
                },
                "additional_level_1_spell_slots_used": {
                    "type": "integer",
                    "description": "When the character usees a level one spell slot, send the number of level one spell slots used in this parameter."
                },
            },
            "required": ["name"]
        }
    },
    {
        "name": "save_game",
        "description": "This function should be called when the user indicates they want to save the game state.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the main character of the game state being saved."
                },
            },
            "required": ["name"]
        },
    },
    {
        "name": "load_game",
        "description": "This function should be called when the user indicates they want to load a game for a character.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the main character of the game state being loaded."
                },
            },
            "required": ["name"]
        },
    },
    {
        "name": "get_character_state",
        "description": "This function should be called at any time that you need to reference a player character's state. It will return a serialized json object representing the character. You can call this function silently without letting the user know if at any time the character's state leaves your context and you need to refresh it.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the character who's state you want returned."
                },
            },
            "required": ["name"]
        },
    },
    {
        "name": "roll_dice",
        "description": "useful for rolling dice",
        "parameters": {
            "type": "object",
            "properties": {
                "num_dice": {
                    "type": "integer",
                    "description": "the number of dice to roll"
                },
                "dice_sides": {
                    "type": "integer",
                    "description": "the number of sides on the die to roll. Should be 4, 6, 8, 10, 12, 20, or 100"
                },
            },
            "required": ["num_dice", "dice_sides"]
        },
    },                 
]