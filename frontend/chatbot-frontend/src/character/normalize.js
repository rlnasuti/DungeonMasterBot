const ABILITY_LABELS = {
  str: 'Strength',
  strength: 'Strength',
  dex: 'Dexterity',
  dexterity: 'Dexterity',
  con: 'Constitution',
  constitution: 'Constitution',
  int: 'Intelligence',
  intelligence: 'Intelligence',
  wis: 'Wisdom',
  wisdom: 'Wisdom',
  cha: 'Charisma',
  charisma: 'Charisma',
};

const CURRENCY_LABELS = {
  pp: 'Platinum',
  gp: 'Gold',
  ep: 'Electrum',
  sp: 'Silver',
  cp: 'Copper',
};

const PROFICIENCY_LABELS = {
  armor: 'Armor',
  weapons: 'Weapons',
  tools: 'Tools',
  languages: 'Languages',
};

function isRecord(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function humanize(value) {
  if (value === undefined || value === null) return '';
  const text = String(value).trim().replace(/[_-]+/g, ' ');
  return text.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatRulesetId(value) {
  const text = String(value || '').trim();
  if (!text || ['manual', 'legacy'].includes(text.toLowerCase())) return '';
  return text
    .replace(/[_-]+/g, ' ')
    .replace(/^srd\b/i, 'SRD')
    .replace(/^d&d\b/i, 'D&D');
}

function conciseText(value, maximum = 240) {
  const text = String(value || '').trim();
  if (text.length <= maximum) return text;
  return `${text.slice(0, maximum - 1).trimEnd()}…`;
}

export function formatModifier(value) {
  if (value === undefined || value === null || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number >= 0 ? `+${number}` : String(number);
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== 'object') return [];
  return Object.entries(value).map(([name, details]) => (
    details && typeof details === 'object' ? { name, ...details } : { name, value: details }
  ));
}

function normalizeStringList(value) {
  let values = [];
  if (Array.isArray(value)) {
    values = value.flatMap((entry) => {
      if (typeof entry === 'string') return [entry];
      if (isRecord(entry)) return [entry.name || entry.label || entry.value];
      return [entry];
    });
  } else if (typeof value === 'string') {
    values = value.split(/[,;]+/);
  } else if (isRecord(value)) {
    values = Object.entries(value).flatMap(([key, entry]) => {
      if (entry === true) return [key];
      if (typeof entry === 'string') return [entry];
      if (isRecord(entry)) return [entry.name || entry.label || key];
      return [];
    });
  }

  const seen = new Set();
  return values
    .filter((entry) => entry !== undefined && entry !== null && String(entry).trim())
    .map((entry) => humanize(entry))
    .filter((entry) => {
      const key = entry.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function normalizeAbilities(character) {
  const source = character.abilities || {
    strength: character.strength,
    dexterity: character.dexterity,
    constitution: character.constitution,
    intelligence: character.intelligence,
    wisdom: character.wisdom,
    charisma: character.charisma,
  };

  return Object.entries(source)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, raw]) => {
      const details = raw && typeof raw === 'object' ? raw : { score: raw };
      const score = Number(details.score ?? details.value);
      const calculatedModifier = Number.isFinite(score) ? Math.floor((score - 10) / 2) : null;
      return {
        key,
        label: details.label || ABILITY_LABELS[key.toLowerCase()] || humanize(key),
        score: Number.isFinite(score) ? score : '—',
        modifier: details.modifier ?? details.mod ?? calculatedModifier,
      };
    });
}

function normalizeNamedModifiers(value) {
  return asArray(value).map((entry, index) => {
    if (typeof entry === 'string') {
      return { name: humanize(entry), modifier: null, proficient: null };
    }
    return {
      ...entry,
      name: humanize(entry.name || entry.label || `Entry ${index + 1}`),
      modifier: entry.modifier ?? entry.bonus ?? entry.value,
      proficient: entry.proficient ?? entry.has_proficiency ?? null,
    };
  });
}

function normalizeSpellSlots(character) {
  const source = character.spell_slots || character.spellSlots || [];
  return asArray(source).map((slot, index) => {
    const level = slot.level ?? slot.name ?? index + 1;
    const maximum = Number(slot.max ?? slot.maximum ?? slot.total ?? 0);
    const availableValue = slot.available ?? slot.current ?? slot.remaining;
    const usedFromAvailable = Number.isFinite(Number(availableValue))
      ? Math.max(0, maximum - Number(availableValue))
      : null;
    const used = Number(slot.used ?? slot.expended ?? usedFromAvailable ?? 0);
    return {
      level,
      maximum: Number.isFinite(maximum) ? Math.max(0, maximum) : 0,
      used: Number.isFinite(used) ? Math.max(0, Math.min(maximum, used)) : 0,
    };
  }).filter((slot) => slot.maximum > 0);
}

function normalizeResources(character) {
  return asArray(character.class_resources || character.classResources).map((resource) => {
    const maximum = Number(resource.max ?? resource.maximum ?? resource.total ?? 0);
    const current = Number(resource.current ?? resource.available ?? resource.value ?? 0);
    return {
      name: humanize(resource.name || resource.label || 'Resource'),
      maximum: Number.isFinite(maximum) ? Math.max(0, maximum) : 0,
      current: Number.isFinite(current) ? Math.max(0, Math.min(maximum, current)) : 0,
    };
  });
}

function formatRange(value) {
  if (value === undefined || value === null || value === '') return '';
  if (typeof value === 'number' || /^\d+$/.test(String(value).trim())) return `${value} ft.`;
  if (!isRecord(value)) return String(value);

  const normal = value.normal ?? value.short ?? value.range ?? value.distance;
  const long = value.long ?? value.maximum;
  const unit = value.unit || 'ft.';
  if (normal !== undefined && long !== undefined) return `${normal}/${long} ${unit}`;
  if (normal !== undefined) return `${normal} ${unit}`;
  return Object.entries(value)
    .filter(([, entry]) => entry !== undefined && entry !== null)
    .map(([key, entry]) => `${humanize(key)} ${entry}`)
    .join(', ');
}

function formatDamage(value, fallbackType, fallbackBonus) {
  if (value === undefined || value === null || value === '') return '';
  if (Array.isArray(value)) {
    return value
      .map((entry) => formatDamage(entry, fallbackType, fallbackBonus))
      .filter(Boolean)
      .join(' plus ');
  }
  if (!isRecord(value)) {
    const suffix = fallbackType ? ` ${fallbackType}` : '';
    return `${value}${suffix}`;
  }

  const dice = value.dice ?? value.formula ?? value.damage_dice ?? value.value ?? '';
  const bonus = value.bonus ?? value.modifier ?? fallbackBonus;
  const type = value.type ?? value.damage_type ?? fallbackType;
  const bonusText = finiteNumber(bonus) === null || Number(bonus) === 0
    ? ''
    : ` ${Number(bonus) > 0 ? '+' : '-'} ${Math.abs(Number(bonus))}`;
  return `${dice}${bonusText}${type ? ` ${type}` : ''}`.trim();
}

function formatCost(value) {
  if (value === undefined || value === null || value === '') return '';
  if (!isRecord(value)) return String(value);
  const quantity = value.quantity ?? value.amount ?? value.value;
  const unit = value.unit ?? value.denomination ?? '';
  return quantity === undefined ? '' : `${quantity}${unit ? ` ${unit}` : ''}`;
}

function normalizeInventory(character) {
  return asArray(character.inventory || character.equipment).map((rawItem, index) => {
    const item = typeof rawItem === 'string' ? { name: rawItem } : rawItem;
    const category = item.category || item.item_type || item.type || '';
    const armorCategory = item.armor_category || item.armorCategory || '';
    const weaponCategory = item.weapon_category || item.weaponCategory || '';
    const damageType = item.damage_type || item.damageType || item.damage?.type || '';
    return {
      id: String(item.item_id ?? item.id ?? `inventory-item-${index + 1}`),
      name: item.name || item.label || 'Item',
      quantity: Math.max(0, finiteNumber(item.quantity ?? item.qty ?? 1) ?? 1),
      equipped: Boolean(item.equipped),
      notes: item.notes || item.description || '',
      category: humanize(category),
      armorCategory: humanize(armorCategory),
      weaponCategory: humanize(weaponCategory),
      damage: formatDamage(item.damage ?? item.damage_dice, damageType, item.damage_bonus),
      range: formatRange(item.range || item.weapon_range),
      armorClass: finiteNumber(item.armor_class ?? item.base_armor_class ?? item.ac),
      armorClassBonus: finiteNumber(item.armor_class_bonus ?? item.ac_bonus),
      properties: normalizeStringList(item.properties || item.weapon_properties),
      weight: finiteNumber(item.weight),
      cost: formatCost(item.cost || item.value),
      attunement: Boolean(item.attuned ?? item.requires_attunement),
      rulesRef: item.rules_ref || item.rulesReference || '',
    };
  });
}

function isShield(item) {
  return /shield/i.test(`${item.category} ${item.armorCategory} ${item.name}`);
}

function isArmor(item) {
  return !isShield(item) && (
    /armor/i.test(`${item.category} ${item.armorCategory}`)
    || item.armorClass !== null
  );
}

function normalizeArmorClass(character, inventory, abilities) {
  const source = character.armor_class_calculation || character.armorClassCalculation || {};
  const dexterity = abilities.find((ability) => ['dex', 'dexterity'].includes(ability.key.toLowerCase()));
  const dexterityModifier = finiteNumber(dexterity?.modifier);
  const dexterityCap = finiteNumber(source.dexterity_cap ?? source.dexterityCap);
  const addDexterity = source.use_dexterity
    ?? source.useDexterity
    ?? source.add_dexterity
    ?? source.addDexterity;
  const armorItemId = source.equipped_armor_item_id ?? source.equippedArmorItemId;
  const shieldItemId = source.equipped_shield_item_id ?? source.equippedShieldItemId;
  const sourceItemIds = Array.isArray(source.source_item_ids ?? source.sourceItemIds)
    ? (source.source_item_ids ?? source.sourceItemIds).map(String)
    : [];
  const sourceItems = sourceItemIds
    .map((itemId) => inventory.find((item) => item.id === itemId))
    .filter(Boolean);
  const armorItem = inventory.find((item) => item.id === String(armorItemId))
    || sourceItems.find(isArmor)
    || inventory.find((item) => item.equipped && isArmor(item));
  const shieldItem = inventory.find((item) => item.id === String(shieldItemId))
    || sourceItems.find(isShield)
    || inventory.find((item) => item.equipped && isShield(item));
  const dexterityContribution = addDexterity && dexterityModifier !== null
    ? Math.min(dexterityModifier, dexterityCap ?? dexterityModifier)
    : null;
  const base = finiteNumber(source.base);
  const shieldBonus = finiteNumber(source.shield_bonus ?? source.shieldBonus);
  const miscBonus = finiteNumber(source.misc_bonus ?? source.miscBonus);

  return {
    description: source.description || '',
    base,
    addDexterity: addDexterity === undefined ? null : Boolean(addDexterity),
    dexterityCap,
    dexterityContribution,
    shieldBonus,
    miscBonus,
    armorItemName: armorItem?.name || '',
    shieldItemName: shieldItem?.name || '',
    hasDetails: Boolean(
      source.description
      || base !== null
      || addDexterity !== undefined
      || shieldBonus !== null
      || miscBonus !== null
      || armorItem
      || shieldItem
    ),
  };
}

function normalizeAttacks(character, inventory) {
  return asArray(character.attacks || character.actions?.attacks).map((rawAttack, index) => {
    const attack = typeof rawAttack === 'string' ? { name: rawAttack } : rawAttack;
    const attackBonusRaw = attack.attack_bonus ?? attack.to_hit ?? attack.bonus ?? attack.modifier;
    const numericBonus = finiteNumber(attackBonusRaw);
    const normalRange = attack.range_normal === undefined || attack.range_normal === null
      ? null
      : finiteNumber(attack.range_normal);
    const longRange = attack.range_long === undefined || attack.range_long === null
      ? null
      : finiteNumber(attack.range_long);
    const reach = attack.reach === undefined || attack.reach === null
      ? null
      : finiteNumber(attack.reach);
    let range = attack.range;
    if (normalRange !== null) {
      range = {
        normal: normalRange,
        ...(longRange !== null ? { long: longRange } : {}),
        unit: attack.range_unit || 'ft.',
      };
    } else if (reach !== null) {
      range = `${reach} ft. reach`;
    } else if (!range) {
      range = attack.weapon_range;
    }
    const sourceItemId = attack.source_item_id ?? attack.sourceItemId;
    const sourceItem = inventory.find((item) => item.id === String(sourceItemId));
    return {
      id: String(attack.attack_id ?? attack.id ?? `attack-${index + 1}`),
      name: attack.name || attack.label || `Attack ${index + 1}`,
      attackType: humanize(attack.attack_type || attack.type || ''),
      attackBonus: numericBonus ?? attackBonusRaw ?? null,
      damage: formatDamage(
        attack.damage ?? attack.damage_dice,
        attack.damage_type,
        attack.damage_bonus,
      ),
      range: formatRange(range),
      properties: normalizeStringList(attack.properties),
      notes: attack.notes || attack.description || '',
      source: sourceItem?.name || attack.source || '',
    };
  });
}

function normalizeFeatures(character) {
  return asArray(character.features || character.features_and_traits).map((rawFeature, index) => {
    const feature = typeof rawFeature === 'string' ? { name: rawFeature } : rawFeature;
    return {
      id: String(feature.feature_id ?? feature.id ?? `feature-${index + 1}`),
      name: feature.name || feature.label || `Feature ${index + 1}`,
      summary: conciseText(feature.summary || feature.description || feature.rules_text || feature.notes),
      source: feature.source || '',
      rulesRef: feature.rules_ref || '',
      resourceKey: feature.resource_key || '',
    };
  });
}

function normalizeProficiencies(character) {
  const source = character.proficiencies || {};
  return Object.entries(PROFICIENCY_LABELS).map(([key, label]) => ({
    key,
    label,
    entries: normalizeStringList(
      source[key]
      ?? (key === 'armor' ? character.armor_proficiencies : undefined)
      ?? (key === 'weapons' ? character.weapon_proficiencies : undefined)
      ?? (key === 'tools' ? character.tool_proficiencies : undefined)
      ?? (key === 'languages' ? character.languages : undefined),
    ),
  }));
}

function normalizeSpeed(value) {
  if (value === undefined || value === null || value === '') return '—';
  if (typeof value === 'number' || /^\d+$/.test(String(value).trim())) return `${value} ft.`;
  if (!isRecord(value)) return String(value);

  const hover = value.hover === true;
  const entries = Object.entries(value)
    .filter(([movement, speed]) => (
      movement.toLowerCase() !== 'hover'
      && speed !== undefined
      && speed !== null
      && speed !== ''
      && (movement.toLowerCase() === 'walk' || finiteNumber(speed) !== 0)
    ))
    .map(([movement, speed]) => {
      const formatted = formatRange(speed);
      const hoverSuffix = movement.toLowerCase() === 'fly' && hover ? ' (hover)' : '';
      return movement.toLowerCase() === 'walk'
        ? formatted
        : `${humanize(movement)} ${formatted}${hoverSuffix}`;
    });
  if (hover && value.fly === undefined) entries.push('Hover');
  return entries.join(', ') || '—';
}

function normalizeComponents(value) {
  if (!value) return '—';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.join(', ');
  if (!isRecord(value)) return String(value);

  const components = [];
  if (value.verbal || value.v) components.push('V');
  if (value.somatic || value.s) components.push('S');
  const material = value.material ?? value.m;
  const materialDescription = value.material_description ?? value.materialDescription;
  if (material) {
    const detail = typeof material === 'string' ? material : materialDescription;
    components.push(detail ? `M (${detail})` : 'M');
  }
  return components.join(', ') || '—';
}

function normalizeIdSet(value) {
  const source = Array.isArray(value) ? value : [];
  return new Set(source.map((entry) => String(isRecord(entry) ? entry.id ?? entry.spell_id : entry)));
}

function normalizeSpellcasting(character, inventory, spellSlots) {
  const rawSource = character.spellcasting || character.spell_casting;
  const source = isRecord(rawSource) ? rawSource : {};
  const rawSpells = source.spells ?? character.spells ?? [];
  const knownIds = normalizeIdSet(source.known_spell_ids ?? source.knownSpellIds);
  const preparedIds = normalizeIdSet(source.prepared_spell_ids ?? source.preparedSpellIds);
  const spellbookIds = normalizeIdSet(source.spellbook_spell_ids ?? source.spellbookSpellIds);
  const alwaysPreparedIds = normalizeIdSet(
    source.always_prepared_spell_ids ?? source.alwaysPreparedSpellIds,
  );
  const spells = asArray(rawSpells).map((rawSpell, index) => {
    const spell = typeof rawSpell === 'string' ? { name: rawSpell } : rawSpell;
    const id = String(spell.spell_id ?? spell.id ?? `spell-${index + 1}`);
    const levelNumber = finiteNumber(spell.level ?? spell.spell_level);
    const level = levelNumber === null ? 0 : Math.max(0, Math.min(9, levelNumber));
    const known = Boolean(spell.known ?? spell.is_known ?? knownIds.has(id));
    const prepared = Boolean(spell.prepared ?? spell.is_prepared ?? preparedIds.has(id));
    const inSpellbook = Boolean(
      spell.in_spellbook ?? spell.inSpellbook ?? spell.spellbook ?? spellbookIds.has(id),
    );
    const alwaysPrepared = Boolean(
      spell.always_prepared ?? spell.alwaysPrepared ?? alwaysPreparedIds.has(id),
    );
    return {
      id,
      name: spell.name || spell.label || `Spell ${index + 1}`,
      level,
      school: humanize(spell.school || ''),
      castingTime: spell.casting_time ?? spell.castingTime ?? '—',
      range: formatRange(spell.range || spell.distance) || '—',
      components: normalizeComponents(spell.components),
      duration: spell.duration || '—',
      concentration: Boolean(spell.concentration ?? spell.requires_concentration),
      ritual: Boolean(spell.ritual ?? spell.can_ritual_cast),
      known,
      prepared,
      inSpellbook,
      alwaysPrepared,
      description: spell.description || spell.summary || '',
      rulesRef: spell.rules_ref || '',
      source: spell.source || '',
    };
  }).sort((left, right) => left.level - right.level || left.name.localeCompare(right.name));

  const focusId = source.focus_item_id ?? source.focusItemId;
  const focus = inventory.find((item) => item.id === String(focusId));
  const abilityKey = source.ability || source.spellcasting_ability || source.spellcastingAbility;
  const saveDc = finiteNumber(source.save_dc ?? source.spell_save_dc ?? source.spellSaveDc);
  const attackBonus = finiteNumber(
    source.spell_attack_bonus ?? source.spellAttackBonus ?? source.attack_bonus,
  );
  const ritualCasting = source.ritual_casting ?? source.ritualCasting;

  return {
    ability: abilityKey ? ABILITY_LABELS[String(abilityKey).toLowerCase()] || humanize(abilityKey) : '—',
    spellSaveDc: saveDc,
    spellAttackBonus: attackBonus,
    preparationMode: source.preparation_mode || source.preparationMode
      ? humanize(source.preparation_mode || source.preparationMode)
      : '—',
    ritualCasting: ritualCasting === undefined ? null : Boolean(ritualCasting),
    focusItemName: focus?.name || '',
    spells,
    hasDetails: Boolean(rawSource || spells.length || spellSlots.length),
  };
}

function normalizeCurrency(character) {
  const source = character.currency || character.coin_purse || {};
  return Object.entries(CURRENCY_LABELS).map(([denomination, label]) => {
    const amount = Number(source?.[denomination] ?? 0);
    return {
      denomination,
      label,
      amount: Number.isInteger(amount) && amount >= 0 ? amount : 0,
    };
  });
}

function normalizeCharacter(player, index) {
  const character = player.character || player.character_sheet || player;
  const hpValue = character.hp ?? character.hit_points ?? {};
  const hp = hpValue && typeof hpValue === 'object' ? hpValue : {};
  const maxHp = Number(
    hp.max ?? hp.maximum ?? character.max_hp ?? character.max_hit_points ?? 0,
  );
  const currentHp = Number(
    hp.current ?? (
      typeof hpValue === 'number' ? hpValue : character.current_hp ?? character.current_hit_points
    ) ?? maxHp,
  );
  const tempHp = Number(
    hp.temp ?? hp.temporary ?? character.temp_hp ?? character.temporary_hit_points ?? 0,
  );
  const playerId = String(player.id ?? player.player_id ?? character.player_id ?? `player-${index + 1}`);
  const characterName = character.name || player.character_name || `Adventurer ${index + 1}`;
  const abilities = normalizeAbilities(character);
  const skills = normalizeNamedModifiers(character.skills);
  const inventory = normalizeInventory(character);
  const spellSlots = normalizeSpellSlots(character);
  const dexterity = abilities.find((ability) => ['dex', 'dexterity'].includes(ability.key.toLowerCase()));
  const perception = skills.find((skill) => String(skill.name).toLowerCase() === 'perception');
  const initiativeRaw = character.initiative;
  const initiative = finiteNumber(
    isRecord(initiativeRaw) ? initiativeRaw.modifier ?? initiativeRaw.bonus : initiativeRaw,
  ) ?? finiteNumber(dexterity?.modifier);
  const passivePerception = finiteNumber(
    character.passive_perception ?? character.passivePerception,
  ) ?? (finiteNumber(perception?.modifier) === null ? null : 10 + Number(perception.modifier));
  const armorClassCalculation = normalizeArmorClass(character, inventory, abilities);
  const spellcasting = normalizeSpellcasting(character, inventory, spellSlots);
  const deathSavesSource = character.death_saves || character.deathSaves;
  const deathSaves = isRecord(deathSavesSource) ? {
    successes: Math.max(0, Math.min(3, finiteNumber(deathSavesSource.successes) ?? 0)),
    failures: Math.max(0, Math.min(3, finiteNumber(deathSavesSource.failures) ?? 0)),
  } : null;
  const heroicInspirationValue = character.heroic_inspiration ?? character.heroicInspiration;

  return {
    playerId,
    playerLabel: player.display_name || player.player_name || player.name || `Player ${index + 1}`,
    characterName,
    className: character.class_name || character.character_class || character.class || 'Adventurer',
    subclassName: character.subclass_name || character.subclass || '',
    rulesetId: formatRulesetId(character.ruleset_id || character.rulesetId),
    level: character.level ?? 1,
    ancestry: character.ancestry || character.race || '',
    background: character.background || '',
    alignment: character.alignment ? humanize(character.alignment) : '',
    size: character.size ? humanize(character.size) : '',
    experiencePoints: finiteNumber(character.experience_points ?? character.experiencePoints),
    heroicInspiration: typeof heroicInspirationValue === 'boolean' ? heroicInspirationValue : null,
    deathSaves,
    hp: {
      current: Number.isFinite(currentHp) ? currentHp : 0,
      maximum: Number.isFinite(maxHp) ? maxHp : 0,
      temporary: Number.isFinite(tempHp) ? tempHp : 0,
    },
    armorClass: character.armor_class ?? character.ac ?? '—',
    armorClassCalculation,
    proficiencyBonus: finiteNumber(character.proficiency_bonus ?? character.proficiencyBonus),
    initiative,
    speed: normalizeSpeed(character.speed),
    passivePerception,
    abilities,
    savingThrows: normalizeNamedModifiers(character.saving_throws || character.saves),
    skills,
    proficiencies: normalizeProficiencies(character),
    attacks: normalizeAttacks(character, inventory),
    features: normalizeFeatures(character),
    conditions: asArray(character.conditions).map((condition) => (
      typeof condition === 'string' ? condition : condition.name || condition.label
    )).filter(Boolean),
    hitDice: character.hit_dice || character.hitDice || '—',
    spellSlots,
    spellcasting,
    classResources: normalizeResources(character),
    currency: normalizeCurrency(character),
    inventory,
  };
}

export function normalizePlayers(snapshot) {
  const source = snapshot?.players || snapshot?.party?.players || snapshot?.characters || [];
  return asArray(source).map(normalizeCharacter);
}

export function normalizePendingRolls(snapshot) {
  const source = snapshot?.pending_rolls || snapshot?.pending_roll;
  if (!source) return [];
  return (Array.isArray(source) ? source : [source]).map((roll, index) => {
    const dcVisibility = roll.dc_visibility === 'public' || roll.dc_visibility === 'private'
      ? roll.dc_visibility
      : null;
    const candidateTarget = roll.target_total === undefined || roll.target_total === null
      || roll.target_total === ''
      ? null
      : finiteNumber(roll.target_total);
    const targetTotal = dcVisibility === 'public' && Number.isInteger(candidateTarget)
      && candidateTarget > 0
      ? candidateTarget
      : null;

    return {
      id: String(roll.id ?? roll.roll_id ?? `pending-roll-${index + 1}`),
      playerId: roll.player_id !== undefined ? String(roll.player_id) : null,
      label: roll.label || roll.reason || roll.prompt || roll.check || 'Ability check',
      die: String(roll.die || 'd20').toLowerCase(),
      modifier: roll.modifier ?? roll.bonus,
      advantage: roll.advantage || roll.roll_mode || 'normal',
      submissionStatus: roll.submission_status,
      dcVisibility,
      targetTotal,
    };
  });
}
