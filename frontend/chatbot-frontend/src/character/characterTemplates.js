const ABILITY_KEYS = [
  'strength',
  'dexterity',
  'constitution',
  'intelligence',
  'wisdom',
  'charisma',
];

const SKILL_KEYS = [
  'acrobatics', 'animal_handling', 'arcana', 'athletics', 'deception', 'history',
  'insight', 'intimidation', 'investigation', 'medicine', 'nature', 'perception',
  'performance', 'persuasion', 'religion', 'sleight_of_hand', 'stealth', 'survival',
];

const CHARACTER_FIELDS = [
  'character_id', 'name', 'class_name', 'subclass_name', 'ruleset_id', 'level',
  'ancestry', 'background', 'alignment', 'experience_points', 'size',
  'heroic_inspiration', 'death_saves', 'hp', 'max_hp', 'temp_hp', 'armor_class',
  'armor_class_calculation', 'proficiency_bonus', 'speed', 'proficiencies',
  'abilities', 'saving_throws', 'skills', 'attacks', 'features', 'spellcasting',
  'hit_dice', 'spell_slots', 'class_resources', 'conditions', 'inventory', 'currency',
];

const CURRENCY_KEYS = ['cp', 'sp', 'ep', 'gp', 'pp'];
const RULESET_ID = 'srd-5.2.1';

function emptyCurrency(overrides = {}) {
  return { ...Object.fromEntries(CURRENCY_KEYS.map((key) => [key, 0])), ...overrides };
}

function slug(value) {
  return String(value || 'player').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

function rulesRef(kind, name) {
  return `${RULESET_ID}:${kind}:${slug(name)}`;
}

function item(itemId, name, {
  equipped = false,
  quantity = 1,
  notes = '',
  category = 'other',
  weight = 0,
  kind = category,
} = {}) {
  return {
    item_id: itemId,
    name,
    quantity,
    equipped,
    notes,
    category,
    weight,
    rules_ref: rulesRef(kind, name),
  };
}

function feature(featureId, name, source, summary, resourceKey = null, kind = 'feature') {
  return {
    feature_id: featureId,
    name,
    source,
    summary,
    resource_key: resourceKey,
    rules_ref: rulesRef(kind, name),
  };
}

function spell(spellId, name, level, school, castingTime, range, duration, components, {
  concentration = false,
  ritual = false,
  source = 'Wizard',
} = {}) {
  return {
    spell_id: spellId,
    name,
    level,
    school,
    casting_time: castingTime,
    range,
    duration,
    components,
    concentration,
    ritual,
    source,
    rules_ref: rulesRef('spell', name),
  };
}

const WIZARD_SPELLS = [
  spell('fire-bolt', 'Fire Bolt', 0, 'Evocation', 'Action', '120 feet', 'Instantaneous', ['V', 'S']),
  spell('mage-hand', 'Mage Hand', 0, 'Conjuration', 'Action', '30 feet', '1 minute', ['V', 'S']),
  spell('minor-illusion', 'Minor Illusion', 0, 'Illusion', 'Action', '30 feet', '1 minute', ['S', 'M']),
  spell('prestidigitation', 'Prestidigitation', 0, 'Transmutation', 'Action', '10 feet', 'Up to 1 hour', ['V', 'S'], { source: 'High Elf' }),
  spell('light', 'Light', 0, 'Evocation', 'Action', 'Touch', '1 hour', ['V', 'M'], { source: 'Magic Initiate (Wizard)' }),
  spell('message', 'Message', 0, 'Transmutation', 'Action', '120 feet', '1 round', ['S', 'M'], { source: 'Magic Initiate (Wizard)' }),
  spell('alarm', 'Alarm', 1, 'Abjuration', '1 minute or Ritual', '30 feet', '8 hours', ['V', 'S', 'M'], { ritual: true }),
  spell('feather-fall', 'Feather Fall', 1, 'Transmutation', 'Reaction', '60 feet', '1 minute', ['V', 'M']),
  spell('find-familiar', 'Find Familiar', 1, 'Conjuration', '1 hour or Ritual', '10 feet', 'Instantaneous', ['V', 'S', 'M'], { ritual: true }),
  spell('mage-armor', 'Mage Armor', 1, 'Abjuration', 'Action', 'Touch', '8 hours', ['V', 'S', 'M']),
  spell('magic-missile', 'Magic Missile', 1, 'Evocation', 'Action', '120 feet', 'Instantaneous', ['V', 'S']),
  spell('shield', 'Shield', 1, 'Abjuration', 'Reaction', 'Self', '1 round', ['V', 'S']),
  spell('sleep', 'Sleep', 1, 'Enchantment', 'Action', '60 feet', 'Concentration, up to 1 minute', ['V', 'S', 'M'], { concentration: true }),
  spell('thunderwave', 'Thunderwave', 1, 'Evocation', 'Action', 'Self (15-foot Cube)', 'Instantaneous', ['V', 'S']),
  spell('misty-step', 'Misty Step', 2, 'Conjuration', 'Bonus Action', 'Self', 'Instantaneous', ['V']),
  spell('detect-thoughts', 'Detect Thoughts', 2, 'Divination', 'Action', 'Self', 'Concentration, up to 1 minute', ['V', 'S', 'M'], { concentration: true }),
  spell('scorching-ray', 'Scorching Ray', 2, 'Evocation', 'Action', '120 feet', 'Instantaneous', ['V', 'S']),
  spell('shatter', 'Shatter', 2, 'Evocation', 'Action', '60 feet', 'Instantaneous', ['V', 'S', 'M']),
  spell('detect-magic', 'Detect Magic', 1, 'Divination', 'Action or Ritual', 'Self', 'Concentration, up to 10 minutes', ['V', 'S'], { concentration: true, ritual: true, source: 'High Elf' }),
  spell('longstrider', 'Longstrider', 1, 'Transmutation', 'Action', 'Touch', '1 hour', ['V', 'S', 'M'], { source: 'Magic Initiate (Wizard)' }),
];

const TEMPLATE_BUILDERS = {
  fighter: (playerId, name) => {
    const prefix = slug(playerId);
    const longswordId = `item-${prefix}-longsword`;
    const chainMailId = `item-${prefix}-chain-mail`;
    const shieldId = `item-${prefix}-shield`;
    const javelinId = `item-${prefix}-javelins`;
    return {
      character_id: `character-${prefix}-fighter`,
      name,
      class_name: 'Fighter',
      subclass_name: 'Champion',
      ruleset_id: RULESET_ID,
      level: 3,
      ancestry: 'Human',
      background: 'Soldier',
      alignment: 'Lawful Good',
      experience_points: 900,
      size: 'Medium',
      heroic_inspiration: false,
      death_saves: { successes: 0, failures: 0 },
      hp: 28,
      max_hp: 28,
      temp_hp: 0,
      armor_class: 19,
      armor_class_calculation: {
        base: 16,
        use_dexterity: false,
        dexterity_cap: null,
        shield_bonus: 2,
        misc_bonus: 1,
        source_item_ids: [chainMailId, shieldId],
      },
      proficiency_bonus: 2,
      speed: { walk: 30 },
      proficiencies: {
        armor: ['Light armor', 'Medium armor', 'Heavy armor', 'Shields'],
        weapons: ['Simple weapons', 'Martial weapons'],
        tools: ['Dice set', "Smith's tools"],
        languages: ['Common', 'Elvish', 'Dwarvish'],
      },
      abilities: {
        strength: 16, dexterity: 12, constitution: 14,
        intelligence: 10, wisdom: 12, charisma: 8,
      },
      saving_throws: {
        strength: 5, dexterity: 1, constitution: 4,
        intelligence: 0, wisdom: 1, charisma: -1,
      },
      skills: {
        acrobatics: 3,
        athletics: 5,
        history: 2,
        insight: 3,
        intimidation: 1,
        perception: 3,
        persuasion: 1,
        survival: 3,
      },
      attacks: [
        {
          attack_id: 'longsword',
          name: 'Longsword',
          attack_type: 'melee_weapon',
          attack_bonus: 5,
          damage: [{ dice: '1d8', bonus: 3, damage_type: 'slashing' }],
          reach: 5,
          range_normal: null,
          range_long: null,
          source_item_id: longswordId,
          properties: ['Versatile (1d10+3)', 'Sap mastery'],
        },
        {
          attack_id: 'javelin-thrown',
          name: 'Javelin (Thrown)',
          attack_type: 'ranged_weapon',
          attack_bonus: 5,
          damage: [{ dice: '1d6', bonus: 3, damage_type: 'piercing' }],
          reach: null,
          range_normal: 30,
          range_long: 120,
          source_item_id: javelinId,
          properties: ['Thrown', 'Slow mastery'],
        },
      ],
      hit_dice: { d10: { maximum: 3, current: 3 } },
      spell_slots: {},
      class_resources: {
        second_wind: { maximum: 2, current: 2 },
        action_surge: { maximum: 1, current: 1 },
      },
      features: [
        feature('defense', 'Fighting Style: Defense', 'Fighter 1', '+1 AC while wearing Light, Medium, or Heavy armor.', null, 'feat'),
        feature('second-wind', 'Second Wind', 'Fighter 1', 'As a Bonus Action, regain 1d10 + 3 HP. One use returns on a Short Rest; all return on a Long Rest.', 'second_wind', 'class-feature'),
        feature('weapon-mastery', 'Weapon Mastery', 'Fighter 1', 'Use the mastery properties of three chosen weapons; this sheet uses Longsword (Sap), Javelin (Slow), and Shortbow (Vex).', null, 'class-feature'),
        feature('action-surge', 'Action Surge', 'Fighter 2', 'Take one additional action on your turn, except the Magic action; refreshes on a Short or Long Rest.', 'action_surge', 'class-feature'),
        feature('tactical-mind', 'Tactical Mind', 'Fighter 2', 'After a failed ability check, spend Second Wind to add 1d10; the use is retained if the check still fails.', 'second_wind', 'class-feature'),
        feature('improved-critical', 'Improved Critical', 'Champion 3', 'Weapon and Unarmed Strike attacks score a Critical Hit on a natural 19 or 20.', null, 'subclass-feature'),
        feature('remarkable-athlete', 'Remarkable Athlete', 'Champion 3', 'Advantage on Initiative and Athletics; after a Critical Hit, move up to half Speed without provoking Opportunity Attacks.', null, 'subclass-feature'),
        feature('resourceful', 'Resourceful', 'Human', 'Gain Heroic Inspiration whenever you finish a Long Rest.', null, 'species-trait'),
        feature('skillful', 'Skillful', 'Human', 'Gain proficiency in one skill of your choice.', null, 'species-trait'),
        feature('versatile', 'Versatile', 'Human', 'Gain an additional Origin feat; this character chose Skilled.', null, 'species-trait'),
        feature('savage-attacker', 'Savage Attacker', 'Soldier', 'Once per turn when you hit with a weapon, roll the damage dice twice and use either roll.', null, 'feat'),
        feature('skilled', 'Skilled', 'Human Origin Feat', 'Gain proficiency in three chosen skills or tools.', null, 'feat'),
      ],
      conditions: [],
      currency: emptyCurrency({ gp: 7 }),
      inventory: [
        item(longswordId, 'Longsword', { equipped: true, category: 'weapon', weight: 3, kind: 'weapon' }),
        item(chainMailId, 'Chain Mail', { equipped: true, category: 'armor', weight: 55, kind: 'armor' }),
        item(shieldId, 'Shield', { equipped: true, category: 'shield', weight: 6, kind: 'armor' }),
        item(javelinId, 'Javelin', { quantity: 4, category: 'weapon', weight: 2, kind: 'weapon' }),
        item(`item-${prefix}-dungeoneers-pack`, "Dungeoneer's Pack", { category: 'adventuring_gear', kind: 'gear' }),
        item(`item-${prefix}-potion`, 'Potion of Healing', { category: 'adventuring_gear', weight: 0.5, kind: 'gear' }),
      ],
    };
  },
  wizard: (playerId, name) => {
    const prefix = slug(playerId);
    const focusId = `item-${prefix}-arcane-focus`;
    const daggerId = `item-${prefix}-daggers`;
    const spellbookIds = [
      'alarm', 'feather-fall', 'find-familiar', 'mage-armor', 'magic-missile',
      'shield', 'sleep', 'thunderwave', 'misty-step', 'detect-thoughts',
      'scorching-ray', 'shatter',
    ];
    return {
      character_id: `character-${prefix}-wizard`,
      name,
      class_name: 'Wizard',
      subclass_name: 'Evoker',
      ruleset_id: RULESET_ID,
      level: 3,
      ancestry: 'High Elf',
      background: 'Sage',
      alignment: 'Neutral Good',
      experience_points: 900,
      size: 'Medium',
      heroic_inspiration: false,
      death_saves: { successes: 0, failures: 0 },
      hp: 20,
      max_hp: 20,
      temp_hp: 0,
      armor_class: 12,
      armor_class_calculation: {
        base: 10,
        use_dexterity: true,
        dexterity_cap: null,
        shield_bonus: 0,
        misc_bonus: 0,
        source_item_ids: [],
      },
      proficiency_bonus: 2,
      speed: { walk: 30 },
      proficiencies: {
        armor: [],
        weapons: ['Simple weapons'],
        tools: ["Calligrapher's supplies"],
        languages: ['Common', 'Elvish', 'Draconic'],
      },
      abilities: {
        strength: 8, dexterity: 14, constitution: 14,
        intelligence: 16, wisdom: 12, charisma: 10,
      },
      saving_throws: {
        strength: -1, dexterity: 2, constitution: 2,
        intelligence: 5, wisdom: 3, charisma: 0,
      },
      skills: { arcana: 5, history: 5, insight: 3, investigation: 7, perception: 3 },
      attacks: [
        {
          attack_id: 'fire-bolt',
          name: 'Fire Bolt',
          attack_type: 'ranged_spell',
          attack_bonus: 5,
          damage: [{ dice: '1d10', bonus: 0, damage_type: 'fire' }],
          reach: null,
          range_normal: 120,
          range_long: null,
          source_item_id: null,
          properties: ['Cantrip', 'Potent Cantrip'],
        },
        {
          attack_id: 'dagger',
          name: 'Dagger',
          attack_type: 'melee_weapon',
          attack_bonus: 4,
          damage: [{ dice: '1d4', bonus: 2, damage_type: 'piercing' }],
          reach: 5,
          range_normal: 20,
          range_long: 60,
          source_item_id: daggerId,
          properties: ['Finesse', 'Light', 'Thrown', 'Nick mastery unavailable'],
        },
      ],
      hit_dice: { d6: { maximum: 3, current: 3 } },
      spell_slots: {
        1: { maximum: 4, current: 4 },
        2: { maximum: 2, current: 2 },
      },
      class_resources: {
        arcane_recovery: { maximum: 1, current: 1 },
        high_elf_detect_magic: { maximum: 1, current: 1 },
        magic_initiate_longstrider: { maximum: 1, current: 1 },
      },
      features: [
        feature('spellcasting', 'Spellcasting', 'Wizard 1', 'Intelligence is the spellcasting ability. Prepare six level 1+ Wizard spells after each Long Rest.', null, 'class-feature'),
        feature('ritual-adept', 'Ritual Adept', 'Wizard 1', 'Cast a ritual-tagged spell directly from the spellbook without preparing it.', null, 'class-feature'),
        feature('arcane-recovery', 'Arcane Recovery', 'Wizard 1', 'After a Short Rest, recover expended slots with combined levels up to 2; refreshes on a Long Rest.', 'arcane_recovery', 'class-feature'),
        feature('scholar', 'Scholar: Investigation', 'Wizard 2', 'Expertise doubles the Proficiency Bonus for Investigation checks.', null, 'class-feature'),
        feature('evocation-savant', 'Evocation Savant', 'Evoker 3', 'Scorching Ray and Shatter were added to the spellbook for free; future slot levels can add another Evocation spell.', null, 'subclass-feature'),
        feature('potent-cantrip', 'Potent Cantrip', 'Evoker 3', 'A damaging cantrip deals half damage when its attack misses or its target succeeds on the save.', null, 'subclass-feature'),
        feature('high-elf-lineage', 'High Elf Lineage', 'High Elf', 'Prestidigitation is known. Detect Magic is always prepared and can be cast once per Long Rest without a slot.', 'high_elf_detect_magic', 'species-trait'),
        feature('fey-ancestry', 'Fey Ancestry', 'Elf', 'Advantage on saves to avoid or end the Charmed condition.', null, 'species-trait'),
        feature('trance', 'Trance', 'Elf', 'Finish a Long Rest in 4 hours while remaining conscious.', null, 'species-trait'),
        feature('magic-initiate', 'Magic Initiate (Wizard)', 'Sage', 'Know Light and Message. Longstrider is always prepared and has one slot-free casting per Long Rest.', 'magic_initiate_longstrider', 'feat'),
      ],
      spellcasting: {
        ability: 'intelligence',
        save_dc: 13,
        attack_bonus: 5,
        preparation_mode: 'spellbook',
        spells: WIZARD_SPELLS,
        known_spell_ids: ['fire-bolt', 'mage-hand', 'minor-illusion', 'prestidigitation', 'light', 'message'],
        prepared_spell_ids: ['feather-fall', 'mage-armor', 'magic-missile', 'shield', 'misty-step', 'detect-thoughts'],
        always_prepared_spell_ids: ['detect-magic', 'longstrider'],
        spellbook_spell_ids: spellbookIds,
        ritual_casting: true,
        focus_item_id: focusId,
      },
      conditions: [],
      currency: emptyCurrency({ gp: 5 }),
      inventory: [
        item(focusId, 'Arcane Focus (Quarterstaff)', { equipped: true, category: 'spellcasting_focus', weight: 4, kind: 'gear' }),
        item(daggerId, 'Dagger', { quantity: 2, category: 'weapon', weight: 1, kind: 'weapon' }),
        item(`item-${prefix}-spellbook`, 'Spellbook', { equipped: true, category: 'adventuring_gear', weight: 3, kind: 'gear' }),
        item(`item-${prefix}-robe`, 'Robe', { equipped: true, category: 'clothing', weight: 4, kind: 'gear' }),
        item(`item-${prefix}-scholars-pack`, "Scholar's Pack", { category: 'adventuring_gear', kind: 'gear' }),
        item(`item-${prefix}-calligraphers-supplies`, "Calligrapher's Supplies", { category: 'tool', weight: 5, kind: 'tool' }),
      ],
    };
  },
};

export const CHARACTER_TEMPLATE_OPTIONS = [
  { value: 'fighter', label: 'Level 3 Champion Fighter', summary: 'Armored front-line hero · AC 19 · 28 HP' },
  { value: 'wizard', label: 'Level 3 Evoker Wizard', summary: 'Prepared arcane caster · 12-spell book · 20 HP' },
];

export function buildTemplateCharacter(templateId, playerId, characterName) {
  const builder = TEMPLATE_BUILDERS[templateId];
  if (!builder) throw new Error(`Unknown character template: ${templateId}`);
  return builder(playerId, characterName.trim());
}

function publicModifierMap(value, allowedKeys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
  return Object.fromEntries(
    Object.entries(value).filter(([key]) => allowedKeys.includes(key)),
  );
}

function publicPools(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
  return Object.fromEntries(Object.entries(value).filter(([key]) => (
    !/(private|secret|hidden|dm[_-])/i.test(key)
  )).map(([key, pool]) => {
    if (!pool || typeof pool !== 'object' || Array.isArray(pool)) return [key, pool];
    return [key, Object.fromEntries(
      Object.entries(pool).filter(([field]) => ['maximum', 'max', 'current'].includes(field)),
    )];
  }));
}

function pickObject(value, fields) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
  return Object.fromEntries(Object.entries(value).filter(([field]) => fields.includes(field)));
}

function publicTextArray(value) {
  return Array.isArray(value) ? value.filter((entry) => typeof entry === 'string') : value;
}

function publicInventory(value) {
  if (!Array.isArray(value)) return value;
  return value.map((entry) => pickObject(entry, [
    'item_id', 'name', 'quantity', 'equipped', 'notes', 'rules_ref', 'category', 'weight',
  ]));
}

function publicAttacks(value) {
  if (!Array.isArray(value)) return value;
  return value.map((entry) => {
    const attack = pickObject(entry, [
      'attack_id', 'name', 'attack_type', 'attack_bonus', 'damage', 'reach',
      'range_normal', 'range_long', 'source_item_id', 'properties',
    ]);
    if (Array.isArray(attack?.damage)) {
      attack.damage = attack.damage.map((damage) => pickObject(damage, ['dice', 'bonus', 'damage_type']));
    }
    if (attack) attack.properties = publicTextArray(attack.properties);
    return attack;
  });
}

function publicFeatures(value) {
  if (!Array.isArray(value)) return value;
  return value.map((entry) => pickObject(entry, [
    'feature_id', 'name', 'source', 'rules_ref', 'summary', 'resource_key',
  ]));
}

function publicSpellcasting(value) {
  const casting = pickObject(value, [
    'ability', 'save_dc', 'attack_bonus', 'preparation_mode', 'spells',
    'known_spell_ids', 'prepared_spell_ids', 'always_prepared_spell_ids',
    'spellbook_spell_ids', 'ritual_casting', 'focus_item_id',
  ]);
  if (!casting) return casting;
  for (const field of ['known_spell_ids', 'prepared_spell_ids', 'always_prepared_spell_ids', 'spellbook_spell_ids']) {
    casting[field] = publicTextArray(casting[field]);
  }
  if (Array.isArray(casting.spells)) {
    casting.spells = casting.spells.map((entry) => {
      const publicSpell = pickObject(entry, [
        'spell_id', 'name', 'level', 'school', 'casting_time', 'range', 'duration',
        'components', 'concentration', 'ritual', 'source', 'rules_ref',
      ]);
      if (publicSpell) publicSpell.components = publicTextArray(publicSpell.components);
      return publicSpell;
    });
  }
  return casting;
}

function publicCurrency(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
  return Object.fromEntries(
    Object.entries(value).filter(([key]) => CURRENCY_KEYS.includes(key)),
  );
}

export function projectPublicImportedCharacter(raw) {
  const candidate = raw?.character && typeof raw.character === 'object' ? raw.character : raw;
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
    throw new Error('The selected JSON must contain a character object.');
  }

  const projected = Object.fromEntries(
    Object.entries(candidate).filter(([field]) => CHARACTER_FIELDS.includes(field)),
  );
  projected.abilities = publicModifierMap(projected.abilities, ABILITY_KEYS);
  projected.saving_throws = publicModifierMap(projected.saving_throws, ABILITY_KEYS);
  projected.skills = publicModifierMap(projected.skills, SKILL_KEYS);
  projected.hit_dice = publicPools(projected.hit_dice);
  projected.spell_slots = publicPools(projected.spell_slots);
  projected.class_resources = publicPools(projected.class_resources);
  projected.currency = publicCurrency(projected.currency);
  projected.inventory = publicInventory(projected.inventory);
  projected.speed = pickObject(projected.speed, ['walk', 'burrow', 'climb', 'fly', 'swim', 'hover']);
  projected.proficiencies = pickObject(projected.proficiencies, ['armor', 'weapons', 'tools', 'languages']);
  if (projected.proficiencies) {
    for (const category of ['armor', 'weapons', 'tools', 'languages']) {
      projected.proficiencies[category] = publicTextArray(projected.proficiencies[category]);
    }
  }
  projected.armor_class_calculation = pickObject(projected.armor_class_calculation, [
    'base', 'use_dexterity', 'dexterity_cap', 'shield_bonus', 'misc_bonus', 'source_item_ids',
  ]);
  if (projected.armor_class_calculation) {
    projected.armor_class_calculation.source_item_ids = publicTextArray(
      projected.armor_class_calculation.source_item_ids,
    );
  }
  projected.attacks = publicAttacks(projected.attacks);
  projected.features = publicFeatures(projected.features);
  projected.spellcasting = publicSpellcasting(projected.spellcasting);
  projected.death_saves = pickObject(projected.death_saves, ['successes', 'failures']);
  if (Array.isArray(projected.conditions)) {
    projected.conditions = projected.conditions.filter((condition) => typeof condition === 'string');
  }
  return projected;
}
