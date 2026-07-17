import React, { useState } from 'react';
import PendingRollCard from './PendingRollCard';
import { formatModifier } from './normalize';

function NamedModifierList({ entries, emptyLabel }) {
  if (!entries.length) return <p className="character-muted">{emptyLabel}</p>;
  return (
    <ul className="character-modifier-list">
      {entries.map((entry, index) => {
        const name = typeof entry === 'string' ? entry : entry.name || entry.label || `Entry ${index + 1}`;
        const modifier = typeof entry === 'object'
          ? entry.modifier ?? entry.bonus ?? entry.value
          : null;
        return (
          <li key={`${name}-${index}`}>
            <span>{name}</span>
            {modifier !== null && modifier !== undefined && <strong>{formatModifier(modifier)}</strong>}
          </li>
        );
      })}
    </ul>
  );
}

function HitDice({ value }) {
  if (!value || typeof value === 'string') return <span>{value || '—'}</span>;
  const keyedPool = !('available' in value) && !('current' in value)
    ? Object.entries(value)[0]
    : null;
  const pool = keyedPool?.[1] && typeof keyedPool[1] === 'object'
    ? keyedPool[1]
    : value;
  const available = pool.available ?? pool.current ?? pool.remaining;
  const maximum = pool.max ?? pool.maximum ?? pool.total;
  const die = value.die || value.type || keyedPool?.[0] || '';
  return <span>{available ?? '—'} / {maximum ?? '—'} {die}</span>;
}

function CoreStatistics({ player }) {
  const statistics = [
    { label: 'Initiative', value: formatModifier(player.initiative) },
    { label: 'Speed', value: player.speed },
    { label: 'Passive Perception', value: player.passivePerception ?? '—' },
    { label: 'Proficiency', value: formatModifier(player.proficiencyBonus) },
  ];
  return (
    <section
      className="character-core-stats"
      aria-label={`${player.characterName} core statistics`}
    >
      {statistics.map((statistic) => (
        <div key={statistic.label}>
          <span>{statistic.label}</span>
          <strong>{statistic.value}</strong>
        </div>
      ))}
    </section>
  );
}

function ArmorClassDetails({ player }) {
  const calculation = player.armorClassCalculation;
  return (
    <section
      className="character-section character-defense"
      aria-labelledby={`${player.playerId}-defense`}
    >
      <h3 id={`${player.playerId}-defense`}>Armor &amp; defense</h3>
      {calculation.hasDetails ? (
        <>
          <dl className="character-definition-list">
            {calculation.armorItemName && (
              <>
                <dt>Armor</dt>
                <dd>{calculation.armorItemName}</dd>
              </>
            )}
            {calculation.shieldItemName && (
              <>
                <dt>Shield</dt>
                <dd>{calculation.shieldItemName}</dd>
              </>
            )}
            {calculation.base !== null && (
              <>
                <dt>Base AC</dt>
                <dd>{calculation.base}</dd>
              </>
            )}
            {calculation.addDexterity !== null && (
              <>
                <dt>Dexterity</dt>
                <dd>
                  {calculation.addDexterity
                    ? `${formatModifier(calculation.dexterityContribution)}${calculation.dexterityCap !== null ? ` (maximum ${formatModifier(calculation.dexterityCap)})` : ''}`
                    : 'Not added'}
                </dd>
              </>
            )}
            {(calculation.shieldBonus !== null && (calculation.shieldBonus !== 0 || calculation.shieldItemName)) && (
              <>
                <dt>Shield bonus</dt>
                <dd>{formatModifier(calculation.shieldBonus)}</dd>
              </>
            )}
            {(calculation.miscBonus !== null && calculation.miscBonus !== 0) && (
              <>
                <dt>Other bonus</dt>
                <dd>{formatModifier(calculation.miscBonus)}</dd>
              </>
            )}
          </dl>
          {calculation.description && <p className="character-rules-note">{calculation.description}</p>}
        </>
      ) : <p className="character-muted">No armor calculation is recorded.</p>}
    </section>
  );
}

function Attacks({ player }) {
  return (
    <section className="character-section" aria-labelledby={`${player.playerId}-attacks`}>
      <h3 id={`${player.playerId}-attacks`}>Attacks</h3>
      {player.attacks.length ? (
        <ul className="character-attack-list" aria-label={`${player.characterName} attacks`}>
          {player.attacks.map((attack) => (
            <li key={attack.id}>
              <article aria-label={attack.name}>
                <header>
                  <div>
                    <h4>{attack.name}</h4>
                    {attack.attackType && <small>{attack.attackType}</small>}
                  </div>
                  {attack.attackBonus !== null && (
                    <strong>{formatModifier(attack.attackBonus)} to hit</strong>
                  )}
                </header>
                <dl className="character-compact-details">
                  {attack.damage && <><dt>Damage</dt><dd>{attack.damage}</dd></>}
                  {attack.range && <><dt>Range</dt><dd>{attack.range}</dd></>}
                  {attack.source && <><dt>Source</dt><dd>{attack.source}</dd></>}
                </dl>
                {attack.properties.length > 0 && (
                  <ul className="character-tag-list" aria-label={`${attack.name} properties`}>
                    {attack.properties.map((property) => <li key={property}>{property}</li>)}
                  </ul>
                )}
                {attack.notes && <p className="character-rules-note">{attack.notes}</p>}
              </article>
            </li>
          ))}
        </ul>
      ) : <p className="character-muted">No attacks recorded.</p>}
    </section>
  );
}

function Proficiencies({ player }) {
  const groups = player.proficiencies.filter((group) => group.entries.length);
  return (
    <section className="character-section" aria-labelledby={`${player.playerId}-proficiencies`}>
      <h3 id={`${player.playerId}-proficiencies`}>Proficiencies &amp; languages</h3>
      {groups.length ? (
        <div className="character-proficiency-grid">
          {groups.map((group) => (
            <div key={group.key}>
              <h4>{group.label}</h4>
              <ul className="character-text-list">
                {group.entries.map((entry) => <li key={entry}>{entry}</li>)}
              </ul>
            </div>
          ))}
        </div>
      ) : <p className="character-muted">No proficiency summary available.</p>}
    </section>
  );
}

function Features({ player }) {
  return (
    <section className="character-section" aria-labelledby={`${player.playerId}-features`}>
      <h3 id={`${player.playerId}-features`}>Features &amp; traits</h3>
      {player.features.length ? (
        <ul className="character-feature-list">
          {player.features.map((feature) => {
            const linkedResource = player.classResources.find((resource) => (
              resource.name.toLowerCase() === feature.resourceKey.replace(/[_-]+/g, ' ').toLowerCase()
            ));
            const references = [feature.source, feature.rulesRef].filter(Boolean).join(' · ');
            return (
              <li key={feature.id}>
                <div>
                  <strong>{feature.name}</strong>
                  {references && <small>{references}</small>}
                </div>
                {feature.summary && <p>{feature.summary}</p>}
                {linkedResource && (
                  <span className="character-feature-resource">
                    {linkedResource.name}: {linkedResource.current} / {linkedResource.maximum}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      ) : <p className="character-muted">No features recorded.</p>}
    </section>
  );
}

function SpellSlots({ player }) {
  return (
    <section className="character-section" aria-labelledby={`${player.playerId}-slots`}>
      <h3 id={`${player.playerId}-slots`}>Spell slots</h3>
      {player.spellSlots.length ? (
        <ul className="character-resource-list">
          {player.spellSlots.map((slot) => {
            const available = slot.maximum - slot.used;
            return (
              <li key={slot.level}>
                <span>Level {slot.level}</span>
                <span className="character-pips" aria-hidden="true">
                  {Array.from({ length: slot.maximum }, (_, index) => (
                    <i key={index} className={index < slot.used ? 'used' : 'available'} />
                  ))}
                </span>
                <span className="character-resource-count">{slot.used} used, {available} available</span>
              </li>
            );
          })}
        </ul>
      ) : <p className="character-muted">No spell slots.</p>}
    </section>
  );
}

function Spellcasting({ player }) {
  const { spellcasting } = player;
  if (!spellcasting.hasDetails) return null;

  const groups = spellcasting.spells.reduce((result, spell) => {
    const existing = result.find((group) => group.level === spell.level);
    if (existing) existing.spells.push(spell);
    else result.push({ level: spell.level, spells: [spell] });
    return result;
  }, []);

  return (
    <section
      className="character-section character-spellcasting"
      aria-label={`${player.characterName} spellcasting`}
    >
      <h3 id={`${player.playerId}-spellcasting`}>Spellcasting</h3>
      <dl className="character-spellcasting-summary">
        <div><dt>Ability</dt><dd>{spellcasting.ability}</dd></div>
        <div><dt>Save DC</dt><dd>{spellcasting.spellSaveDc ?? '—'}</dd></div>
        <div><dt>Spell attack</dt><dd>{formatModifier(spellcasting.spellAttackBonus)}</dd></div>
        <div><dt>Preparation</dt><dd>{spellcasting.preparationMode}</dd></div>
        {spellcasting.focusItemName && <div><dt>Focus</dt><dd>{spellcasting.focusItemName}</dd></div>}
        <div>
          <dt>Ritual casting</dt>
          <dd>{spellcasting.ritualCasting === null ? '—' : spellcasting.ritualCasting ? 'Yes' : 'No'}</dd>
        </div>
      </dl>

      {groups.length ? groups.map((group) => (
        <div className="character-spell-level" key={group.level}>
          <h4>{group.level === 0 ? 'Cantrips' : `Level ${group.level} spells`}</h4>
          <ul className="character-spell-list" aria-label={group.level === 0 ? 'Cantrips' : `Level ${group.level} spells`}>
            {group.spells.map((spell) => {
              const stateBadges = [
                spell.known && 'Known',
                spell.prepared && 'Prepared',
                spell.alwaysPrepared && 'Always prepared',
                spell.inSpellbook && 'Spellbook',
              ].filter(Boolean);
              const spellAttribution = [spell.school, spell.source].filter(Boolean).join(' · ');
              return (
                <li key={spell.id}>
                  <article aria-label={`${spell.name} spell`}>
                    <header>
                      <div>
                        <h5>{spell.name}</h5>
                        {spellAttribution && <small>{spellAttribution}</small>}
                      </div>
                      {stateBadges.length > 0 && (
                        <ul className="character-spell-badges" aria-label={`${spell.name} status`}>
                          {stateBadges.map((badge) => <li key={badge}>{badge}</li>)}
                        </ul>
                      )}
                    </header>
                    <dl className="character-spell-details">
                      <div><dt>Casting time</dt><dd>{spell.castingTime}</dd></div>
                      <div><dt>Range</dt><dd>{spell.range}</dd></div>
                      <div><dt>Components</dt><dd>{spell.components}</dd></div>
                      <div><dt>Duration</dt><dd>{spell.duration}</dd></div>
                    </dl>
                    {(spell.concentration || spell.ritual || spell.rulesRef) && (
                      <ul className="character-tag-list" aria-label={`${spell.name} casting properties`}>
                        {spell.concentration && <li>Concentration</li>}
                        {spell.ritual && <li>Ritual</li>}
                        {spell.rulesRef && <li>{spell.rulesRef}</li>}
                      </ul>
                    )}
                    {spell.description && <p className="character-rules-note">{spell.description}</p>}
                  </article>
                </li>
              );
            })}
          </ul>
        </div>
      )) : <p className="character-muted">No spell list available.</p>}
    </section>
  );
}

function Inventory({ player }) {
  return (
    <section className="character-section" aria-labelledby={`${player.playerId}-inventory`}>
      <h3 id={`${player.playerId}-inventory`}>Inventory</h3>
      {player.inventory.length ? (
        <ul className="character-inventory character-inventory-detailed">
          {player.inventory.map((item) => {
            const details = [
              item.category,
              item.armorCategory,
              item.weaponCategory,
              item.armorClass !== null && `AC ${item.armorClass}`,
              item.armorClassBonus !== null && `AC ${formatModifier(item.armorClassBonus)}`,
              item.damage && `${item.damage} damage`,
              item.range && `Range ${item.range}`,
              item.properties.length && item.properties.join(', '),
              item.weight !== null && item.weight > 0 && `${item.weight} lb.`,
              item.cost,
              item.rulesRef,
            ].filter(Boolean);
            return (
              <li key={item.id}>
                <div className="character-inventory-heading">
                  <strong>{item.name}</strong>
                  <span>{item.quantity > 1 ? `×${item.quantity}` : ''}{item.equipped ? ' · Equipped' : ''}</span>
                </div>
                {details.length > 0 && <small>{details.join(' · ')}</small>}
                {item.notes && <p>{item.notes}</p>}
              </li>
            );
          })}
        </ul>
      ) : <p className="character-muted">Inventory is empty.</p>}
    </section>
  );
}

export default function CharacterSheet({ player, pendingRoll, submittingRollId, onSubmitRoll }) {
  const sheetTabs = [
    { id: 'core', label: 'Core' },
    { id: 'features', label: 'Features' },
    { id: 'spells', label: 'Spells' },
    { id: 'inventory', label: 'Inventory' },
  ];
  const [selectedTabs, setSelectedTabs] = useState({});
  const selectedTab = selectedTabs[player.playerId] || 'core';
  const hpMaximum = Math.max(0, player.hp.maximum);
  const hpCurrent = Math.max(0, Math.min(hpMaximum, player.hp.current));
  const identityDetails = [
    player.ancestry,
    player.size,
    player.background,
    player.alignment,
    player.experiencePoints !== null ? `${player.experiencePoints} XP` : '',
  ].filter(Boolean).join(' · ');

  const selectTab = (tabId) => {
    setSelectedTabs((currentTabs) => ({
      ...currentTabs,
      [player.playerId]: tabId,
    }));
  };

  const selectAndFocusTab = (tabId) => {
    selectTab(tabId);
    document.getElementById(`character-sheet-tab-${player.playerId}-${tabId}`)?.focus();
  };

  const handleTabKeyDown = (event, currentIndex) => {
    let nextIndex = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % sheetTabs.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + sheetTabs.length) % sheetTabs.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = sheetTabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    selectAndFocusTab(sheetTabs[nextIndex].id);
  };

  return (
    <article className="character-sheet">
      <header className="character-sheet-header">
        <div>
          <p className="character-eyebrow">{player.playerLabel}</p>
          <h2>{player.characterName}</h2>
          <p>
            {player.className}{player.subclassName ? ` — ${player.subclassName}` : ''} · Level {player.level}
          </p>
          {(identityDetails || player.rulesetId) && (
            <p className="character-identity-details">
              {identityDetails}{identityDetails && player.rulesetId ? ' · ' : ''}{player.rulesetId}
            </p>
          )}
        </div>
        <div className="character-ac" aria-label={`Armor class ${player.armorClass}`}>
          <span>AC</span>
          <strong>{player.armorClass}</strong>
        </div>
      </header>

      {pendingRoll && (
        <PendingRollCard
          roll={pendingRoll}
          player={player}
          submitting={submittingRollId === pendingRoll.id}
          onSubmit={onSubmitRoll}
        />
      )}

      <div
        className="character-sheet-tabs"
        role="tablist"
        aria-label={`${player.characterName} character sheet sections`}
      >
        {sheetTabs.map((tab, index) => {
          const isSelected = selectedTab === tab.id;
          return (
            <button
              key={tab.id}
              id={`character-sheet-tab-${player.playerId}-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={isSelected}
              aria-controls={`character-sheet-panel-${player.playerId}-${tab.id}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => selectTab(tab.id)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <section
        id={`character-sheet-panel-${player.playerId}-core`}
        className="character-sheet-tabpanel"
        role="tabpanel"
        aria-labelledby={`character-sheet-tab-${player.playerId}-core`}
        tabIndex="0"
        hidden={selectedTab !== 'core'}
      >
        <CoreStatistics player={player} />

        <section className="character-vitals" aria-labelledby={`${player.playerId}-vitals`}>
          <div>
            <h3 id={`${player.playerId}-vitals`}>Hit points</h3>
            <div
              className="character-hp-meter"
              role="progressbar"
              aria-label={`${player.characterName} hit points`}
              aria-valuemin="0"
              aria-valuemax={hpMaximum}
              aria-valuenow={hpCurrent}
            >
              <span style={{ width: hpMaximum ? `${(hpCurrent / hpMaximum) * 100}%` : '0%' }} />
            </div>
            <output className="character-hp-total" aria-live="polite">
              {player.hp.current} / {player.hp.maximum}
            </output>
            <span className="character-temp-hp">Temp HP: {player.hp.temporary}</span>
          </div>
          <div>
            <h3>Recovery</h3>
            <dl className="character-recovery-list">
              <dt>Hit dice</dt>
              <dd><HitDice value={player.hitDice} /></dd>
              {player.deathSaves && (
                <>
                  <dt>Death saves</dt>
                  <dd>
                    {player.deathSaves.successes} {player.deathSaves.successes === 1 ? 'success' : 'successes'} · {' '}
                    {player.deathSaves.failures} {player.deathSaves.failures === 1 ? 'failure' : 'failures'}
                  </dd>
                </>
              )}
              {player.heroicInspiration !== null && (
                <>
                  <dt>Heroic inspiration</dt>
                  <dd>{player.heroicInspiration ? 'Available' : 'Not available'}</dd>
                </>
              )}
            </dl>
          </div>
        </section>

        <div className="character-two-column character-combat-grid">
          <ArmorClassDetails player={player} />
          <Attacks player={player} />
        </div>

        <section className="character-section" aria-labelledby={`${player.playerId}-abilities`}>
          <h3 id={`${player.playerId}-abilities`}>Abilities</h3>
          {player.abilities.length ? (
            <div className="character-ability-grid">
              {player.abilities.map((ability) => (
                <div key={ability.key} className="character-ability">
                  <span>{ability.label}</span>
                  <strong>{ability.score}</strong>
                  <small>{formatModifier(ability.modifier)}</small>
                </div>
              ))}
            </div>
          ) : <p className="character-muted">No ability scores available.</p>}
        </section>

        <div className="character-two-column">
          <section className="character-section" aria-labelledby={`${player.playerId}-saves`}>
            <h3 id={`${player.playerId}-saves`}>Saving throws</h3>
            <NamedModifierList entries={player.savingThrows} emptyLabel="No saving throw summary available." />
          </section>
          <section className="character-section" aria-labelledby={`${player.playerId}-skills`}>
            <h3 id={`${player.playerId}-skills`}>Skills</h3>
            <NamedModifierList entries={player.skills} emptyLabel="No skill summary available." />
          </section>
        </div>

        <section className="character-section" aria-labelledby={`${player.playerId}-conditions`}>
          <h3 id={`${player.playerId}-conditions`}>Conditions</h3>
          {player.conditions.length ? (
            <ul className="character-chip-list">
              {player.conditions.map((condition) => <li key={condition}>{condition}</li>)}
            </ul>
          ) : <p className="character-muted">No active conditions.</p>}
        </section>
      </section>

      <section
        id={`character-sheet-panel-${player.playerId}-features`}
        className="character-sheet-tabpanel"
        role="tabpanel"
        aria-labelledby={`character-sheet-tab-${player.playerId}-features`}
        tabIndex="0"
        hidden={selectedTab !== 'features'}
      >
        <Proficiencies player={player} />
        <Features player={player} />

        <section className="character-section" aria-labelledby={`${player.playerId}-resources`}>
          <h3 id={`${player.playerId}-resources`}>Class resources</h3>
          {player.classResources.length ? (
            <ul className="character-resource-list">
              {player.classResources.map((resource) => (
                <li key={resource.name}>
                  <span>{resource.name}</span>
                  <div
                    className="character-resource-meter"
                    role="progressbar"
                    aria-label={resource.name}
                    aria-valuemin="0"
                    aria-valuemax={resource.maximum}
                    aria-valuenow={resource.current}
                  >
                    <span style={{ width: resource.maximum ? `${(resource.current / resource.maximum) * 100}%` : '0%' }} />
                  </div>
                  <span>{resource.current} / {resource.maximum}</span>
                </li>
              ))}
            </ul>
          ) : <p className="character-muted">No class resources.</p>}
        </section>
      </section>

      <section
        id={`character-sheet-panel-${player.playerId}-spells`}
        className="character-sheet-tabpanel"
        role="tabpanel"
        aria-labelledby={`character-sheet-tab-${player.playerId}-spells`}
        tabIndex="0"
        hidden={selectedTab !== 'spells'}
      >
        <SpellSlots player={player} />
        <Spellcasting player={player} />
      </section>

      <section
        id={`character-sheet-panel-${player.playerId}-inventory`}
        className="character-sheet-tabpanel"
        role="tabpanel"
        aria-labelledby={`character-sheet-tab-${player.playerId}-inventory`}
        tabIndex="0"
        hidden={selectedTab !== 'inventory'}
      >
        <section className="character-section" aria-labelledby={`${player.playerId}-currency`}>
          <h3 id={`${player.playerId}-currency`}>Coin purse</h3>
          <ul className="character-currency" aria-label={`${player.characterName} currency`}>
            {player.currency.map((coin) => (
              <li key={coin.denomination}>
                <span>{coin.label}</span>
                <strong>{coin.amount} {coin.denomination}</strong>
              </li>
            ))}
          </ul>
        </section>

        <Inventory player={player} />
      </section>
    </article>
  );
}
